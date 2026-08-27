"""AI Root-Cause Explainer and Customer Notification Engine for Ghost Payment Resolver."""

from __future__ import annotations

import json
import os

import httpx
from pydantic import BaseModel, Field

from ghost_payment_resolver.schemas import AuditRecord, LabeledCase
from ghost_payment_resolver.states import Action, CaseState


class AIExplanation(BaseModel):
    """Structured AI-generated explanation and customer recovery messaging."""

    case_id: str
    observed_state: CaseState
    action_taken: Action
    amount_recovered_inr: float
    root_cause_analysis: str = Field(
        description="Deep-dive analysis of why the payment-order mismatch occurred."
    )
    merchant_summary: str = Field(
        description="Executive summary for merchant finance and operations teams."
    )
    customer_message_en: str = Field(
        description="Customer notification draft in English (SMS/WhatsApp/Email)."
    )
    customer_message_hinglish: str = Field(
        description="Customer notification draft in Hinglish for Indian merchants."
    )
    action_safety_note: str = Field(
        description="Verification that resolution strictly adheres to allowlisted policy guardrails."
    )
    source: str = Field(
        default="deterministic_engine",
        description="Source of the explanation ('llm' or 'deterministic_engine').",
    )


def generate_fallback_explanation(case: LabeledCase, record: AuditRecord) -> AIExplanation:
    """Generate high-fidelity, deterministic root-cause analysis and customer drafts without LLM."""
    state = record.observed_state
    action = record.action_taken
    amount_inr = record.amount_recovered_paise / 100
    order_id = case.order.order_id if case.order else "N/A"
    order_amount_inr = (case.order.amount_paise / 100) if case.order else amount_inr

    # Specialized scenario insights
    if state == CaseState.GHOST_SUCCESS:
        if case.signals.webhook_delayed:
            root_cause = (
                f"A gateway webhook latency occurred. Razorpay payment rail captured "
                f"₹{amount_inr:,.2f}, but the merchant's backend webhook was delayed or dropped. "
                f"The order status remained '{case.order.status.value if case.order else 'pending'}'."
            )
            merchant_summary = (
                f"Automated reconciliation detected verified rail capture for Order {order_id}. "
                f"Order auto-confirmed to 'paid' under safety limits, recovering ₹{amount_inr:,.2f}."
            )
            customer_en = (
                f"Good news! Your payment of ₹{amount_inr:,.2f} for Order #{order_id} has been "
                f"verified and your order is confirmed. Thank you for shopping with us!"
            )
            customer_hinglish = (
                f"Namaste! Aapka ₹{amount_inr:,.2f} ka payment Order #{order_id} ke liye safalta-purvak "
                f"receive ho gaya hai. Aapka order confirm kar diya gaya hai!"
            )
        else:
            root_cause = (
                "Client browser timeout during checkout. The customer authorized payment on UPI/Card rail, "
                "but the browser disconnected before redirection back to the merchant."
            )
            merchant_summary = (
                f"Recovered abandoned checkout session. Rail captured ₹{amount_inr:,.2f}; order "
                f"status automatically updated to 'paid' without requiring customer support intervention."
            )
            customer_en = (
                f"We noticed your checkout was interrupted, but your payment of ₹{amount_inr:,.2f} was "
                f"received successfully. Order #{order_id} is now confirmed!"
            )
            customer_hinglish = (
                f"Checkout ke dauran connection drop ho gaya tha, lekin aapka ₹{amount_inr:,.2f} ka payment "
                f"receive ho chuka hai. Order #{order_id} confirm kar diya gaya hai."
            )

    elif state == CaseState.ORPHAN_PAYMENT:
        root_cause = (
            f"Orphan payment detected. Payment of ₹{amount_inr:,.2f} was captured on the rail, but no "
            f"matching merchant order_id was found or order was dropped before creation."
        )
        merchant_summary = (
            f"Safety action initiated: Linked or initiated auto-refund of ₹{amount_inr:,.2f} to prevent "
            f"unreconciled merchant liability and chargebacks."
        )
        customer_en = (
            f"We received your payment of ₹{amount_inr:,.2f}, but could not find an associated order. "
            f"A full refund has been initiated to your original payment method (3-5 business days)."
        )
        customer_hinglish = (
            f"Aapka ₹{amount_inr:,.2f} ka payment receive hua tha par koi matching order nahi mila. "
            f"Aapke account me refund process kar diya gaya hai (3-5 din me aayega)."
        )

    elif state == CaseState.SOFT_DECLINE:
        root_cause = (
            f"Temporary rail or bank failure (e.g. UPI PIN timeout or bank network congestion). "
            f"Error code: {case.payments[0].error_code if case.payments else 'GATEWAY_TIMEOUT'}."
        )
        merchant_summary = (
            f"Soft decline detected for Order {order_id}. Scheduled bounded auto-retry within policy "
            f"limits (attempt 1/2). Potential revenue to recover: ₹{order_amount_inr:,.2f}."
        )
        customer_en = (
            f"Your payment attempt of ₹{order_amount_inr:,.2f} for Order #{order_id} was temporarily "
            f"interrupted by the bank. We have scheduled a retry. Click here if you'd like to pay now."
        )
        customer_hinglish = (
            f"Bank network issue ke karan Order #{order_id} ka payment poora nahi ho paya. "
            f"Hum retry kar rahe hain, ya aap dobara try kar sakte hain."
        )

    elif state == CaseState.HARD_FAIL:
        root_cause = (
            f"Permanent payment decline (e.g. invalid credentials, card expired, or explicit fraud reject). "
            f"Error code: {case.payments[0].error_code if case.payments else 'CARD_DECLINED'}."
        )
        merchant_summary = (
            f"Hard decline on Order {order_id}. Marked lost to prevent invalid order fulfillment. ₹0 recovered."
        )
        customer_en = (
            f"Payment of ₹{order_amount_inr:,.2f} for Order #{order_id} was declined by your bank. "
            f"Please retry using an alternative payment method."
        )
        customer_hinglish = (
            f"Bank ne Order #{order_id} ka payment decline kar diya hai. Kripya doosra card ya UPI method use karein."
        )

    elif state == CaseState.AMBIGUOUS:
        root_cause = (
            f"Conflicting signals or payment gateway API degraded (API available: {case.signals.api_available}). "
            f"Circuit breaker triggered to safeguard merchant funds."
        )
        merchant_summary = (
            "Strict guardrail escalation: Escalate to human operations queue. System prohibited "
            "auto-confirmation while signals are unverified."
        )
        customer_en = (
            f"We are verifying the status of your payment for Order #{order_id}. Our team is reviewing it "
            f"and we will update you shortly."
        )
        customer_hinglish = (
            f"Aapke Order #{order_id} ke payment verification me thoda samay lag raha hai. "
            f"Hamari team ise check karke jaldi update karegi."
        )

    else:  # ALIGNED
        root_cause = "Payment and order statuses are perfectly aligned. No mismatch detected."
        merchant_summary = f"Order {order_id} processed normally. No action required (NO_OP)."
        customer_en = f"Your order #{order_id} has been placed successfully. Thank you!"
        customer_hinglish = f"Aapka Order #{order_id} safalta-purvak place ho gaya hai. Dhanyawad!"

    safety_note = (
        f"Action '{action.value}' was strictly selected from the allowlisted state transitions. "
        f"Ground-truth payment rail status was verified before any state modification."
    )

    return AIExplanation(
        case_id=case.case_id,
        observed_state=state,
        action_taken=action,
        amount_recovered_inr=amount_inr,
        root_cause_analysis=root_cause,
        merchant_summary=merchant_summary,
        customer_message_en=customer_en,
        customer_message_hinglish=customer_hinglish,
        action_safety_note=safety_note,
        source="deterministic_engine",
    )


