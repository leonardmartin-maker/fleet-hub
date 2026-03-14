from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.repositories.events_pg import EventRepositoryPG
from app.repositories.tenants_pg import TenantRepositoryPG
from app.repositories.orders_pg import OrderRepositoryPG
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


def normalize_shipday_client_status(payload: Dict[str, Any]) -> Optional[str]:
    event = str(payload.get("event") or "").upper()
    order_status = str(payload.get("order_status") or "").upper()

    event_mapping = {
        "ORDER_ACCEPTED": "created",
        "ORDER_DRIVERASSIGNED": "driver_assigned",
        "ORDER_PICKEDUP": "collected",
        "ORDER_ONTHEWAY": "to_customer",
        "ORDER_DELIVERED": "delivered",
        "ORDER_CANCELLED": "cancelled",
    }

    if event in event_mapping:
        return event_mapping[event]

    status_mapping = {
        "NOT_ASSIGNED": "created",
        "DRIVER_ASSIGNED": "driver_assigned",
        "PICKEDUP": "collected",
        "READY_TO_DELIVER": "to_customer",
        "DELIVERED": "delivered",
        "CANCELLED": "cancelled",
        "CANCELED": "cancelled",
    }

    return status_mapping.get(order_status)


@router.post("/webhooks/shipday-client/{tenant_id}")
async def shipday_client_webhook(tenant_id: str, request: Request):
    tenant = TenantRepositoryPG.get(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Unknown tenant")

    require_shipday_client_token(tenant, request)

    payload: Dict[str, Any] = await request.json()
    ts = now_ts()
    event_id = stable_event_id(payload)

    order = payload.get("order") or {}
    pickup = payload.get("pickup_details") or {}
    delivery = payload.get("delivery_details") or {}
    carrier = payload.get("carrier") or {}
    third_party_delivery = payload.get("thirdPartyDeliveryOrder") or {}

    pickup_location = pickup.get("location") or {}
    delivery_location = delivery.get("location") or {}

    source_order_id = (
        order.get("order_number")
        or payload.get("orderId")
        or payload.get("orderNumber")
    )

    shipday_order_id = order.get("id")
    tracking_url = payload.get("trackingUrl")
    normalized_status = normalize_shipday_client_status(payload)

    driver_id = carrier.get("id")
    driver_name = third_party_delivery.get("driverName") or carrier.get("name")
    driver_phone = third_party_delivery.get("driverPhone") or carrier.get("phone")
    shipday_fleet_delivery_id = third_party_delivery.get("referenceId")

    if not source_order_id:
        raise HTTPException(status_code=422, detail="Missing source order id")

    try:
        paths = tenant_log_paths(tenant_id)
        jsonl_append(
            paths["shipday_client_in"],
            {
                "ts": ts,
                "tenantId": tenant_id,
                "eventId": event_id,
                "orderId": source_order_id,
                "payload": payload,
                "normalizedStatus": normalized_status,
            },
        )
    except Exception:
        pass

    raw_event = str(payload.get("event") or "").upper()
    event_type = f"shipday.client.{raw_event.lower()}" if raw_event else "shipday.client.received"

    EventRepositoryPG.append(
        tenant_id=tenant_id,
        event_type=event_type,
        order_id=source_order_id,
        payload={
            "ts": ts,
            "eventId": event_id,
            "normalizedStatus": normalized_status,
            "payload": payload,
        },
    )

    existing_order = OrderRepositoryPG.find_by_source(source_order_id)

    if existing_order:
        if normalized_status:
            OrderRepositoryPG.update_status(source_order_id, normalized_status)

        if driver_id:
            OrderRepositoryPG.update_driver(
                source_order_id=source_order_id,
                driver_id=str(driver_id),
                lat=None,
                lng=None,
            )

        merged_data = dict(existing_order.get("data") or {})
        merged_data.update(
            {
                "pickupLatitude": pickup_location.get("lat"),
                "pickupLongitude": pickup_location.get("lng"),
                "customerLatitude": delivery_location.get("lat"),
                "customerLongitude": delivery_location.get("lng"),
                "driverName": driver_name,
                "driverPhone": driver_phone,
                "trackingUrl": tracking_url,
                "shipdayFleetDeliveryId": shipday_fleet_delivery_id,
                "shipdayClientOrderId": shipday_order_id,
            }
        )

        OrderRepositoryPG.update_metadata(
            source_order_id=source_order_id,
            shipday_order_id=shipday_order_id,
            shipday_tracking_url=tracking_url,
            shipday_tracking_id=None,
            data=merged_data,
        )

    return JSONResponse(
        status_code=202,
        content={
            "accepted": True,
            "scope": "client",
            "tenantId": tenant_id,
            "orderId": source_order_id,
            "normalizedStatus": normalized_status,
        },
    )