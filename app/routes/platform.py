from fastapi import APIRouter

from app.storage import load_tenants
from app.repositories.orders import OrderRepository
from app.repositories.events import EventRepository
from app.services.order_state import build_order_view
from app.services.replay import replay_order
from app.services.metrics import get_health, get_stats, get_retries

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True, "v": "4"}


@router.get("/tenants")
def list_tenants():
    tenants = load_tenants()
    return {"tenants": sorted(list(tenants.keys()))}


@router.get("/platform/restaurants")
def platform_restaurants():
    tenants = load_tenants()
    restaurants = []

    for tenant_id, tenant in tenants.items():
        restaurants.append(
            {
                "tenantId": tenant_id,
                "restaurantName": tenant.get("restaurantName"),
                "platforms": tenant.get("platforms", []),
                "justeatRestaurantId": ((tenant.get("justeat") or {}).get("restaurant_id")),
            }
        )

    return {"restaurants": restaurants}

@router.get("/platform/orders")
def list_orders():
    return {"orders": OrderRepository.list()}

@router.get("/platform/orders/{order_id}")
def order_view(order_id: str):

    view = build_order_view(order_id)

    if not view:
        return {"error": "order_not_found"}

    return view

@router.get("/platform/events")
def list_events():
    return {"events": EventRepository.list()}


@router.get("/platform/events/{tenant_id}")
def list_events_by_tenant(tenant_id: str):
    return {"events": EventRepository.list_by_tenant(tenant_id)}


@router.get("/platform/events/order/{order_id}")
def list_events_by_order(order_id: str):
    return {"events": EventRepository.list_by_order(order_id)}

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