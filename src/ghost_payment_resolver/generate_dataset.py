"""Generate a labeled synthetic dataset of ghost-payment scenarios."""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ghost_payment_resolver.schemas import CaseSignals, Dataset, LabeledCase, Order, Payment
from ghost_payment_resolver.states import (
    HARD_ERROR_CODES,
    SOFT_ERROR_CODES,
    STATE_DEFAULT_ACTION,
    Action,
    CaseState,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "data" / "cases.json"

# Mix from SPEC.md (100 cases)
SCENARIO_PLAN: list[tuple[str, CaseState, int]] = [
    ("aligned", CaseState.ALIGNED, 40),
    ("webhook_delayed_ghost", CaseState.GHOST_SUCCESS, 15),
    ("client_timeout_ghost", CaseState.GHOST_SUCCESS, 15),
    ("double_submit", CaseState.GHOST_SUCCESS, 10),  # one captured + pending order → confirm
    ("soft_decline", CaseState.SOFT_DECLINE, 10),
    ("hard_decline", CaseState.HARD_FAIL, 5),
    ("ambiguous_api_down", CaseState.AMBIGUOUS, 5),
]


def _ts(rng: random.Random, base: datetime) -> datetime:
    return base + timedelta(seconds=rng.randint(0, 86_400))


def _amount(rng: random.Random) -> int:
    # ₹99 – ₹9,999 in paise
    rupees = rng.choice([99, 149, 199, 499, 999, 1499, 2499, 4999, 9999])
    return rupees * 100


def _ids(rng: random.Random, n: int) -> tuple[str, str]:
    order_id = f"order_{n:04d}_{rng.randint(1000, 9999)}"
    payment_id = f"pay_{n:04d}_{rng.randint(10000, 99999)}"
    return order_id, payment_id


def _method(rng: random.Random) -> PaymentMethod:
    return rng.choice(list(PaymentMethod))


def build_case(rng: random.Random, index: int, scenario: str, state: CaseState, base: datetime) -> LabeledCase:
    order_id, payment_id = _ids(rng, index)
    amount = _amount(rng)
    created = _ts(rng, base)
    method = _method(rng)
    action = STATE_DEFAULT_ACTION[state]
    recovered = 0

    order: Order | None
    payments: list[Payment]
    signals = CaseSignals()

    if scenario == "aligned":
        order = Order(
            order_id=order_id,
            amount_paise=amount,
            status=OrderStatus.PAID,
            created_at=created,
        )
        payments = [
            Payment(
                payment_id=payment_id,
                order_id=order_id,
                amount_paise=amount,
                status=PaymentStatus.CAPTURED,
                method=method,
                created_at=created,
                captured_at=created + timedelta(seconds=rng.randint(2, 30)),
            )
        ]
        recovered = 0

    elif scenario == "webhook_delayed_ghost":
        signals = CaseSignals(webhook_delayed=True, notes="Webhook delayed; order still pending")
        order = Order(
            order_id=order_id,
            amount_paise=amount,
            status=OrderStatus.PENDING,
            created_at=created,
        )
        payments = [
            Payment(
                payment_id=payment_id,
                order_id=order_id,
                amount_paise=amount,
                status=PaymentStatus.CAPTURED,
                method=method,
                created_at=created,
                captured_at=created + timedelta(seconds=rng.randint(2, 20)),
            )
        ]
        recovered = amount

    elif scenario == "client_timeout_ghost":
        signals = CaseSignals(client_timeout=True, notes="Client timed out; payment captured on rail")
        order = Order(
            order_id=order_id,
            amount_paise=amount,
            status=OrderStatus.FAILED,
            created_at=created,
        )
        payments = [
            Payment(
                payment_id=payment_id,
                order_id=order_id,
                amount_paise=amount,
                status=PaymentStatus.CAPTURED,
                method=method,
                created_at=created,
                captured_at=created + timedelta(seconds=rng.randint(5, 60)),
            )
        ]
        recovered = amount

    elif scenario == "double_submit":
        signals = CaseSignals(double_submit=True, notes="Two payment attempts; one captured")
        order = Order(
            order_id=order_id,
            amount_paise=amount,
            status=OrderStatus.PENDING,
            created_at=created,
        )
        pay2 = f"pay_{index:04d}_{rng.randint(10000, 99999)}"
        payments = [
            Payment(
                payment_id=payment_id,
                order_id=order_id,
                amount_paise=amount,
                status=PaymentStatus.FAILED,
                method=method,
                error_code="GATEWAY_TIMEOUT",
                created_at=created,
                failed_at=created + timedelta(seconds=3),
            ),
            Payment(
                payment_id=pay2,
                order_id=order_id,
                amount_paise=amount,
                status=PaymentStatus.CAPTURED,
                method=method,
                created_at=created + timedelta(seconds=8),
                captured_at=created + timedelta(seconds=12),
            ),
        ]
        recovered = amount

    elif scenario == "soft_decline":
        code = rng.choice(sorted(SOFT_ERROR_CODES))
        order = Order(
            order_id=order_id,
            amount_paise=amount,
            status=OrderStatus.PENDING,
            created_at=created,
        )
        payments = [
            Payment(
                payment_id=payment_id,
                order_id=order_id,
                amount_paise=amount,
                status=PaymentStatus.FAILED,
                method=method,
                error_code=code,
                created_at=created,
                failed_at=created + timedelta(seconds=rng.randint(2, 15)),
            )
        ]
        # Optimistic label: successful retry recovers full amount in simulation
        recovered = amount
        signals = CaseSignals(notes=f"Soft decline {code}")

    elif scenario == "hard_decline":
        code = rng.choice(sorted(HARD_ERROR_CODES))
        order = Order(
            order_id=order_id,
            amount_paise=amount,
            status=OrderStatus.FAILED,
            created_at=created,
        )
        payments = [
            Payment(
                payment_id=payment_id,
                order_id=order_id,
                amount_paise=amount,
                status=PaymentStatus.FAILED,
                method=method,
                error_code=code,
                created_at=created,
                failed_at=created + timedelta(seconds=rng.randint(2, 15)),
            )
        ]
        recovered = 0
        signals = CaseSignals(notes=f"Hard decline {code}")

    elif scenario == "ambiguous_api_down":
        signals = CaseSignals(api_available=False, notes="Payment API unavailable")
        order = Order(
            order_id=order_id,
            amount_paise=amount,
            status=OrderStatus.PENDING,
            created_at=created,
        )
        # Stale / incomplete payment view
        payments = [
            Payment(
                payment_id=payment_id,
                order_id=order_id,
                amount_paise=amount,
                status=PaymentStatus.CREATED,
                method=method,
                created_at=created,
            )
        ]
        recovered = 0
        action = Action.ESCALATE

    else:
        raise ValueError(f"Unknown scenario: {scenario}")

    # Orphan variant: peel a few ghost successes into ORPHAN_PAYMENT for diversity
    # (handled via meta flag on a subset — see generate())

    return LabeledCase(
        case_id=f"case_{index:04d}",
        scenario=scenario,
        order=order,
        payments=payments,
        signals=signals,
        expected_state=state,
        expected_action=action,
        expected_amount_recovered_paise=recovered,
        meta={"index": index},
    )


def _make_orphan(rng: random.Random, index: int, base: datetime) -> LabeledCase:
    """Captured payment with no merchant order — classic ghost orphan."""
    _, payment_id = _ids(rng, index)
    amount = _amount(rng)
    created = _ts(rng, base)
    return LabeledCase(
        case_id=f"case_{index:04d}",
        scenario="orphan_payment",
        order=None,
        payments=[
            Payment(
                payment_id=payment_id,
                order_id=None,
                amount_paise=amount,
                status=PaymentStatus.CAPTURED,
                method=_method(rng),
                created_at=created,
                captured_at=created + timedelta(seconds=5),
            )
        ],
        signals=CaseSignals(notes="Payment captured without order linkage"),
        expected_state=CaseState.ORPHAN_PAYMENT,
        expected_action=Action.LINK_OR_REFUND,
        # Protecting revenue / trust: we count amount as "recovered/protected" when handled
        expected_amount_recovered_paise=amount,
        meta={"index": index, "orphan": True},
    )


def generate(seed: int = 42, total: int = 100) -> Dataset:
    rng = random.Random(seed)
    base = datetime(2026, 8, 1, tzinfo=timezone.utc)
    cases: list[LabeledCase] = []
    index = 1

    planned = sum(count for _, _, count in SCENARIO_PLAN)
    if planned != total:
        raise ValueError(f"total={total} but SCENARIO_PLAN sums to {planned}")

    for scenario, state, count in SCENARIO_PLAN:
        for _ in range(count):
            cases.append(build_case(rng, index, scenario, state, base))
            index += 1

    # Convert 5 of the webhook_delayed ghosts into orphans for ORPHAN coverage
    # without breaking the 100 count: replace last 5 webhook cases.
    webhook_indices = [i for i, c in enumerate(cases) if c.scenario == "webhook_delayed_ghost"]
    for i in webhook_indices[-5:]:
        old = cases[i]
        n = int(old.meta["index"])
        cases[i] = _make_orphan(rng, n, base)

    return Dataset(generated_at=datetime.now(timezone.utc), seed=seed, cases=cases)


def save_dataset(dataset: Dataset, path: Path = DEFAULT_OUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dataset.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_dataset(path: Path = DEFAULT_OUT) -> Dataset:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Dataset.model_validate(raw)


def summarize(dataset: Dataset) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in dataset.cases:
        key = f"{case.expected_state.value}:{case.scenario}"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Ghost Payment Resolver dataset")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    dataset = generate(seed=args.seed, total=100)
    out = save_dataset(dataset, args.out)
    print(f"Wrote {len(dataset.cases)} cases -> {out}")
    for k, v in summarize(dataset).items():
        print(f"  {v:3d}  {k}")


if __name__ == "__main__":
    main()
