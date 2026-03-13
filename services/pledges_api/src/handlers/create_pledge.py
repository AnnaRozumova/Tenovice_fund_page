"""Create pledge handler"""
import json
import os
import uuid
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError

from domain.validation import validate_pledge_input
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
    Create a new pledge.

    Expected body:
    {
        "name": "John Doe",
        "email": "john@example.com",
        "amount": 100,
        "is_monthly": true,
        "message": "Optional message"
    }
    """
    table_name = os.environ["PLEDGES_TABLE_NAME"]
    table = dynamodb.Table(table_name)

    # Parse request body
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return _response(400, {"error": "Invalid JSON in request body"})

    # Validate input
    is_valid, error_message = validate_pledge_input(body)
    if not is_valid:
        return _response(400, {"error": error_message})

    # Create pledge
    pledge_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    pledge = Pledge(
        pledge_id=pledge_id,
        name=body["name"].strip(),
        email=body["email"].strip().lower(),
        amount=int(body["amount"]),
        is_monthly=body["is_monthly"],
        created_at=created_at,
        message=body.get("message", "").strip() if body.get("message") else None,
    )

    # Save to DynamoDB
    try:
        table.put_item(Item=pledge.to_dynamodb_item())

        _update_stats(table, pledge)

        return _response(201, {
            "pledge_id": pledge.pledge_id,
            "message": "Pledge created successfully"
        })

    except ClientError as e:
        return _response(500, {"error": "Failed to create pledge", "detail": str(e)})


def _update_stats(table, pledge: Pledge):
    """
    Update the STATS record with new pledge data.
    """
    try:
        # Increment counters
        update_expression = "ADD pledged_total :amount, pledgers_count :one"
        expression_values = {
            ":amount": pledge.amount,
            ":one": 1,
            ":timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if pledge.is_monthly:
            update_expression += ", monthly_total :amount"

        update_expression += " SET updated_at = :timestamp"

        table.update_item(
            Key={"pledgeID": "STATS"},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
        )
    except ClientError:
        # Don't fail the whole request if stats update fails
        pass
