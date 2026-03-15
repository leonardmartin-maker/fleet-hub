"""Tests for JustEat service (status mapping, payload building)."""

from app.services.justeat import map_shipday_to_jet_state, build_deliverystate_payload


class TestMapShipdayToJetState:
    def test_driver_assigned(self):
        assert map_shipday_to_jet_state("driver_assigned") == "torestaurant"

    def test_collected(self):
        assert map_shipday_to_jet_state("collected") == "collected"

    def test_delivered(self):
        assert map_shipday_to_jet_state("delivered") == "delivered"

    def test_unknown_returns_none(self):
        assert map_shipday_to_jet_state("received") is None
        assert map_shipday_to_jet_state("created") is None

    def test_cancelled(self):
        assert map_shipday_to_jet_state("cancelled") == "cancelled"


class TestBuildDeliverystatePayload:
    def test_basic_payload(self):
        body = build_deliverystate_payload("driver_assigned", "D1", None, None)
        assert body["DriverId"] == "D1"
        assert "TimeStampWithUtcOffset" in body
        assert "Location" not in body

    def test_with_location(self):
        body = build_deliverystate_payload("to_customer", "D2", 46.2, 6.1)
        assert body["Location"]["Latitude"] == 46.2
        assert body["Location"]["Longitude"] == 6.1

    def test_eta_added_for_some_statuses(self):
        body = build_deliverystate_payload("collected", "D1", None, None)
        assert "EtaAtDeliveryAddress" in body

    def test_no_eta_for_driver_assigned(self):
        body = build_deliverystate_payload("driver_assigned", "D1", None, None)
        assert "EtaAtDeliveryAddress" not in body

    def test_unknown_driver_fallback(self):
        body = build_deliverystate_payload("to_customer", None, None, None)
        assert body["DriverId"] == "unknown-driver"
