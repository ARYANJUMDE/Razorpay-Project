"""Tests for Razorpay test mode client and webhook verification."""

import hashlib
import hmac

from ghost_payment_resolver.razorpay_client import RazorpayClient
from ghost_payment_resolver.states import PaymentMethod, PaymentStatus


def test_webhook_signature_verification():
    secret = "whsec_test_secret_123"
    client = RazorpayClient(webhook_secret=secret)

    payload = '{"event": "payment.captured", "payload": {}}'
    valid_sig = hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    assert client.verify_webhook_signature(payload, valid_sig) is True
    assert client.verify_webhook_signature(payload, "invalid_sig_123") is False


def test_parse_webhook_to_case():
    client = RazorpayClient()
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_wh_99",
                    "amount": 199900,
                    "status": "captured",
                    "order_id": "order_wh_99",
                    "method": "upi",
                }
            }
        },
    }

    case = client.parse_webhook_to_case(payload)
    assert case.case_id == "case_wh_pay_test_wh_99"
    assert case.order.order_id == "order_wh_99"
    assert case.payments[0].payment_id == "pay_test_wh_99"
    assert case.payments[0].status == PaymentStatus.CAPTURED
    assert case.payments[0].method == PaymentMethod.UPI
    assert case.expected_amount_recovered_paise == 199900
