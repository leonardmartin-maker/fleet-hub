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