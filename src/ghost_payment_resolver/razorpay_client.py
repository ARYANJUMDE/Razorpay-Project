"""Razorpay test-mode API integration and webhook signature verification."""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

import httpx

from ghost_payment_resolver.schemas import CaseSignals, LabeledCase, Order, Payment
from ghost_payment_resolver.states import (
    Action,
    CaseState,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
)


class RazorpayClient:
    """Client for Razorpay test-mode API interactions and webhook verification."""

    def __init__(
        self,
        key_id: str | None = None,
        key_secret: str | None = None,
        webhook_secret: str | None = None,
        base_url: str = "https://api.razorpay.com/v1",
    ) -> None:
        self.key_id = key_id or os.environ.get("RAZORPAY_KEY_ID", "rzp_test_mock123")
        self.key_secret = key_secret or os.environ.get("RAZORPAY_KEY_SECRET", "mock_secret_456")
        self.webhook_secret = webhook_secret or os.environ.get("RAZORPAY_WEBHOOK_SECRET", "whsec_test_secret_789")
        self.base_url = base_url

    def verify_webhook_signature(self, raw_body: bytes | str, signature: str) -> bool:
        """Verify HMAC-SHA256 signature sent by Razorpay webhook headers."""
        if not signature or not self.webhook_secret:
            return False

        if isinstance(raw_body, str):
            raw_body = raw_body.encode("utf-8")

        expected = hmac.new(
            self.webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        """Fetch payment status from Razorpay test API (with mock fallback)."""
        if self.key_id.startswith("rzp_test_mock"):
            # Return realistic mock payment payload
            return {
                "id": payment_id,
                "entity": "payment",
                "amount": 149900,
                "currency": "INR",
                "status": "captured",
                "order_id": "order_mock_test123",
                "method": "upi",
                "captured": True,
                "error_code": None,
            }

        url = f"{self.base_url}/payments/{payment_id}"
        with httpx.Client(auth=(self.key_id, self.key_secret), timeout=5.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()

    def parse_webhook_to_case(self, payload: dict[str, Any]) -> LabeledCase:
        """Convert a Razorpay webhook JSON payload into a LabeledCase for resolution."""
        event = payload.get("event", "payment.captured")
        contains = payload.get("payload", {}).get("payment", {}).get("entity", {})
        order_entity = payload.get("payload", {}).get("order", {}).get("entity", {})

        payment_id = contains.get("id", "pay_wh_test")
        order_id = contains.get("order_id") or order_entity.get("id") or "order_wh_test"
        amount_paise = contains.get("amount") or order_entity.get("amount", 100000)

        # Map payment status
        raw_status = contains.get("status", "captured")
        status_map = {
            "created": PaymentStatus.CREATED,
            "authorized": PaymentStatus.AUTHORIZED,
            "captured": PaymentStatus.CAPTURED,
            "failed": PaymentStatus.FAILED,
            "refunded": PaymentStatus.REFUNDED,
        }
        pay_status = status_map.get(raw_status, PaymentStatus.CAPTURED)

        # Map payment method
        raw_method = contains.get("method", "upi")
        method_map = {
            "upi": PaymentMethod.UPI,
            "card": PaymentMethod.CARD,
            "netbanking": PaymentMethod.NETBANKING,
            "wallet": PaymentMethod.WALLET,
        }
        pay_method = method_map.get(raw_method, PaymentMethod.UPI)

        payment = Payment(
            payment_id=payment_id,
            order_id=order_id,
            amount_paise=amount_paise,
            status=pay_status,
            method=pay_method,
            error_code=contains.get("error_code"),
            created_at=order_entity.get("created_at") or "2026-08-27T12:00:00Z",
        )

        # In a real webhook scenario, order status in merchant DB might still be pending
        order_status = (
            OrderStatus.PENDING
            if event == "payment.captured"
            else OrderStatus.CREATED
        )

        order = Order(
            order_id=order_id,
            amount_paise=amount_paise,
            status=order_status,
            created_at=order_entity.get("created_at") or "2026-08-27T12:00:00Z",
        )

        signals = CaseSignals(
            webhook_delayed=True,
            client_timeout=False,
            double_submit=False,
            api_available=True,
        )

        return LabeledCase(
            case_id=f"case_wh_{payment_id}",
            scenario="Live Razorpay Webhook Ingestion",
            order=order,
            payments=[payment],
            signals=signals,
            expected_state=CaseState.GHOST_SUCCESS,
            expected_action=Action.CONFIRM_ORDER,
            expected_amount_recovered_paise=amount_paise,
        )
