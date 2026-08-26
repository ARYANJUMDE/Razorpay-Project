"""Tests for policy guardrails, caps, and circuit breakers."""

from ghost_payment_resolver.policy import PolicyConfig, PolicyEngine
from ghost_payment_resolver.states import Action


def test_circuit_breaker_blocks_action():
    engine = PolicyEngine(PolicyConfig())
    # Normal action when API down should be converted to ESCALATE
    decision = engine.evaluate(
        proposed_action=Action.CONFIRM_ORDER,
        amount_paise=10000,
        api_available=False,
    )
    assert not decision.allowed
    assert decision.final_action == Action.ESCALATE
    assert "Circuit breaker" in decision.reason


def test_force_api_down_demo_flag():
    engine = PolicyEngine(PolicyConfig())
    decision = engine.evaluate(
        proposed_action=Action.CONFIRM_ORDER,
        amount_paise=10000,
        api_available=True,
        force_api_down=True,
    )
    assert not decision.allowed
    assert decision.final_action == Action.ESCALATE
    assert "forced down" in decision.reason


def test_daily_cap_enforcement():
    # Set small daily cap of ₹100 (10,000 paise)
    engine = PolicyEngine(PolicyConfig(daily_cap_paise=10000))

    # First transaction ₹60 -> passes
    d1 = engine.evaluate(Action.CONFIRM_ORDER, amount_paise=6000)
    assert d1.allowed
    assert d1.final_action == Action.CONFIRM_ORDER
    engine.record_action(Action.CONFIRM_ORDER, amount_paise=6000)

    # Second transaction ₹50 -> exceeds 10,000 -> escalated
    d2 = engine.evaluate(Action.CONFIRM_ORDER, amount_paise=5000)
    assert not d2.allowed
    assert d2.final_action == Action.ESCALATE
    assert "daily recovery cap" in d2.reason


def test_max_retries_enforcement():
    engine = PolicyEngine(PolicyConfig(max_retries=2))
    order_id = "order_retry_test"

    # Retry 1
    d1 = engine.evaluate(Action.SCHEDULE_RETRY, amount_paise=5000, order_id=order_id)
    assert d1.allowed
    engine.record_action(Action.SCHEDULE_RETRY, amount_paise=5000, order_id=order_id)

    # Retry 2
    d2 = engine.evaluate(Action.SCHEDULE_RETRY, amount_paise=5000, order_id=order_id)
    assert d2.allowed
    engine.record_action(Action.SCHEDULE_RETRY, amount_paise=5000, order_id=order_id)

    # Retry 3 -> Exceeded limit
    d3 = engine.evaluate(Action.SCHEDULE_RETRY, amount_paise=5000, order_id=order_id)
    assert not d3.allowed
    assert d3.final_action == Action.ESCALATE
    assert "exceeded max retries" in d3.reason
