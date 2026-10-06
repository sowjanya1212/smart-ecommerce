import os
import tempfile

# Must be set BEFORE the app is imported (settings are read at import time).
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.sqlite3"
os.environ["MEDIA_ROOT"] = f"{_tmp}/media"
os.environ["PASSWORD_ITERATIONS"] = "1000"
os.environ["STRIPE_SECRET_KEY"] = ""  # force MOCK payments
os.environ["INTERNAL_SECRET"] = "test-secret"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Category, Product, User  # noqa: E402
from app.security import hash_password  # noqa: E402


@pytest.fixture(scope="session")
def client():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        electronics, books = Category(name="Electronics", slug="electronics"), Category(name="Books", slug="books")
        db.add_all([electronics, books])
        db.flush()
        db.add_all([
            Product(name="Phone", description="Smart phone", price=500, stock=5, sold_count=10, category_id=electronics.id),
            Product(name="Cable", description="USB cable", price=10, stock=100, sold_count=50, category_id=electronics.id),
            Product(name="Novel", description="A story", price=15, stock=0, sold_count=5, category_id=books.id),
            Product(name="Hidden", description="inactive", price=1, stock=9, is_active=False),
        ])
        for email, role in (("staff@test.com", "staff"), ("admin@test.com", "admin")):
            db.add(User(name=role.title(), email=email, password=hash_password("Passw0rd!"), role=role,
                        is_staff=True, is_superuser=role == "admin", is_active=True))
        db.commit()
    with TestClient(app) as c:
        yield c


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def make_user(client):
    counter = {"n": 0}

    def _make():
        counter["n"] += 1
        r = client.post("/api/auth/register", json={"name": "Test", "email": f"user{counter['n']}@test.com",
                                                    "password": "Passw0rd!"})
        assert r.status_code == 201, r.text
        return _headers(r.json()["access_token"])
    return _make


@pytest.fixture()
def login(client):
    def _login(email):
        r = client.post("/api/auth/login", json={"email": email, "password": "Passw0rd!"})
        assert r.status_code == 200, r.text
        return _headers(r.json()["access_token"])
    return _login


def product_id(client, name):
    items = client.get("/api/products", params={"q": name}).json()["items"]
    return items[0]["id"]
