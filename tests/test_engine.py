"""Tests for ResolutionEngine batch execution and scoring metrics."""

from ghost_payment_resolver.engine import ResolutionEngine
from ghost_payment_resolver.generate_dataset import DEFAULT_OUT, generate, load_dataset
from ghost_payment_resolver.states import Action


def test_batch_resolution_on_generated_dataset():
    # Load dataset
    if DEFAULT_OUT.exists():
        dataset = load_dataset(DEFAULT_OUT)
    else:
        dataset = generate(seed=42, total=100)

    engine = ResolutionEngine()
    audits, metrics = engine.run_batch(dataset)

    assert len(audits) == 100
    assert metrics.total_cases == 100
    assert metrics.false_actions == 0
    assert metrics.false_action_rate == 0.0
    assert metrics.recovery_rate == 1.0
    assert metrics.escalation_precision == 1.0
    assert metrics.amount_recovered_paise > 0
    assert len(metrics.exceptions) == 0


def test_batch_resolution_with_force_api_down():
    dataset = generate(seed=42, total=100)
    engine = ResolutionEngine()
    audits, metrics = engine.run_batch(dataset, force_api_down=True)

    # Everything must escalate when payment API is down
    assert metrics.escalations == 100
    for audit in audits:
        assert audit.action_taken == Action.ESCALATE
        assert not audit.policy_allowed or "circuit breaker" in audit.reason.lower()
