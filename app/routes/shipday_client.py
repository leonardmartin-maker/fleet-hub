from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.repositories.events_pg import EventRepositoryPG
from app.repositories.tenants_pg import TenantRepositoryPG
from app.utils import now_ts, stable_event_id, tenant_log_paths, jsonl_append

router = APIRouter()


def require_shipday_client_token(tenant: Dict[str, Any], request: Request) -> None:
    expected = ((tenant.get("shipday") or {}).get("webhook_token")) or ""

    incoming = (
        request.headers.get("x-hub-token")
        or request.headers.get("X-Hub-Token")
        or request.headers.get("authorization")
        or request.headers.get("Authorization")
        or ""
    )

    if expected and incoming != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/webhooks/shipday-client/{tenant_id}")
async def shipday_client_webhook(tenant_id: str, request: Request):
    tenant = TenantRepositoryPG.get(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Unknown tenant")

    require_shipday_client_token(tenant, request)

    payload: Dict[str, Any] = await request.json()
    import json
    print("SHIPDAY CLIENT PAYLOAD =", json.dumps(payload, indent=2, ensure_ascii=False))
    ts = now_ts()
    event_id = stable_event_id(payload)

    order_id = payload.get("orderId") or payload.get("orderNumber")

    try:
        paths = tenant_log_paths(tenant_id)
        jsonl_append(
            paths["shipday_client_in"],
            {
                "ts": ts,
                "tenantId": tenant_id,
                "eventId": event_id,
                "orderId": order_id,
                "payload": payload,
            },
        )
    except Exception:
        pass

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
        content={
            "accepted": True,
            "scope": "client",
            "tenantId": tenant_id,
            "orderId": order_id,
        },
    )