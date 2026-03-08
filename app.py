from fastapi import FastAPI, Request, HTTPException
from typing import Any, Dict, Optional, Tuple, List
from datetime import datetime, timezone
import os
import time
import json
import hashlib
from pathlib import Path

import httpx

app = FastAPI()

CONFIG_PATH = Path(os.getenv("TENANTS_JSON", "/etc/fleet-webhooks/tenants.json"))
LOG_DIR = Path(os.getenv("LOG_DIR", "/var/log/fleet-webhooks"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

SHIPDAY_ORDERS_URL = "https://api.shipday.com/orders"
JET_BASE_URL = "https://uk-partnerapi.just-eat.io"


# ---------- Storage (JSON today, Postgres later) ----------

def _load_tenants() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise RuntimeError(f"Missing tenants config: {CONFIG_PATH}")
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise RuntimeError("tenants.json must be an object {tenant_id: {...}}")
    return data


def _get_tenant(tenant_id: str) -> Dict[str, Any]:
    tenants = _load_tenants()
    tenant = tenants.get(tenant_id)
    if not isinstance(tenant, dict):
        raise HTTPException(status_code=404, detail="Unknown tenant")
    return tenant


def _find_tenant_by_justeat_restaurant_id(restaurant_id: str) -> Tuple[str, Dict[str, Any]]:
    tenants = _load_tenants()
    for tenant_id, tenant in tenants.items():
        justeat = tenant.get("justeat") or {}
        if str(justeat.get("restaurant_id", "")).strip() == str(restaurant_id).strip():
            return tenant_id, tenant
    raise HTTPException(status_code=404, detail="Unknown JustEat restaurant_id")


def _require_shipday_token(tenant: Dict[str, Any], request: Request) -> None:
    expected = ((tenant.get("shipday") or {}).get("webhook_token")) or ""
    incoming = request.headers.get("x-shipday-token") or request.headers.get("X-Shipday-Token") or ""
    if expected and incoming != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _require_justeat_token(tenant: Dict[str, Any], request: Request) -> None:
    expected = ((tenant.get("justeat") or {}).get("webhook_token")) or ""
    incoming = request.headers.get("x-hub-token") or request.headers.get("X-Hub-Token") or ""
    if expected and incoming != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ---------- Utils ----------

def _now_ts() -> int:
    return int(time.time())


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _jsonl_append(path: Path, obj: Dict[str, Any]) -> None:
    line = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _stable_event_id(payload: Dict[str, Any]) -> str:
    for key in ("eventId", "event_id", "id"):
        value = payload.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value)

    base = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:32]


def _pick(obj: Dict[str, Any], *keys: str) -> Optional[Any]:
    for key in keys:
        if key in obj and obj[key] is not None and str(obj[key]).strip() != "":
            return obj[key]
    return None


def _extract_order_id(payload: Dict[str, Any]) -> Optional[str]:
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


def _extract_driver_id(payload: Dict[str, Any]) -> Optional[str]:
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


