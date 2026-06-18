"""Admin-only write of the editable CONFIG row (balance / goal / breakdown).

Guarded by a single shared secret (decision D6): the caller sends it as a bearer
token over HTTPS and we compare it in **constant time** against ``ADMIN_SECRET``.
The secret is injected from SSM / Secrets Manager at deploy (D13) — never committed,
never logged. Cognito would be overkill for a single trusted editor (Anna). The
matching public read path is ``get_config`` (C1).

Fails closed: if no secret is configured, every request is rejected.
"""
import hmac
import json
import os

import boto3
from botocore.exceptions import ClientError

from domain.validation import validate_config_input
from utils.response import response

dynamodb = boto3.resource("dynamodb")

_BEARER_PREFIX = "Bearer "


def _is_authorized(event) -> bool:
    secret = os.environ.get("ADMIN_SECRET", "")
    if not secret:
        # No secret configured → deny everything rather than allow.
        return False

    headers = event.get("headers") or {}
    # API Gateway lowercases header names, but be defensive about casing.
    auth = headers.get("authorization") or headers.get("Authorization") or ""

    if not auth.startswith(_BEARER_PREFIX):
        return False

    provided = auth[len(_BEARER_PREFIX):]
    return hmac.compare_digest(provided, secret)


def handler(event, context):
    if not _is_authorized(event):
        return response(401, {"error": "Unauthorized"})

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return response(400, {"error": "Invalid JSON in request body"})

    try:
        validated = validate_config_input(body)
    except ValueError as e:
        return response(400, {"error": str(e)})

    table_name = os.environ["PLEDGES_TABLE_NAME"]
    table = dynamodb.Table(table_name)

    try:
        table.put_item(
            Item={
                "pledgeID": "CONFIG",
                "current_balance": validated["current_balance"],
                "fundraising_goal": validated["fundraising_goal"],
                "breakdown": validated["breakdown"],
            }
        )
    except ClientError as e:
        return response(500, {"error": "Failed to update config", "detail": str(e)})

    return response(200, {"message": "Config updated"})
