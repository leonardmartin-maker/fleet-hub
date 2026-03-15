"""Tests for Shipday client status normalization."""

from app.routes.shipday_client import normalize_shipday_client_status


class TestNormalizeShipdayClientStatus:
    def test_order_delivered(self):
        assert normalize_shipday_client_status({"event": "ORDER_DELIVERED"}) == "delivered"

    def test_order_driverassigned(self):
        assert normalize_shipday_client_status({"event": "ORDER_DRIVERASSIGNED"}) == "driver_assigned"

    def test_order_pickedup(self):
        assert normalize_shipday_client_status({"event": "ORDER_PICKEDUP"}) == "collected"

    def test_order_cancelled(self):
        assert normalize_shipday_client_status({"event": "ORDER_CANCELLED"}) == "cancelled"

    def test_driver_unassigned(self):
        assert normalize_shipday_client_status({"event": "DRIVER_UNASSIGNED"}) == "created"

    def test_status_fallback(self):
        assert normalize_shipday_client_status({"order_status": "ON_THE_WAY"}) == "to_customer"

    def test_timestamp_fallback_delivered(self):
        assert normalize_shipday_client_status({
            "order": {"delivery_time": "2026-01-01T12:00:00"}
        }) == "delivered"

    def test_timestamp_fallback_assigned(self):
        assert normalize_shipday_client_status({
            "order": {"assigned_time": "2026-01-01T12:00:00"}
        }) == "driver_assigned"

    def test_unknown(self):
        assert normalize_shipday_client_status({}) is None
