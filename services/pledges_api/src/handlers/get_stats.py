"""Return the running campaign totals (the STATS row)."""
import os
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from utils.response import response

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    table_name = os.environ["PLEDGES_TABLE_NAME"]
    table = dynamodb.Table(table_name)

    try:
        resp = table.get_item(Key={"pledgeID": "STATS"})
        stats = resp.get("Item")

        return response(
            200,
            {
                "pledged_total": stats.get("pledged_total", Decimal("0")),
                "contributors_count": stats.get("contributors_count", 0),
                "monthly_total": stats.get("monthly_total", Decimal("0")),
            },
        )

    except ClientError:
        return response(500, {"error": "Failed to fetch stats"})