def _extract_geo(payload: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
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


def _extract_justeat_restaurant_id(payload: Dict[str, Any]) -> Optional[str]:
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


def _normalize_status(payload: Dict[str, Any]) -> str:
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


def _justeat_draft(
    normalized_status: str,
    order_id: str,
    driver_id: Optional[str],
    lat: Optional[float],
    lng: Optional[float],
    ts: int,
) -> Dict[str, Any]:
    status_to_state = {
        "driver_assigned": "torestaurant",
        "to_restaurant": "torestaurant",
        "at_restaurant": "atrestaurant",
        "collected": "collected",
        "to_customer": "tocustomer",
        "delivered": "delivered",
        "cancelled": "cancelled",
        "unknown": "unknown",
    }
    state = status_to_state.get(normalized_status, normalized_status)

    return {
        "ts": ts,
        "orderId": order_id,
        "justEat": {
            "action": "deliverystate" if state != "unknown" else "noop",
            "state": state,
            "endpointHint": f"/orders/{order_id}/deliverystate/{state}" if state != "unknown" else None,
            "driverId": driver_id,
            "position": {"lat": lat, "lng": lng} if lat is not None and lng is not None else None,
        },
    }


def _tenant_log_paths(tenant_id: str) -> Dict[str, Path]:
    tenant_dir = LOG_DIR / "tenants" / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    return {
        "shipday_events": tenant_dir / "shipday_events.jsonl",
        "justeat_drafts": tenant_dir / "justeat_drafts.jsonl",
        "justeat_in": tenant_dir / "justeat_in.jsonl",
        "shipday_create": tenant_dir / "shipday_create.jsonl",
        "justeat_out": tenant_dir / "justeat_out.jsonl",
    }


def _require_fields(obj: Dict[str, Any], fields: List[str]) -> None:
    missing = [field for field in fields if not obj.get(field)]
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing required fields: {missing}")


# ---------- Shipday create order ----------

def _map_justeat_to_shipday(tenant: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    defaults = tenant.get("defaults") or {}
    order_id = _extract_order_id(payload) or "UNKNOWN"

    customer = payload.get("customer") or (payload.get("order") or {}).get("customer") or {}
    delivery = payload.get("delivery") or (payload.get("order") or {}).get("delivery") or {}
    restaurant = payload.get("restaurant") or (payload.get("order") or {}).get("restaurant") or {}

    customer_name = _pick(customer, "name", "fullName") or _pick(payload, "customerName")
    customer_phone = _pick(customer, "phone", "phoneNumber") or _pick(payload, "customerPhoneNumber")
    customer_address = (
        _pick(delivery, "address", "deliveryAddress")
        or _pick((delivery.get("address") if isinstance(delivery.get("address"), dict) else {}), "full", "line1")
        or _pick(payload, "customerAddress")
    )

    restaurant_name = _pick(restaurant, "name") or _pick(payload, "restaurantName") or defaults.get("restaurantName")
    restaurant_address = _pick(restaurant, "address") or _pick(payload, "restaurantAddress") or defaults.get("restaurantAddress")
    restaurant_phone = _pick(restaurant, "phone", "phoneNumber") or _pick(payload, "restaurantPhoneNumber") or defaults.get("restaurantPhoneNumber")

    items = payload.get("items") or (payload.get("order") or {}).get("items") or []
    order_items: List[Dict[str, Any]] = []
    total_cost = 0.0

    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            name = _pick(item, "name", "title") or "Item"
            qty = _pick(item, "quantity", "qty") or 1
            price = _pick(item, "price", "unitPrice", "amount")
            try:
                qty = int(qty)
            except Exception:
                qty = 1

            row = {"name": str(name), "quantity": qty}
            order_items.append(row)

            try:
                if price is not None:
                    total_cost += float(price) * qty
            except Exception:
                pass

    shipday_payload = {
        "customerName": customer_name,
        "customerAddress": customer_address,
        "customerPhoneNumber": customer_phone,
        "restaurantName": restaurant_name,
        "restaurantAddress": restaurant_address,
        "restaurantPhoneNumber": restaurant_phone,
        "orderItem": order_items,
        "totalOrderCost": round(total_cost, 2),
        "paymentMethod": "credit_card",
        "deliveryFee": 0,
        "tax": 0,
        "tips": 0,
        "discountAmount": 0,
        "orderSource": "JustEat",
        "additionalId": str(order_id),
        "orderNumber": str(order_id),
    }

    _require_fields(
        shipday_payload,
        [
            "customerName",
            "customerAddress",
            "customerPhoneNumber",
            "restaurantName",
            "restaurantAddress",
        ],
    )

    return shipday_payload


async def _shipday_create_order(shipday_api_key: str, body: Dict[str, Any]) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Basic {shipday_api_key}",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(15.0, connect=10.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(SHIPDAY_ORDERS_URL, headers=headers, json=body)
        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        return {
            "ok": response.status_code < 400,
            "status": response.status_code,
            "response": data,
        }


# ---------- Just Eat outbound ----------

def _jet_headers(tenant: Dict[str, Any]) -> Dict[str, str]:
    justeat = tenant.get("justeat") or {}
    api_key = justeat.get("api_key")
    application = justeat.get("application", "fleet-hub/1.0")
    if not api_key:
        raise HTTPException(status_code=422, detail="Tenant missing justeat.api_key")

    return {
        "X-Flyt-Api-Key": api_key,
        "x-jet-application": application,
        "Content-Type": "application/json",
    }


def _map_shipday_to_jet_state(normalized_status: str) -> Optional[str]:
    mapping = {
        "to_restaurant": "torestaurant",
        "at_restaurant": "atrestaurant",
        "collected": "collected",
        "to_customer": "tocustomer",
        "delivered": "delivered",
        "cancelled": "cancelled",
    }
    return mapping.get(normalized_status)


def _build_jet_deliverystate_payload(
    payload: Dict[str, Any],
    normalized_status: str,
    driver_id: Optional[str],
    lat: Optional[float],
    lng: Optional[float],
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "TimeStampWithUtcOffset": _iso_utc_now(),
        "DriverId": driver_id or "unknown-driver",
    }

    if lat is not None and lng is not None:
        body["Location"] = {
            "Latitude": lat,
            "Longitude": lng,
            "Speed": 0,
            "Heading": 0,
            "Accuracy": 0,
        }

    if normalized_status in ("at_restaurant", "collected", "to_customer"):
        body["EtaAtDeliveryAddress"] = _iso_utc_now()

    return body


async def _jet_put_deliverystate(
    tenant: Dict[str, Any],
    order_id: str,
    state: str,
    body: Dict[str, Any],
) -> Dict[str, Any]:
    url = f"{JET_BASE_URL}/orders/{order_id}/deliverystate/{state}"
    headers = _jet_headers(tenant)
    timeout = httpx.Timeout(15.0, connect=10.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.put(url, headers=headers, json=body)
        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        return {
            "ok": response.status_code < 400,
            "status": response.status_code,
            "response": data,
            "url": url,
        }


# ---------- Platform endpoints ----------

@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "v": "3"}


@app.get("/tenants")
def list_tenants() -> Dict[str, Any]:
    tenants = _load_tenants()
    return {"tenants": sorted(list(tenants.keys()))}


@app.get("/platform/restaurants")
def platform_restaurants() -> Dict[str, Any]:
    tenants = _load_tenants()
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


@app.get("/platform/stats")
def platform_stats() -> Dict[str, Any]:
    tenants = _load_tenants()
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


# ---------- Inbound Just Eat (platform-style, routed by restaurant_id) ----------

@app.post("/webhooks/justeat")
async def justeat_webhook(request: Request) -> Dict[str, Any]:
    payload: Dict[str, Any] = await request.json()
    ts = _now_ts()

    restaurant_id = _extract_justeat_restaurant_id(payload)
    if not restaurant_id:
        raise HTTPException(status_code=422, detail="Missing JustEat restaurant_id in payload")

    tenant_id, tenant = _find_tenant_by_justeat_restaurant_id(restaurant_id)
    _require_justeat_token(tenant, request)

    paths = _tenant_log_paths(tenant_id)
    event_id = _stable_event_id(payload)
    order_id = _extract_order_id(payload)

    _jsonl_append(
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

    shipday_body = _map_justeat_to_shipday(tenant, payload)
    result = await _shipday_create_order(shipday_api_key, shipday_body)

    _jsonl_append(
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

    if not result["ok"] or not result["response"].get("success", False):
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


# ---------- Inbound Shipday (tenant-style, keeps current working model) ----------

@app.post("/webhooks/shipday/{tenant_id}")
async def shipday_webhook_tenant(tenant_id: str, request: Request) -> Dict[str, Any]:
    tenant = _get_tenant(tenant_id)
    _require_shipday_token(tenant, request)

    payload: Dict[str, Any] = await request.json()
    ts = _now_ts()

    event_id = _stable_event_id(payload)
    order_id = _extract_order_id(payload)
    normalized_status = _normalize_status(payload)
    driver_id = _extract_driver_id(payload)
    lat, lng = _extract_geo(payload)

    paths = _tenant_log_paths(tenant_id)

    _jsonl_append(
        paths["shipday_events"],
        {
            "ts": ts,
            "tenantId": tenant_id,
            "eventId": event_id,
            "orderId": order_id,
            "normalizedStatus": normalized_status,
            "headers": {
                "user-agent": request.headers.get("user-agent"),
                "x-forwarded-for": request.headers.get("x-forwarded-for"),
            },
            "payload": payload,
        },
    )

    if order_id:
        _jsonl_append(
            paths["justeat_drafts"],
            _justeat_draft(normalized_status, order_id, driver_id, lat, lng, ts),
        )

    jet_state = _map_shipday_to_jet_state(normalized_status)
    jet_result = None

    if order_id and jet_state:
        jet_body = _build_jet_deliverystate_payload(
            payload=payload,
            normalized_status=normalized_status,
            driver_id=driver_id,
            lat=lat,
            lng=lng,
        )

        jet_result = await _jet_put_deliverystate(
            tenant=tenant,
            order_id=order_id,
            state=jet_state,
            body=jet_body,
        )

        _jsonl_append(
            paths["justeat_out"],
            {
                "ts": ts,
                "tenantId": tenant_id,
                "eventId": event_id,
                "orderId": order_id,
                "normalizedStatus": normalized_status,
                "jetState": jet_state,
                "jetRequest": jet_body,
                "jetResult": jet_result,
            },
        )

    return {
        "ok": True,
        "tenantId": tenant_id,
        "eventId": event_id,
        "orderId": order_id,
        "normalizedStatus": normalized_status,
        "justeat": jet_result,
    }
