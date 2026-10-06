"""Tiny staff-only API that demonstrates role-based access control (full admin UI lives in Django)."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_roles
from ..models import Order, Product, User
from ..realtime import manager

router = APIRouter(prefix="/admin", tags=["staff"])


@router.get("/summary")
def summary(_: User = Depends(require_roles("admin", "staff")), db: Session = Depends(get_db)):
    revenue = db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(Order.payment_status == "paid"))
    return {
        "orders": db.scalar(select(func.count()).select_from(Order)),
        "paid_revenue": float(revenue or 0),
        "customers": db.scalar(select(func.count()).select_from(User).where(User.role == "customer")),
        "low_stock": db.scalar(select(func.count()).select_from(Product).where(Product.stock <= 5, Product.is_active.is_(True))),
        "online_users": manager.online_users(),
    }


@router.get("/users", response_model=list[dict])
def users(_: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    """Admin-only (staff get 403)."""
    rows = db.scalars(select(User).order_by(User.id)).all()
    return [{"id": u.id, "email": u.email, "name": u.name, "role": u.role, "is_active": u.is_active} for u in rows]