def explain_case_with_llm(
    case: LabeledCase,
    record: AuditRecord,
    api_key: str | None = None,
    provider: str = "groq",  # "groq", "openai", "gemini"
) -> AIExplanation:
    """Generate LLM-driven explanation with strict safety bounds, falling back if API is unavailable."""
    key = (
        api_key
        or os.environ.get("GROQ_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
    )

    # If no key configured, immediately use high-quality deterministic generator
    if not key:
        return generate_fallback_explanation(case, record)

    prompt = f"""You are the Ghost Payment Resolver AI Explainability Agent for Razorpay merchants.
Diagnose the following payment-order mismatch case and provide structured outputs.

CASE DETAILS:
- Case ID: {case.case_id}
- Scenario: {case.scenario}
- Observed State: {record.observed_state.value}
- Action Taken: {record.action_taken.value}
- Recovered Amount: INR {record.amount_recovered_paise / 100:.2f}
- Reason: {record.reason}
- Inputs: {json.dumps(record.inputs)}

INSTRUCTIONS:
1. Explain the technical root cause (why the mismatch happened: webhook lag, client timeout, duplicate submit, bank decline, etc.).
2. Write an executive summary for merchant finance.
3. Write a polite customer notification in English.
4. Write an engaging customer notification in Hinglish (Roman Hindi + English mix commonly used in India).
5. State the policy safety confirmation.

Return JSON in this EXACT schema:
{{
  "root_cause_analysis": "string",
  "merchant_summary": "string",
  "customer_message_en": "string",
  "customer_message_hinglish": "string",
  "action_safety_note": "string"
}}
"""

    try:
        # Standard OpenAI / Groq compatible chat endpoint
        url = (
            "https://api.groq.com/openai/v1/chat/completions"
            if "groq" in provider.lower() or os.environ.get("GROQ_API_KEY")
            else "https://api.openai.com/v1/chat/completions"
        )
        model = "llama-3.3-70b-versatile" if "groq" in provider.lower() else "gpt-4o-mini"

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a specialized payment recovery and diagnostic assistant. Respond ONLY with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        with httpx.Client(timeout=8.0) as client:
            response = client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                return AIExplanation(
                    case_id=case.case_id,
                    observed_state=record.observed_state,
                    action_taken=record.action_taken,
                    amount_recovered_inr=record.amount_recovered_paise / 100,
                    root_cause_analysis=parsed.get("root_cause_analysis", ""),
                    merchant_summary=parsed.get("merchant_summary", ""),
                    customer_message_en=parsed.get("customer_message_en", ""),
                    customer_message_hinglish=parsed.get("customer_message_hinglish", ""),
                    action_safety_note=parsed.get(
                        "action_safety_note",
                        "Guaranteed bounded resolution according to policy guardrails.",
                    ),
                    source="llm",
                )
    except Exception as exc:  # noqa: BLE001
        # Fallback if LLM call fails or times out
        _ = exc
        return generate_fallback_explanation(case, record)

    return generate_fallback_explanation(case, record)
