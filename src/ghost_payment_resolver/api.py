"""FastAPI service and demo endpoints for Ghost Payment Resolver."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from ghost_payment_resolver import __version__
from ghost_payment_resolver.engine import ResolutionEngine
from ghost_payment_resolver.generate_dataset import DEFAULT_OUT, load_dataset
from ghost_payment_resolver.policy import PolicyConfig
from ghost_payment_resolver.schemas import AuditRecord, BatchMetrics, LabeledCase

app = FastAPI(
    title="Ghost Payment Resolver API",
    description="AI Revenue Recovery agent for payment-order mismatches (Razorpay /buildathon Track 03)",
    version=__version__,
)

DATA_PATH = DEFAULT_OUT
_engine = ResolutionEngine()
_last_metrics: BatchMetrics | None = None


class BatchRunResponse(BaseModel):
    metrics: BatchMetrics
    sample_audits: list[AuditRecord]


@app.get("/health")
def health() -> dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "ghost-payment-resolver",
        "version": __version__,
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
    engine = ResolutionEngine()
    record = engine.resolve_case(case, force_api_down=force_api_down)
    return record


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
    engine = ResolutionEngine(PolicyConfig(daily_cap_paise=daily_cap_paise))
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
