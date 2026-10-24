import socket
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config, restaurant_client
from .database import db_is_up, get_db, init_db
from .models import TRANSITIONS, Order, OrderItem, OrderStatus
from .schemas import CreateOrderRequest, OrderResponse, UpdateStatusRequest


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="FoodExpress Order Service",
    description="Places and tracks food orders. Validates items with the Restaurant Service.",
    version="1.0.0",
    lifespan=lifespan,
)


def _get_order(db: Session, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.get("/health")
def health(response: Response):
    db_up = db_is_up()
    if not db_up:
        response.status_code = 503
    return {
        "service": "order-service",
        "status": "UP" if db_up else "DOWN",
        "database": "connected" if db_up else "disconnected",
        "restaurantService": "reachable" if restaurant_client.is_reachable() else "unreachable",
        "pod": socket.gethostname(),
    }


@app.get("/ready")
def ready(response: Response):
    """Lightweight Kubernetes probe: checks only our own DB, never downstream services."""
    db_up = db_is_up()
    if not db_up:
        response.status_code = 503
    return {"status": "READY" if db_up else "NOT_READY"}


# ---------- Commands ----------

@app.post("/orders", response_model=OrderResponse, status_code=201)
def create_order(req: CreateOrderRequest, db: Session = Depends(get_db)):
    try:
        validated = restaurant_client.validate_order(
            req.restaurantId, [i.model_dump() for i in req.items]
        )
    except restaurant_client.OrderRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.body)
    except restaurant_client.RestaurantServiceUnavailable as exc:
        raise HTTPException(
            status_code=503, detail=f"Restaurant service unavailable, please retry: {exc}"
        )

    subtotal = validated["subtotal"]
    tax = round(subtotal * config.TAX_RATE, 2)
    order = Order(
        customer_id=req.customerId,
        restaurant_id=validated["restaurantId"],
        restaurant_name=validated["restaurantName"],
        delivery_address=req.deliveryAddress,
        status=OrderStatus.CONFIRMED,
        subtotal=subtotal,
        tax=tax,
        delivery_fee=config.DELIVERY_FEE,
        total=round(subtotal + tax + config.DELIVERY_FEE, 2),
        items=[
            OrderItem(
                menu_item_id=line["menuItemId"],
                name=line["name"],
                unit_price=line["unitPrice"],
                quantity=line["quantity"],
                line_total=line["lineTotal"],
            )
            for line in validated["items"]
        ],
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@app.patch("/orders/{order_id}/status", response_model=OrderResponse)
def update_status(order_id: int, req: UpdateStatusRequest, db: Session = Depends(get_db)):
    order = _get_order(db, order_id)
    if req.status not in TRANSITIONS[order.status]:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot move order from {order.status.value} to {req.status.value}",
        )
    order.status = req.status
    db.commit()
    db.refresh(order)
    return order


@app.post("/orders/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(order_id: int, db: Session = Depends(get_db)):
    return update_status(order_id, UpdateStatusRequest(status=OrderStatus.CANCELLED), db)


# ---------- Queries ----------

@app.get("/orders", response_model=List[OrderResponse])
def list_orders(
    customerId: Optional[str] = None,
    restaurantId: Optional[str] = None,
    status: Optional[OrderStatus] = None,
    db: Session = Depends(get_db),
):
    query = select(Order).order_by(Order.id.desc())
    if customerId:
        query = query.where(Order.customer_id == customerId)
    if restaurantId:
        query = query.where(Order.restaurant_id == restaurantId)
    if status:
        query = query.where(Order.status == status)
    return db.scalars(query).all()


@app.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, db: Session = Depends(get_db)):
    return _get_order(db, order_id)
