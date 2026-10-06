"""Business rules applied when a payment finishes (shared by Stripe webhook + mock confirm)."""
from sqlalchemy import update
from sqlalchemy.orm import Session

from ..models import Payment, Product
from .notifications import notify


def mark_payment_succeeded(db: Session, payment: Payment):
    if payment.status == "succeeded":
        return  # idempotent: Stripe may deliver the webhook more than once
    order = payment.order
    payment.status = "succeeded"
    order.payment_status = "paid"
    if order.order_status == "pending":
        order.order_status = "processing"
    for item in order.items:
        if item.product_id:
            db.execute(update(Product).where(Product.id == item.product_id)
                       .values(sold_count=Product.sold_count + item.quantity))
    notify(db, order.user_id, "order_confirmation",
           f"Payment received - your order #{order.id} is confirmed. Total: {order.total:.2f}.",
           email_subject=f"Order #{order.id} confirmed")


def mark_payment_failed(db: Session, payment: Payment, reason: str = "Payment was declined"):
    if payment.status in ("succeeded", "failed"):
        return
    order = payment.order
    payment.status = "failed"
    order.payment_status = "failed"
    notify(db, order.user_id, "payment_failed",
           f"Payment for order #{order.id} failed: {reason}. You can retry from your orders page.",
           email_subject=f"Payment failed for order #{order.id}")


def restock_order(db: Session, order):
    for item in order.items:
        if item.product_id:
            db.execute(update(Product).where(Product.id == item.product_id)
                       .values(stock=Product.stock + item.quantity))
