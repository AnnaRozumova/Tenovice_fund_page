"""Get pledge handler"""
import json
import os
import boto3
from botocore.exceptions import ClientError

from domain.models import Pledge

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
    """
    Get a pledge by ID.

    Expected path parameter: pledgeID
    """
    table_name = os.environ["PLEDGES_TABLE_NAME"]
    table = dynamodb.Table(table_name)

    # Extract pledge ID from path parameters
    pledge_id = event.get("pathParameters", {}).get("pledgeID")

    if not pledge_id:
        return _response(400, {"error": "Missing pledgeID in path"})

    # Prevent fetching the STATS record
    if pledge_id == "STATS":
        return _response(404, {"error": "Pledge not found"})

    try:
        response = table.get_item(Key={"pledgeID": pledge_id})

        item = response.get("Item")
        if not item:
            return _response(404, {"error": "Pledge not found"})

        # Convert DynamoDB item to Pledge model and return
        pledge = Pledge.from_dynamodb_item(item)

        return _response(200, {
            "pledge_id": pledge.pledge_id,
            "name": pledge.name,
            "email": pledge.email,
            "amount": pledge.amount,
            "is_monthly": pledge.is_monthly,
            "created_at": pledge.created_at,
            "message": pledge.message,
        })

    except ClientError as e:
        return _response(500, {"error": "Failed to retrieve pledge", "detail": str(e)})
