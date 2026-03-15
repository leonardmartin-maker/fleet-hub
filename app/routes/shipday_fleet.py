from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import FLEET_WEBHOOK_TOKEN, logger
from app.repositories.events_pg import EventRepositoryPG
from app.repositories.orders_pg import OrderRepositoryPG
from app.utils import now_ts, stable_event_id

router = APIRouter()


def require_shipday_fleet_token(request: Request) -> None:
    incoming = (
        request.headers.get("x-hub-token")
        or request.headers.get("authorization")
        or ""
    )
    if FLEET_WEBHOOK_TOKEN and incoming != FLEET_WEBHOOK_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/webhooks/shipday-fleet")
async def shipday_fleet_webhook(request: Request):
    require_shipday_fleet_token(request)

    payload: Dict[str, Any] = await request.json()
    ts = now_ts()
    event_id = stable_event_id(payload)

    logger.debug("shipday-fleet payload received: %s", payload)

    order_id = payload.get("orderId") or payload.get("orderNumber")
    driver = payload.get("driver") or {}
    driver_location = payload.get("driverLocation") or {}

    existing_order = OrderRepositoryPG.find_by_source(order_id) if order_id else None
    tenant_id = existing_order.get("tenant_id") if existing_order else "fleet"

    EventRepositoryPG.append(
        tenant_id=tenant_id,
        event_type="shipday.status.received",
        order_id=order_id,
        payload={
            "ts": ts,
            "eventId": event_id,
            "driverId": driver.get("id"),
            "lat": driver_location.get("lat"),
            "lng": driver_location.get("lng"),
            "payload": payload,
        },
    )

    if existing_order and order_id and driver.get("id"):
        OrderRepositoryPG.update_driver(
            source_order_id=order_id,
            driver_id=str(driver.get("id")),
            lat=driver_location.get("lat"),
            lng=driver_location.get("lng"),
        )

    return JSONResponse(
        status_code=202,
        content={"accepted": True, "scope": "fleet", "orderId": order_id},
    )