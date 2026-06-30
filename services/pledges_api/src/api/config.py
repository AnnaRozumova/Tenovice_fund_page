"""Campaign config: ``GET /config`` (public read) and ``POST /config`` (admin write).

The editable numbers (balance, goal, 3-direction breakdown, exchange rate) live in a
single ``CONFIG`` row, mirroring ``STATS``. The read path falls back to documented
defaults when the row is absent (C1) and converts amounts to the requested currency
(D22). The write path is admin-only (D6): a shared secret sent as a bearer token,
compared in **constant time** against ``ADMIN_SECRET``; it fails closed (no secret
configured → 401) and never logs the secret.

This module also owns the shared "where the exchange rate comes from" helpers
(``exchange_rate_of`` / ``read_exchange_rate``) and the response ``localize`` helper, so
every route reads the rate and converts amounts the same way (D19 — logic in one place).
"""
import hmac
import json
import os
from decimal import Decimal

from botocore.exceptions import ClientError
from fastapi import APIRouter, Request

from config_defaults import (
    DEFAULT_BREAKDOWN,
    DEFAULT_CURRENT_BALANCE,
    DEFAULT_EXCHANGE_RATE,
    DEFAULT_FUNDRAISING_GOAL,
)
from db import get_table
from domain.currency import CANONICAL_CURRENCY, convert_fields, parse_currency, to_display
from domain.validation import validate_config_input
from utils.http import json_response

router = APIRouter()

_BEARER_PREFIX = "Bearer "


def exchange_rate_of(config_item: dict) -> Decimal:
    """The CZK→EUR rate from a CONFIG item dict, falling back to the documented default.

    One place owns the key name + default, so a caller that already holds the CONFIG
    item (get_config, update_config) reuses it instead of re-reading or re-deriving.
    """
    return config_item.get("exchange_rate", DEFAULT_EXCHANGE_RATE)


def read_exchange_rate(table) -> Decimal:
    """Read the current CZK→EUR rate from the ``CONFIG`` row (default if the row is unset).

    For routes that don't otherwise read CONFIG (stats, pledges). Routes that already
    load the CONFIG item should call ``exchange_rate_of(item)`` to avoid a second read.
    """
    config = table.get_item(Key={"pledgeID": "CONFIG"}).get("Item") or {}
    return exchange_rate_of(config)


def localize(table, body: dict, fields, currency: str) -> dict:
    """Tag ``body`` with ``currency`` and convert its named CZK money fields to it.

    The single read+convert+tag path for flat response dicts (stats, by-email): reads
    the rate only when a conversion is actually needed.
    """
    body["currency"] = currency
    if currency != CANONICAL_CURRENCY:
        convert_fields(body, fields, currency, read_exchange_rate(table))
    return body


@router.get("/config")
def get_config(currency: str | None = None):
    currency = parse_currency(currency)
    table = get_table()
    try:
        config = table.get_item(Key={"pledgeID": "CONFIG"}).get("Item") or {}
    except ClientError:
        return json_response(500, {"error": "Failed to fetch config"})

    rate = exchange_rate_of(config)

    # Convert a fresh copy of the breakdown so the shared DEFAULT_BREAKDOWN (a
    # module-level list) is never mutated. Tolerate an item without 'amount' (a
    # hand-edited CONFIG item) instead of raising on the EUR path.
    breakdown = config.get("breakdown", DEFAULT_BREAKDOWN)
    if currency != CANONICAL_CURRENCY:
        converted = []
        for item in breakdown:
            new_item = dict(item)
            if new_item.get("amount") is not None:
                new_item["amount"] = to_display(Decimal(new_item["amount"]), currency, rate)
            converted.append(new_item)
        breakdown = converted

    body = {
        "current_balance": config.get("current_balance", DEFAULT_CURRENT_BALANCE),
        "fundraising_goal": config.get("fundraising_goal", DEFAULT_FUNDRAISING_GOAL),
        "breakdown": breakdown,
        # The rate itself is currency-independent — always returned as stored.
        "exchange_rate": rate,
        "currency": currency,
    }
    convert_fields(body, ("current_balance", "fundraising_goal"), currency, rate)
    return json_response(200, body)


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
        # Preserve the existing exchange rate when the caller doesn't send one, so a
        # tool that only edits the numbers (admin.html) can't wipe a console-set rate.
        existing = table.get_item(Key={"pledgeID": "CONFIG"}).get("Item") or {}
        exchange_rate = validated.get("exchange_rate", exchange_rate_of(existing))
        table.put_item(
            Item={
                "pledgeID": "CONFIG",
                "current_balance": validated["current_balance"],
                "fundraising_goal": validated["fundraising_goal"],
                "breakdown": validated["breakdown"],
                "exchange_rate": exchange_rate,
            }
        )
    except ClientError:
        return json_response(500, {"error": "Failed to update config"})

    return json_response(200, {"message": "Config updated"})
