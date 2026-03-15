import time
from typing import Dict, Any

from app.config import logger
from app.repositories.events_pg import EventRepositoryPG
from app.services.replay import replay_order

RETRY_QUEUE = []


def enqueue_retry(order_id: str):
    RETRY_QUEUE.append(
        {
            "orderId": order_id,
            "attempts": 0,
            "nextTry": time.time() + 10,
        }
    )


async def process_retry_queue():
    now = time.time()

    for item in RETRY_QUEUE[:]:
        if item["nextTry"] > now:
            continue

        order_id = item["orderId"]

        result = await replay_order(order_id)

        if result["ok"]:
            RETRY_QUEUE.remove(item)
            continue

        item["attempts"] += 1
        item["nextTry"] = time.time() + (item["attempts"] * 30)

        if item["attempts"] > 5:
            RETRY_QUEUE.remove(item)

            logger.warning("Retry gave up for order %s after %d attempts", order_id, item["attempts"])
            EventRepositoryPG.append(
                tenant_id=result.get("tenantId"),
                event_type="justeat.retry.gave_up",
                order_id=order_id,
                payload=result,
            )