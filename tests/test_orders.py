import os

# Use an in-memory SQLite DB for tests; must be set before the app is imported
os.environ["DATABASE_URL"] = "sqlite://"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import database, restaurant_client  # noqa: E402

database.engine = database.create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
database.SessionLocal.configure(bind=database.engine)

from app.main import app  # noqa: E402

VALIDATED = {
    "valid": True,
    "restaurantId": "r1",
    "restaurantName": "Spice Garden",
    "items": [
        {"menuItemId": "m1", "name": "Paneer Tikka", "unitPrice": 250, "quantity": 2, "lineTotal": 500}
    ],
    "subtotal": 500,
}

ORDER = {
    "customerId": "cust-1",
    "restaurantId": "r1",
    "deliveryAddress": "221B Baker Street",
    "items": [{"menuItemId": "m1", "quantity": 2}],
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(restaurant_client, "validate_order", lambda rid, items: VALIDATED)
    monkeypatch.setattr(restaurant_client, "is_reachable", lambda: True)
    database.Base.metadata.drop_all(bind=database.engine)
    with TestClient(app) as c:
        yield c


def test_create_order_computes_totals(client):
    resp = client.post("/orders", json=ORDER)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "CONFIRMED"
    assert body["subtotal"] == 500
    assert body["tax"] == 25
    assert body["total"] == 565  # 500 + 5% tax + 40 delivery


def test_order_lifecycle_and_invalid_transition(client):
    order_id = client.post("/orders", json=ORDER).json()["id"]
    assert client.patch(f"/orders/{order_id}/status", json={"status": "PREPARING"}).status_code == 200
    # Cannot cancel once preparing
    assert client.post(f"/orders/{order_id}/cancel").status_code == 409


def test_rejected_by_restaurant_service(client, monkeypatch):
    def reject(rid, items):
        raise restaurant_client.OrderRejected(422, {"valid": False, "error": "Order validation failed"})

    monkeypatch.setattr(restaurant_client, "validate_order", reject)
    assert client.post("/orders", json=ORDER).status_code == 422


def test_restaurant_service_down_returns_503(client, monkeypatch):
    def down(rid, items):
        raise restaurant_client.RestaurantServiceUnavailable("connection refused")

    monkeypatch.setattr(restaurant_client, "validate_order", down)
    assert client.post("/orders", json=ORDER).status_code == 503


def test_list_and_filter_orders(client):
    client.post("/orders", json=ORDER)
    client.post("/orders", json={**ORDER, "customerId": "cust-2"})
    assert len(client.get("/orders").json()) == 2
    assert len(client.get("/orders", params={"customerId": "cust-2"}).json()) == 1
    assert client.get("/orders/999").status_code == 404
