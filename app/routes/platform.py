from fastapi import APIRouter

from app.repositories.tenants_pg import TenantRepositoryPG
from app.config import LOG_DIR
from app.repositories.orders_pg import OrderRepositoryPG
from app.repositories.events_pg import EventRepositoryPG
from app.services.order_state import build_order_view
from app.services.replay import replay_order
from app.services.metrics import get_health, get_stats, get_retries
from app.repositories.tenants_pg import TenantRepositoryPG
from app.services.shipday import assign_order_to_driver

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True, "v": "4"}


@router.get("/tenants")
def list_tenants():
    tenants = TenantRepositoryPG.list()
    return {"tenants": sorted([t.get("tenantId") for t in tenants if t.get("tenantId")])}


@router.get("/platform/restaurants")
def platform_restaurants():
    tenants = TenantRepositoryPG.list()

    restaurants = []
    for tenant in tenants:
        restaurants.append(
            {
                "tenantId": tenant.get("tenantId"),
                "restaurantName": tenant.get("restaurantName"),
                "platforms": tenant.get("platforms", []),
                "justeatRestaurantId": ((tenant.get("justeat") or {}).get("restaurant_id")),
            }
        )

    return {"restaurants": restaurants}

@router.get("/platform/orders")
def list_orders():
    raw_orders = OrderRepositoryPG.list()
    orders = []

    for o in raw_orders:
        orders.append(
            {
                "id": o.get("id"),
                "tenant_id": o.get("tenant_id"),
                "source_platform": o.get("source_platform"),
                "source_order_id": o.get("source_order_id"),
                "shipday_order_id": o.get("shipday_order_id"),
                "shipday_tracking_url": o.get("shipday_tracking_url"),
                "shipday_tracking_id": o.get("shipday_tracking_id"),
                "status": o.get("status"),
                "driver_id": o.get("driver_id"),
                "driver_lat": o.get("driver_lat"),
                "driver_lng": o.get("driver_lng"),
                "driver_last_seen_at": o.get("driver_last_seen_at"),
                "data": o.get("data"),
                "created_at": o.get("created_at"),
            }
        )

    return {"orders": orders}

@router.get("/platform/orders/{order_id}")
def order_view(order_id: str):

    view = build_order_view(order_id)

    if not view:
        return {"error": "order_not_found"}

    return view

@router.get("/platform/events")
def list_events():
    return {"events": EventRepositoryPG.list()}


@router.get("/platform/events/{tenant_id}")
def list_events_by_tenant(tenant_id: str):
    return {"events": EventRepositoryPG.list_by_tenant(tenant_id)}


@router.get("/platform/events/order/{order_id}")
def list_events_by_order(order_id: str):
    return {"events": EventRepositoryPG.list_by_order(order_id)}

@router.get("/platform/dispatch/orders")
def dispatch_orders():

    orders = OrderRepositoryPG.list()

    waiting = [
        o for o in orders
        if o["status"] == "received"
    ]

    return {"orders": waiting}

@router.post("/platform/replay/{order_id}")
async def replay_order_route(order_id: str):
    return await replay_order(order_id)

@router.get("/platform/health")
def platform_health():
    return get_health()


@router.get("/platform/stats")
def platform_stats():
    return get_stats()


@router.get("/platform/retries")
def platform_retries():
    return get_retries()

@router.post("/dispatch/assign/{order_id}/{carrier_id}")
async def dispatch_assign(order_id: str, carrier_id: str):
    order = OrderRepositoryPG.find_by_source(order_id)
    if not order:
        return {"ok": False, "error": "order_not_found"}

    tenant_id = order.get("tenant_id")
    tenant = TenantRepositoryPG.get(tenant_id)
    if not tenant:
        return {"ok": False, "error": "tenant_not_found"}

    shipday_api_key = ((tenant.get("shipday") or {}).get("api_key")) or ""
    if not shipday_api_key:
        return {"ok": False, "error": "shipday_api_key_missing"}

    shipday_order_id = order.get("shipday_order_id")
    if not shipday_order_id:
        return {"ok": False, "error": "shipday_order_id_missing"}

    result = await assign_order_to_driver(
        shipday_api_key=shipday_api_key,
        shipday_order_id=shipday_order_id,
        carrier_id=carrier_id,
    )

    EventRepositoryPG.append(
        tenant_id=tenant_id,
        event_type="shipday.order.assign.requested",
        order_id=order_id,
        payload={
            "shipdayOrderId": shipday_order_id,
            "carrierId": carrier_id,
            "result": result,
        },
    )

    if result["ok"]:
        OrderRepositoryPG.update_status(order_id, "driver_assigned")
        OrderRepositoryPG.update_driver(
            source_order_id=order_id,
            driver_id=str(carrier_id),
            lat=None,
            lng=None,
        )

    return {
        "ok": result["ok"],
        "orderId": order_id,
        "shipdayOrderId": shipday_order_id,
        "carrierId": carrier_id,
        "shipday": result,
    }