from typing import Any, Dict, Optional
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.repositories.events_pg import EventRepositoryPG
from app.repositories.tenants_pg import TenantRepositoryPG
from app.repositories.orders_pg import OrderRepositoryPG
from app.utils import now_ts, stable_event_id, tenant_log_paths, jsonl_append
from app.services.justeat import (
    map_shipday_to_jet_state,
    build_deliverystate_payload,
    put_deliverystate,
)

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


def extract_tracking_id(tracking_url: str | None) -> str | None:
    if not tracking_url:
        return None

    m = re.search(r"/trackingPage/([^&/?]+)", tracking_url)
    if not m:
        return None

    return m.group(1)


def normalize_shipday_client_status(payload: Dict[str, Any]) -> Optional[str]:
    event = str(payload.get("event") or "").upper()
    order_status = str(payload.get("order_status") or "").upper()
    order = payload.get("order") or {}

    event_mapping = {
        "ORDER_ACCEPTED": "created",
        "ORDER_CONFIRMED": "created",
        "ORDER_DRIVERASSIGNED": "driver_assigned",
        "ORDER_PICKEDUP": "collected",
        "ORDER_ONTHEWAY": "to_customer",
        "ORDER_ARRIVED": "to_customer",
        "ORDER_DELIVERED": "delivered",
        "ORDER_COMPLETED": "delivered",
        "ORDER_FAILED": "failed",
        "ORDER_CANCELLED": "cancelled",
        "ORDER_CANCELED": "cancelled",
        "DRIVER_UNASSIGNED": "created",
        "ORDER_UNASSIGNED": "created",
    }

    if event in event_mapping:
        return event_mapping[event]

    status_mapping = {
        "NOT_ASSIGNED": "created",
        "ACCEPTED": "created",
        "CONFIRMED": "created",
        "DRIVER_ASSIGNED": "driver_assigned",
        "PICKEDUP": "collected",
        "READY_TO_DELIVER": "to_customer",
        "ONTHEWAY": "to_customer",
        "ON_THE_WAY": "to_customer",
        "DELIVERED": "delivered",
        "COMPLETED": "delivered",
        "FAILED": "failed",
        "CANCELLED": "cancelled",
        "CANCELED": "cancelled",
    }

    if order_status in status_mapping:
        return status_mapping[order_status]

    if order.get("delivery_time") or order.get("completed_time") or order.get("end_time"):
        return "delivered"

    if order.get("arrived_time"):
        return "to_customer"

    if order.get("pickedup_time"):
        return "collected"

    if order.get("assigned_time") or order.get("start_time"):
        return "driver_assigned"

    return None


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
    tracking_id = extract_tracking_id(tracking_url)
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
    if raw_event in {"DRIVER_UNASSIGNED", "ORDER_UNASSIGNED"}:

        OrderRepositoryPG.clear_driver(source_order_id)

        OrderRepositoryPG.update_status(
            source_order_id,
            "created"
        )
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

            jet_state = map_shipday_to_jet_state(normalized_status or "")

            if jet_state:
                jet_body = build_deliverystate_payload(
                    normalized_status=normalized_status or "",
                    driver_id=str(driver_id) if driver_id else None,
                    lat=None,
                    lng=None,
                )

                jet_result = await put_deliverystate(
                    tenant=tenant,
                    order_id=source_order_id,
                    state=jet_state,
                    body=jet_body,
                )

                EventRepositoryPG.append(
                    tenant_id=tenant_id,
                    event_type="justeat.status.pushed" if jet_result["ok"] else "justeat.status.failed",
                    order_id=source_order_id,
                    payload={
                        "normalizedStatus": normalized_status,
                        "jetState": jet_state,
                        "body": jet_body,
                        "result": jet_result,
                    },
                )

        if driver_id:
            OrderRepositoryPG.update_driver(
                source_order_id=source_order_id,
                driver_id=str(driver_id),
                lat=None,
                lng=None,
            )

        merged_data = dict(existing_order.get("data") or {})

        new_data = {
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

        for key, value in new_data.items():
            if value is not None:
                merged_data[key] = value

        OrderRepositoryPG.update_metadata(
            source_order_id=source_order_id,
            shipday_order_id=shipday_order_id,
            shipday_tracking_url=tracking_url,
            shipday_tracking_id=tracking_id,
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