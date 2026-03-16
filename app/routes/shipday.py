from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Request

from app.config import logger
from app.storage import get_tenant
from app.utils import (
    now_ts,
    stable_event_id,
    extract_order_id,
    extract_driver_id,
    extract_geo,
    normalize_status,
)
from app.services.justeat import (
    map_shipday_to_jet_state,
    build_deliverystate_payload,
    put_deliverystate,
)
from app.repositories.events_pg import EventRepositoryPG
from app.services.retry_queue import enqueue_retry

router = APIRouter()


def require_shipday_token(tenant: Dict[str, Any], request: Request) -> None:
    expected = ((tenant.get("shipday") or {}).get("webhook_token")) or ""
    incoming = request.headers.get("x-shipday-token") or ""
    if expected and incoming != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


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

    EventRepositoryPG.append(
        tenant_id=tenant_id,
        event_type="shipday.status.received",
        order_id=order_id,
        payload={
            "eventId": event_id,
            "normalizedStatus": normalized_status,
            "driverId": driver_id,
            "lat": lat,
            "lng": lng,
        },
    )

    jet_state = map_shipday_to_jet_state(normalized_status)
    jet_result = None

    if order_id and jet_state:
        jet_body = build_deliverystate_payload(
            normalized_status=normalized_status,
            driver_id=driver_id,
            lat=lat,
            lng=lng,
        )

        # Use tenant-specific base URL if JET Connect is configured
        tenant_base_url = (tenant.get("jet_connect") or {}).get("base_url")

        jet_result = await put_deliverystate(
            tenant=tenant,
            order_id=order_id,
            state=jet_state,
            body=jet_body,
            base_url=tenant_base_url,
        )

        event_type = "justeat.status.sent" if jet_result["ok"] else "justeat.status.failed"
        EventRepositoryPG.append(
            tenant_id=tenant_id,
            event_type=event_type,
            order_id=order_id,
            payload={
                "eventId": event_id,
                "jetState": jet_state,
                "jetResult": jet_result,
            },
        )

        if not jet_result["ok"]:
            enqueue_retry(order_id)
            logger.warning("JustEat push failed for order %s, enqueued retry", order_id)

    return {
        "ok": True,
        "tenantId": tenant_id,
        "eventId": event_id,
        "orderId": order_id,
        "normalizedStatus": normalized_status,
        "justeat": jet_result,
    }