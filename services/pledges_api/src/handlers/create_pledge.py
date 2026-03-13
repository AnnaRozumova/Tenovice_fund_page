"""Upsert pledge handler (create or update by email)"""
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
    Upsert a pledge by email.

    If email exists: updates the existing pledge and adjusts stats.
    If email is new: creates a new pledge and adds to stats.

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

    email = body["email"].strip().lower()

    try:
        # Query existing pledge by email using GSI
        existing_pledge = _find_pledge_by_email(table, email)

        if existing_pledge:
            # Update existing pledge
            return _update_existing_pledge(table, existing_pledge, body)
        else:
            # Create new pledge
            return _create_new_pledge(table, body)

    except ClientError as e:
        return _response(500, {"error": "Failed to process pledge", "detail": str(e)})


def _find_pledge_by_email(table, email: str):
    """Query pledge by email using GSI"""
    try:
        response = table.query(
            IndexName="EmailIndex",
            KeyConditionExpression="email = :email",
            ExpressionAttributeValues={":email": email}
        )
        items = response.get("Items", [])

        # Filter out STATS record if it somehow has an email
        items = [item for item in items if item.get("pledgeID") != "STATS"]

        if items:
            return Pledge.from_dynamodb_item(items[0])
        return None
    except ClientError:
        return None


def _create_new_pledge(table, body: dict):
    """Create a new pledge and add to stats"""
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
    table.put_item(Item=pledge.to_dynamodb_item())

    # Add to stats
    _adjust_stats(table, amount_delta=pledge.amount, count_delta=1,
                  monthly_delta=pledge.amount if pledge.is_monthly else 0)

    return _response(201, {
        "pledge_id": pledge.pledge_id,
        "message": "Pledge created successfully"
    })


def _update_existing_pledge(table, existing_pledge: Pledge, body: dict):
    """Update existing pledge and adjust stats"""
    # Calculate deltas
    old_amount = existing_pledge.amount
    old_monthly = existing_pledge.amount if existing_pledge.is_monthly else 0

    new_amount = int(body["amount"])
    new_is_monthly = body["is_monthly"]
    new_monthly = new_amount if new_is_monthly else 0

    amount_delta = new_amount - old_amount
    monthly_delta = new_monthly - old_monthly

    # Update pledge record
    update_expression = "SET #name = :name, amount = :amount, is_monthly = :is_monthly, updated_at = :updated_at"
    expression_values = {
        ":name": body["name"].strip(),
        ":amount": new_amount,
        ":is_monthly": new_is_monthly,
        ":updated_at": datetime.now(timezone.utc).isoformat(),
    }
    expression_names = {"#name": "name"}

    # Update message if provided
    message = body.get("message", "").strip() if body.get("message") else None
    if message is not None:
        update_expression += ", message = :message"
        expression_values[":message"] = message

    table.update_item(
        Key={"pledgeID": existing_pledge.pledge_id},
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_values,
        ExpressionAttributeNames=expression_names,
    )

    # Adjust stats by delta (no change in count)
    _adjust_stats(table, amount_delta=amount_delta, count_delta=0, monthly_delta=monthly_delta)

    return _response(200, {
        "pledge_id": existing_pledge.pledge_id,
        "message": "Pledge updated successfully"
    })


def _adjust_stats(table, amount_delta: int, count_delta: int, monthly_delta: int):
    """
    Adjust STATS record by delta values.

    Args:
        amount_delta: Change in total pledged amount (can be negative)
        count_delta: Change in pledger count (0 or 1)
        monthly_delta: Change in monthly total (can be negative)
    """
    try:
        update_expression = "ADD pledged_total :amount_delta, pledgers_count :count_delta"
        expression_values = {
            ":amount_delta": amount_delta,
            ":count_delta": count_delta,
            ":timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if monthly_delta != 0:
            update_expression += ", monthly_total :monthly_delta"
            expression_values[":monthly_delta"] = monthly_delta

        update_expression += " SET updated_at = :timestamp"

        table.update_item(
            Key={"pledgeID": "STATS"},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
        )
    except ClientError:
        # Don't fail the whole request if stats update fails
        pass
