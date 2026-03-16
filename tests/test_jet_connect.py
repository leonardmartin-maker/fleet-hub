"""Tests for JET Connect (eat.ch) integration."""

import hashlib
import hmac
import base64
import json
import time

import pytest

from app.services.jet_connect import (
    validate_hmac,
    map_jet_connect_to_shipday,
    _build_name,
    _build_address,
)


# ── HMAC Validation Tests ────────────────────────────────────────────


class TestValidateHmac:

    def _make_hmac_header(self, body: bytes, secret: str, timestamp_ms: int = None) -> str:
        """Helper to generate a valid HMAC header."""
        if timestamp_ms is None:
            timestamp_ms = int(time.time() * 1000)

        sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
        sig_b64 = base64.b64encode(sig).decode("utf-8")

        return f"HMAC-SHA256 t={timestamp_ms},signature={sig_b64}"

    def test_valid_hmac(self):
        body = b'{"id":"order-123","posLocationId":"loc-1"}'
        secret = "my-secret-key"
        header = self._make_hmac_header(body, secret)

        assert validate_hmac(body, header, secret) is True

    def test_invalid_signature(self):
        body = b'{"id":"order-123"}'
        secret = "my-secret-key"
        header = self._make_hmac_header(body, "wrong-secret")

        assert validate_hmac(body, header, secret) is False

    def test_tampered_body(self):
        body = b'{"id":"order-123"}'
        secret = "my-secret-key"
        header = self._make_hmac_header(body, secret)

        tampered_body = b'{"id":"order-456"}'
        assert validate_hmac(tampered_body, header, secret) is False

    def test_expired_timestamp(self):
        body = b'{"id":"order-123"}'
        secret = "my-secret-key"
        old_ts = int((time.time() - 600) * 1000)  # 10 minutes ago
        header = self._make_hmac_header(body, secret, timestamp_ms=old_ts)

        assert validate_hmac(body, header, secret, max_age_seconds=300) is False

    def test_empty_header(self):
        body = b'{"id":"order-123"}'
        assert validate_hmac(body, "", "secret") is False

    def test_empty_secret(self):
        body = b'{"id":"order-123"}'
        header = "HMAC-SHA256 t=123,signature=abc"
        assert validate_hmac(body, header, "") is False

    def test_malformed_header(self):
        body = b'{"id":"order-123"}'
        assert validate_hmac(body, "INVALID_FORMAT", "secret") is False
        assert validate_hmac(body, "HMAC-SHA256 no_params", "secret") is False

    def test_fresh_timestamp(self):
        body = b'{"id":"order-123"}'
        secret = "my-secret-key"
        now_ms = int(time.time() * 1000)
        header = self._make_hmac_header(body, secret, timestamp_ms=now_ms)

        assert validate_hmac(body, header, secret, max_age_seconds=300) is True


# ── Mapping Tests ────────────────────────────────────────────────────


