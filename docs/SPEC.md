# Ghost Payment Resolver — Product Spec (Day 1)

## One-liner

An agent that finds **payment–order mismatches** (ghost/stuck payments), diagnoses why, runs a **bounded recovery** (confirm / retry / refund / escalate), and reports **₹ recovered + audit trail** on a synthetic batch.

## In scope (MVP)

1. Detect mismatches between payment rail status and merchant order status
2. Classify into a finite set of states
3. Propose + execute an allowlisted action behind policy gates
4. Run a labeled batch (100+ cases) and report metrics
5. Always write an audit row; demonstrate one graceful failure path

## Out of scope (MVP)

- Full merchant dashboard polish
- Live bank / NPCI integrations
- Voice / Hinglish recovery
- Multi-country rails
- Letting an LLM invent payment truth

## Source of truth rule

**Payment status from APIs / fixtures is ground truth for money.**  
The LLM (later) may only explain and choose from an **allowlist** of actions. It must never invent “paid” or amounts.

---

## Entities

### Order

| Field | Notes |
|-------|--------|
| `order_id` | Merchant order id |
| `amount_paise` | Integer paise |
| `currency` | `INR` |
| `status` | `created` \| `pending` \| `paid` \| `failed` \| `cancelled` |
| `created_at` | ISO timestamp |

### Payment

| Field | Notes |
|-------|--------|
| `payment_id` | Razorpay-like id |
| `order_id` | May be missing for orphan payments |
| `amount_paise` | Integer paise |
| `status` | `created` \| `authorized` \| `captured` \| `failed` \| `refunded` |
| `method` | `upi` \| `card` \| `netbanking` \| `wallet` |
| `error_code` | Optional soft/hard decline code |
| `captured_at` / `failed_at` | Optional |

### Signals (derived)

- Amount match / mismatch
- Order linked / missing
- Webhook delay flag
- Double-submit (2+ payments for one order)
- API available / unavailable

---

## States

| State | Meaning |
|-------|---------|
| `ALIGNED` | Payment + order agree; nothing to do |
| `GHOST_SUCCESS` | Money captured on rail; order still pending/failed |
| `ORPHAN_PAYMENT` | Captured payment with no matching order |
| `SOFT_DECLINE` | Failed payment with retryable error |
| `HARD_FAIL` | Failed payment, non-retryable |
| `AMBIGUOUS` | Conflicting / incomplete signals — hold |

---

## Allowed actions

| Action | When | Effect (synthetic) |
|--------|------|---------------------|
| `NO_OP` | `ALIGNED` | No change |
| `CONFIRM_ORDER` | `GHOST_SUCCESS` | Mark order `paid`; count amount as recovered |
| `LINK_OR_REFUND` | `ORPHAN_PAYMENT` | Prefer link if possible; else refund (prevents loss / support cost) |
| `SCHEDULE_RETRY` | `SOFT_DECLINE` | Queue retry within caps; recovered if retry succeeds in sim |
| `MARK_LOST` | `HARD_FAIL` | Close case; ₹ recovered = 0 |
| `ESCALATE` | `AMBIGUOUS` or policy block | Human queue; **never** auto-fulfill |

---

## Policy gates (must enforce)

- Max **2** retries per order
- Daily recovery action cap (default **₹50,000** = 5_000_000 paise) — configurable
- Cooldown between retries (e.g. 15–120 min by error class)
- If payment API / fixture marked unavailable → **force `ESCALATE`**
- Unknown action from any advisor → reject → `ESCALATE`

---

## Metrics (batch)

- `recoverable_cases` — cases whose expected action recovers or protects revenue
- `recovery_rate` — correctly recovered / recoverable
- `amount_recovered_paise`
- `false_action_rate` — wrong action vs label (esp. false confirm/refund)
- `escalation_precision` — escalations that should have been escalated
- `exceptions` — cases agent could not resolve (honest list)

---

## Dataset mix (100 cases)

| Share | Scenario |
|------:|----------|
| 40% | `ALIGNED` |
| 15% | Webhook delayed → `GHOST_SUCCESS` |
| 15% | Client timeout but captured → `GHOST_SUCCESS` |
| 10% | Double-submit |
| 10% | Soft decline → `SOFT_DECLINE` |
| 5% | Hard decline → `HARD_FAIL` |
| 5% | Ambiguous / API down → `AMBIGUOUS` |

Each case includes `expected_state`, `expected_action`, `expected_amount_recovered_paise`.

---

## Demo failure (required)

Button / flag: `force_api_down=true` → agent escalates, writes audit, **does not** confirm order.
