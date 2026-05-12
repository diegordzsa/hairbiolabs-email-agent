"""Shopify Admin API client using client credentials grant flow."""
import logging
from typing import Any

import requests

from src import config

logger = logging.getLogger(__name__)

API_VERSION = "2025-01"

_cached_token: str | None = None


def _get_access_token() -> str:
    global _cached_token
    if _cached_token:
        return _cached_token

    url = f"https://{config.SHOPIFY_STORE_DOMAIN}/admin/oauth/access_token"
    resp = requests.post(url, data={
        "grant_type": "client_credentials",
        "client_id": config.SHOPIFY_CLIENT_ID,
        "client_secret": config.SHOPIFY_CLIENT_SECRET,
    }, timeout=10)
    resp.raise_for_status()
    _cached_token = resp.json()["access_token"]
    return _cached_token


def _api_get(endpoint: str, params: dict[str, Any] | None = None) -> dict:
    token = _get_access_token()
    url = f"https://{config.SHOPIFY_STORE_DOMAIN}/admin/api/{API_VERSION}/{endpoint}"
    resp = requests.get(url, headers={
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json",
    }, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def lookup_customer(email: str) -> dict[str, Any]:
    """Find customer by email and return their recent orders with tracking."""
    try:
        data = _api_get("customers/search.json", {"query": f"email:{email}"})
    except requests.HTTPError as e:
        logger.warning("Shopify customer search failed for %s: %s", email, e)
        return {"found": False, "customer": None, "orders": []}

    customers = data.get("customers", [])
    if not customers:
        return {"found": False, "customer": None, "orders": []}

    customer = customers[0]
    customer_id = customer["id"]

    customer_info = {
        "id": customer_id,
        "name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
        "email": customer.get("email", ""),
        "orders_count": customer.get("orders_count", 0),
    }

    try:
        orders_data = _api_get("orders.json", {
            "customer_id": customer_id,
            "status": "any",
            "limit": 5,
            "order": "created_at desc",
        })
    except requests.HTTPError as e:
        logger.warning("Shopify orders lookup failed for customer %s: %s", customer_id, e)
        return {"found": True, "customer": customer_info, "orders": []}

    orders = []
    for order in orders_data.get("orders", []):
        tracking_numbers = []
        tracking_urls = []
        for f in order.get("fulfillments", []):
            tracking_numbers.extend(f.get("tracking_numbers", []))
            tracking_urls.extend(f.get("tracking_urls", []))

        line_items = [
            {"title": li["title"], "quantity": li["quantity"], "price": li["price"]}
            for li in order.get("line_items", [])
        ]

        orders.append({
            "id": order["id"],
            "name": order.get("name", ""),
            "created_at": order.get("created_at", ""),
            "financial_status": order.get("financial_status", ""),
            "fulfillment_status": order.get("fulfillment_status"),
            "total_price": order.get("total_price", ""),
            "currency": order.get("currency", "MXN"),
            "line_items": line_items,
            "tracking_numbers": tracking_numbers,
            "tracking_urls": tracking_urls,
        })

    return {"found": True, "customer": customer_info, "orders": orders}
