# Ghost Payment Resolver

AI Revenue Recovery agent for Razorpay /buildathon (**Track 03 — AI Revenue Recovery**).

Detects payment–order mismatches (“ghost payments”), diagnoses root cause, runs a **bounded** recovery workflow, and reports measured ₹ recovered with a full audit trail.

## Stack

- **Python 3.10+**
- **FastAPI** — REST API + demo failure injection
- **Pydantic v2** — case, payment, audit, and policy schemas
- **Pytest** — comprehensive unit & batch test suite

## Status

- [x] Product spec + state machine (`docs/SPEC.md`)
- [x] Pydantic schemas (`src/ghost_payment_resolver/schemas.py`)
- [x] Synthetic dataset generator (100 labeled cases) (`src/ghost_payment_resolver/generate_dataset.py`)
- [x] Policy guardrails & safety caps (`src/ghost_payment_resolver/policy.py`)
- [x] Matcher & diagnostic engine (`src/ghost_payment_resolver/matcher.py`)
- [x] Core resolution engine & batch runner (`src/ghost_payment_resolver/engine.py`)
- [x] FastAPI demo endpoints (`src/ghost_payment_resolver/api.py`)
- [x] 100% test coverage for matcher, policy, engine, and API (`tests/`)

## Quick Start

### 1. Installation

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
```

### 2. Generate Synthetic Dataset

```bash
gpr-generate
# Or: python -m ghost_payment_resolver.generate_dataset
```

### 3. Run Batch Evaluation

```bash
gpr-resolve
# Or: python -m ghost_payment_resolver.engine
```

**Output:**
```text
============================================================
 GHOST PAYMENT RESOLVER -- BATCH EVALUATION REPORT
============================================================
 Total Cases Evaluated   : 100
 Recoverable Cases       : 50
 Correctly Recovered     : 50
 Recovery Rate           : 100.00%
 Total Amount Recovered  : INR 139,050.00 (13905000 paise)
 False Actions           : 0
 False Action Rate       : 0.00%
 Total Escalations       : 5
 Escalation Precision    : 100.00%
 Exceptions Encountered  : 0
============================================================
```

### 4. Test Demo Failure (Circuit Breaker)

Simulate payment API downtime to demonstrate guaranteed safe escalation (never auto-confirms when signals are untrusted):

```bash
gpr-resolve --force-api-down
```

### 5. Run API Server

```bash
uvicorn ghost_payment_resolver.api:app --reload --port 8000
```

- Swagger UI: `http://127.0.0.1:8000/docs`
- Run Batch via API: `POST /batch/run`
- Resolve Single Case: `POST /resolve/{case_id}?force_api_down=true`

### 6. Run Tests

```bash
pytest -v
ruff check .
```

## Project Layout

```text
docs/SPEC.md                 # Product spec + state machine rules
src/ghost_payment_resolver/  # Core package
  schemas.py                 # Pydantic models (Order, Payment, Audit, BatchMetrics)
  states.py                  # Enums + state transitions + error codes
  generate_dataset.py        # 100 labeled benchmark cases
  policy.py                  # Safety guardrails, caps, retry limits, circuit breaker
  matcher.py                 # Payment-order diagnostic classifier
  engine.py                  # Resolution loop, batch runner, and metrics calculator
  api.py                     # FastAPI server with demo endpoints
data/cases.json              # 100-case synthetic dataset
tests/                       # Pytest test suite (19 test cases)
```
