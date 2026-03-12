from typing import Any, Dict, List, Optional

from app.repositories.orders_pg import OrderRepositoryPG
from app.repositories.events_pg import EventRepositoryPG


STATUS_PRIORITY = [
    "received",
    "created",
    "driver_assigned",
    "to_restaurant",
    "at_restaurant",
    "collected",
    "to_customer",
    "delivered",
    "cancelled",
]


def _status_rank(status: str) -> int:
    try:
        return STATUS_PRIORITY.index(status)
    except ValueError:
        return -1


def _event_type(event: Dict[str, Any]) -> Optional[str]:
    return event.get("eventType") or event.get("event_type")


def _event_ts(event: Dict[str, Any]) -> Any:
    return event.get("ts") or event.get("created_at") or event.get("createdAt")


def _compute_status(events: List[Dict[str, Any]]) -> str:
    current = "received"

    for event in events:
        event_type = _event_type(event)
        payload = event.get("payload", {}) or {}

        if event_type == "shipday.order.created":
            if _status_rank("created") > _status_rank(current):
                current = "created"

        elif event_type == "shipday.status.received":
            normalized_status = payload.get("normalizedStatus")
            if normalized_status and _status_rank(normalized_status) > _status_rank(current):
                current = normalized_status

    return current


def _extract_shipday_fields(
    base_order: Dict[str, Any],
    events: List[Dict[str, Any]],
) -> Dict[str, Optional[Any]]:
    shipday_order_id = base_order.get("shipday_order_id")
    shipday_tracking_url = base_order.get("shipday_tracking_url")
    shipday_tracking_id = base_order.get("shipday_tracking_id")

    for event in reversed(events):
        if _event_type(event) == "shipday.order.created":
            payload = event.get("payload", {}) or {}

            if shipday_order_id is None:
                shipday_order_id = payload.get("shipdayOrderId")

            if not shipday_tracking_url:
                shipday_tracking_url = payload.get("shipdayTrackingUrl")

            if not shipday_tracking_id:
                shipday_tracking_id = payload.get("shipdayTrackingId")

    return {
        "shipdayOrderId": shipday_order_id,
        "shipdayTrackingUrl": shipday_tracking_url,
        "shipdayTrackingId": shipday_tracking_id,
    }


def build_order_view(order_id: str) -> Optional[Dict[str, Any]]:
    base_order = OrderRepositoryPG.find_by_source(order_id)
    if not base_order:
        return None

    events = EventRepositoryPG.list_by_order(order_id)
    events = sorted(events, key=lambda e: _event_ts(e) or 0)

    status = _compute_status(events)
    shipday_fields = _extract_shipday_fields(base_order, events)

    timeline = []
    for event in events:
        timeline.append(
            {
                "ts": _event_ts(event),
                "event": _event_type(event),
                "payload": event.get("payload", {}),
            }
        )

    return {
        "orderId": base_order.get("source_order_id"),
        "tenantId": base_order.get("tenant_id"),
        "platform": base_order.get("source_platform"),
        "shipdayOrderId": shipday_fields["shipdayOrderId"],
        "shipdayTrackingUrl": shipday_fields["shipdayTrackingUrl"],
        "shipdayTrackingId": shipday_fields["shipdayTrackingId"],
        "status": status,
        "timeline": timeline,
    }