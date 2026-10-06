from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import Order, Payment, User
from ..schemas import MockConfirmIn, OrderOut
from ..services import stripe_service
from ..services.payments import mark_payment_failed, mark_payment_succeeded

router = APIRouter(prefix="/payments", tags=["payments"])


def _by_txn(db: Session, txn_id: str) -> Payment | None:
    return db.scalar(select(Payment).where(Payment.transaction_id == txn_id))


@router.get("/config")
def payment_config():
    return {"publishable_key": settings.STRIPE_PUBLISHABLE_KEY or None, "mock": not settings.stripe_enabled,
            "currency": settings.CURRENCY}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe -> us. Configure in the dashboard: POST /api/payments/webhook,
    events payment_intent.succeeded + payment_intent.payment_failed."""
    if not settings.stripe_enabled or not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(501, "Stripe webhook is not configured")
    payload = await request.body()
    try:
        event = stripe_service.construct_event(payload, request.headers.get("stripe-signature", ""))
    except Exception:
        raise HTTPException(400, "Invalid signature")

    obj = event["data"]["object"]
    payment = _by_txn(db, obj["id"])
    if payment:
        if event["type"] == "payment_intent.succeeded":
            mark_payment_succeeded(db, payment)
        elif event["type"] == "payment_intent.payment_failed":
            reason = (obj.get("last_payment_error") or {}).get("message", "Payment was declined")
            mark_payment_failed(db, payment, reason)
    return {"received": True}


@router.post("/{order_id}/mock-confirm", response_model=OrderOut)
def mock_confirm(order_id: int, body: MockConfirmIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """DEMO ONLY: simulate the gateway result when no Stripe keys are configured."""
    if settings.stripe_enabled:
        raise HTTPException(403, "Mock payments are disabled when Stripe is configured")
    order = db.get(Order, order_id)
    if not order or order.user_id != user.id:
        raise HTTPException(404, "Order not found")
    payment = next((p for p in order.payments if p.status == "pending"), None)
    if not payment:
        raise HTTPException(400, "No pending payment for this order")
    if body.success:
        mark_payment_succeeded(db, payment)
    else:
        mark_payment_failed(db, payment, "Your card was declined (simulated)")
    db.refresh(order)
    return order
