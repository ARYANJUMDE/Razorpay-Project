"""FastAPI service, Web UI dashboard, and demo endpoints for Ghost Payment Resolver."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ghost_payment_resolver import __version__
from ghost_payment_resolver.ai_explainer import AIExplanation, explain_case_with_llm
from ghost_payment_resolver.engine import ResolutionEngine
from ghost_payment_resolver.generate_dataset import DEFAULT_OUT, load_dataset
from ghost_payment_resolver.policy import PolicyConfig
from ghost_payment_resolver.razorpay_client import RazorpayClient
from ghost_payment_resolver.schemas import AuditRecord, BatchMetrics, LabeledCase
from ghost_payment_resolver.storage import AuditDatabase

app = FastAPI(
    title="Ghost Payment Resolver API & Dashboard",
    description="AI Revenue Recovery agent for payment-order mismatches (Razorpay /buildathon Track 03)",
    version=__version__,
)

DATA_PATH = DEFAULT_OUT
STATIC_DIR = Path(__file__).parent / "static"

_storage = AuditDatabase()
_engine = ResolutionEngine(storage=_storage)
_razorpay_client = RazorpayClient()
_last_metrics: BatchMetrics | None = None

# Mount static folder if exists
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class BatchRunResponse(BaseModel):
    metrics: BatchMetrics
    sample_audits: list[AuditRecord]


@app.get("/", include_in_schema=False)
@app.get("/dashboard", include_in_schema=False)
def serve_dashboard() -> FileResponse:
    """Serve the interactive merchant dashboard."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Dashboard UI not found.")
    return FileResponse(str(index_file))


@app.get("/health")
def health() -> dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "ghost-payment-resolver",
        "version": __version__,
        "total_audits_persisted": _storage.count_audits(),
    }


@app.get("/cases", response_model=list[LabeledCase])
def list_cases(
    scenario: str | None = None,
    state: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[LabeledCase]:
    """List synthetic cases from the dataset with optional filtering."""
    if not DATA_PATH.exists():
        raise HTTPException(status_code=404, detail="Dataset not found. Run dataset generator first.")

    dataset = load_dataset(DATA_PATH)
    cases = dataset.cases

    if scenario:
        cases = [c for c in cases if c.scenario.lower() == scenario.lower()]
    if state:
        cases = [c for c in cases if c.expected_state.value.lower() == state.lower()]

    return cases[:limit]


@app.get("/cases/{case_id}", response_model=LabeledCase)
def get_case(case_id: str) -> LabeledCase:
    """Retrieve a single case by ID."""
    if not DATA_PATH.exists():
        raise HTTPException(status_code=404, detail="Dataset not found.")

    dataset = load_dataset(DATA_PATH)
    for c in dataset.cases:
        if c.case_id == case_id:
            return c

    raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")


@app.post("/resolve/{case_id}", response_model=AuditRecord)
def resolve_case_endpoint(
    case_id: str,
    force_api_down: bool = Query(
        default=False,
        description="Simulate payment gateway API downtime (circuit breaker demo failure)",
    ),
) -> AuditRecord:
    """Resolve a specific case through the state machine and policy gates."""
    case = get_case(case_id)
    engine = ResolutionEngine(storage=_storage)
    record = engine.resolve_case(case, force_api_down=force_api_down)
    return record


@app.post("/cases/{case_id}/explain", response_model=AIExplanation)
def explain_case_endpoint(
    case_id: str,
    force_api_down: bool = Query(
        default=False,
        description="Simulate API downtime",
    ),
) -> AIExplanation:
    """Generate AI-powered root-cause post-mortem and English/Hinglish customer drafts."""
    case = get_case(case_id)
    engine = ResolutionEngine(storage=_storage)
    record = engine.resolve_case(case, force_api_down=force_api_down)
    explanation = explain_case_with_llm(case, record)
    return explanation


@app.post("/batch/run", response_model=BatchRunResponse)
def run_batch_endpoint(
    force_api_down: bool = Query(
        default=False,
        description="Force API down across all cases in batch run",
    ),
    daily_cap_paise: int = Query(
        default=50_000_000,
        description="Daily recovery cap in paise (default ₹500,000)",
    ),
) -> BatchRunResponse:
    """Run resolution across the entire 100-case dataset and compute evaluation metrics."""
    global _last_metrics
    if not DATA_PATH.exists():
        raise HTTPException(status_code=404, detail="Dataset not found.")

    dataset = load_dataset(DATA_PATH)
    engine = ResolutionEngine(
        policy_config=PolicyConfig(daily_cap_paise=daily_cap_paise),
        storage=_storage,
    )
    audits, metrics = engine.run_batch(dataset, force_api_down=force_api_down)
    _last_metrics = metrics

    return BatchRunResponse(
        metrics=metrics,
        sample_audits=audits[:10],
    )


@app.get("/metrics", response_model=BatchMetrics)
def get_latest_metrics() -> BatchMetrics:
    """Get the latest batch evaluation metrics or trigger a default batch run."""
    if _last_metrics is not None:
        return _last_metrics

    # If not yet computed, compute default batch
    response = run_batch_endpoint()
    return response.metrics


@app.get("/audits", response_model=list[AuditRecord])
def list_audits(
    case_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[AuditRecord]:
    """Retrieve persisted audit logs from SQLite database."""
    return _storage.get_audits(case_id=case_id, limit=limit, offset=offset)


@app.get("/audits/export")
def export_audits_csv() -> Response:
    """Download entire SQLite audit logs as a CSV file for merchant finance reconciliation."""
    csv_data = _storage.export_csv()
    return PlainTextResponse(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ghost_payment_audit_report.csv"},
    )


@app.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(default=""),
) -> dict[str, Any]:
    """Ingest live or simulated Razorpay webhook events with signature verification."""
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")

    # If signature is provided, verify it (otherwise allow mock payload if secret is default)
    if x_razorpay_signature:
        is_valid = _razorpay_client.verify_webhook_signature(body_str, x_razorpay_signature)
        if not is_valid:
            raise HTTPException(status_code=400, detail="Invalid Razorpay webhook signature")

    try:
        import json
        payload = json.loads(body_str)
        case = _razorpay_client.parse_webhook_to_case(payload)
        record = _engine.resolve_case(case)
        return {
            "status": "processed",
            "event": payload.get("event"),
            "case_id": case.case_id,
            "action_taken": record.action_taken.value,
            "amount_recovered_inr": record.amount_recovered_paise / 100,
            "audit_id": record.audit_id,
        }
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Webhook processing error: {e!s}") from e
