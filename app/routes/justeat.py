from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Request

from app.storage import find_tenant_by_justeat_restaurant_id
from app.utils import (
    now_ts,
    stable_event_id,
    extract_order_id,
    extract_justeat_restaurant_id,
    tenant_log_paths,
    jsonl_append,
)
from app.services.shipday import map_justeat_to_shipday, create_order
from app.repositories.orders import OrderRepository
from app.repositories.events import EventRepository
from app.repositories.orders_pg import OrderRepositoryPG
from app.repositories.events_pg import EventRepositoryPG

router = APIRouter()


def require_justeat_token(tenant: Dict[str, Any], request: Request) -> None:
    expected = ((tenant.get("justeat") or {}).get("webhook_token")) or ""
    incoming = request.headers.get("x-hub-token") or request.headers.get("X-Hub-Token") or ""
    if expected and incoming != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/webhooks/justeat")
async def justeat_webhook(request: Request):
    payload: Dict[str, Any] = await request.json()
    ts = now_ts()

    restaurant_id = extract_justeat_restaurant_id(payload)
    if not restaurant_id:
        raise HTTPException(status_code=422, detail="Missing JustEat restaurant_id in payload")

    tenant_id, tenant = find_tenant_by_justeat_restaurant_id(restaurant_id)
    require_justeat_token(tenant, request)

    paths = tenant_log_paths(tenant_id)
    event_id = stable_event_id(payload)
    order_id = extract_order_id(payload)

    if not order_id:
        raise HTTPException(status_code=422, detail="Missing orderId")

    # Order registry: crée l'entrée logique si elle n'existe pas encore
    OrderRepository.create(
        tenant_id=tenant_id,
        platform="justeat",
        source_order_id=order_id,
    )

    OrderRepositoryPG.create(
        tenant_id=tenant_id,
        platform="justeat",
        source_order_id=order_id,
    )

    # Event store: commande Just Eat reçue
    EventRepository.append(
        tenant_id=tenant_id,
        event_type="justeat.order.received",
        order_id=order_id,
        payload={
            "restaurantId": restaurant_id,
            "eventId": event_id,
        },
    )

    EventRepositoryPG.append(
        tenant_id=tenant_id,
        event_type="justeat.order.received",
        order_id=order_id,
        payload={
            "restaurantId": restaurant_id,
            "eventId": event_id,
        },
    )

    # Log brut entrant
    jsonl_append(
        paths["justeat_in"],
        {
            "ts": ts,
            "tenantId": tenant_id,
            "restaurantId": restaurant_id,
            "eventId": event_id,
            "orderId": order_id,
            "headers": {
                "user-agent": request.headers.get("user-agent"),
                "x-forwarded-for": request.headers.get("x-forwarded-for"),
            },
            "payload": payload,
        },
    )

    shipday_api_key = ((tenant.get("shipday") or {}).get("api_key")) or ""
    if not shipday_api_key:
        raise HTTPException(status_code=422, detail="Tenant missing shipday.api_key")

    shipday_body = map_justeat_to_shipday(tenant, payload)

    # Event store: création Shipday demandée
    EventRepository.append(
        tenant_id=tenant_id,
        event_type="shipday.order.create.requested",
        order_id=order_id,
        payload={
            "restaurantId": restaurant_id,
            "eventId": event_id,
            "shipdayRequest": shipday_body,
        },
    )

    result = await create_order(shipday_api_key, shipday_body)

    # Log brut création Shipday
    jsonl_append(
        paths["shipday_create"],
        {
            "ts": ts,
            "tenantId": tenant_id,
            "restaurantId": restaurant_id,
            "eventId": event_id,
            "orderId": order_id,
            "shipdayRequest": shipday_body,
            "shipdayResult": result,
        },
    )

    # Succès Shipday
    if result["ok"] and result["response"].get("success", False):
        shipday_order_id = result["response"].get("orderId")

        OrderRepository.mark_shipday_created(
            source_order_id=order_id,
            shipday_order_id=shipday_order_id,
        )

        OrderRepositoryPG.mark_shipday_created(
            source_order_id=order_id,
            shipday_order_id=shipday_order_id,
        )

        EventRepository.append(
            tenant_id=tenant_id,
            event_type="shipday.order.created",
            order_id=order_id,
            payload={
                "eventId": event_id,
                "shipdayOrderId": shipday_order_id,
            },
        )

        EventRepositoryPG.append(
            tenant_id=tenant_id,
            event_type="shipday.order.created",
            order_id=order_id,
            payload={
                "eventId": event_id,
                "shipdayOrderId": shipday_order_id,
            },
        )

    # Échec Shipday
    if not result["ok"] or not result["response"].get("success", False):
        EventRepository.append(
            tenant_id=tenant_id,
            event_type="shipday.order.create.failed",
            order_id=order_id,
            payload={
                "eventId": event_id,
                "result": result,
            },
        )

        raise HTTPException(
            status_code=502,
            detail={
                "shipday_status": result["status"],
                "shipday_response": result["response"],
            },
        )

    return {
        "ok": True,
        "tenantId": tenant_id,
        "restaurantId": restaurant_id,
        "eventId": event_id,
        "orderId": order_id,
        "shipday": result,
    }