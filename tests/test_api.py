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


def test_dashboard_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "Ghost Payment Resolver" in response.text


def test_explain_case_endpoint():
    cases_resp = client.get("/cases?limit=1")
    first_case_id = cases_resp.json()[0]["case_id"]

    response = client.post(f"/cases/{first_case_id}/explain")
    assert response.status_code == 200
    data = response.json()
    assert "root_cause_analysis" in data
    assert "customer_message_hinglish" in data
    assert "merchant_summary" in data


def test_audits_and_export_endpoints():
    response = client.get("/audits?limit=5")
    assert response.status_code == 200
    audits = response.json()
    assert isinstance(audits, list)

    export_resp = client.get("/audits/export")
    assert export_resp.status_code == 200
    assert "audit_id" in export_resp.text


def test_razorpay_webhook_endpoint():
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_live_test_001",
                    "amount": 250000,
                    "status": "captured",
                    "order_id": "order_live_001",
                    "method": "upi",
                }
            }
        },
    }
    response = client.post("/webhooks/razorpay", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["action_taken"] == Action.CONFIRM_ORDER.value

