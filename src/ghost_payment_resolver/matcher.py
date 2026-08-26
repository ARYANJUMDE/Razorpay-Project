"""Matcher and diagnostic logic for Ghost Payment Resolver."""

from __future__ import annotations

from dataclasses import dataclass

from ghost_payment_resolver.schemas import CaseSignals, Order, Payment
from ghost_payment_resolver.states import (
    HARD_ERROR_CODES,
    SOFT_ERROR_CODES,
    STATE_DEFAULT_ACTION,
    Action,
    CaseState,
    OrderStatus,
    PaymentStatus,
)


@dataclass
class DiagnosticResult:
    """Outcome of case diagnosis."""

    state: CaseState
    proposed_action: Action
    reason: str
    recoverable_amount_paise: int = 0


def diagnose_case(
    order: Order | None,
    payments: list[Payment],
    signals: CaseSignals | None = None,
    force_api_down: bool = False,
) -> DiagnosticResult:
    """Analyze order, payment signals, and rail records to classify case state and propose action."""
    signals = signals or CaseSignals()

    # 1. API Availability / Circuit Breaker
    if not signals.api_available or force_api_down:
        return DiagnosticResult(
            state=CaseState.AMBIGUOUS,
            proposed_action=Action.ESCALATE,
            reason="Payment gateway API unavailable or incomplete rail visibility.",
            recoverable_amount_paise=0,
        )

    # 2. Orphan Payment (Payment captured on rail with no matching merchant order)
    if order is None:
        captured_payments = [p for p in payments if p.status == PaymentStatus.CAPTURED]
        if captured_payments:
            amount = sum(p.amount_paise for p in captured_payments)
            return DiagnosticResult(
                state=CaseState.ORPHAN_PAYMENT,
                proposed_action=STATE_DEFAULT_ACTION[CaseState.ORPHAN_PAYMENT],
                reason=f"Found {len(captured_payments)} captured payment(s) without merchant order linkage.",
                recoverable_amount_paise=amount,
            )
        return DiagnosticResult(
            state=CaseState.AMBIGUOUS,
            proposed_action=Action.ESCALATE,
            reason="No merchant order and no captured payments found.",
            recoverable_amount_paise=0,
        )

    # 3. Order Exists — Inspect Payments
    captured_payments = [p for p in payments if p.status == PaymentStatus.CAPTURED]
    failed_payments = [p for p in payments if p.status == PaymentStatus.FAILED]

    # Scenario A: Money is captured on rail
    if captured_payments:
        # Check if already aligned with order
        if order.status == OrderStatus.PAID:
            return DiagnosticResult(
                state=CaseState.ALIGNED,
                proposed_action=Action.NO_OP,
                reason="Order status 'paid' matches captured payment rail status.",
                recoverable_amount_paise=0,
            )

        # Ghost Success: Money was captured, but merchant order is pending or failed
        # (e.g. Delayed webhook, client timeout, or successful retry after double-submit)
        captured_amount = captured_payments[0].amount_paise
        reason_detail = []
        if signals.webhook_delayed:
            reason_detail.append("webhook delayed")
        if signals.client_timeout:
            reason_detail.append("client timeout")
        if signals.double_submit or len(payments) > 1:
            reason_detail.append("multiple payment attempts with successful capture")

        detail_str = f" ({', '.join(reason_detail)})" if reason_detail else ""
        return DiagnosticResult(
            state=CaseState.GHOST_SUCCESS,
            proposed_action=STATE_DEFAULT_ACTION[CaseState.GHOST_SUCCESS],
            reason=f"Payment captured on rail while order status is '{order.status.value}'{detail_str}.",
            recoverable_amount_paise=captured_amount,
        )

    # Scenario B: No captured payments, inspect failed payments
    if failed_payments:
        # Check for soft (retryable) errors
        soft_fails = [
            p for p in failed_payments if p.error_code and p.error_code in SOFT_ERROR_CODES
        ]
        if soft_fails:
            error_codes = ", ".join({p.error_code for p in soft_fails if p.error_code})
            return DiagnosticResult(
                state=CaseState.SOFT_DECLINE,
                proposed_action=STATE_DEFAULT_ACTION[CaseState.SOFT_DECLINE],
                reason=f"Payment failed with retryable gateway/bank error ({error_codes}).",
                recoverable_amount_paise=order.amount_paise,
            )

        # Check for hard (terminal) errors
        hard_fails = [
            p for p in failed_payments if p.error_code and p.error_code in HARD_ERROR_CODES
        ]
        if hard_fails:
            error_codes = ", ".join({p.error_code for p in hard_fails if p.error_code})
            return DiagnosticResult(
                state=CaseState.HARD_FAIL,
                proposed_action=STATE_DEFAULT_ACTION[CaseState.HARD_FAIL],
                reason=f"Payment failed with non-retryable error ({error_codes}).",
                recoverable_amount_paise=0,
            )

    # Scenario C: Incomplete or ambiguous state
    return DiagnosticResult(
        state=CaseState.AMBIGUOUS,
        proposed_action=Action.ESCALATE,
        reason="Inconclusive payment records or unhandled state.",
        recoverable_amount_paise=0,
    )
