from typing import Dict, Any
from app.repositories.events import EventRepository
from app.repositories.orders import OrderRepository
from app.services.retry_queue import RETRY_QUEUE


def get_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "fleet-hub",
    }


def get_stats() -> Dict[str, Any]:

    events = EventRepository.list()

    stats = {
        "orders": len(OrderRepository.list()),
        "events": len(events),
        "justeat_sent": 0,
        "justeat_failed": 0,
        "shipday_created": 0,
    }

    for e in events:

        t = e.get("eventType")

        if t == "justeat.status.sent":
            stats["justeat_sent"] += 1

        elif t == "justeat.status.failed":
            stats["justeat_failed"] += 1

        elif t == "shipday.order.created":
            stats["shipday_created"] += 1

    return stats


def get_retries() -> Dict[str, Any]:

    return {
        "queue_size": len(RETRY_QUEUE),
        "items": RETRY_QUEUE,
    }