from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, PlainSerializer

# Decimals are returned as JSON numbers (friendlier for the JS frontend)
Money = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- auth
class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class Auth0In(BaseModel):
    id_token: str
    nonce: str | None = None


class UserOut(ORM):
    id: int
    name: str
    email: str
    role: str
    auth_provider: str
    date_joined: datetime


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    user: UserOut | None = None


# ---- catalogue
class CategoryOut(ORM):
    id: int
    name: str
    slug: str


class ProductOut(BaseModel):
    id: int
    name: str
    description: str
    price: Money
    stock: int
    sold_count: int
    category: CategoryOut | None
    images: list[str]


class ProductPage(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    page_size: int


# ---- cart
class CartAddIn(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1, le=100)


class CartUpdateIn(BaseModel):
    quantity: int = Field(ge=1, le=100)


class CartLineOut(BaseModel):
    product: ProductOut
    quantity: int
    line_total: Money


class CartOut(BaseModel):
    items: list[CartLineOut]
    count: int
    total: Money


# ---- orders / payments
class OrderItemOut(ORM):
    product_id: int | None
    product_name: str
    unit_price: Money
    quantity: int


class PaymentOut(ORM):
    id: int
    amount: Money
    payment_method: str
    transaction_id: str
    status: str
    created_at: datetime


class OrderOut(ORM):
    id: int
    total: Money
    payment_status: str
    order_status: str
    shipping_address: str
    created_at: datetime
    items: list[OrderItemOut]
    payments: list[PaymentOut]


class CheckoutIn(BaseModel):
    shipping_address: str = Field(min_length=5, max_length=500)


class CheckoutOut(BaseModel):
    order: OrderOut
    client_secret: str | None
    publishable_key: str | None
    mock: bool


class MockConfirmIn(BaseModel):
    success: bool = True


class NotificationOut(ORM):
    id: int
    type: str
    message: str
    is_read: bool
    created_at: datetime
