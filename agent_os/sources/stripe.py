"""sources/stripe.py — Stripe event normalizer.

Converts Stripe webhook payloads into canonical Signal format.
Monitors business-critical events: payments, subscriptions, refunds, revenue.
"""

from __future__ import annotations

from typing import Any


def normalize(event_type: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Convert Stripe event to canonical Signal format.

    Returns: {metric_name, value, timestamp, metadata} or None if unsupported.
    """

    data = payload.get("data", {})
    obj = data.get("object", {})
    timestamp = obj.get("created") or payload.get("created")
    # Convert Unix timestamp to ISO format if needed
    if isinstance(timestamp, (int, float)):
        from datetime import datetime, timezone
        timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()

    # ── payment_intent ─────────────────────────────────────────────
    if event_type == "payment_intent.succeeded":
        amount_cents = obj.get("amount", 0)
        return {
            "metric_name": "stripe.payment.success",
            "value": float(amount_cents),
            "timestamp": timestamp,
            "metadata": {
                "amount_cents": amount_cents,
                "amount_dollars": amount_cents / 100.0,
                "currency": obj.get("currency"),
                "customer": obj.get("customer"),
                "payment_method": obj.get("payment_method"),
                "description": obj.get("description"),
                "payment_intent_id": obj.get("id"),
            },
        }

    elif event_type == "payment_intent.payment_failed":
        amount_cents = obj.get("amount", 0)
        last_error = obj.get("last_payment_error", {})
        return {
            "metric_name": "stripe.payment.failure",
            "value": 1.0,
            "timestamp": timestamp,
            "metadata": {
                "amount_cents": amount_cents,
                "amount_dollars": amount_cents / 100.0,
                "error_code": last_error.get("code"),
                "error_message": last_error.get("message"),
                "customer": obj.get("customer"),
                "payment_intent_id": obj.get("id"),
            },
        }

    # ── subscription ───────────────────────────────────────────────
    elif event_type == "customer.subscription.created":
        plan = obj.get("plan", {})
        return {
            "metric_name": "stripe.subscription.created",
            "value": 1.0,
            "timestamp": timestamp,
            "metadata": {
                "subscription_id": obj.get("id"),
                "customer": obj.get("customer"),
                "plan_id": plan.get("id"),
                "plan_amount_cents": plan.get("amount"),
                "plan_currency": plan.get("currency"),
                "plan_interval": plan.get("interval"),
                "status": obj.get("status"),
                "current_period_start": obj.get("current_period_start"),
                "current_period_end": obj.get("current_period_end"),
            },
        }

    elif event_type == "customer.subscription.deleted":
        return {
            "metric_name": "stripe.subscription.churn",
            "value": 1.0,
            "timestamp": timestamp,
            "metadata": {
                "subscription_id": obj.get("id"),
                "customer": obj.get("customer"),
                "cancel_at_period_end": obj.get("cancel_at_period_end"),
                "cancellation_details": obj.get("cancellation_details"),
                "status": obj.get("status"),
            },
        }

    elif event_type == "customer.subscription.updated":
        previous = data.get("previous_attributes", {})
        # Detect plan changes specifically
        if "plan" in previous:
            old_plan = previous.get("plan", {})
            new_plan = obj.get("plan", {})
            return {
                "metric_name": "stripe.subscription.plan_change",
                "value": 1.0,
                "timestamp": timestamp,
                "metadata": {
                    "subscription_id": obj.get("id"),
                    "customer": obj.get("customer"),
                    "old_plan": old_plan.get("id"),
                    "new_plan": new_plan.get("id"),
                    "upgrade": (new_plan.get("amount", 0) > old_plan.get("amount", 0)),
                },
            }

    # ── refund ─────────────────────────────────────────────────────
    elif event_type == "charge.refunded":
        charge = obj.get("charge")
        amount_cents = obj.get("amount", 0)
        return {
            "metric_name": "stripe.refund.amount",
            "value": float(amount_cents),
            "timestamp": timestamp,
            "metadata": {
                "refund_id": obj.get("id"),
                "amount_cents": amount_cents,
                "amount_dollars": amount_cents / 100.0,
                "reason": obj.get("reason"),
                "customer": obj.get("customer") or charge.get("customer") if isinstance(charge, dict) else None,
                "payment_intent": obj.get("payment_intent"),
                "status": obj.get("status"),
            },
        }

    # ── invoice ────────────────────────────────────────────────────
    elif event_type == "invoice.paid":
        amount_cents = obj.get("amount_paid", 0)
        return {
            "metric_name": "stripe.revenue.recurring",
            "value": float(amount_cents),
            "timestamp": timestamp,
            "metadata": {
                "invoice_id": obj.get("id"),
                "customer": obj.get("customer"),
                "amount_cents": amount_cents,
                "amount_dollars": amount_cents / 100.0,
                "subscription": obj.get("subscription"),
                "currency": obj.get("currency"),
            },
        }

    # Unsupported event type
    return None
