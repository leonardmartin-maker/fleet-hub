from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Request

from app.storage import find_tenant_by_justeat_restaurant_id
from app.utils import (
    now_ts,
    stable_event_id,
    extract_order_id,
    extract_justeat_restaurant_id,
    tenant_log_paths,
    jsonl_append,
)
from app.services.shipday import (
    map_justeat_to_shipday,
    create_order,
    get_order_details,
    extract_tracking_fields_from_order_details,
)
from app.repositories.orders_pg import OrderRepositoryPG
from app.repositories.events_pg import EventRepositoryPG

router = APIRouter()


def require_justeat_token(tenant: Dict[str, Any], request: Request) -> None:
    expected = ((tenant.get("justeat") or {}).get("webhook_token")) or ""
    incoming = request.headers.get("x-hub-token") or request.headers.get("X-Hub-Token") or ""
    if expected and incoming != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/webhooks/justeat")
async def justeat_webhook(request: Request):
    payload: Dict[str, Any] = await request.json()
    ts = now_ts()

    restaurant_id = extract_justeat_restaurant_id(payload)
    if not restaurant_id:
        raise HTTPException(status_code=422, detail="Missing JustEat restaurant_id in payload")

    tenant_id, tenant = find_tenant_by_justeat_restaurant_id(restaurant_id)
    if not tenant.get("enabled", True):
        raise HTTPException(status_code=403, detail="Tenant disabled")
    require_justeat_token(tenant, request)

    paths = tenant_log_paths(tenant_id)
    event_id = stable_event_id(payload)
    order_id = extract_order_id(payload)

    if not order_id:
        raise HTTPException(status_code=422, detail="Missing orderId")

    OrderRepositoryPG.create(
        tenant_id=tenant_id,
        platform="justeat",
        source_order_id=order_id,
    )

    EventRepositoryPG.append(
        tenant_id=tenant_id,
        event_type="justeat.order.received",
        order_id=order_id,
        payload={
            "restaurantId": restaurant_id,
            "eventId": event_id,
        },
    )

    jsonl_append(
        paths["justeat_in"],
        {
            "ts": ts,
            "tenantId": tenant_id,
            "restaurantId": restaurant_id,
            "eventId": event_id,
            "orderId": order_id,
            "headers": {
                "user-agent": request.headers.get("user-agent"),
                "x-forwarded-for": request.headers.get("x-forwarded-for"),
            },
            "payload": payload,
        },
    )

    shipday_api_key = ((tenant.get("shipday") or {}).get("api_key")) or ""
    if not shipday_api_key:
        raise HTTPException(status_code=422, detail="Tenant missing shipday.api_key")

    shipday_body = map_justeat_to_shipday(tenant, payload)

    EventRepositoryPG.append(
        tenant_id=tenant_id,
        event_type="shipday.order.create.requested",
        order_id=order_id,
        payload={
            "restaurantId": restaurant_id,
            "eventId": event_id,
            "shipdayRequest": shipday_body,
        },
    )

    result = await create_order(shipday_api_key, shipday_body)

    jsonl_append(
        paths["shipday_create"],
        {
            "ts": ts,
            "tenantId": tenant_id,
            "restaurantId": restaurant_id,
            "eventId": event_id,
            "orderId": order_id,
            "shipdayRequest": shipday_body,
            "shipdayResult": result,
        },
    )

    if not result["ok"] or not result["response"].get("success", False):
        EventRepositoryPG.append(
            tenant_id=tenant_id,
            event_type="shipday.order.create.failed",
            order_id=order_id,
            payload={
                "eventId": event_id,
                "result": result,
            },
        )

        raise HTTPException(
            status_code=502,
            detail={
                "shipday_status": result["status"],
                "shipday_response": result["response"],
            },
        )

    shipday_response = result["response"]
    shipday_order_id = shipday_response.get("orderId")

    shipday_tracking_url = None
    shipday_tracking_id = None
    details = None

    try:
        details = await get_order_details(shipday_api_key, order_id)

        if details["ok"]:
            tracking = extract_tracking_fields_from_order_details(details["response"])
            shipday_tracking_url = tracking["tracking_url"]
            shipday_tracking_id = tracking["tracking_id"]
    except Exception as exc:
        details = {
            "ok": False,
            "status": 500,
            "response": {"error": str(exc)},
        }

    OrderRepositoryPG.mark_shipday_created(
        source_order_id=order_id,
        shipday_order_id=shipday_order_id,
        shipday_tracking_url=shipday_tracking_url,
        shipday_tracking_id=shipday_tracking_id,
    )

    EventRepositoryPG.append(
        tenant_id=tenant_id,
        event_type="shipday.order.created",
        order_id=order_id,
        payload={
            "eventId": event_id,
            "shipdayOrderId": shipday_order_id,
            "shipdayTrackingUrl": shipday_tracking_url,
            "shipdayTrackingId": shipday_tracking_id,
            "shipdayDetails": details,
        },
    )

    return {
        "ok": True,
        "tenantId": tenant_id,
        "restaurantId": restaurant_id,
        "eventId": event_id,
        "orderId": order_id,
        "shipdayOrderId": shipday_order_id,
        "shipdayTrackingUrl": shipday_tracking_url,
        "shipdayTrackingId": shipday_tracking_id,
        "shipday": result,
        "shipdayDetails": details,
    }