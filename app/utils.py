from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import time

from app.config import LOG_DIR


def now_ts() -> int:
    return int(time.time())


def iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def jsonl_append(path: Path, obj: Dict[str, Any]) -> None:
    line = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def stable_event_id(payload: Dict[str, Any]) -> str:
    for key in ("eventId", "event_id", "id"):
        value = payload.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value)
    base = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:32]


def pick(obj: Dict[str, Any], *keys: str) -> Optional[Any]:
    for key in keys:
        if key in obj and obj[key] is not None and str(obj[key]).strip() != "":
            return obj[key]
    return None


def extract_order_id(payload: Dict[str, Any]) -> Optional[str]:
    for key in ("orderId", "order_id", "orderNumber", "id", "orderID"):
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value)
    order = payload.get("order")
    if isinstance(order, dict):
        for key in ("id", "orderId", "orderNumber", "orderID"):
            value = order.get(key)
            if value is not None and str(value).strip():
                return str(value)
    return None


def extract_driver_id(payload: Dict[str, Any]) -> Optional[str]:
    for key in ("driverId", "driver_id", "riderId", "courierId"):
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value)
    driver = payload.get("driver") or payload.get("rider") or {}
    if isinstance(driver, dict):
        for key in ("id", "driverId", "riderId"):
            value = driver.get(key)
            if value is not None and str(value).strip():
                return str(value)
    return None


def extract_geo(payload: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    candidates = [payload]
    geo = payload.get("driverLocation") or payload.get("location") or payload.get("gps")
    if isinstance(geo, dict):
        candidates.append(geo)
    for obj in candidates:
        if not isinstance(obj, dict):
            continue
        lat = obj.get("lat", obj.get("latitude"))
        lng = obj.get("lng", obj.get("lon", obj.get("longitude")))
        try:
            if lat is not None and lng is not None:
                return float(lat), float(lng)
        except Exception:
            pass
    return None, None


def extract_justeat_restaurant_id(payload: Dict[str, Any]) -> Optional[str]:
    direct_keys = ("restaurantId", "restaurant_id", "posLocationId", "locationId")
    for key in direct_keys:
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value)

    order = payload.get("order") or {}
    if isinstance(order, dict):
        for key in direct_keys:
            value = order.get(key)
            if value is not None and str(value).strip():
                return str(value)

    restaurant = payload.get("restaurant") or {}
    if isinstance(restaurant, dict):
        for key in ("id", "restaurantId", "restaurant_id", "posLocationId"):
            value = restaurant.get(key)
            if value is not None and str(value).strip():
                return str(value)

    return None


def normalize_status(payload: Dict[str, Any]) -> str:
    raw = payload.get("status") or payload.get("event") or payload.get("deliveryStatus") or ""
    raw_s = str(raw).strip().lower()

    if raw_s in ("assigned", "driver_assigned", "courier_assigned"):
        return "driver_assigned"
    if raw_s in ("to_pickup", "heading_to_pickup", "enroute_to_restaurant", "to_restaurant"):
        return "to_restaurant"
    if raw_s in ("at_pickup", "arrived_at_restaurant", "at_restaurant"):
        return "at_restaurant"
    if raw_s in ("picked_up", "pickedup", "collected", "pickup_complete"):
        return "collected"
    if raw_s in ("to_dropoff", "enroute_to_customer", "to_customer"):
        return "to_customer"
    if raw_s in ("delivered", "completed", "dropoff_complete"):
        return "delivered"
    if raw_s in ("cancelled", "canceled", "failed", "delivery_failed"):
        return "cancelled"

    return raw_s or "unknown"


def tenant_log_paths(tenant_id: str) -> Dict[str, Path]:
    tenant_dir = LOG_DIR / "tenants" / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    return {
        "shipday_events": tenant_dir / "shipday_events.jsonl",
        "justeat_drafts": tenant_dir / "justeat_drafts.jsonl",
        "justeat_in": tenant_dir / "justeat_in.jsonl",
        "shipday_create": tenant_dir / "shipday_create.jsonl",
        "justeat_out": tenant_dir / "justeat_out.jsonl",
    }