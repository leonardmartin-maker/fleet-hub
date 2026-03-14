from typing import Any, Dict
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.repositories.events_pg import EventRepositoryPG
from app.utils import now_ts, stable_event_id

router = APIRouter()


@router.post("/webhooks/shipday-client")
async def shipday_client_webhook(request: Request):
    payload: Dict[str, Any] = await request.json()
    ts = now_ts()
    event_id = stable_event_id(payload)

    order_id = payload.get("orderId") or payload.get("orderNumber")
    tenant_id = payload.get("tenantId") or "unknown"

    EventRepositoryPG.append(
        tenant_id=tenant_id,
        event_type="shipday.client.received",
        order_id=order_id,
        payload={
            "ts": ts,
            "eventId": event_id,
            "payload": payload,
        },
    )

    return JSONResponse(
        status_code=202,
        content={"accepted": True, "scope": "client", "orderId": order_id},
    )