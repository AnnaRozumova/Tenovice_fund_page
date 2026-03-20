"""List all pledges anonymously"""
import json
import os
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError


dynamodb = boto3.resource("dynamodb")

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def _response(status: int, body: dict):
    return {
        "statusCode": status,
        "headers": {
            "content-type": "application/json",
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }


def handler(event, context):
    table_name = os.environ["PLEDGES_TABLE_NAME"]
    table = dynamodb.Table(table_name)

    try:
        response = table.scan()
        items = response.get("Items", [])

        pledges = []
        for item in items:
            if item.get("pledgeID") == "STATS":
                continue

            pledges.append(
                {
                    "amount": item.get("amount", Decimal("0")),
                    "is_monthly": item.get("is_monthly", False),
                    "contributors_count": item.get("contributors_count", 0),
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

        return _response(200, {"pledges": pledges})

    except ClientError as e:
        return _response(
            500,
            {
                "error": "Failed to list pledges",
                "detail": str(e),
            },
        )
