"""Synchronous REST client for the Restaurant Service.

The Order Service never trusts prices sent by the client; it asks the Restaurant
Service (the owner of menu data) to validate items and return authoritative prices.
"""
import time

import httpx

from . import config


class RestaurantServiceUnavailable(Exception):
    pass


class OrderRejected(Exception):
    def __init__(self, status_code: int, body: dict):
        super().__init__(body.get("error", "Order rejected by restaurant service"))
        self.status_code = status_code
        self.body = body


def validate_order(restaurant_id: str, items: list) -> dict:
    url = f"{config.RESTAURANT_SERVICE_URL}/restaurants/{restaurant_id}/validate-order"
    payload = {"items": items}
    last_error = None

    # Retry only on network failures / 5xx; business rejections (4xx) are returned immediately
    for attempt in range(config.RESTAURANT_MAX_RETRIES + 1):
        try:
            resp = httpx.post(url, json=payload, timeout=config.RESTAURANT_TIMEOUT_SECONDS)
        except httpx.HTTPError as exc:
            last_error = exc
        else:
            if resp.status_code == 200:
                return resp.json()
            if 400 <= resp.status_code < 500:
                raise OrderRejected(resp.status_code, resp.json())
            last_error = Exception(f"restaurant-service returned {resp.status_code}")
        time.sleep(0.5 * (attempt + 1))

    raise RestaurantServiceUnavailable(str(last_error))


def is_reachable() -> bool:
    try:
        resp = httpx.get(f"{config.RESTAURANT_SERVICE_URL}/health", timeout=1)
        return resp.status_code == 200
    except httpx.HTTPError:
        return False
