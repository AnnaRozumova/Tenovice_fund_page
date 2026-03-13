"""Update pledge handler"""
import json
import os
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError

from domain.validation import validate_pledge_input

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
    Update an existing pledge.

    Expected path parameter: pledgeID
    Expected body (all fields optional):
    {
        "name": "John Doe",
        "email": "john@example.com",
        "amount": 100,
        "is_monthly": true,
        "message": "Updated message"
    }
    """
    table_name = os.environ["PLEDGES_TABLE_NAME"]
    table = dynamodb.Table(table_name)

    # Extract pledge ID from path parameters
    pledge_id = event.get("pathParameters", {}).get("pledgeID")

    if not pledge_id:
        return _response(400, {"error": "Missing pledgeID in path"})

    # Prevent updating the STATS record
    if pledge_id == "STATS":
        return _response(403, {"error": "Cannot update this resource"})

    # Parse request body
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return _response(400, {"error": "Invalid JSON in request body"})

    if not body:
        return _response(400, {"error": "Request body cannot be empty"})

    # Check if pledge exists
    try:
        response = table.get_item(Key={"pledgeID": pledge_id})
        if "Item" not in response:
            return _response(404, {"error": "Pledge not found"})
    except ClientError as e:
        return _response(500, {"error": "Failed to retrieve pledge", "detail": str(e)})

    # Build update expression dynamically based on provided fields
    update_parts = []
    expression_values = {}
    expression_names = {}

    # Validate and prepare updates
    if "name" in body:
        name = body["name"].strip()
        if not name or len(name) < 2 or len(name) > 100:
            return _response(400, {"error": "Name must be between 2 and 100 characters"})
        update_parts.append("#name = :name")
        expression_values[":name"] = name
        expression_names["#name"] = "name"

    if "email" in body:
        import re
        email = body["email"].strip().lower()
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return _response(400, {"error": "Invalid email format"})
        update_parts.append("email = :email")
        expression_values[":email"] = email

    if "amount" in body:
        try:
            amount = int(body["amount"])
            if amount < 1 or amount > 1000000:
                return _response(400, {"error": "Amount must be between 1 and 1,000,000"})
            update_parts.append("amount = :amount")
            expression_values[":amount"] = amount
        except (ValueError, TypeError):
            return _response(400, {"error": "Amount must be a valid integer"})

    if "is_monthly" in body:
        if not isinstance(body["is_monthly"], bool):
            return _response(400, {"error": "is_monthly must be a boolean"})
        update_parts.append("is_monthly = :is_monthly")
        expression_values[":is_monthly"] = body["is_monthly"]

    if "message" in body:
        message = body["message"]
        if message is None:
            update_parts.append("message = :message")
            expression_values[":message"] = None
        else:
            if not isinstance(message, str):
                return _response(400, {"error": "Message must be a string"})
            if len(message) > 500:
                return _response(400, {"error": "Message must be less than 500 characters"})
            message = message.strip()
            update_parts.append("message = :message")
            expression_values[":message"] = message if message else None

    # Add updated_at timestamp
    update_parts.append("updated_at = :updated_at")
    expression_values[":updated_at"] = datetime.now(timezone.utc).isoformat()

    # Build update expression
    update_expression = "SET " + ", ".join(update_parts)

    # Update the pledge
    try:
        update_params = {
            "Key": {"pledgeID": pledge_id},
            "UpdateExpression": update_expression,
            "ExpressionAttributeValues": expression_values,
            "ReturnValues": "ALL_NEW",
        }

        if expression_names:
            update_params["ExpressionAttributeNames"] = expression_names

        result = table.update_item(**update_params)

        updated_item = result["Attributes"]

        return _response(200, {
            "pledge_id": updated_item["pledgeID"],
            "name": updated_item["name"],
            "email": updated_item["email"],
            "amount": int(updated_item["amount"]),
            "is_monthly": bool(updated_item["is_monthly"]),
            "created_at": updated_item["created_at"],
            "updated_at": updated_item.get("updated_at"),
            "message": updated_item.get("message"),
        })

    except ClientError as e:
        return _response(500, {"error": "Failed to update pledge", "detail": str(e)})
