from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Request

from app.storage import get_tenant
from app.utils import (
    now_ts,
    stable_event_id,
    extract_order_id,
    extract_driver_id,
    extract_geo,
    normalize_status,
    tenant_log_paths,
    jsonl_append,
)

from app.services.justeat import (
    map_shipday_to_jet_state,
    build_deliverystate_payload,
    put_deliverystate,
)

router = APIRouter()


def require_shipday_token(tenant: Dict[str, Any], request: Request) -> None:
    expected = ((tenant.get("shipday") or {}).get("webhook_token")) or ""
    incoming = request.headers.get("x-shipday-token") or request.headers.get("X-Shipday-Token") or ""
    if expected and incoming != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def justeat_draft(
    normalized_status: str,
    order_id: str,
    driver_id,
    lat,
    lng,
    ts: int,
):
    status_to_state = {
        "driver_assigned": "torestaurant",
        "to_restaurant": "torestaurant",
        "at_restaurant": "atrestaurant",
        "collected": "collected",
        "to_customer": "tocustomer",
        "delivered": "delivered",
        "cancelled": "cancelled",
        "unknown": "unknown",
    }
    state = status_to_state.get(normalized_status, normalized_status)

    return {
        "ts": ts,
        "orderId": order_id,
        "justEat": {
            "action": "deliverystate" if state != "unknown" else "noop",
            "state": state,
            "endpointHint": f"/orders/{order_id}/deliverystate/{state}" if state != "unknown" else None,
            "driverId": driver_id,
            "position": {"lat": lat, "lng": lng} if lat is not None and lng is not None else None,
        },
    }


@router.post("/webhooks/shipday/{tenant_id}")
async def shipday_webhook_tenant(tenant_id: str, request: Request):
    tenant = get_tenant(tenant_id)
    require_shipday_token(tenant, request)

    payload: Dict[str, Any] = await request.json()
    ts = now_ts()

    event_id = stable_event_id(payload)
    order_id = extract_order_id(payload)
    normalized_status = normalize_status(payload)
    driver_id = extract_driver_id(payload)
    lat, lng = extract_geo(payload)

    paths = tenant_log_paths(tenant_id)

    jsonl_append(
        paths["shipday_events"],
        {
            "ts": ts,
            "tenantId": tenant_id,
            "eventId": event_id,
            "orderId": order_id,
            "normalizedStatus": normalized_status,
            "headers": {
                "user-agent": request.headers.get("user-agent"),
                "x-forwarded-for": request.headers.get("x-forwarded-for"),
            },
            "payload": payload,
        },
    )

    if order_id:
        jsonl_append(paths["justeat_drafts"], justeat_draft(normalized_status, order_id, driver_id, lat, lng, ts))

    jet_state = map_shipday_to_jet_state(normalized_status)
    jet_result = None

    if order_id and jet_state:
        jet_body = build_deliverystate_payload(
            normalized_status=normalized_status,
            driver_id=driver_id,
            lat=lat,
            lng=lng,
        )

        jet_result = await put_deliverystate(
            tenant=tenant,
            order_id=order_id,
            state=jet_state,
            body=jet_body,
        )

        jsonl_append(
            paths["justeat_out"],
            {
                "ts": ts,
                "tenantId": tenant_id,
                "eventId": event_id,
                "orderId": order_id,
                "normalizedStatus": normalized_status,
                "jetState": jet_state,
                "jetRequest": jet_body,
                "jetResult": jet_result,
            },
        )

    return {
        "ok": True,
        "tenantId": tenant_id,
        "eventId": event_id,
        "orderId": order_id,
        "normalizedStatus": normalized_status,
        "justeat": jet_result,
    }