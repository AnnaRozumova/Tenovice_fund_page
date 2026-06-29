"""Unit tests for the shared Decimal JSON encoding (Phase B / B2, kept through R1).

DynamoDB numbers come back as ``Decimal``; ``DecimalEncoder`` locks the encoding
(whole numbers as int, others as float). The FastAPI response wrapper
(``utils.http.DecimalJSONResponse``) reuses this exact encoder.
"""
import json
from decimal import Decimal

from utils.response import DecimalEncoder


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
