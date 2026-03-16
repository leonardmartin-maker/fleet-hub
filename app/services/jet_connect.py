"""JET Connect (eat.ch) integration service.

Handles HMAC validation, order mapping to Shipday format,
and async acknowledgment callbacks to the JET Connect API.
"""

import hashlib
import hmac
import base64
import json
import time
from typing import Any, Dict, Optional

import httpx

from app.config import JET_CONNECT_BASE_URL, logger
from app.utils import iso_utc_now, pick, extract_order_id


# ── HMAC-SHA256 Validation ──────────────────────────────────────────


def validate_hmac(
    raw_body: bytes,
    header_value: str,
    secret: str,
    max_age_seconds: int = 300,
) -> bool:
    """Validate the X-JET-Connect-Hash HMAC-SHA256 signature.

    Header format: HMAC-SHA256 t={unix_ms},signature={base64_sig}

    Args:
        raw_body: Raw request body bytes.
        header_value: Value of X-JET-Connect-Hash header.
        secret: Shared HMAC secret for this tenant.
        max_age_seconds: Maximum age of the timestamp (default 5 minutes).

    Returns:
        True if the signature is valid and timestamp is fresh.
    """
    if not header_value or not secret:
        return False

    try:
        # Parse header: "HMAC-SHA256 t=1234567890,signature=abc123=="
        parts = header_value.strip().split(" ", 1)
        if len(parts) != 2 or parts[0] != "HMAC-SHA256":
            return False

        params = {}
        for param in parts[1].split(","):
            key, _, value = param.partition("=")
            params[key.strip()] = value.strip()

        timestamp_ms = int(params.get("t", "0"))
        provided_signature = params.get("signature", "")

        if not timestamp_ms or not provided_signature:
            return False

        # Check timestamp freshness (prevent replay attacks)
        now_ms = int(time.time() * 1000)
        age_seconds = abs(now_ms - timestamp_ms) / 1000
        if age_seconds > max_age_seconds:
            logger.warning(
                "JET Connect HMAC timestamp too old: %.0fs (max %ds)",
                age_seconds,
                max_age_seconds,
            )
            return False

        # Compute expected HMAC
        computed = hmac.new(
            secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).digest()
        computed_b64 = base64.b64encode(computed).decode("utf-8")

        return hmac.compare_digest(computed_b64, provided_signature)

    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("JET Connect HMAC validation error: %s", exc)
        return False


# ── Headers for outbound JET Connect API calls ──────────────────────


def jet_connect_headers(tenant: Dict[str, Any]) -> Dict[str, str]:
    """Build headers for outbound JET Connect API calls."""
    jc = tenant.get("jet_connect") or {}
    api_key = jc.get("api_key") or ""
    return {
        "X-Flyt-Api-Key": api_key,
        "x-jet-application": "fleet-hub/1.0",
        "Content-Type": "application/json",
    }


def get_jet_connect_base_url(tenant: Dict[str, Any]) -> str:
    """Get the JET Connect base URL for this tenant."""
    jc = tenant.get("jet_connect") or {}
    return jc.get("base_url") or JET_CONNECT_BASE_URL


# ── Order Mapping: JET Connect → Shipday ────────────────────────────