class TestMapJetConnectToShipday:

    SAMPLE_TENANT = {
        "tenantId": "test-cafe",
        "restaurantName": "Test Cafe",
        "jet_connect": {
            "pos_location_id": "loc-123",
            "hmac_secret": "secret",
            "api_key": "api-key",
            "price_divisor": 100,
        },
        "shipday": {
            "api_key": "shipday-key",
        },
        "defaults": {
            "restaurantName": "Test Cafe",
            "restaurantAddress": "Rue du Lac 14, 1007 Lausanne",
            "restaurantPhoneNumber": "+41789415042",
        },
    }

    SAMPLE_PAYLOAD = {
        "id": "abc-123-def-456",
        "third_party_order_reference": "REF-001",
        "type": "delivery-by-merchant",
        "posLocationId": "loc-123",
        "deliver_at": "2026-03-16T12:30:00+01:00",
        "payment_method": "CARD",
        "delivery": {
            "first_name": "Jean",
            "last_name": "Dupont",
            "phone_number": "+41791234567",
            "email": "jean@example.com",
            "coordinates": {
                "latitude": 46.5197,
                "longitude": 6.6323,
            },
        },
        "items": [
            {
                "name": "Margherita Pizza",
                "quantity": 2,
                "price": {"inc_tax": 1850},  # 18.50 CHF in rappen
            },
            {
                "name": "Coca-Cola",
                "quantity": 1,
                "price": {"inc_tax": 350},  # 3.50 CHF
            },
        ],
        "payment": {
            "final": {"inc_tax": 4050, "tax": 300},
        },
        "kitchen_notes": "Sans oignons",
        "delivery_notes": "3eme etage, code 1234",
    }

    def test_basic_mapping(self):
        result = map_jet_connect_to_shipday(self.SAMPLE_TENANT, self.SAMPLE_PAYLOAD)

        assert result["orderNumber"] == "abc-123-def-456"
        assert result["additionalId"] == "abc-123-def-456"
        assert result["orderSource"] == "eat.ch"
        assert result["customerName"] == "Jean Dupont"
        assert result["customerPhoneNumber"] == "+41791234567"
        assert result["restaurantName"] == "Test Cafe"
        assert result["restaurantAddress"] == "Rue du Lac 14, 1007 Lausanne"

    def test_price_conversion(self):
        result = map_jet_connect_to_shipday(self.SAMPLE_TENANT, self.SAMPLE_PAYLOAD)

        # 2 * 18.50 + 1 * 3.50 = 40.50
        assert result["totalOrderCost"] == 40.50

    def test_payment_method(self):
        result = map_jet_connect_to_shipday(self.SAMPLE_TENANT, self.SAMPLE_PAYLOAD)
        assert result["paymentMethod"] == "credit_card"

        cash_payload = {**self.SAMPLE_PAYLOAD, "payment_method": "CASH"}
        result2 = map_jet_connect_to_shipday(self.SAMPLE_TENANT, cash_payload)
        assert result2["paymentMethod"] == "cash"

    def test_delivery_coordinates(self):
        result = map_jet_connect_to_shipday(self.SAMPLE_TENANT, self.SAMPLE_PAYLOAD)
        assert result["deliveryLatitude"] == 46.5197
        assert result["deliveryLongitude"] == 6.6323

    def test_delivery_time(self):
        result = map_jet_connect_to_shipday(self.SAMPLE_TENANT, self.SAMPLE_PAYLOAD)
        assert result["expectedDeliveryDate"] == "2026-03-16"
        assert result["expectedDeliveryTime"] == "12:30"

    def test_notes(self):
        result = map_jet_connect_to_shipday(self.SAMPLE_TENANT, self.SAMPLE_PAYLOAD)
        assert "Sans oignons" in result["deliveryInstruction"]
        assert "3eme etage" in result["deliveryInstruction"]

    def test_items_mapping(self):
        result = map_jet_connect_to_shipday(self.SAMPLE_TENANT, self.SAMPLE_PAYLOAD)
        assert len(result["orderItem"]) == 2
        assert result["orderItem"][0] == {"name": "Margherita Pizza", "quantity": 2}
        assert result["orderItem"][1] == {"name": "Coca-Cola", "quantity": 1}

    def test_missing_delivery_person(self):
        payload = {**self.SAMPLE_PAYLOAD, "delivery": None}
        result = map_jet_connect_to_shipday(self.SAMPLE_TENANT, payload)

        assert result["customerName"] == "Client eat.ch"  # fallback
        assert result["customerPhoneNumber"] == ""

    def test_empty_items(self):
        payload = {**self.SAMPLE_PAYLOAD, "items": []}
        result = map_jet_connect_to_shipday(self.SAMPLE_TENANT, payload)

        assert result["orderItem"] == []
        # Should fallback to payment.final
        assert result["totalOrderCost"] == 40.50

    def test_custom_price_divisor(self):
        tenant = {
            **self.SAMPLE_TENANT,
            "jet_connect": {**self.SAMPLE_TENANT["jet_connect"], "price_divisor": 1000},
        }
        result = map_jet_connect_to_shipday(tenant, self.SAMPLE_PAYLOAD)

        # 2 * 1.85 + 1 * 0.35 = 4.05
        assert result["totalOrderCost"] == 4.05


# ── Helper Function Tests ────────────────────────────────────────────


class TestBuildName:

    def test_full_name(self):
        assert _build_name({"first_name": "Jean", "last_name": "Dupont"}) == "Jean Dupont"

    def test_first_name_only(self):
        assert _build_name({"first_name": "Jean"}) == "Jean"

    def test_empty(self):
        assert _build_name({}) == ""

    def test_masked_name(self):
        assert _build_name({"first_name": "***", "last_name": "***"}) == "*** ***"


class TestBuildAddress:

    def test_full_address(self):
        addr = {
            "line_one": "Rue du Lac 14",
            "line_two": "App 3",
            "city": "Lausanne",
            "postcode": "1007",
        }
        result = _build_address(addr)
        assert result == "Rue du Lac 14, App 3, 1007 Lausanne"

    def test_line1_only(self):
        addr = {"line_one": "Rue du Lac 14"}
        assert _build_address(addr) == "Rue du Lac 14"

    def test_alias_keys(self):
        addr = {"line1": "Main St 5", "city": "Zurich", "postcode": "8001"}
        assert _build_address(addr) == "Main St 5, 8001 Zurich"

    def test_empty(self):
        assert _build_address({}) == ""
        assert _build_address(None) == ""
