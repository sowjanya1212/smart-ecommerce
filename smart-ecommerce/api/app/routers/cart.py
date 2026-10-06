from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import CartItem, Product, User
from ..realtime import manager
from ..schemas import CartAddIn, CartLineOut, CartOut, CartUpdateIn
from .products import product_out

router = APIRouter(prefix="/cart", tags=["cart"])


def build_cart(db: Session, user: User) -> CartOut:
    rows = db.scalars(select(CartItem).where(CartItem.user_id == user.id).order_by(CartItem.id)).unique().all()
    lines = [CartLineOut(product=product_out(r.product), quantity=r.quantity,
                         line_total=r.product.price * r.quantity) for r in rows]
    total = sum((l.line_total for l in lines), Decimal("0"))
    return CartOut(items=lines, count=sum(l.quantity for l in lines), total=total)


def _broadcast(user: User, cart: CartOut):
    """Real-time cart sync across the user's open tabs/devices."""
    manager.push(user.id, {"event": "cart_updated", "count": cart.count, "total": float(cart.total)})


def _active_product(db: Session, product_id: int) -> Product:
    p = db.get(Product, product_id)
    if not p or not p.is_active:
        raise HTTPException(404, "Product not found")
    return p


@router.get("", response_model=CartOut)
def get_cart(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return build_cart(db, user)


@router.post("", response_model=CartOut)
def add_to_cart(body: CartAddIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    product = _active_product(db, body.product_id)
    item = db.scalar(select(CartItem).where(CartItem.user_id == user.id, CartItem.product_id == product.id))
    new_qty = (item.quantity if item else 0) + body.quantity
    if new_qty > product.stock:
        raise HTTPException(400, f"Only {product.stock} unit(s) of '{product.name}' in stock")
    if item:
        item.quantity = new_qty
    else:
        db.add(CartItem(user_id=user.id, product_id=product.id, quantity=new_qty))
    db.commit()
    cart = build_cart(db, user)
    _broadcast(user, cart)
    return cart


@router.patch("/{product_id}", response_model=CartOut)
def set_quantity(product_id: int, body: CartUpdateIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    item = db.scalar(select(CartItem).where(CartItem.user_id == user.id, CartItem.product_id == product_id))
    if not item:
        raise HTTPException(404, "Item not in cart")
    if body.quantity > item.product.stock:
        raise HTTPException(400, f"Only {item.product.stock} unit(s) in stock")
    item.quantity = body.quantity
    db.commit()
    cart = build_cart(db, user)
    _broadcast(user, cart)
    return cart


@router.delete("/{product_id}", response_model=CartOut)
def remove_from_cart(product_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(delete(CartItem).where(CartItem.user_id == user.id, CartItem.product_id == product_id))
    db.commit()
    cart = build_cart(db, user)
    _broadcast(user, cart)
    return cart


@router.delete("", response_model=CartOut)
def clear_cart(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(delete(CartItem).where(CartItem.user_id == user.id))
    db.commit()
    cart = build_cart(db, user)
    _broadcast(user, cart)
    return cart
