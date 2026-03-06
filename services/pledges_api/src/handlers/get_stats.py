"""Docstring"""
import json
import os
import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")

def _response(status: int, body: dict):
    return {
        "statusCode": status,
        "headers": {
            "content-type": "application/json",
        },
        "body": json.dumps(body),
    }


def handler(event, context):
    table_name = os.environ["PLEDGES_TABLE_NAME"]
    table = dynamodb.Table(table_name)

    try:
        resp = table.get_item(Key={"pledgeID": "STATS"})
        item = resp.get("Item")
        if not item:
            return _response(
                200,
                {
                    "pledged_total": 0,
                    "pledgers_count": 0,
                    "monthly_total": 0,
                },
            )

        return _response(
            200,
            {
                "pledged_total": int(item.get("pledged_total", 0)),
                "pledgers_count": int(item.get("pledgers_count", 0)),
                "monthly_total": int(item.get("monthly_total", 0)),
                "updated_at": item.get("updated_at"),
            },
        )

    except ClientError as e:
        return _response(500, {"error": "DynamoDB error", "detail": str(e)})
