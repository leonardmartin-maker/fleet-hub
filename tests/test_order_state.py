"""Tests for order state computation."""

from app.services.order_state import _compute_status, _status_rank


class TestStatusRank:
    def test_known_statuses(self):
        assert _status_rank("received") < _status_rank("created")
        assert _status_rank("created") < _status_rank("driver_assigned")
        assert _status_rank("driver_assigned") < _status_rank("delivered")

    def test_unknown_status(self):
        assert _status_rank("bogus") == -1


class TestComputeStatus:
    def test_empty_events(self):
        assert _compute_status([]) == "received"

    def test_created_event(self):
        events = [{"event_type": "shipday.order.created", "payload": {}}]
        assert _compute_status(events) == "created"

    def test_status_progression(self):
        events = [
            {"event_type": "shipday.order.created", "payload": {}},
            {
                "event_type": "shipday.status.received",
                "payload": {"normalizedStatus": "driver_assigned"},
            },
        ]
        assert _compute_status(events) == "driver_assigned"

    def test_no_regression(self):
        events = [
            {
                "event_type": "shipday.status.received",
                "payload": {"normalizedStatus": "delivered"},
            },
            {
                "event_type": "shipday.status.received",
                "payload": {"normalizedStatus": "created"},
            },
        ]
        assert _compute_status(events) == "delivered"
