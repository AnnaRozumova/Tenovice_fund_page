"""Unit tests for the shared response util (Phase B / B2).

All handlers route their JSON through ``utils.response`` — this locks the
Decimal encoding (whole numbers as int, others as float) and the envelope shape.
"""
import json
from decimal import Decimal

from utils.response import DecimalEncoder, response


class TestDecimalEncoder:
    def test_whole_decimal_serializes_as_int(self):
        out = json.dumps({"x": Decimal("100")}, cls=DecimalEncoder)
        assert out == '{"x": 100}'

    def test_fractional_decimal_serializes_as_float(self):
        out = json.dumps({"x": Decimal("12.50")}, cls=DecimalEncoder)
        assert json.loads(out)["x"] == 12.5

    def test_non_decimal_falls_through(self):
        out = json.dumps({"a": "s", "b": True, "c": None}, cls=DecimalEncoder)
        assert json.loads(out) == {"a": "s", "b": True, "c": None}


class TestResponse:
    def test_envelope_shape(self):
        result = response(201, {"ok": True})
        assert result["statusCode"] == 201
        assert result["headers"]["Content-Type"] == "application/json"
        assert json.loads(result["body"]) == {"ok": True}

    def test_body_encodes_decimals(self):
        result = response(200, {"pledged_total": Decimal("228150"), "rate": Decimal("0.5")})
        body = json.loads(result["body"])
        assert body["pledged_total"] == 228150
        assert body["rate"] == 0.5
