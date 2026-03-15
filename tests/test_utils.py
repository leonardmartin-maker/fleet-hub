"""Tests for utility functions."""

from app.utils import (
    extract_order_id,
    extract_driver_id,
    extract_geo,
    extract_justeat_restaurant_id,
    normalize_status,
    stable_event_id,
)


class TestExtractOrderId:
    def test_direct_orderId(self):
        assert extract_order_id({"orderId": "ABC-123"}) == "ABC-123"

    def test_nested_order_id(self):
        assert extract_order_id({"order": {"id": "X1"}}) == "X1"

    def test_order_number(self):
        assert extract_order_id({"orderNumber": "42"}) == "42"

    def test_missing_returns_none(self):
        assert extract_order_id({}) is None

    def test_empty_string_returns_none(self):
        assert extract_order_id({"orderId": "  "}) is None


class TestExtractDriverId:
    def test_direct(self):
        assert extract_driver_id({"driverId": "D1"}) == "D1"

    def test_nested(self):
        assert extract_driver_id({"driver": {"id": "D2"}}) == "D2"

    def test_missing(self):
        assert extract_driver_id({}) is None


class TestExtractGeo:
    def test_direct(self):
        assert extract_geo({"lat": 46.2, "lng": 6.1}) == (46.2, 6.1)

    def test_driver_location(self):
        assert extract_geo({"driverLocation": {"lat": 1.0, "lng": 2.0}}) == (1.0, 2.0)

    def test_missing(self):
        assert extract_geo({}) == (None, None)


class TestExtractJusteatRestaurantId:
    def test_direct(self):
        assert extract_justeat_restaurant_id({"restaurantId": "R1"}) == "R1"

    def test_nested_restaurant(self):
        assert extract_justeat_restaurant_id({"restaurant": {"id": "R2"}}) == "R2"

    def test_missing(self):
        assert extract_justeat_restaurant_id({}) is None


class TestNormalizeStatus:
    def test_assigned(self):
        assert normalize_status({"status": "assigned"}) == "driver_assigned"

    def test_delivered(self):
        assert normalize_status({"status": "delivered"}) == "delivered"

    def test_cancelled(self):
        assert normalize_status({"status": "cancelled"}) == "cancelled"

    def test_pickedup(self):
        assert normalize_status({"status": "pickedup"}) == "collected"

    def test_unknown(self):
        assert normalize_status({"status": "something_new"}) == "something_new"

    def test_empty(self):
        assert normalize_status({}) == "unknown"


class TestStableEventId:
    def test_uses_eventId_field(self):
        assert stable_event_id({"eventId": "EVT-1"}) == "EVT-1"

    def test_uses_id_field(self):
        assert stable_event_id({"id": "ID-2"}) == "ID-2"

    def test_generates_hash_if_no_id(self):
        result = stable_event_id({"foo": "bar"})
        assert len(result) == 32
        # Deterministic
        assert stable_event_id({"foo": "bar"}) == result
