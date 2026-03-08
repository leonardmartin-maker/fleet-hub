from fastapi import APIRouter

from app.storage import load_tenants
from app.config import LOG_DIR

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True, "v": "3"}


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


@router.get("/platform/stats")
def platform_stats():
    tenants = load_tenants()
    total_restaurants = len(tenants)

    total_shipday_events = 0
    total_justeat_in = 0
    total_shipday_create = 0

    base = LOG_DIR / "tenants"
    if base.exists():
        for tenant_id in tenants.keys():
            tenant_dir = base / tenant_id

            for filename, bucket in (
                ("shipday_events.jsonl", "shipday"),
                ("justeat_in.jsonl", "justeat_in"),
                ("shipday_create.jsonl", "shipday_create"),
            ):
                path = tenant_dir / filename
                if path.exists():
                    with path.open("r", encoding="utf-8") as f:
                        count = sum(1 for _ in f)

                    if bucket == "shipday":
                        total_shipday_events += count
                    elif bucket == "justeat_in":
                        total_justeat_in += count
                    elif bucket == "shipday_create":
                        total_shipday_create += count

    return {
        "restaurants": total_restaurants,
        "shipday_events": total_shipday_events,
        "justeat_in": total_justeat_in,
        "shipday_create": total_shipday_create,
    }