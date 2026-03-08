from typing import Any, Dict, Optional
from fastapi import HTTPException
import httpx

from app.config import JET_BASE_URL
from app.utils import iso_utc_now


def jet_headers(tenant: Dict[str, Any]) -> Dict[str, str]:
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


def map_shipday_to_jet_state(normalized_status: str) -> Optional[str]:
    mapping = {
        "to_restaurant": "torestaurant",
        "at_restaurant": "atrestaurant",
        "collected": "collected",
        "to_customer": "tocustomer",
        "delivered": "delivered",
        "cancelled": "cancelled",
    }
    return mapping.get(normalized_status)


def build_deliverystate_payload(
    normalized_status: str,
    driver_id: Optional[str],
    lat: Optional[float],
    lng: Optional[float],
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "TimeStampWithUtcOffset": iso_utc_now(),
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
        body["EtaAtDeliveryAddress"] = iso_utc_now()

    return body


async def put_deliverystate(
    tenant: Dict[str, Any],
    order_id: str,
    state: str,
    body: Dict[str, Any],
) -> Dict[str, Any]:
    url = f"{JET_BASE_URL}/orders/{order_id}/deliverystate/{state}"
    headers = jet_headers(tenant)
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