# Ghost Payment Resolver

AI Revenue Recovery agent for Razorpay /buildathon (**Track 03 — AI Revenue Recovery**).

Detects payment–order mismatches (“ghost payments”), diagnoses root cause, runs a **bounded** recovery workflow, and reports measured ₹ recovered with a full audit trail.

## Stack

- **Python 3.10+**
- **FastAPI** — REST API + Web UI dashboard + demo failure injection
- **Pydantic v2** — case, payment, audit, and policy schemas
- **SQLite** — persistent audit log storage and CSV export
- **AI Explainer** — LLM-driven post-mortems and English/Hinglish customer messaging (with zero-crash deterministic fallback)
- **Razorpay Rail** — test-mode client and HMAC-SHA256 webhook verification
- **Pytest** — comprehensive unit & batch test suite (30 test cases)

## Status

- [x] Product spec + state machine (`docs/SPEC.md`)
- [x] Pydantic schemas (`src/ghost_payment_resolver/schemas.py`)
- [x] Synthetic dataset generator (100 labeled cases) (`src/ghost_payment_resolver/generate_dataset.py`)
- [x] Policy guardrails & safety caps (`src/ghost_payment_resolver/policy.py`)
- [x] Matcher & diagnostic engine (`src/ghost_payment_resolver/matcher.py`)
- [x] Core resolution engine & batch runner (`src/ghost_payment_resolver/engine.py`)
- [x] SQLite persistent audit log storage (`src/ghost_payment_resolver/storage.py`)
- [x] AI Explainer & Hinglish Customer Notification engine (`src/ghost_payment_resolver/ai_explainer.py`)
- [x] Razorpay test-mode client & webhook receiver (`src/ghost_payment_resolver/razorpay_client.py`)
- [x] Interactive Web UI Dashboard (`src/ghost_payment_resolver/static/`)
- [x] FastAPI REST endpoints (`src/ghost_payment_resolver/api.py`)
- [x] 100% test coverage across all layers (`tests/` — 30/30 tests passing)

## Quick Start

### 1. Installation

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
```

### 2. Run Interactive Web Dashboard

```bash
uvicorn ghost_payment_resolver.api:app --reload --port 8000
```

- **Dashboard UI**: Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) or `/dashboard` in your browser.
- **Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 3. Generate Synthetic Dataset

```bash
gpr-generate
# Or: python -m ghost_payment_resolver.generate_dataset
```

### 4. Run Batch Evaluation (CLI)

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

### 5. Test Demo Failure (Circuit Breaker)

Simulate payment API downtime to demonstrate guaranteed safe escalation (never auto-confirms when signals are untrusted):

```bash
gpr-resolve --force-api-down
```

### 6. Run Tests & Linter

```bash
pytest -v
ruff check .
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` or `/dashboard` | Interactive Web UI Dashboard |
| `GET` | `/health` | Service health and persistent audit counter |
| `GET` | `/cases` | List and filter 100 benchmark cases |
| `GET` | `/cases/{id}` | Retrieve case details |
| `POST` | `/resolve/{id}` | Resolve single case (`?force_api_down=true`) |
| `POST` | `/cases/{id}/explain` | Generate AI Root-Cause post-mortem & Hinglish customer message |
| `POST` | `/batch/run` | Execute batch resolution across all 100 cases |
| `GET` | `/metrics` | Get latest batch recovery metrics |
| `GET` | `/audits` | Query persisted audit logs from SQLite (`data/audit.db`) |
| `GET` | `/audits/export` | Download audit history as CSV for finance reconciliation |
| `POST` | `/webhooks/razorpay` | Ingest live or simulated Razorpay webhook events |

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
  storage.py                 # SQLite persistence layer and CSV export
  ai_explainer.py            # AI root-cause explainer & English/Hinglish customer drafts
  razorpay_client.py         # Razorpay test-mode API & HMAC webhook verifier
  api.py                     # FastAPI server with UI & REST endpoints
  static/                    # Interactive web dashboard (index.html, style.css, app.js)
data/cases.json              # 100-case synthetic dataset
data/audit.db                # SQLite persistent audit storage
tests/                       # Pytest test suite (30 test cases)
```
