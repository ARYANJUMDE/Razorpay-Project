"""Pydantic schemas: orders, payments, labeled cases, audit rows."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from ghost_payment_resolver.states import (
    Action,
    CaseState,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
)


class Order(BaseModel):
    order_id: str
    amount_paise: int = Field(gt=0)
    currency: str = "INR"
    status: OrderStatus
    created_at: datetime


class Payment(BaseModel):
    payment_id: str
    order_id: str | None = None
    amount_paise: int = Field(gt=0)
    currency: str = "INR"
    status: PaymentStatus
    method: PaymentMethod = PaymentMethod.UPI
    error_code: str | None = None
    created_at: datetime
    captured_at: datetime | None = None
    failed_at: datetime | None = None


class CaseSignals(BaseModel):
    webhook_delayed: bool = False
    client_timeout: bool = False
    double_submit: bool = False
    api_available: bool = True
    notes: str | None = None


class LabeledCase(BaseModel):
    """One synthetic scenario with ground-truth labels for scoring."""

    case_id: str
    scenario: str
    order: Order | None = None
    payments: list[Payment] = Field(default_factory=list)
    signals: CaseSignals = Field(default_factory=CaseSignals)
    expected_state: CaseState
    expected_action: Action
    expected_amount_recovered_paise: int = Field(ge=0)
    meta: dict[str, Any] = Field(default_factory=dict)

    @field_validator("payments")
    @classmethod
    def at_least_something_to_resolve(cls, payments: list[Payment], info):  # type: ignore[no-untyped-def]
        # Orphan / ambiguous may still have payments; aligned always has both.
        return payments


class AuditRecord(BaseModel):
    """Immutable-ish decision log for every resolution attempt."""

    audit_id: str
    case_id: str
    timestamp: datetime
    observed_state: CaseState
    proposed_action: Action
    policy_allowed: bool
    action_taken: Action
    reason: str
    amount_recovered_paise: int = 0
    inputs: dict[str, Any] = Field(default_factory=dict)
    outcome: dict[str, Any] = Field(default_factory=dict)


class BatchMetrics(BaseModel):
    total_cases: int
    recoverable_cases: int
    correctly_recovered: int
    recovery_rate: float
    amount_recovered_paise: int
    false_actions: int
    false_action_rate: float
    escalations: int
    correct_escalations: int
    escalation_precision: float
    exceptions: list[str] = Field(default_factory=list)


class Dataset(BaseModel):
    version: str = "1.0"
    generated_at: datetime
    seed: int
    cases: list[LabeledCase]
