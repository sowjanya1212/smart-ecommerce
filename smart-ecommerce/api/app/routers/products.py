from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Category, Product
from ..schemas import CategoryOut, ProductOut, ProductPage

router = APIRouter(tags=["catalogue"])


def product_out(p: Product) -> ProductOut:
    return ProductOut(
        id=p.id, name=p.name, description=p.description or "", price=p.price, stock=p.stock,
        sold_count=p.sold_count,
        category=CategoryOut.model_validate(p.category) if p.category else None,
        images=[f"/media/{img.image}" for img in p.images],
    )


@router.get("/categories", response_model=list[CategoryOut])
def categories(db: Session = Depends(get_db)):
    return db.scalars(select(Category).order_by(Category.name)).all()


@router.get("/products", response_model=ProductPage)
def list_products(
    category: str | None = Query(None, description="Category slug"),
    q: str | None = Query(None, description="Search in name/description"),
    min_price: Decimal | None = Query(None, ge=0),
    max_price: Decimal | None = Query(None, ge=0),
    in_stock: bool = False,
    sort: Literal["popularity", "price_asc", "price_desc", "newest"] = "newest",
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db),
):
    conditions = [Product.is_active.is_(True)]
    if category:
        conditions.append(Product.category_id == select(Category.id).where(Category.slug == category).scalar_subquery())
    if q:
        like = f"%{q.lower()}%"
        conditions.append(func.lower(Product.name).like(like) | func.lower(Product.description).like(like))
    if min_price is not None:
        conditions.append(Product.price >= min_price)
    if max_price is not None:
        conditions.append(Product.price <= max_price)
    if in_stock:
        conditions.append(Product.stock > 0)

    order = {
        "popularity": (Product.sold_count.desc(), Product.id),
        "price_asc": (Product.price.asc(), Product.id),
        "price_desc": (Product.price.desc(), Product.id),
        "newest": (Product.created_at.desc(), Product.id.desc()),
    }[sort]
    total = db.scalar(select(func.count()).select_from(Product).where(*conditions)) or 0
    rows = db.scalars(select(Product).where(*conditions).order_by(*order)
                      .limit(page_size).offset((page - 1) * page_size)).unique().all()
    return ProductPage(items=[product_out(p) for p in rows], total=total, page=page, page_size=page_size)


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if not p or not p.is_active:
        raise HTTPException(404, "Product not found")
    return product_out(p)
