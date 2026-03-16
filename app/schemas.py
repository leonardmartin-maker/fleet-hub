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

# ── JET Connect webhook (eat.ch) ────────────────────────────────────

class JetConnectCoordinates(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class JetConnectAddress(BaseModel):
    model_config = {"extra": "allow"}

    line_one: Optional[str] = Field(None, alias="line1")
    line_two: Optional[str] = Field(None, alias="line2")
    city: Optional[str] = None
    postcode: Optional[str] = None
    coordinates: Optional[JetConnectCoordinates] = None


class JetConnectPerson(BaseModel):
    model_config = {"extra": "allow"}

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    phone_masking_code: Optional[str] = None
    email: Optional[str] = None
    coordinates: Optional[JetConnectCoordinates] = None


class JetConnectDelivery(BaseModel):
    model_config = {"extra": "allow"}

    address: Optional[JetConnectAddress] = None
    deliver_at: Optional[str] = None
    delivery_notes: Optional[str] = None


class JetConnectPrice(BaseModel):
    inc_tax: Optional[int] = None  # minor units (rappen/pence)
    tax: Optional[int] = None


class JetConnectItemPrice(BaseModel):
    inc_tax: Optional[int] = None


class JetConnectItem(BaseModel):
    model_config = {"extra": "allow"}

    name: Optional[str] = None
    plu: Optional[str] = None
    quantity: Optional[int] = 1
    price: Optional[JetConnectItemPrice] = None


class JetConnectPayment(BaseModel):
    model_config = {"extra": "allow"}

    items_in_cart: Optional[JetConnectPrice] = None
    final: Optional[JetConnectPrice] = None
    adjustments: Optional[List[Dict[str, Any]]] = None
    deposit: Optional[int] = None


class JetConnectLocation(BaseModel):
    id: Optional[str] = None
    timezone: Optional[str] = None


class JetConnectOrderPayload(BaseModel):
    model_config = {"extra": "allow"}

    id: str  # UUID from JET Connect
    third_party_order_reference: Optional[str] = None
    type: Optional[str] = None  # delivery-by-merchant, delivery-by-delivery-partner, collection-by-customer
    posLocationId: Optional[str] = None
    location: Optional[JetConnectLocation] = None
    items: Optional[List[JetConnectItem]] = None
    created_at: Optional[str] = None
    deliver_at: Optional[str] = None
    collect_at: Optional[str] = None
    delivery_notes: Optional[str] = None
    kitchen_notes: Optional[str] = None
    payment_method: Optional[str] = None  # CARD, CASH
    payment: Optional[JetConnectPayment] = None
    delivery: Optional[JetConnectPerson] = None  # delivery person/address info
    driver: Optional[Dict[str, Any]] = None
    collector: Optional[Dict[str, Any]] = None
    promotions: Optional[List[Dict[str, Any]]] = None
    extras: Optional[Dict[str, Any]] = None


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
