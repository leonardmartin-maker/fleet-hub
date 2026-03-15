"""Tests for dispatch service (haversine + driver suggestion)."""

from app.services.dispatch import haversine_km, suggest_best_driver


class TestHaversine:
    def test_same_point(self):
        assert haversine_km(46.2, 6.1, 46.2, 6.1) == 0.0

    def test_known_distance(self):
        # Geneva (46.2044, 6.1432) to Lausanne (46.5197, 6.6323) ~ 52 km
        d = haversine_km(46.2044, 6.1432, 46.5197, 6.6323)
        assert 50 < d < 55


class TestSuggestBestDriver:
    def test_returns_closest_driver(self):
        order = {"data": {"pickupLatitude": 46.2, "pickupLongitude": 6.1}}
        drivers = [
            {"id": 1, "name": "Far", "latitude": 47.0, "longitude": 7.0},
            {"id": 2, "name": "Close", "latitude": 46.21, "longitude": 6.11},
        ]
        best = suggest_best_driver(order, drivers)
        assert best["id"] == 2
        assert best["distanceKm"] < 2

    def test_no_pickup_coords(self):
        order = {"data": {}}
        drivers = [{"id": 1, "name": "A", "latitude": 46.0, "longitude": 6.0}]
        assert suggest_best_driver(order, drivers) is None

    def test_no_drivers(self):
        order = {"data": {"pickupLatitude": 46.2, "pickupLongitude": 6.1}}
        assert suggest_best_driver(order, []) is None

    def test_driver_without_coords_skipped(self):
        order = {"data": {"pickupLatitude": 46.2, "pickupLongitude": 6.1}}
        drivers = [
            {"id": 1, "name": "NoGPS"},
            {"id": 2, "name": "HasGPS", "latitude": 46.21, "longitude": 6.11},
        ]
        best = suggest_best_driver(order, drivers)
        assert best["id"] == 2
