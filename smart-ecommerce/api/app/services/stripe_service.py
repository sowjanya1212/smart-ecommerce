"""Stripe wrapper with a MOCK mode (no STRIPE_SECRET_KEY) so the whole flow is demo-able offline."""
import uuid
from decimal import Decimal

from ..config import settings


def create_payment_intent(order_id: int, amount: Decimal, customer_email: str):
    """Returns (transaction_id, client_secret|None)."""
    if not settings.stripe_enabled:
        return f"mock_pi_{uuid.uuid4().hex[:18]}", None
    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    intent = stripe.PaymentIntent.create(
        amount=int((amount * 100).to_integral_value()),
        currency=settings.CURRENCY,
        receipt_email=customer_email,
        metadata={"order_id": str(order_id)},
        automatic_payment_methods={"enabled": True},
    )
    return intent["id"], intent["client_secret"]


def construct_event(payload: bytes, signature: str):
    import stripe

    return stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
