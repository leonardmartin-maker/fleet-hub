"""Pydantic models for webhook payload validation."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── JustEat webhook ──────────────────────────────────────────────────

class JustEatCustomer(BaseModel):
    name: Optional[str] = Field(None, alias="name")
    phone: Optional[str] = Field(None, alias="phone")
    fullName: Optional[str] = None
    phoneNumber: Optional[str] = None


class JustEatDelivery(BaseModel):
    address: Any = None
    deliveryAddress: Optional[str] = None


class JustEatItem(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    quantity: Optional[int] = Field(None, ge=0)
    qty: Optional[int] = None
    price: Optional[float] = None
    unitPrice: Optional[float] = None
    amount: Optional[float] = None


class JustEatWebhookPayload(BaseModel):
    model_config = {"extra": "allow"}

    orderId: Optional[str] = None
    order_id: Optional[str] = None
    orderNumber: Optional[str] = None
    id: Optional[str] = None
    restaurantId: Optional[str] = None
    restaurant_id: Optional[str] = None
    posLocationId: Optional[str] = None
    customer: Optional[JustEatCustomer] = None
    delivery: Optional[JustEatDelivery] = None
    items: Optional[List[JustEatItem]] = None
    order: Optional[Dict[str, Any]] = None
    restaurant: Optional[Dict[str, Any]] = None


# ── Shipday Client webhook ───────────────────────────────────────────

class ShipdayOrder(BaseModel):
    model_config = {"extra": "allow"}

    id: Optional[int] = None
    order_number: Optional[str] = None


class ShipdayCarrier(BaseModel):
    model_config = {"extra": "allow"}

    id: Optional[int] = None
    name: Optional[str] = None
    phone: Optional[str] = None


class ShipdayLocation(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None


class ShipdayPickupDetails(BaseModel):
    model_config = {"extra": "allow"}

    location: Optional[ShipdayLocation] = None


class ShipdayDeliveryDetails(BaseModel):
    model_config = {"extra": "allow"}

    location: Optional[ShipdayLocation] = None


class ShipdayClientWebhookPayload(BaseModel):
    model_config = {"extra": "allow"}

    event: Optional[str] = None
    order_status: Optional[str] = None
    order: Optional[ShipdayOrder] = None
    orderId: Optional[str] = None
    orderNumber: Optional[str] = None
    carrier: Optional[ShipdayCarrier] = None
    pickup_details: Optional[ShipdayPickupDetails] = None
    delivery_details: Optional[ShipdayDeliveryDetails] = None
    trackingUrl: Optional[str] = None
    thirdPartyDeliveryOrder: Optional[Dict[str, Any]] = None


# ── Shipday Fleet webhook ────────────────────────────────────────────

class ShipdayDriverLocation(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None


class ShipdayDriver(BaseModel):
    model_config = {"extra": "allow"}

    id: Optional[int] = None
    name: Optional[str] = None


class ShipdayFleetWebhookPayload(BaseModel):
    model_config = {"extra": "allow"}

    orderId: Optional[str] = None
    orderNumber: Optional[str] = None
    driver: Optional[ShipdayDriver] = None
    driverLocation: Optional[ShipdayDriverLocation] = None
