from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.repositories.events_pg import EventRepositoryPG
from app.repositories.orders_pg import OrderRepositoryPG
from app.utils import now_ts, stable_event_id

router = APIRouter()

FLEET_WEBHOOK_TOKEN = "CHANGE_ME_FLEET_TOKEN"


def require_shipday_fleet_token(request: Request) -> None:
    incoming = (
        request.headers.get("x-hub-token")
        or request.headers.get("X-Hub-Token")
        or request.headers.get("authorization")
        or request.headers.get("Authorization")
        or ""
    )

    if FLEET_WEBHOOK_TOKEN and incoming != FLEET_WEBHOOK_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


def normalize_shipday_status(status: Optional[str]) -> Optional[str]:
    if not status:
        return None

    mapping = {
        "driver_assigned": "driver_assigned",
        "assigned": "driver_assigned",
        "picked_up": "collected",
        "pickedup": "collected",
        "on_the_way": "to_customer",
        "on_the_way_to_customer": "to_customer",
        "delivered": "delivered",
        "cancelled": "cancelled",
        "canceled": "cancelled",
    }
    return mapping.get(str(status).lower())


@router.post("/webhooks/shipday/fleet")
async def shipday_fleet_webhook(request: Request):
    require_shipday_fleet_token(request)

    payload: Dict[str, Any] = await request.json()
    ts = now_ts()
    event_id = stable_event_id(payload)

    order_id = payload.get("orderId") or payload.get("orderNumber")
    driver = payload.get("driver") or {}
    driver_location = payload.get("driverLocation") or {}
    raw_status = payload.get("status")
    normalized_status = normalize_shipday_status(raw_status)

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
            "normalizedStatus": normalized_status,
            "payload": payload,
        },
    )

    return JSONResponse(
        status_code=202,
        content={"accepted": True, "scope": "fleet", "orderId": order_id},
    )