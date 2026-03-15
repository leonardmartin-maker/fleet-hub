from typing import Dict, Any
from app.repositories.events_pg import EventRepositoryPG
from app.repositories.orders_pg import OrderRepositoryPG
from app.services.retry_queue import RETRY_QUEUE
from app.db import get_conn


def get_health() -> Dict[str, Any]:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "service": "fleet-hub",
        "database": "connected" if db_ok else "unreachable",
    }


def get_stats() -> Dict[str, Any]:
    events = EventRepositoryPG.list()

    stats = {
        "orders": len(OrderRepositoryPG.list()),
        "events": len(events),
        "justeat_sent": 0,
        "justeat_failed": 0,
        "shipday_created": 0,
    }

    for e in events:
        t = e.get("event_type")

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