"""JET Connect (eat.ch) webhook route.

Receives orders from the JET Connect platform via HMAC-signed webhooks,
creates them in the database, dispatches to Shipday, and sends async
acknowledgments back to JET Connect.
"""

import json
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import logger
from app.repositories.orders_pg import OrderRepositoryPG
from app.repositories.events_pg import EventRepositoryPG
from app.repositories.tenants_pg import TenantRepositoryPG
from app.services.jet_connect import (
    validate_hmac,
    map_jet_connect_to_shipday,
    acknowledge_success,
    acknowledge_failure,
)
from app.services.shipday import (
    create_order,
    get_order_details,
    extract_tracking_fields_from_order_details,
)
from app.utils import stable_event_id

router = APIRouter()


async def _finalize_order(
    tenant: Dict[str, Any],
    tenant_id: str,
    jet_order_id: str,
    shipday_ok: bool,
    shipday_result: Dict[str, Any],
    shipday_api_key: str,
    event_id: str,
):
    """Background task: send acknowledgment to JET Connect and update order metadata."""
    try:
        if shipday_ok:
            # Acknowledge success to JET Connect
            ack_result = await acknowledge_success(tenant, jet_order_id)

            # Fetch tracking details from Shipday
            shipday_tracking_url = None
            shipday_tracking_id = None
            shipday_order_id = shipday_result.get("response", {}).get("orderId")

            try:
                details = await get_order_details(shipday_api_key, jet_order_id)
                if details["ok"]:
                    tracking = extract_tracking_fields_from_order_details(details["response"])
                    shipday_tracking_url = tracking["tracking_url"]
                    shipday_tracking_id = tracking["tracking_id"]
            except Exception as exc:
                logger.warning("Failed to fetch Shipday tracking for %s: %s", jet_order_id, exc)

            # Update order in DB
            OrderRepositoryPG.mark_shipday_created(
                source_order_id=jet_order_id,
                shipday_order_id=shipday_order_id,
                shipday_tracking_url=shipday_tracking_url,
                shipday_tracking_id=shipday_tracking_id,
            )

            EventRepositoryPG.append(
                tenant_id=tenant_id,
                event_type="jet_connect.ack.success",
                order_id=jet_order_id,
                payload={
                    "eventId": event_id,
                    "ackResult": ack_result,
                    "shipdayOrderId": shipday_order_id,
                    "shipdayTrackingUrl": shipday_tracking_url,
                    "shipdayTrackingId": shipday_tracking_id,
                },
            )

            logger.info("JET Connect order %s acknowledged successfully", jet_order_id)

        else:
            # Acknowledge failure to JET Connect
            error_msg = str(shipday_result.get("response", {}))[:200]
            ack_result = await acknowledge_failure(
                tenant,
                jet_order_id,
                error_code="SHIPDAY_CREATE_FAILED",
                error_message=f"Shipday order creation failed: {error_msg}",
            )

            EventRepositoryPG.append(
                tenant_id=tenant_id,
                event_type="jet_connect.ack.failure",
                order_id=jet_order_id,
                payload={
                    "eventId": event_id,
                    "ackResult": ack_result,
                    "shipdayResult": shipday_result,
                },
            )

            logger.warning("JET Connect order %s acknowledged as failed", jet_order_id)

    except Exception as exc:
        logger.exception("Error in JET Connect finalization for %s: %s", jet_order_id, exc)
        EventRepositoryPG.append(
            tenant_id=tenant_id,
            event_type="jet_connect.ack.error",
            order_id=jet_order_id,
            payload={
                "eventId": event_id,
                "error": str(exc),
            },
        )


