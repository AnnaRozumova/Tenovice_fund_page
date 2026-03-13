"""List all pledges anonymously"""
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
    """
    List all pledges anonymously.

    Returns only public information: amount, is_monthly, created_at, updated_at, message.
    Does NOT return: name, email, pledgeID (to maintain anonymity).
    """
    table_name = os.environ["PLEDGES_TABLE_NAME"]
    table = dynamodb.Table(table_name)

    try:
        # Scan all items
        response = table.scan()
        items = response.get("Items", [])

        # Filter out STATS record
        pledges = [item for item in items if item.get("pledgeID") != "STATS"]

        # Return only public/anonymous fields
        anonymous_pledges = []
        for pledge in pledges:
            anonymous_pledges.append({
                "amount": int(pledge.get("amount", 0)),
                "is_monthly": bool(pledge.get("is_monthly", False)),
                "created_at": pledge.get("created_at"),
                "updated_at": pledge.get("updated_at"),
                "message": pledge.get("message"),
            })

        # Sort by created_at descending (newest first)
        anonymous_pledges.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return _response(200, {
            "pledges": anonymous_pledges,
            "count": len(anonymous_pledges)
        })

    except ClientError as e:
        return _response(500, {"error": "Failed to list pledges", "detail": str(e)})
