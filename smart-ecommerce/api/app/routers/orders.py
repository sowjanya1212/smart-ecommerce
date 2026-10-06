from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import CartItem, Order, OrderItem, Payment, Product, User
from ..realtime import manager
from ..schemas import CheckoutIn, CheckoutOut, OrderOut
from ..services.notifications import notify
from ..services.payments import restock_order
from ..services.stripe_service import create_payment_intent

router = APIRouter(prefix="/orders", tags=["orders"])


def _checkout_out(order: Order, client_secret: str | None) -> CheckoutOut:
    return CheckoutOut(order=OrderOut.model_validate(order), client_secret=client_secret,
                       publishable_key=settings.STRIPE_PUBLISHABLE_KEY or None,
                       mock=not settings.stripe_enabled)


def _start_payment(db: Session, order: Order, user: User) -> str | None:
    try:
        txn_id, secret = create_payment_intent(order.id, order.total, user.email)
    except Exception as exc:  # Stripe/network failure -> roll everything back
        db.rollback()
        raise HTTPException(502, f"Payment provider error: {exc}")
    db.add(Payment(order_id=order.id, amount=order.total, payment_method="card",
                   transaction_id=txn_id, status="pending"))
    return secret


@router.post("/checkout", response_model=CheckoutOut, status_code=201)
def checkout(body: CheckoutIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Turn the cart into an order, reserve stock and create a Stripe PaymentIntent."""
    cart = db.scalars(select(CartItem).where(CartItem.user_id == user.id)).unique().all()
    if not cart:
        raise HTTPException(400, "Your cart is empty")

    total = Decimal("0")
    order = Order(user_id=user.id, total=Decimal("0"), payment_status="pending", order_status="pending",
                  shipping_address=body.shipping_address.strip())
    db.add(order)
    db.flush()  # get order.id

    for line in cart:
        p = line.product
        if not p.is_active:
            db.rollback()
            raise HTTPException(400, f"'{p.name}' is no longer available")
        # Atomic stock reservation: fails (0 rows) if someone else bought the last units meanwhile
        res = db.execute(update(Product).where(Product.id == p.id, Product.stock >= line.quantity)
                         .values(stock=Product.stock - line.quantity))
        if res.rowcount != 1:
            db.rollback()
            raise HTTPException(409, f"Not enough stock for '{p.name}'")
        db.add(OrderItem(order_id=order.id, product_id=p.id, product_name=p.name,
                         unit_price=p.price, quantity=line.quantity))
        total += p.price * line.quantity

    order.total = total.quantize(Decimal("0.01"))
    secret = _start_payment(db, order, user)
    db.execute(delete(CartItem).where(CartItem.user_id == user.id))
    db.commit()
    db.refresh(order)
    manager.push(user.id, {"event": "cart_updated", "count": 0, "total": 0})
    return _checkout_out(order, secret)


@router.get("", response_model=list[OrderOut])
def my_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Order).where(Order.user_id == user.id).order_by(Order.id.desc())).unique().all()


def _own_order(db: Session, user: User, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if not order or (order.user_id != user.id and user.role not in ("admin", "staff")):
        raise HTTPException(404, "Order not found")
    return order


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _own_order(db, user, order_id)


@router.post("/{order_id}/pay", response_model=CheckoutOut)
def retry_payment(order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a fresh PaymentIntent for an unpaid order (e.g. after a failed payment)."""
    order = _own_order(db, user, order_id)
    if order.user_id != user.id:
        raise HTTPException(403, "Not your order")
    if order.payment_status not in ("pending", "failed") or order.order_status == "cancelled":
        raise HTTPException(400, "This order cannot be paid")
    secret = _start_payment(db, order, user)
    order.payment_status = "pending"
    db.commit()
    db.refresh(order)
    return _checkout_out(order, secret)


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = _own_order(db, user, order_id)
    if order.user_id != user.id:
        raise HTTPException(403, "Not your order")
    if order.payment_status == "paid" or order.order_status != "pending":
        raise HTTPException(400, "Only unpaid, pending orders can be cancelled")
    order.order_status = "cancelled"
    for p in order.payments:
        if p.status == "pending":
            p.status = "failed"
    restock_order(db, order)
    notify(db, user.id, "order_status", f"Your order #{order.id} was cancelled.",
           email_subject=f"Order #{order.id} cancelled")
    db.refresh(order)
    return order
