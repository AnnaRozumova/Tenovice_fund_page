"""List all pledges anonymously"""
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
        scan_result = table.scan()
        items = scan_result.get("Items", [])

        pledges = []
        for item in items:
            if item.get("pledgeID") == "STATS":
                continue

            pledges.append(
                {
                    "amount": item.get("amount", Decimal("0")),
                    "is_monthly": item.get("is_monthly", False),
                    "campaign_total": item.get("campaign_total", Decimal("0")),
                    "end_month": item.get("end_month"),
                    "end_year": item.get("end_year"),
                    "created_at": item.get("created_at"),
                    "message": item.get("message"),
                }
            )

        pledges.sort(
            key=lambda pledge: pledge.get("created_at") or "",
            reverse=True,
        )

        return response(200, {"pledges": pledges})

    except ClientError as e:
        return response(
            500,
            {
                "error": "Failed to list pledges",
                "detail": str(e),
            },
        )
