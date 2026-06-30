"""``GET /stats`` — the running campaign totals (the ``STATS`` row)."""
from decimal import Decimal

from botocore.exceptions import ClientError
from fastapi import APIRouter

from api.config import localize
from db import get_table
from domain.currency import parse_currency
from utils.http import json_response

router = APIRouter()


@router.get("/stats")
def get_stats(currency: str | None = None):
    currency = parse_currency(currency)
    table = get_table()
    try:
        # The STATS row is absent until the first pledge (fresh table) — default to
        # an empty dict so the totals fall back to zero instead of 500ing (P1).
        stats = table.get_item(Key={"pledgeID": "STATS"}).get("Item") or {}
        body = {
            "pledged_total": stats.get("pledged_total", Decimal("0")),
            # contributors_count is a people count, never a money amount — not converted.
            "contributors_count": stats.get("contributors_count", 0),
            "monthly_total": stats.get("monthly_total", Decimal("0")),
        }
        # Tags currency + converts the two money fields (reads the rate only if needed).
        return json_response(200, localize(table, body, ("pledged_total", "monthly_total"), currency))
    except ClientError:
        return json_response(500, {"error": "Failed to fetch stats"})
