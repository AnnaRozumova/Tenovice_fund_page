"""Docstring"""
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
        resp = table.get_item(Key={"pledgeID": "STATS"})
        stats = resp.get("Item")
        
        return _response(
            200,
            {
                "pledged_total": stats.get("pledged_total", Decimal("0")),
                "contributors_count": stats.get("contributors_count", 0),
                "monthly_total": stats.get("monthly_total", Decimal("0")),
            },
        )

    except ClientError as e:
        return _response(
            500,
            {
                "error": "Failed to fetch stats",
                "detail": str(e),
            },
        )
