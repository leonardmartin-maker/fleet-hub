from math import radians, sin, cos, sqrt, atan2
from typing import Any, Dict, List, Optional


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return r * c


def suggest_best_driver(order: Dict[str, Any], drivers: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    data = order.get("data") or {}

    pickup_lat = data.get("pickupLatitude") or data.get("restaurantLatitude") or data.get("latitude")
    pickup_lng = data.get("pickupLongitude") or data.get("restaurantLongitude") or data.get("longitude")

    if pickup_lat is None or pickup_lng is None:
        return None

    best = None

    for d in drivers:
        lat = d.get("latitude")
        lng = d.get("longitude")

        if lat is None or lng is None:
            continue

        distance = haversine_km(float(pickup_lat), float(pickup_lng), float(lat), float(lng))

        candidate = {
            "id": d.get("id"),
            "name": d.get("name"),
            "latitude": lat,
            "longitude": lng,
            "distanceKm": round(distance, 2),
        }

        if best is None or candidate["distanceKm"] < best["distanceKm"]:
            best = candidate

    return best