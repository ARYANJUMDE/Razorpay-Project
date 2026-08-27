"""Core resolution loop, batch runner, and scoring metrics for Ghost Payment Resolver."""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ghost_payment_resolver.generate_dataset import DEFAULT_OUT, load_dataset
from ghost_payment_resolver.matcher import diagnose_case
from ghost_payment_resolver.policy import PolicyConfig, PolicyEngine
from ghost_payment_resolver.schemas import (
    AuditRecord,
    BatchMetrics,
    Dataset,
    LabeledCase,
)
from ghost_payment_resolver.states import Action
from ghost_payment_resolver.storage import AuditDatabase


class ResolutionEngine:
    """Coordinates matcher diagnostics, policy checks, action execution, and audit logging."""

    def __init__(
        self,
        policy_config: PolicyConfig | None = None,
        storage: AuditDatabase | None = None,
        persist_audits: bool = True,
    ) -> None:
        self.policy_engine = PolicyEngine(policy_config or PolicyConfig(daily_cap_paise=50_000_000))
        self.storage = storage or AuditDatabase()
        self.persist_audits = persist_audits

    def resolve_case(
        self,
        case: LabeledCase,
        force_api_down: bool = False,
    ) -> AuditRecord:
        """Resolve a single case and return an immutable audit record."""
        # 1. Matcher Diagnosis
        diagnostic = diagnose_case(
            order=case.order,
            payments=case.payments,
            signals=case.signals,
            force_api_down=force_api_down,
        )

        order_id = case.order.order_id if case.order else None

        # 2. Policy Evaluation
        policy_decision = self.policy_engine.evaluate(
            proposed_action=diagnostic.proposed_action,
            amount_paise=diagnostic.recoverable_amount_paise,
            api_available=case.signals.api_available,
            order_id=order_id,
            force_api_down=force_api_down,
        )

        # 3. Action Execution (Simulated)
        action_taken = policy_decision.final_action
        amount_recovered = 0

        if action_taken in {Action.CONFIRM_ORDER, Action.LINK_OR_REFUND, Action.SCHEDULE_RETRY}:
            amount_recovered = diagnostic.recoverable_amount_paise

        # 4. Record action in policy accumulator
        self.policy_engine.record_action(
            action_taken=action_taken,
            amount_paise=amount_recovered,
            order_id=order_id,
        )

        # 5. Build Audit Record
        now = datetime.now(timezone.utc)
        audit_id = f"aud_{case.case_id}_{uuid.uuid4().hex[:8]}"

        reason = diagnostic.reason
        if not policy_decision.allowed:
            reason = f"{diagnostic.reason} [Policy Block: {policy_decision.reason}]"

        inputs_summary: dict[str, Any] = {
            "order_id": order_id,
            "order_status": case.order.status.value if case.order else None,
            "order_amount_paise": case.order.amount_paise if case.order else None,
            "payment_count": len(case.payments),
            "payment_statuses": [p.status.value for p in case.payments],
            "signals": case.signals.model_dump(),
        }

        outcome_summary: dict[str, Any] = {
            "state": diagnostic.state.value,
            "action": action_taken.value,
            "recovered_paise": amount_recovered,
            "recovered_inr": amount_recovered / 100,
        }

        record = AuditRecord(
            audit_id=audit_id,
            case_id=case.case_id,
            timestamp=now,
            observed_state=diagnostic.state,
            proposed_action=diagnostic.proposed_action,
            policy_allowed=policy_decision.allowed,
            action_taken=action_taken,
            reason=reason,
            amount_recovered_paise=amount_recovered,
            inputs=inputs_summary,
            outcome=outcome_summary,
        )

        if self.persist_audits:
            try:
                self.storage.save_audit(record)
            except Exception as e:  # noqa: BLE001
                _ = e

        return record

    def run_batch(
        self,
        dataset: Dataset,
        force_api_down: bool = False,
        reset_policy: bool = True,
    ) -> tuple[list[AuditRecord], BatchMetrics]:
        """Execute resolution loop against an entire dataset and compute evaluation metrics."""
        if reset_policy:
            self.policy_engine.reset_daily_stats()

        audit_records: list[AuditRecord] = []
        recoverable_cases = 0
        correctly_recovered = 0
        total_amount_recovered = 0
        false_actions = 0
        escalations = 0
        correct_escalations = 0
        exceptions: list[str] = []

        for case in dataset.cases:
            try:
                record = self.resolve_case(case, force_api_down=force_api_down)
                audit_records.append(record)

                is_recoverable = case.expected_amount_recovered_paise > 0
                if is_recoverable:
                    recoverable_cases += 1

                # Check recovery correctness
                if (
                    is_recoverable
                    and record.action_taken == case.expected_action
                    and record.amount_recovered_paise == case.expected_amount_recovered_paise
                ):
                    correctly_recovered += 1

                # Check false actions
                if record.action_taken != case.expected_action:
                    false_actions += 1

                # Check escalations
                if record.action_taken == Action.ESCALATE:
                    escalations += 1
                    if case.expected_action == Action.ESCALATE:
                        correct_escalations += 1

                total_amount_recovered += record.amount_recovered_paise

            except Exception as e:  # noqa: BLE001
                exceptions.append(f"Case {case.case_id} failed: {type(e).__name__} - {e!s}")

        total_cases = len(dataset.cases)
        recovery_rate = (
            (correctly_recovered / recoverable_cases) if recoverable_cases > 0 else 1.0
        )
        false_action_rate = (false_actions / total_cases) if total_cases > 0 else 0.0
        escalation_precision = (
            (correct_escalations / escalations) if escalations > 0 else 1.0
        )

        metrics = BatchMetrics(
            total_cases=total_cases,
            recoverable_cases=recoverable_cases,
            correctly_recovered=correctly_recovered,
            recovery_rate=round(recovery_rate, 4),
            amount_recovered_paise=total_amount_recovered,
            false_actions=false_actions,
            false_action_rate=round(false_action_rate, 4),
            escalations=escalations,
            correct_escalations=correct_escalations,
            escalation_precision=round(escalation_precision, 4),
            exceptions=exceptions,
        )

        return audit_records, metrics