def map_jet_connect_to_shipday(
    tenant: Dict[str, Any],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Transform a JET Connect order payload into Shipday order format.

    JET Connect prices are in minor units (rappen for CHF, pence for GBP).
    Customer data may be masked with asterisks.
    """
    defaults = tenant.get("defaults") or {}
    jc = tenant.get("jet_connect") or {}
    price_divisor = jc.get("price_divisor", 100)

    jet_order_id = payload.get("id", "UNKNOWN")

    # ── Customer info ──
    delivery_person = payload.get("delivery") or {}
    customer_name = _build_name(delivery_person)
    customer_phone = delivery_person.get("phone_number") or ""
    customer_email = delivery_person.get("email") or ""

    # ── Delivery address ──
    # In JET Connect, address may be in extras or a separate structure
    extras = payload.get("extras") or {}
    address_obj = extras.get("delivery_address") or {}

    # Try to build address from delivery person coordinates + notes
    customer_address = _build_address(address_obj)

    # Fallback: use delivery notes as address hint
    if not customer_address:
        delivery_notes = payload.get("delivery_notes") or ""
        customer_address = delivery_notes

    # ── Coordinates for pickup/delivery ──
    delivery_coords = delivery_person.get("coordinates") or {}
    delivery_lat = delivery_coords.get("latitude")
    delivery_lng = delivery_coords.get("longitude")

    # ── Restaurant info (from tenant defaults) ──
    restaurant_name = defaults.get("restaurantName", "")
    restaurant_address = defaults.get("restaurantAddress", "")
    restaurant_phone = defaults.get("restaurantPhoneNumber", "")

    # ── Items ──
    items = payload.get("items") or []
    order_items = []
    total_cost = 0.0

    for item in items:
        if not isinstance(item, dict):
            continue

        name = item.get("name") or "Item"
        qty = item.get("quantity") or 1

        try:
            qty = int(qty)
        except (ValueError, TypeError):
            qty = 1

        order_items.append({"name": str(name), "quantity": qty})

        # Price in minor units
        price_obj = item.get("price") or {}
        price_minor = price_obj.get("inc_tax") if isinstance(price_obj, dict) else None
        if price_minor is not None:
            try:
                total_cost += float(price_minor) / price_divisor * qty
            except (ValueError, TypeError):
                pass

    # ── Payment total (fallback) ──
    payment = payload.get("payment") or {}
    final_payment = payment.get("final") or {}
    if final_payment.get("inc_tax") is not None and total_cost == 0:
        try:
            total_cost = float(final_payment["inc_tax"]) / price_divisor
        except (ValueError, TypeError):
            pass

    # ── Delivery time ──
    deliver_at = payload.get("deliver_at") or ""

    shipday_payload: Dict[str, Any] = {
        "customerName": customer_name or "Client eat.ch",
        "customerAddress": customer_address or restaurant_address,
        "customerPhoneNumber": customer_phone or "",
        "customerEmail": customer_email,
        "restaurantName": restaurant_name,
        "restaurantAddress": restaurant_address,
        "restaurantPhoneNumber": restaurant_phone,
        "orderItem": order_items,
        "totalOrderCost": round(total_cost, 2),
        "paymentMethod": "credit_card" if payload.get("payment_method") == "CARD" else "cash",
        "deliveryFee": 0,
        "tax": 0,
        "tips": 0,
        "discountAmount": 0,
        "orderSource": "eat.ch",
        "additionalId": str(jet_order_id),
        "orderNumber": str(jet_order_id),
    }

    # Add delivery coordinates if available
    if delivery_lat is not None and delivery_lng is not None:
        shipday_payload["deliveryLatitude"] = delivery_lat
        shipday_payload["deliveryLongitude"] = delivery_lng

    # Add pickup coordinates from defaults if available
    pickup_lat = defaults.get("pickupLatitude")
    pickup_lng = defaults.get("pickupLongitude")
    if pickup_lat is not None and pickup_lng is not None:
        shipday_payload["pickupLatitude"] = pickup_lat
        shipday_payload["pickupLongitude"] = pickup_lng

    # Add expected delivery time
    if deliver_at:
        shipday_payload["expectedDeliveryDate"] = deliver_at[:10]  # YYYY-MM-DD
        shipday_payload["expectedDeliveryTime"] = deliver_at[11:16]  # HH:MM

    # Add kitchen/delivery notes
    notes_parts = []
    if payload.get("kitchen_notes"):
        notes_parts.append(f"Cuisine: {payload['kitchen_notes']}")
    if payload.get("delivery_notes"):
        notes_parts.append(f"Livraison: {payload['delivery_notes']}")
    if notes_parts:
        shipday_payload["deliveryInstruction"] = " | ".join(notes_parts)

    return shipday_payload


def _build_name(person: Dict[str, Any]) -> str:
    """Build full name from first_name + last_name."""
    first = person.get("first_name") or ""
    last = person.get("last_name") or ""
    full = f"{first} {last}".strip()
    return full if full else ""


def _build_address(address: Dict[str, Any]) -> str:
    """Build a full address string from JET Connect address object."""
    if not address:
        return ""

    parts = []
    line1 = address.get("line_one") or address.get("line1") or ""
    line2 = address.get("line_two") or address.get("line2") or ""
    city = address.get("city") or ""
    postcode = address.get("postcode") or ""

    if line1:
        parts.append(line1)
    if line2:
        parts.append(line2)
    if postcode and city:
        parts.append(f"{postcode} {city}")
    elif city:
        parts.append(city)
    elif postcode:
        parts.append(postcode)

    return ", ".join(parts)


# ── Async Acknowledgment ────────────────────────────────────────────


async def acknowledge_success(
    tenant: Dict[str, Any],
    jet_order_id: str,
) -> Dict[str, Any]:
    """Notify JET Connect that the order was successfully processed.

    Must be called within 3 minutes of receiving a 202 response.
    POST /order/{id}/sent-to-pos-success
    """
    base_url = get_jet_connect_base_url(tenant)
    url = f"{base_url}/order/{jet_order_id}/sent-to-pos-success"
    headers = jet_connect_headers(tenant)
    body = {"happenedAt": iso_utc_now()}
    timeout = httpx.Timeout(15.0, connect=10.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=body)
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
    except Exception as exc:
        logger.error("JET Connect ack success failed for %s: %s", jet_order_id, exc)
        return {
            "ok": False,
            "status": 0,
            "response": {"error": str(exc)},
            "url": url,
        }


async def acknowledge_failure(
    tenant: Dict[str, Any],
    jet_order_id: str,
    error_code: str,
    error_message: str,
) -> Dict[str, Any]:
    """Notify JET Connect that the order processing failed.

    Must be called within 3 minutes of receiving a 202 response.
    POST /order/{id}/sent-to-pos-failed
    """
    base_url = get_jet_connect_base_url(tenant)
    url = f"{base_url}/order/{jet_order_id}/sent-to-pos-failed"
    headers = jet_connect_headers(tenant)
    body = {
        "happenedAt": iso_utc_now(),
        "errorCode": error_code,
        "errorMessage": error_message,
    }
    timeout = httpx.Timeout(15.0, connect=10.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=body)
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
    except Exception as exc:
        logger.error("JET Connect ack failure failed for %s: %s", jet_order_id, exc)
        return {
            "ok": False,
            "status": 0,
            "response": {"error": str(exc)},
            "url": url,
        }
