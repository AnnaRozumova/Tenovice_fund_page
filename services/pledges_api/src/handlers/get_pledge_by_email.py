"""Docstring"""
import json
import os
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key


dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["PLEDGES_TABLE_NAME"])


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return super().default(obj)


def response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }


def handler(event, context):
    params = event.get("queryStringParameters") or {}
    email = params.get("email")

    if not email:
        return response(400, {"message": "email query parameter is required"})

    result = table.query(
        IndexName="EmailIndex",
        KeyConditionExpression=Key("email").eq(email),
        Limit=1,
    )

    items = result.get("Items", [])

    if not items:
        return response(404, {"message": "not found"})

    return response(200, items[0])
