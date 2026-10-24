from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field

from .models import OrderStatus


class OrderItemRequest(BaseModel):
    menuItemId: str
    quantity: int = Field(gt=0)


class CreateOrderRequest(BaseModel):
    customerId: str = Field(min_length=1)
    restaurantId: str = Field(min_length=1)
    deliveryAddress: str = Field(min_length=1)
    items: List[OrderItemRequest] = Field(min_length=1)


class UpdateStatusRequest(BaseModel):
    status: OrderStatus


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    menu_item_id: str
    name: str
    unit_price: float
    quantity: int
    line_total: float


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: str
    restaurant_id: str
    restaurant_name: str
    delivery_address: str
    status: OrderStatus
    items: List[OrderItemResponse]
    subtotal: float
    tax: float
    delivery_fee: float
    total: float
    created_at: datetime
    updated_at: datetime
