"""Tests for Pydantic schema validation."""

from app.schemas import (
    JustEatWebhookPayload,
    ShipdayClientWebhookPayload,
    ShipdayFleetWebhookPayload,
)


class TestJustEatSchema:
    def test_valid_payload(self):
        p = JustEatWebhookPayload(
            orderId="123",
            restaurantId="R1",
            customer={"name": "John", "phone": "+41123"},
        )
        assert p.orderId == "123"
        assert p.customer.name == "John"

    def test_extra_fields_allowed(self):
        p = JustEatWebhookPayload(orderId="1", unknownField="ok")
        assert p.orderId == "1"

    def test_empty_payload(self):
        p = JustEatWebhookPayload()
        assert p.orderId is None


class TestShipdayClientSchema:
    def test_valid_payload(self):
        p = ShipdayClientWebhookPayload(
            event="ORDER_DELIVERED",
            order={"id": 42, "order_number": "ORD-1"},
        )
        assert p.event == "ORDER_DELIVERED"
        assert p.order.id == 42

    def test_with_carrier(self):
        p = ShipdayClientWebhookPayload(
            carrier={"id": 5, "name": "Driver A"},
        )
        assert p.carrier.id == 5


class TestShipdayFleetSchema:
    def test_valid_payload(self):
        p = ShipdayFleetWebhookPayload(
            orderId="X1",
            driver={"id": 10},
            driverLocation={"lat": 46.2, "lng": 6.1},
        )
        assert p.orderId == "X1"
        assert p.driverLocation.lat == 46.2
