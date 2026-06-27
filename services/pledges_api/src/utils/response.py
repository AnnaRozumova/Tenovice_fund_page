"""Shared HTTP response helpers for the pledges API Lambda handlers.

Every handler returns JSON, and DynamoDB hands numbers back as ``Decimal``. This
module centralizes both concerns — the JSON encoding (whole numbers as ``int``,
the rest as ``float``; EUR amounts and counts display as integers) and the
response envelope — so handlers don't each redefine their own.
"""
import json
from decimal import Decimal


class DecimalEncoder(json.JSONEncoder):
    """Encode DynamoDB ``Decimal`` values as ``int`` when whole, else ``float``."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return super().default(obj)


def response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }
