"""Tests for FastAPI endpoints."""

from fastapi.testclient import TestClient

from ghost_payment_resolver.api import app
from ghost_payment_resolver.states import Action

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "ghost-payment-resolver"


def test_list_cases():
    response = client.get("/cases?limit=10")
    assert response.status_code == 200
    cases = response.json()
    assert len(cases) == 10
    assert "case_id" in cases[0]


def test_resolve_case():
    # Fetch first case
    cases_resp = client.get("/cases?limit=1")
    first_case_id = cases_resp.json()[0]["case_id"]

    response = client.post(f"/resolve/{first_case_id}")
    assert response.status_code == 200
    audit = response.json()
    assert audit["case_id"] == first_case_id
    assert "action_taken" in audit


def test_resolve_case_force_api_down():
    cases_resp = client.get("/cases?limit=1")
    first_case_id = cases_resp.json()[0]["case_id"]

    response = client.post(f"/resolve/{first_case_id}?force_api_down=true")
    assert response.status_code == 200
    audit = response.json()
    assert audit["action_taken"] == Action.ESCALATE.value
    assert not audit["policy_allowed"]


def test_batch_run_and_metrics():
    response = client.post("/batch/run")
    assert response.status_code == 200
    data = response.json()
    assert "metrics" in data
    assert data["metrics"]["total_cases"] == 100
    assert data["metrics"]["false_actions"] == 0

    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    metrics = metrics_resp.json()
    assert metrics["total_cases"] == 100
