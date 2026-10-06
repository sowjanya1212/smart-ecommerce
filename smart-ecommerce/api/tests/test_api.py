from app.security import hash_password, verify_password

from .conftest import product_id


def test_password_hash_is_django_compatible():
    h = hash_password("s3cret-pass")
    algo, iterations, salt, digest = h.split("$")
    assert algo == "pbkdf2_sha256" and int(iterations) > 0 and len(salt) == 22
    assert verify_password("s3cret-pass", h)
    assert not verify_password("wrong", h)
    assert not verify_password("x", "!unusable")


def test_register_login_me_refresh(client):
    r = client.post("/api/auth/register", json={"name": "Zed", "email": "zed@test.com", "password": "Passw0rd!"})
    assert r.status_code == 201
    assert client.post("/api/auth/register", json={"name": "Zed", "email": "ZED@test.com", "password": "Passw0rd!"}).status_code == 409
    assert client.post("/api/auth/login", json={"email": "zed@test.com", "password": "nope-nope"}).status_code == 401
    tokens = client.post("/api/auth/login", json={"email": "zed@test.com", "password": "Passw0rd!"}).json()
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200 and me.json()["role"] == "customer"
    assert client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 200
    # an access token must not work as a refresh token
    assert client.post("/api/auth/refresh", json={"refresh_token": tokens["access_token"]}).status_code == 401


def test_product_filters_and_sorting(client):
    assert {p["name"] for p in client.get("/api/products").json()["items"]} == {"Phone", "Cable", "Novel"}
    assert [p["name"] for p in client.get("/api/products", params={"category": "books"}).json()["items"]] == ["Novel"]
    assert [p["name"] for p in client.get("/api/products", params={"min_price": 100}).json()["items"]] == ["Phone"]
    assert client.get("/api/products", params={"sort": "popularity"}).json()["items"][0]["name"] == "Cable"
    assert client.get("/api/products", params={"sort": "price_desc"}).json()["items"][0]["name"] == "Phone"
    assert client.get("/api/products", params={"in_stock": True}).json()["total"] == 2


def test_cart_flow_and_stock_limit(client, make_user):
    h = make_user()
    phone = product_id(client, "Phone")
    assert client.get("/api/cart").status_code == 401
    cart = client.post("/api/cart", json={"product_id": phone, "quantity": 2}, headers=h).json()
    assert cart["count"] == 2 and cart["total"] == 1000
    assert client.post("/api/cart", json={"product_id": phone, "quantity": 4}, headers=h).status_code == 400
    assert client.patch(f"/api/cart/{phone}", json={"quantity": 1}, headers=h).json()["total"] == 500
    assert client.delete(f"/api/cart/{phone}", headers=h).json()["count"] == 0


def test_checkout_and_successful_payment(client, make_user):
    h = make_user()
    cable = product_id(client, "Cable")
    before = client.get(f"/api/products/{cable}").json()["stock"]
    client.post("/api/cart", json={"product_id": cable, "quantity": 2}, headers=h)
    co = client.post("/api/orders/checkout", json={"shipping_address": "1 Main Street"}, headers=h)
    assert co.status_code == 201, co.text
    body = co.json()
    assert body["mock"] is True and body["order"]["total"] == 20 and body["order"]["payment_status"] == "pending"
    assert client.get("/api/cart", headers=h).json()["count"] == 0
    assert client.get(f"/api/products/{cable}").json()["stock"] == before - 2

    oid = body["order"]["id"]
    paid = client.post(f"/api/payments/{oid}/mock-confirm", json={"success": True}, headers=h).json()
    assert paid["payment_status"] == "paid" and paid["order_status"] == "processing"
    assert paid["payments"][0]["status"] == "succeeded"
    types = [n["type"] for n in client.get("/api/notifications", headers=h).json()]
    assert "order_confirmation" in types
    assert client.get("/api/orders", headers=h).json()[0]["id"] == oid


def test_failed_payment_then_retry_and_cancel_restocks(client, make_user):
    h = make_user()
    cable = product_id(client, "Cable")
    before = client.get(f"/api/products/{cable}").json()["stock"]
    client.post("/api/cart", json={"product_id": cable, "quantity": 3}, headers=h)
    oid = client.post("/api/orders/checkout", json={"shipping_address": "2 Side Road"}, headers=h).json()["order"]["id"]
    failed = client.post(f"/api/payments/{oid}/mock-confirm", json={"success": False}, headers=h).json()
    assert failed["payment_status"] == "failed"
    assert "payment_failed" in [n["type"] for n in client.get("/api/notifications", headers=h).json()]

    retry = client.post(f"/api/orders/{oid}/pay", headers=h).json()
    assert retry["order"]["payment_status"] == "pending"
    cancelled = client.post(f"/api/orders/{oid}/cancel", headers=h).json()
    assert cancelled["order_status"] == "cancelled"
    assert client.get(f"/api/products/{cable}").json()["stock"] == before


def test_orders_are_private(client, make_user):
    a, b = make_user(), make_user()
    cable = product_id(client, "Cable")
    client.post("/api/cart", json={"product_id": cable, "quantity": 1}, headers=a)
    oid = client.post("/api/orders/checkout", json={"shipping_address": "3 Private Ave"}, headers=a).json()["order"]["id"]
    assert client.get(f"/api/orders/{oid}", headers=b).status_code == 404


def test_checkout_empty_cart(client, make_user):
    assert client.post("/api/orders/checkout", json={"shipping_address": "4 Empty Lane"},
                       headers=make_user()).status_code == 400


def test_role_based_access(client, make_user, login):
    customer, staff, admin = make_user(), login("staff@test.com"), login("admin@test.com")
    assert client.get("/api/admin/summary").status_code == 401
    assert client.get("/api/admin/summary", headers=customer).status_code == 403
    assert client.get("/api/admin/summary", headers=staff).status_code == 200
    assert client.get("/api/admin/users", headers=staff).status_code == 403
    assert client.get("/api/admin/users", headers=admin).status_code == 200


def test_websocket_receives_realtime_events(client, make_user):
    h = make_user()
    token = h["Authorization"].split()[1]
    cable = product_id(client, "Cable")
    with client.websocket_connect(f"/ws/notifications?token={token}") as ws:
        assert ws.receive_json()["event"] == "connected"
        client.post("/api/cart", json={"product_id": cable, "quantity": 1}, headers=h)
        assert ws.receive_json() == {"event": "cart_updated", "count": 1, "total": 10.0}


def test_websocket_rejects_bad_token(client):
    import pytest
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/notifications?token=garbage"):
            pass


def test_internal_notify_requires_secret(client):
    body = {"user_id": 1, "notification": {"id": 1, "type": "x", "message": "m"}}
    assert client.post("/api/internal/notify", json=body).status_code == 403
    assert client.post("/api/internal/notify", json=body, headers={"X-Internal-Secret": "test-secret"}).status_code == 200
