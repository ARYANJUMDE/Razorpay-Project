"""Tests for AI Explainer and customer messaging engine."""

from datetime import datetime, timezone

from ghost_payment_resolver.ai_explainer import (
    generate_fallback_explanation,
)
from ghost_payment_resolver.schemas import (
    AuditRecord,
    CaseSignals,
    LabeledCase,
    Order,
    Payment,
)
from ghost_payment_resolver.states import (
    Action,
    CaseState,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
)


def test_ai_explainer_ghost_success():
    order = Order(
        order_id="ord_test_ai_1",
        amount_paise=299900,
        status=OrderStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )
    payment = Payment(
        payment_id="pay_ai_1",
        order_id="ord_test_ai_1",
        amount_paise=299900,
        status=PaymentStatus.CAPTURED,
        method=PaymentMethod.UPI,
        created_at=datetime.now(timezone.utc),
    )
    signals = CaseSignals(
        webhook_delayed=True,
        client_timeout=False,
        double_submit=False,
        api_available=True,
    )
    case = LabeledCase(
        case_id="case_ai_1",
        scenario="Webhook Delayed",
        order=order,
        payments=[payment],
        signals=signals,
        expected_state=CaseState.GHOST_SUCCESS,
        expected_action=Action.CONFIRM_ORDER,
        expected_amount_recovered_paise=299900,
    )
    record = AuditRecord(
        audit_id="aud_ai_1",
        case_id="case_ai_1",
        timestamp=datetime.now(timezone.utc),
        observed_state=CaseState.GHOST_SUCCESS,
        proposed_action=Action.CONFIRM_ORDER,
        policy_allowed=True,
        action_taken=Action.CONFIRM_ORDER,
        reason="Webhook delayed",
        amount_recovered_paise=299900,
        inputs={},
        outcome={},
    )

    explanation = generate_fallback_explanation(case, record)
    assert explanation.observed_state == CaseState.GHOST_SUCCESS
    assert explanation.amount_recovered_inr == 2999.0
    assert "webhook" in explanation.root_cause_analysis.lower()
    assert "Namaste" in explanation.customer_message_hinglish or "Aapka" in explanation.customer_message_hinglish
    assert len(explanation.customer_message_en) > 10


def test_ai_explainer_soft_decline():
    order = Order(
        order_id="ord_test_soft",
        amount_paise=50000,
        status=OrderStatus.CREATED,
        created_at=datetime.now(timezone.utc),
    )
    payment = Payment(
        payment_id="pay_soft_1",
        order_id="ord_test_soft",
        amount_paise=50000,
        status=PaymentStatus.FAILED,
        method=PaymentMethod.UPI,
        error_code="GATEWAY_TIMEOUT",
        created_at=datetime.now(timezone.utc),
    )
    signals = CaseSignals(
        webhook_delayed=False,
        client_timeout=False,
        double_submit=False,
        api_available=True,
    )
    case = LabeledCase(
        case_id="case_ai_soft",
        scenario="Soft Decline",
        order=order,
        payments=[payment],
        signals=signals,
        expected_state=CaseState.SOFT_DECLINE,
        expected_action=Action.SCHEDULE_RETRY,
        expected_amount_recovered_paise=50000,
    )
    record = AuditRecord(
        audit_id="aud_ai_soft",
        case_id="case_ai_soft",
        timestamp=datetime.now(timezone.utc),
        observed_state=CaseState.SOFT_DECLINE,
        proposed_action=Action.SCHEDULE_RETRY,
        policy_allowed=True,
        action_taken=Action.SCHEDULE_RETRY,
        reason="Retryable failure",
        amount_recovered_paise=50000,
        inputs={},
        outcome={},
    )

    explanation = generate_fallback_explanation(case, record)
    assert "GATEWAY_TIMEOUT" in explanation.root_cause_analysis
    assert "retry" in explanation.merchant_summary.lower()
