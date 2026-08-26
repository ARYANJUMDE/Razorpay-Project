"""Policy engine and guardrails for Ghost Payment Resolver."""

from __future__ import annotations

from dataclasses import dataclass

from ghost_payment_resolver.states import Action


@dataclass
class PolicyConfig:
    """Configurable safety limits and policy guardrails."""

    daily_cap_paise: int = 5_000_000  # ₹50,000 default daily cap
    max_retries: int = 2
    enforce_circuit_breaker: bool = True
    allowed_actions: set[Action] = frozenset(Action)  # type: ignore[assignment]


@dataclass
class PolicyDecision:
    """Result of policy evaluation for a proposed action."""

    allowed: bool
    final_action: Action
    reason: str


class PolicyEngine:
    """Enforces safety guardrails, caps, and circuit breakers."""

    def __init__(self, config: PolicyConfig | None = None) -> None:
        self.config = config or PolicyConfig()
        self.daily_recovered_paise: int = 0
        self.retry_counts: dict[str, int] = {}

    def reset_daily_stats(self) -> None:
        """Reset daily accumulator for new simulation/day."""
        self.daily_recovered_paise = 0
        self.retry_counts.clear()

    def evaluate(
        self,
        proposed_action: Action,
        amount_paise: int = 0,
        api_available: bool = True,
        order_id: str | None = None,
        force_api_down: bool = False,
    ) -> PolicyDecision:
        """Evaluate whether a proposed action is permitted by policy gates.

        If any guardrail fails, safely fallback to Action.ESCALATE.
        """
        # 1. Circuit Breaker / API Availability Check
        if self.config.enforce_circuit_breaker and (not api_available or force_api_down):
            return PolicyDecision(
                allowed=False,
                final_action=Action.ESCALATE,
                reason="Circuit breaker triggered: Payment API unavailable or forced down.",
            )

        # 2. Action Allowlist Check
        if proposed_action not in self.config.allowed_actions:
            return PolicyDecision(
                allowed=False,
                final_action=Action.ESCALATE,
                reason=f"Action '{proposed_action}' not in approved allowlist.",
            )

        # 3. Retry Limits Check
        if proposed_action == Action.SCHEDULE_RETRY and order_id:
            current_retries = self.retry_counts.get(order_id, 0)
            if current_retries >= self.config.max_retries:
                return PolicyDecision(
                    allowed=False,
                    final_action=Action.ESCALATE,
                    reason=(
                        f"Order {order_id} exceeded max retries limit "
                        f"({current_retries}/{self.config.max_retries})."
                    ),
                )

        # 4. Daily Recovery Cap Check
        if proposed_action in {Action.CONFIRM_ORDER, Action.LINK_OR_REFUND, Action.SCHEDULE_RETRY}:
            projected_total = self.daily_recovered_paise + amount_paise
            if projected_total > self.config.daily_cap_paise:
                return PolicyDecision(
                    allowed=False,
                    final_action=Action.ESCALATE,
                    reason=(
                        f"Action would exceed daily recovery cap of ₹{self.config.daily_cap_paise / 100:.2f} "
                        f"(Projected: ₹{projected_total / 100:.2f})."
                    ),
                )

        # All checks passed
        return PolicyDecision(
            allowed=True,
            final_action=proposed_action,
            reason="Policy check passed.",
        )

    def record_action(
        self,
        action_taken: Action,
        amount_paise: int = 0,
        order_id: str | None = None,
    ) -> None:
        """Update policy state after action execution."""
        if action_taken in {Action.CONFIRM_ORDER, Action.LINK_OR_REFUND, Action.SCHEDULE_RETRY}:
            self.daily_recovered_paise += amount_paise

        if action_taken == Action.SCHEDULE_RETRY and order_id:
            self.retry_counts[order_id] = self.retry_counts.get(order_id, 0) + 1