def print_metrics_summary(metrics: BatchMetrics) -> None:
    """Format and print batch evaluation metrics in a clean CLI table."""
    inr_recovered = metrics.amount_recovered_paise / 100
    print("\n" + "=" * 60)
    print(" GHOST PAYMENT RESOLVER -- BATCH EVALUATION REPORT")
    print("=" * 60)
    print(f" Total Cases Evaluated   : {metrics.total_cases}")
    print(f" Recoverable Cases       : {metrics.recoverable_cases}")
    print(f" Correctly Recovered     : {metrics.correctly_recovered}")
    print(f" Recovery Rate           : {metrics.recovery_rate * 100:.2f}%")
    print(f" Total Amount Recovered  : INR {inr_recovered:,.2f} ({metrics.amount_recovered_paise} paise)")
    print(f" False Actions           : {metrics.false_actions}")
    print(f" False Action Rate       : {metrics.false_action_rate * 100:.2f}%")
    print(f" Total Escalations       : {metrics.escalations}")
    print(f" Escalation Precision    : {metrics.escalation_precision * 100:.2f}%")
    if metrics.exceptions:
        print(f" Exceptions Encountered  : {len(metrics.exceptions)}")
        for exc in metrics.exceptions:
            print(f"   ! {exc}")
    else:
        print(" Exceptions Encountered  : 0")
    print("=" * 60 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ghost Payment Resolver -- Batch Runner")
    parser.add_argument("--data", type=Path, default=DEFAULT_OUT, help="Path to cases.json")
    parser.add_argument("--force-api-down", action="store_true", help="Simulate payment API downtime")
    parser.add_argument("--cap", type=int, default=50_000_000, help="Daily cap in paise")
    args = parser.parse_args()

    if not args.data.exists():
        print(f"Dataset not found at {args.data}. Run 'gpr-generate' first.")
        sys.exit(1)

    dataset = load_dataset(args.data)
    engine = ResolutionEngine(PolicyConfig(daily_cap_paise=args.cap))
    _, metrics = engine.run_batch(dataset, force_api_down=args.force_api_down)
    print_metrics_summary(metrics)


if __name__ == "__main__":
    main()
