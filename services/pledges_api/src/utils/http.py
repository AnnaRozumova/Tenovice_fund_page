"""FastAPI JSON responses that encode DynamoDB ``Decimal`` values.

Starlette's default ``JSONResponse`` can't serialize ``Decimal``, but the API
speaks in DynamoDB Decimals (EUR amounts, counts). This reuses the project's
existing ``DecimalEncoder`` (``utils.response``) so every route encodes numbers the
same way — whole values as ``int``, the rest as ``float`` — and ``json_response``
mirrors the old Lambda ``response(status, body)`` so route code stays familiar.
"""
import json

from fastapi.responses import JSONResponse

from utils.response import DecimalEncoder


class DecimalJSONResponse(JSONResponse):
    """A ``JSONResponse`` that serializes DynamoDB Decimals via ``DecimalEncoder``."""

    def render(self, content) -> bytes:
        return json.dumps(content, cls=DecimalEncoder).encode("utf-8")


def json_response(status_code: int, body: dict) -> DecimalJSONResponse:
    """Build a JSON response with an explicit status code (mirrors ``response()``)."""
    return DecimalJSONResponse(content=body, status_code=status_code)
