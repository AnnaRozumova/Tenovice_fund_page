"""Shared JSON encoding for the pledges API.

DynamoDB hands numbers back as ``Decimal``; ``DecimalEncoder`` serializes whole
values as ``int`` and the rest as ``float`` (EUR amounts and counts display as
integers). The FastAPI response wrapper (``utils.http.DecimalJSONResponse``) reuses
this encoder so every route encodes numbers the same way.
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
