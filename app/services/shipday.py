import re
from typing import Any, Dict, List
from fastapi import HTTPException
import httpx

from app.config import SHIPDAY_ORDERS_URL
from app.utils import pick, extract_order_id


def require_fields(obj: Dict[str, Any], fields: List[str]) -> None:
    missing = [field for field in fields if not obj.get(field)]
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing required fields: {missing}")


def map_justeat_to_shipday(tenant: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    defaults = tenant.get("defaults") or {}
    order_id = extract_order_id(payload) or "UNKNOWN"

    customer = payload.get("customer") or (payload.get("order") or {}).get("customer") or {}
    delivery = payload.get("delivery") or (payload.get("order") or {}).get("delivery") or {}
    restaurant = payload.get("restaurant") or (payload.get("order") or {}).get("restaurant") or {}

    customer_name = pick(customer, "name", "fullName") or pick(payload, "customerName")
    customer_phone = pick(customer, "phone", "phoneNumber") or pick(payload, "customerPhoneNumber")
    customer_address = (
        pick(delivery, "address", "deliveryAddress")
        or pick((delivery.get("address") if isinstance(delivery.get("address"), dict) else {}), "full", "line1")
        or pick(payload, "customerAddress")
    )

    restaurant_name = (
        pick(restaurant, "name")
        or pick(payload, "restaurantName")
        or defaults.get("restaurantName")
    )
    restaurant_address = (
        pick(restaurant, "address")
        or pick(payload, "restaurantAddress")
        or defaults.get("restaurantAddress")
    )
    restaurant_phone = (
        pick(restaurant, "phone", "phoneNumber")
        or pick(payload, "restaurantPhoneNumber")
        or defaults.get("restaurantPhoneNumber")
    )

    items = payload.get("items") or (payload.get("order") or {}).get("items") or []
    order_items = []
    total_cost = 0.0

    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue

            name = pick(item, "name", "title") or "Item"
            qty = pick(item, "quantity", "qty") or 1
            price = pick(item, "price", "unitPrice", "amount")

            try:
                qty = int(qty)
            except Exception:
                qty = 1

            order_items.append({"name": str(name), "quantity": qty})

            try:
                if price is not None:
                    total_cost += float(price) * qty
            except Exception:
                pass

    shipday_payload = {
        "customerName": customer_name,
        "customerAddress": customer_address,
        "customerPhoneNumber": customer_phone,
        "restaurantName": restaurant_name,
        "restaurantAddress": restaurant_address,
        "restaurantPhoneNumber": restaurant_phone,
        "orderItem": order_items,
        "totalOrderCost": round(total_cost, 2),
        "paymentMethod": "credit_card",
        "deliveryFee": 0,
        "tax": 0,
        "tips": 0,
        "discountAmount": 0,
        "orderSource": "JustEat",
        "additionalId": str(order_id),
        "orderNumber": str(order_id),
    }

    require_fields(
        shipday_payload,
        [
            "customerName",
            "customerAddress",
            "customerPhoneNumber",
            "restaurantName",
            "restaurantAddress",
        ],
    )

    return shipday_payload


async def create_order(shipday_api_key: str, body: Dict[str, Any]) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Basic {shipday_api_key}",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(15.0, connect=10.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(SHIPDAY_ORDERS_URL, headers=headers, json=body)
        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        return {
            "ok": response.status_code < 400,
            "status": response.status_code,
            "response": data,
        }


async def get_order_details(shipday_api_key: str, order_number: str) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Basic {shipday_api_key}",
        "Accept": "application/json",
    }
    timeout = httpx.Timeout(15.0, connect=10.0)

    url = f"{SHIPDAY_ORDERS_URL}/{order_number}"

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, headers=headers)
        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        return {
            "ok": response.status_code < 400,
            "status": response.status_code,
            "response": data,
        }
    
async def assign_order_to_driver(
    shipday_api_key: str,
    shipday_order_id: str | int,
    carrier_id: str | int,
) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Basic {shipday_api_key}",
        "Accept": "application/json",
    }
    timeout = httpx.Timeout(15.0, connect=10.0)
    url = f"{SHIPDAY_ORDERS_URL}/assign/{shipday_order_id}/{carrier_id}"

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.put(url, headers=headers)

        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        return {
            "ok": response.status_code < 400,
            "status": response.status_code,
            "response": data,
        }


def extract_tracking_fields_from_order_details(response: Any) -> Dict[str, Any]:
    order: Dict[str, Any]

    if isinstance(response, list) and response:
        first = response[0]
        order = first if isinstance(first, dict) else {}
    elif isinstance(response, dict):
        order = response
    else:
        order = {}

    tracking_url = (
        order.get("trackingLink")
        or order.get("trackingUrl")
        or order.get("trackingPageUrl")
    )

    tracking_id = None
    if tracking_url:
        match = re.search(r"/trackingPage/([^?&]+)", tracking_url)
        if match:
            tracking_id = match.group(1)

    return {
        "tracking_url": tracking_url,
        "tracking_id": tracking_id,
    }