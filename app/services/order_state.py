from typing import Any, Dict, List, Optional

from app.repositories.orders import OrderRepository
from app.repositories.events import EventRepository


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


def _compute_status(events: List[Dict[str, Any]]) -> str:
    current = "received"

    for event in events:
        event_type = event.get("eventType")
        payload = event.get("payload", {}) or {}

        if event_type == "shipday.order.created":
            if _status_rank("created") > _status_rank(current):
                current = "created"

        elif event_type == "shipday.status.received":
            normalized_status = payload.get("normalizedStatus")
            if normalized_status and _status_rank(normalized_status) > _status_rank(current):
                current = normalized_status

    return current


def _extract_shipday_order_id(events: List[Dict[str, Any]]) -> Optional[Any]:
    for event in reversed(events):
        if event.get("eventType") == "shipday.order.created":
            payload = event.get("payload", {}) or {}
            shipday_order_id = payload.get("shipdayOrderId")
            if shipday_order_id is not None:
                return shipday_order_id

    return None


def build_order_view(order_id: str) -> Optional[Dict[str, Any]]:
    base_order = OrderRepository.find_by_source(order_id)
    if not base_order:
        return None

    events = EventRepository.list_by_order(order_id)
    events = sorted(events, key=lambda e: e.get("ts", 0))

    status = _compute_status(events)
    shipday_order_id = _extract_shipday_order_id(events)

    timeline = []
    for event in events:
        timeline.append(
            {
                "ts": event.get("ts"),
                "event": event.get("eventType"),
                "payload": event.get("payload", {}),
            }
        )

    return {
        "orderId": base_order.get("sourceOrderId"),
        "tenantId": base_order.get("tenantId"),
        "platform": base_order.get("sourcePlatform"),
        "shipdayOrderId": shipday_order_id,
        "status": status,
        "timeline": timeline,
    }