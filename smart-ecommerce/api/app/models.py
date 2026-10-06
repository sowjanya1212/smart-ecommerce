"""
SQLAlchemy mapping of the tables created by Django migrations (admin_panel/shop).
The API never creates/alters tables in production - Django owns the schema.
(Tests call Base.metadata.create_all on a throw-away SQLite file.)
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

PK = BigInteger().with_variant(Integer, "sqlite")  # SQLite needs INTEGER for autoincrement


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    password: Mapped[str] = mapped_column(String(128))
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    role: Mapped[str] = mapped_column(String(20), default="customer")
    auth_provider: Mapped[str] = mapped_column(String(30), default="local")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    date_joined: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    category_id: Mapped[int | None] = mapped_column(PK, ForeignKey("categories.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    stock: Mapped[int] = mapped_column(Integer, default=0)
    sold_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    category: Mapped[Optional["Category"]] = relationship(lazy="joined")
    images: Mapped[list["ProductImage"]] = relationship(
        order_by="ProductImage.position, ProductImage.id", lazy="selectin")


class ProductImage(Base):
    __tablename__ = "product_images"
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    product_id: Mapped[int] = mapped_column(PK, ForeignKey("products.id"))
    image: Mapped[str] = mapped_column(String(100))
    position: Mapped[int] = mapped_column(Integer, default=0)


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_cart_user_product"),)
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    user_id: Mapped[int] = mapped_column(PK, ForeignKey("users.id"))
    product_id: Mapped[int] = mapped_column(PK, ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    product: Mapped["Product"] = relationship(lazy="joined")


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    user_id: Mapped[int] = mapped_column(PK, ForeignKey("users.id"))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    payment_status: Mapped[str] = mapped_column(String(20), default="pending")
    order_status: Mapped[str] = mapped_column(String(20), default="pending")
    shipping_address: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    items: Mapped[list["OrderItem"]] = relationship(lazy="selectin", order_by="OrderItem.id")
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="order", lazy="selectin", order_by="Payment.id.desc()")


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    order_id: Mapped[int] = mapped_column(PK, ForeignKey("orders.id"))
    product_id: Mapped[int | None] = mapped_column(PK, ForeignKey("products.id"), nullable=True)
    product_name: Mapped[str] = mapped_column(String(200))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    quantity: Mapped[int] = mapped_column(Integer)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    order_id: Mapped[int] = mapped_column(PK, ForeignKey("orders.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    payment_method: Mapped[str] = mapped_column(String(30), default="card")
    transaction_id: Mapped[str] = mapped_column(String(255), default="", index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    order: Mapped["Order"] = relationship(back_populates="payments")


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    user_id: Mapped[int] = mapped_column(PK, ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
