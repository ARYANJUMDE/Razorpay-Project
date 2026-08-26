"""Tests for matcher diagnosis logic across all scenario types."""

from datetime import datetime, timezone

from ghost_payment_resolver.matcher import diagnose_case
from ghost_payment_resolver.schemas import CaseSignals, Order, Payment
from ghost_payment_resolver.states import (
    Action,
    CaseState,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
)


def _dt() -> datetime:
    return datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_aligned_case():
    order = Order(
        order_id="ord_1",
        amount_paise=10000,
        status=OrderStatus.PAID,
        created_at=_dt(),
    )
    payment = Payment(
        payment_id="pay_1",
        order_id="ord_1",
        amount_paise=10000,
        status=PaymentStatus.CAPTURED,
        created_at=_dt(),
    )
    res = diagnose_case(order, [payment])
    assert res.state == CaseState.ALIGNED
    assert res.proposed_action == Action.NO_OP
    assert res.recoverable_amount_paise == 0


def test_webhook_delayed_ghost():
    order = Order(
        order_id="ord_2",
        amount_paise=25000,
        status=OrderStatus.PENDING,
        created_at=_dt(),
    )
    payment = Payment(
        payment_id="pay_2",
        order_id="ord_2",
        amount_paise=25000,
        status=PaymentStatus.CAPTURED,
        created_at=_dt(),
    )
    signals = CaseSignals(webhook_delayed=True)
    res = diagnose_case(order, [payment], signals)
    assert res.state == CaseState.GHOST_SUCCESS
    assert res.proposed_action == Action.CONFIRM_ORDER
    assert res.recoverable_amount_paise == 25000


def test_client_timeout_ghost():
    order = Order(
        order_id="ord_3",
        amount_paise=15000,
        status=OrderStatus.FAILED,
        created_at=_dt(),
    )
    payment = Payment(
        payment_id="pay_3",
        order_id="ord_3",
        amount_paise=15000,
        status=PaymentStatus.CAPTURED,
        created_at=_dt(),
    )
    signals = CaseSignals(client_timeout=True)
    res = diagnose_case(order, [payment], signals)
    assert res.state == CaseState.GHOST_SUCCESS
    assert res.proposed_action == Action.CONFIRM_ORDER
    assert res.recoverable_amount_paise == 15000


def test_double_submit():
    order = Order(
        order_id="ord_4",
        amount_paise=50000,
        status=OrderStatus.PENDING,
        created_at=_dt(),
    )
    pay1 = Payment(
        payment_id="pay_4a",
        order_id="ord_4",
        amount_paise=50000,
        status=PaymentStatus.FAILED,
        error_code="GATEWAY_TIMEOUT",
        created_at=_dt(),
    )
    pay2 = Payment(
        payment_id="pay_4b",
        order_id="ord_4",
        amount_paise=50000,
        status=PaymentStatus.CAPTURED,
        created_at=_dt(),
    )
    signals = CaseSignals(double_submit=True)
    res = diagnose_case(order, [pay1, pay2], signals)
    assert res.state == CaseState.GHOST_SUCCESS
    assert res.proposed_action == Action.CONFIRM_ORDER
    assert res.recoverable_amount_paise == 50000


def test_orphan_payment():
    payment = Payment(
        payment_id="pay_orphan",
        order_id=None,
        amount_paise=30000,
        status=PaymentStatus.CAPTURED,
        method=PaymentMethod.UPI,
        created_at=_dt(),
    )
    res = diagnose_case(None, [payment])
    assert res.state == CaseState.ORPHAN_PAYMENT
    assert res.proposed_action == Action.LINK_OR_REFUND
    assert res.recoverable_amount_paise == 30000


def test_soft_decline():
    order = Order(
        order_id="ord_5",
        amount_paise=40000,
        status=OrderStatus.PENDING,
        created_at=_dt(),
    )
    payment = Payment(
        payment_id="pay_5",
        order_id="ord_5",
        amount_paise=40000,
        status=PaymentStatus.FAILED,
        error_code="BANK_TECHNICAL_ERROR",
        created_at=_dt(),
    )
    res = diagnose_case(order, [payment])
    assert res.state == CaseState.SOFT_DECLINE
    assert res.proposed_action == Action.SCHEDULE_RETRY
    assert res.recoverable_amount_paise == 40000


def test_hard_decline():
    order = Order(
        order_id="ord_6",
        amount_paise=40000,
        status=OrderStatus.FAILED,
        created_at=_dt(),
    )
    payment = Payment(
        payment_id="pay_6",
        order_id="ord_6",
        amount_paise=40000,
        status=PaymentStatus.FAILED,
        error_code="INVALID_VPA",
        created_at=_dt(),
    )
    res = diagnose_case(order, [payment])
    assert res.state == CaseState.HARD_FAIL
    assert res.proposed_action == Action.MARK_LOST
    assert res.recoverable_amount_paise == 0


def test_ambiguous_api_down():
    order = Order(
        order_id="ord_7",
        amount_paise=10000,
        status=OrderStatus.PENDING,
        created_at=_dt(),
    )
    payment = Payment(
        payment_id="pay_7",
        order_id="ord_7",
        amount_paise=10000,
        status=PaymentStatus.CREATED,
        created_at=_dt(),
    )
    signals = CaseSignals(api_available=False)
    res = diagnose_case(order, [payment], signals)
    assert res.state == CaseState.AMBIGUOUS
    assert res.proposed_action == Action.ESCALATE
