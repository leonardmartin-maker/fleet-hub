from fastapi import APIRouter
import os
import httpx

from app.repositories.orders_pg import OrderRepositoryPG
from app.services.dispatch import suggest_best_driver

router = APIRouter()

SHIPDAY_TOKEN = os.getenv("SHIPDAY_TOKEN")


async def fetch_drivers():
    url = "https://api.shipday.com/drivers"
    headers = {
        "Authorization": f"Bearer {SHIPDAY_TOKEN}"
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, headers=headers)

    if r.status_code != 200:
        return []

    data = r.json()
    if isinstance(data, dict) and "drivers" in data:
        return data["drivers"]
    if isinstance(data, list):
        return data
    return []


@router.get("/dispatch/suggest/{order_id}")
async def dispatch_suggest(order_id: str):
    order = OrderRepositoryPG.find_by_source(order_id)
    if not order:
        return {"error": "order_not_found"}

    drivers = await fetch_drivers()
    best_driver = suggest_best_driver(order, drivers)

    return {
        "orderId": order_id,
        "bestDriver": best_driver,
    }

@router.post("/dispatch/assign/{order_id}/{driver_id}")
async def dispatch_assign(order_id: str, driver_id: str):

    order = OrderRepositoryPG.find_by_source(order_id)

    if not order:
        return {"error": "order_not_found"}

    shipday_order_id = order.get("shipday_order_id")

    if not shipday_order_id:
        return {"error": "shipday_order_missing"}

    url = f"https://api.shipday.com/orders/{shipday_order_id}/assign"

    headers = {
        "Authorization": f"Bearer {SHIPDAY_TOKEN}"
    }

    payload = {
        "driverId": driver_id
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(url, json=payload, headers=headers)

    if r.status_code != 200:
        return {
            "error": "shipday_assign_failed",
            "status": r.status_code
        }

    OrderRepositoryPG.update_status(order_id, "assigned")

    return {
        "success": True,
        "orderId": order_id,
        "driverId": driver_id
    }