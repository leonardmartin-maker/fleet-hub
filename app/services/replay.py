from typing import Any, Dict, Optional

from app.storage import get_tenant
from app.repositories.events import EventRepository
from app.services.justeat import (
    map_shipday_to_jet_state,
    build_deliverystate_payload,
    put_deliverystate,
)


def _find_last_shipday_status_event(order_id: str) -> Optional[Dict[str, Any]]:
    events = EventRepository.list_by_order(order_id)
    events = sorted(events, key=lambda e: e.get("ts", 0), reverse=True)

    for event in events:
        if event.get("eventType") == "shipday.status.received":
            return event

    return None


async def replay_order(order_id: str) -> Dict[str, Any]:
    last_status_event = _find_last_shipday_status_event(order_id)

    if not last_status_event:
        return {
            "ok": False,
            "reason": "no_shipday_status_event_found",
            "orderId": order_id,
        }

    tenant_id = last_status_event.get("tenantId")
    tenant = get_tenant(tenant_id)

    payload = last_status_event.get("payload", {}) or {}
    normalized_status = payload.get("normalizedStatus")
    driver_id = payload.get("driverId")
    lat = payload.get("lat")
    lng = payload.get("lng")

    jet_state = map_shipday_to_jet_state(normalized_status)
    if not jet_state:
        return {
            "ok": False,
            "reason": "no_justeat_mapping_for_status",
            "orderId": order_id,
            "normalizedStatus": normalized_status,
        }

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

    EventRepository.append(
        tenant_id=tenant_id,
        event_type="justeat.status.sent" if jet_result["ok"] else "justeat.status.failed",
        order_id=order_id,
        payload={
            "replay": True,
            "jetState": jet_state,
            "jetRequest": jet_body,
            "jetResult": jet_result,
        },
    )

    return {
        "ok": jet_result["ok"],
        "tenantId": tenant_id,
        "orderId": order_id,
        "jetState": jet_state,
        "jetResult": jet_result,
    }