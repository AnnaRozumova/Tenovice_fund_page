"""Campaign config: ``GET /config`` (public read) and ``POST /config`` (admin write).

The editable numbers (balance, goal, 3-direction breakdown) live in a single
``CONFIG`` row, mirroring ``STATS``. The read path falls back to documented defaults
when the row is absent (C1). The write path is admin-only (D6): a shared secret sent
as a bearer token, compared in **constant time** against ``ADMIN_SECRET``; it fails
closed (no secret configured → 401) and never logs the secret.
"""
import hmac
import json
import os

from botocore.exceptions import ClientError
from fastapi import APIRouter, Request

from config_defaults import (
    DEFAULT_BREAKDOWN,
    DEFAULT_CURRENT_BALANCE,
    DEFAULT_FUNDRAISING_GOAL,
)
from db import get_table
from domain.validation import validate_config_input
from utils.http import json_response

router = APIRouter()

_BEARER_PREFIX = "Bearer "


@router.get("/config")
def get_config():
    table = get_table()
    try:
        config = table.get_item(Key={"pledgeID": "CONFIG"}).get("Item") or {}
        return json_response(
            200,
            {
                "current_balance": config.get("current_balance", DEFAULT_CURRENT_BALANCE),
                "fundraising_goal": config.get("fundraising_goal", DEFAULT_FUNDRAISING_GOAL),
                "breakdown": config.get("breakdown", DEFAULT_BREAKDOWN),
            },
        )
    except ClientError:
        return json_response(500, {"error": "Failed to fetch config"})


def _is_authorized(request: Request) -> bool:
    secret = os.environ.get("ADMIN_SECRET", "")
    if not secret:
        # No secret configured → deny everything rather than allow (fail closed).
        return False

    # Starlette headers are case-insensitive, so this also matches "Authorization".
    auth = request.headers.get("authorization") or ""
    if not auth.startswith(_BEARER_PREFIX):
        return False

    provided = auth[len(_BEARER_PREFIX):]
    return hmac.compare_digest(provided, secret)


@router.post("/config")
async def update_config(request: Request):
    if not _is_authorized(request):
        return json_response(401, {"error": "Unauthorized"})

    try:
        body = json.loads(await request.body() or b"{}")
    except json.JSONDecodeError:
        return json_response(400, {"error": "Invalid JSON in request body"})

    try:
        validated = validate_config_input(body)
    except ValueError as e:
        return json_response(400, {"error": str(e)})

    table = get_table()
    try:
        table.put_item(
            Item={
                "pledgeID": "CONFIG",
                "current_balance": validated["current_balance"],
                "fundraising_goal": validated["fundraising_goal"],
                "breakdown": validated["breakdown"],
            }
        )
    except ClientError:
        return json_response(500, {"error": "Failed to update config"})

    return json_response(200, {"message": "Config updated"})
