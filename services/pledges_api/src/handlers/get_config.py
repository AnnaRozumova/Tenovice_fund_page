"""Return the editable campaign config (balance, goal, 3-direction breakdown).

The numbers Anna can edit live in a single ``CONFIG`` row (``pledgeID="CONFIG"``),
mirroring the ``STATS`` row. If the row — or any field — is absent the handler
falls back to documented defaults, so the endpoint and the site keep working
before the row is ever seeded (the writer is added in C2; real values in F2).
"""
import os
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from utils.response import response

dynamodb = boto3.resource("dynamodb")

# Defaults used until the CONFIG row is seeded. The breakdown stores stable
# identifier keys (not display names): the localized CZ/EN labels live in the
# frontend i18n dictionary (D3), keeping content out of the data layer. The goal
# and per-direction amounts are provisional pending Anna's confirmation.
DEFAULT_CURRENT_BALANCE = Decimal("320000")
DEFAULT_FUNDRAISING_GOAL = Decimal("2700000")
DEFAULT_BREAKDOWN = [
    {"key": "new_gompa", "amount": Decimal("1200000")},
    {"key": "sangha_house", "amount": Decimal("1200000")},
    {"key": "basecamp_north", "amount": Decimal("320000")},
]


def handler(event, context):
    table_name = os.environ["PLEDGES_TABLE_NAME"]
    table = dynamodb.Table(table_name)

    try:
        resp = table.get_item(Key={"pledgeID": "CONFIG"})
        config = resp.get("Item") or {}

        return response(
            200,
            {
                "current_balance": config.get("current_balance", DEFAULT_CURRENT_BALANCE),
                "fundraising_goal": config.get("fundraising_goal", DEFAULT_FUNDRAISING_GOAL),
                "breakdown": config.get("breakdown", DEFAULT_BREAKDOWN),
            },
        )

    except ClientError as e:
        return response(
            500,
            {
                "error": "Failed to fetch config",
                "detail": str(e),
            },
        )
