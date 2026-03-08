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
from app.services.shipday import map_justeat_to_shipday, create_order

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
    require_justeat_token(tenant, request)

    paths = tenant_log_paths(tenant_id)
    event_id = stable_event_id(payload)
    order_id = extract_order_id(payload)

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
        raise HTTPException(
            status_code=502,
            detail={
                "shipday_status": result["status"],
                "shipday_response": result["response"],
            },
        )

    return {
        "ok": True,
        "tenantId": tenant_id,
        "restaurantId": restaurant_id,
        "eventId": event_id,
        "orderId": order_id,
        "shipday": result,
    }