@router.post("/webhooks/jet-connect")
async def jet_connect_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receive and process an order from JET Connect (eat.ch).

    Flow:
    1. Read raw body for HMAC validation
    2. Lookup tenant by posLocationId
    3. Validate HMAC signature
    4. Create order in DB + log event
    5. Map to Shipday format + create Shipday order
    6. Return 202 Accepted
    7. Background: send async acknowledgment to JET Connect
    """

    # 1. Read raw body (needed for HMAC before JSON parsing)
    raw_body = await request.body()
    try:
        payload: Dict[str, Any] = json.loads(raw_body)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # 2. Extract posLocationId and lookup tenant
    pos_location_id = payload.get("posLocationId")
    if not pos_location_id:
        # Fallback: try location.id
        location = payload.get("location") or {}
        pos_location_id = location.get("id")

    if not pos_location_id:
        raise HTTPException(status_code=422, detail="Missing posLocationId in payload")

    tenant = TenantRepositoryPG.find_by_jet_connect_location_id(pos_location_id)
    if not tenant:
        raise HTTPException(
            status_code=404,
            detail=f"No tenant found for posLocationId: {pos_location_id}",
        )

    tenant_id = tenant["tenantId"]

    # 3. Check tenant enabled
    if not tenant.get("enabled", True):
        raise HTTPException(status_code=403, detail="Tenant disabled")

    # 4. Validate HMAC signature
    jc_config = tenant.get("jet_connect") or {}
    hmac_secret = jc_config.get("hmac_secret") or ""
    hmac_header = (
        request.headers.get("X-JET-Connect-Hash")
        or request.headers.get("x-jet-connect-hash")
        or ""
    )

    if hmac_secret:
        if not validate_hmac(raw_body, hmac_header, hmac_secret):
            logger.warning(
                "JET Connect HMAC validation failed for tenant %s",
                tenant_id,
            )
            raise HTTPException(status_code=401, detail="HMAC validation failed")
    else:
        logger.warning(
            "JET Connect tenant %s has no hmac_secret configured, skipping HMAC validation",
            tenant_id,
        )

    # 5. Extract order ID
    jet_order_id = payload.get("id")
    if not jet_order_id:
        raise HTTPException(status_code=422, detail="Missing order id in payload")

    event_id = stable_event_id(payload)

    # 6. Create order in DB
    OrderRepositoryPG.create(
        tenant_id=tenant_id,
        platform="jet_connect",
        source_order_id=jet_order_id,
    )

    EventRepositoryPG.append(
        tenant_id=tenant_id,
        event_type="jet_connect.order.received",
        order_id=jet_order_id,
        payload={
            "posLocationId": pos_location_id,
            "eventId": event_id,
            "orderType": payload.get("type"),
            "paymentMethod": payload.get("payment_method"),
        },
    )

    # 7. Map to Shipday format
    shipday_api_key = ((tenant.get("shipday") or {}).get("api_key")) or ""
    if not shipday_api_key:
        raise HTTPException(status_code=422, detail="Tenant missing shipday.api_key")

    shipday_body = map_jet_connect_to_shipday(tenant, payload)

    EventRepositoryPG.append(
        tenant_id=tenant_id,
        event_type="shipday.order.create.requested",
        order_id=jet_order_id,
        payload={
            "eventId": event_id,
            "source": "jet_connect",
            "shipdayRequest": shipday_body,
        },
    )

    # 8. Create Shipday order
    result = await create_order(shipday_api_key, shipday_body)
    shipday_ok = result["ok"] and result["response"].get("success", False)

    if not shipday_ok:
        EventRepositoryPG.append(
            tenant_id=tenant_id,
            event_type="shipday.order.create.failed",
            order_id=jet_order_id,
            payload={
                "eventId": event_id,
                "source": "jet_connect",
                "result": result,
            },
        )

    # 9. Schedule background acknowledgment to JET Connect
    background_tasks.add_task(
        _finalize_order,
        tenant=tenant,
        tenant_id=tenant_id,
        jet_order_id=jet_order_id,
        shipday_ok=shipday_ok,
        shipday_result=result,
        shipday_api_key=shipday_api_key,
        event_id=event_id,
    )

    # 10. Return 202 Accepted (JET Connect expects this for async processing)
    return JSONResponse(
        status_code=202,
        content={
            "accepted": True,
            "tenantId": tenant_id,
            "posLocationId": pos_location_id,
            "eventId": event_id,
            "orderId": jet_order_id,
            "orderType": payload.get("type"),
        },
    )
