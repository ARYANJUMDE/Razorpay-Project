"""State machine enums for Ghost Payment Resolver."""

from enum import Enum


class OrderStatus(str, Enum):
    CREATED = "created"
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaymentStatus(str, Enum):
    CREATED = "created"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentMethod(str, Enum):
    UPI = "upi"
    CARD = "card"
    NETBANKING = "netbanking"
    WALLET = "wallet"


class CaseState(str, Enum):
    ALIGNED = "ALIGNED"
    GHOST_SUCCESS = "GHOST_SUCCESS"
    ORPHAN_PAYMENT = "ORPHAN_PAYMENT"
    SOFT_DECLINE = "SOFT_DECLINE"
    HARD_FAIL = "HARD_FAIL"
    AMBIGUOUS = "AMBIGUOUS"


class Action(str, Enum):
    NO_OP = "NO_OP"
    CONFIRM_ORDER = "CONFIRM_ORDER"
    LINK_OR_REFUND = "LINK_OR_REFUND"
    SCHEDULE_RETRY = "SCHEDULE_RETRY"
    MARK_LOST = "MARK_LOST"
    ESCALATE = "ESCALATE"


# Soft (retryable) vs hard decline codes used in synthetic data
SOFT_ERROR_CODES = frozenset(
    {
        "GATEWAY_TIMEOUT",
        "BANK_TECHNICAL_ERROR",
        "UPI_TEMPORARY_FAILURE",
        "INSUFFICIENT_BALANCE",  # often retryable later in India flows
    }
)

HARD_ERROR_CODES = frozenset(
    {
        "PAYMENT_DECLINED",
        "INVALID_VPA",
        "ACCOUNT_BLOCKED",
        "CARD_EXPIRED",
    }
)

# Default mapping: state → preferred action (policy may still escalate)
STATE_DEFAULT_ACTION: dict[CaseState, Action] = {
    CaseState.ALIGNED: Action.NO_OP,
    CaseState.GHOST_SUCCESS: Action.CONFIRM_ORDER,
    CaseState.ORPHAN_PAYMENT: Action.LINK_OR_REFUND,
    CaseState.SOFT_DECLINE: Action.SCHEDULE_RETRY,
    CaseState.HARD_FAIL: Action.MARK_LOST,
    CaseState.AMBIGUOUS: Action.ESCALATE,
}
