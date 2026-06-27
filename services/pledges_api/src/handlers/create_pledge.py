"""Upsert pledge handler (create or update by email)"""
import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from domain.models import Pledge
from domain.pledge_math import calculate_pledge_values
from domain.validation import validate_pledge_input
from utils.response import response

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    table_name = os.environ["PLEDGES_TABLE_NAME"]
    table = dynamodb.Table(table_name)

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return response(400, {"error": "Invalid JSON in request body"})

    try:
        validated = validate_pledge_input(body)
    except ValueError as e:
        return response(400, {"error": str(e)})

    email = validated["email"]

    try:
        existing_pledge = _find_pledge_by_email(table, email)

        if existing_pledge:
            return _update_existing_pledge(table, existing_pledge, validated)

        return _create_new_pledge(table, validated)

    except ClientError as e:
        return response(500, {"error": "Failed to process pledge", "detail": str(e)})


def _find_pledge_by_email(table, email: str):
    response = table.query(
        IndexName="EmailIndex",
        KeyConditionExpression="email = :email",
        ExpressionAttributeValues={":email": email},
    )
    items = response.get("Items", [])
    items = [item for item in items if item.get("pledgeID") != "STATS"]

    if items:
        return Pledge.from_dynamodb_item(items[0])

    return None


def _create_new_pledge(table, data: dict):
    pledge_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    amount: Decimal = data["amount"]
    is_monthly: bool = data["is_monthly"]
    end_month: int | None = data["end_month"]
    end_year: int | None = data["end_year"]

    campaign_total, monthly_value = calculate_pledge_values(
        amount=amount,
        is_monthly=is_monthly,
        end_month=end_month,
        end_year=end_year,
    )

    pledge = Pledge(
        pledge_id=pledge_id,
        email=data["email"],
        amount=amount,
        is_monthly=is_monthly,
        created_at=timestamp,
        campaign_total=campaign_total,
        message=data.get("message"),
        end_month=end_month,
        end_year=end_year,
        updated_at=None,
    )

    table.put_item(Item=pledge.to_dynamodb_item())

    # A new pledge is one new supporter (B4: 1 pledge = 1 supporter).
    _adjust_stats(
        table,
        pledged_total_delta=campaign_total,
        supporters_delta=1,
        monthly_total_delta=monthly_value,
    )

    return response(
        201,
        {
            "pledge_id": pledge.pledge_id,
            "message": "Pledge created successfully",
        },
    )


def _update_existing_pledge(table, existing_pledge: Pledge, data: dict):
    new_amount: Decimal = data["amount"]
    new_is_monthly: bool = data["is_monthly"]
    new_end_month: int | None = data["end_month"]
    new_end_year: int | None = data["end_year"]
    new_message = data.get("message")
    updated_at = datetime.now(timezone.utc).isoformat()

    old_campaign_total: Decimal = existing_pledge.campaign_total
    old_monthly_value: Decimal = (
        existing_pledge.amount if existing_pledge.is_monthly else Decimal("0")
    )

    new_campaign_total, new_monthly_value = calculate_pledge_values(
        amount=new_amount,
        is_monthly=new_is_monthly,
        end_month=new_end_month,
        end_year=new_end_year,
    )

    pledged_total_delta = new_campaign_total - old_campaign_total
    monthly_total_delta = new_monthly_value - old_monthly_value
    # Editing a pledge is still the same one supporter — no change to the count.

    set_parts = [
        "email = :email",
        "amount = :amount",
        "is_monthly = :is_monthly",
        "campaign_total = :campaign_total",
        "updated_at = :updated_at",
    ]
    remove_parts = []

    expression_values = {
        ":email": data["email"],
        ":amount": new_amount,
        ":is_monthly": new_is_monthly,
        ":campaign_total": new_campaign_total,
        ":updated_at": updated_at,
    }

    if new_message is not None:
        set_parts.append("message = :message")
        expression_values[":message"] = new_message
    else:
        remove_parts.append("message")

    if new_is_monthly:
        set_parts.append("end_month = :end_month")
        set_parts.append("end_year = :end_year")
        expression_values[":end_month"] = new_end_month
        expression_values[":end_year"] = new_end_year
    else:
        remove_parts.extend(["end_month", "end_year"])

    update_expression = "SET " + ", ".join(set_parts)
    if remove_parts:
        update_expression += " REMOVE " + ", ".join(remove_parts)

    table.update_item(
        Key={"pledgeID": existing_pledge.pledge_id},
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_values,
    )

    _adjust_stats(
        table,
        pledged_total_delta=pledged_total_delta,
        supporters_delta=0,
        monthly_total_delta=monthly_total_delta,
    )

    return response(
        200,
        {
            "pledge_id": existing_pledge.pledge_id,
            "message": "Pledge updated successfully",
        },
    )


def _adjust_stats(
    table,
    pledged_total_delta: Decimal,
    supporters_delta: int,
    monthly_total_delta: Decimal,
):
    # The STATS supporter tally is still stored under ``contributors_count`` (the
    # field the frontend reads); since B4 it counts pledges (1 per supporter), not
    # a per-pledge group size — +1 on create, +0 on edit.
    update_expression = "ADD pledged_total :pledged_total_delta, contributors_count :supporters_delta"
    expression_values = {
        ":pledged_total_delta": pledged_total_delta,
        ":supporters_delta": supporters_delta,
        ":timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if monthly_total_delta != Decimal("0"):
        update_expression += ", monthly_total :monthly_total_delta"
        expression_values[":monthly_total_delta"] = monthly_total_delta

    update_expression += " SET updated_at = :timestamp"

    table.update_item(
        Key={"pledgeID": "STATS"},
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_values,
    )