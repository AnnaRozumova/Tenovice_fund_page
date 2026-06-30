"""Pledge endpoints: list, upsert by email, and look up your own pledge.

- ``GET /pledges`` — anonymous public list (no identity fields).
- ``POST /pledges`` — create or update a pledge keyed by email; a returning pledger
  edits their own record. B4: one pledge = one supporter (the ``STATS`` tally, still
  stored under ``contributors_count``, is +1 on create / +0 on edit).
- ``GET /pledges/by-email`` — the caller's own pledge, projected to an explicit
  allowlist (never the raw item; the email is not echoed back — B1/H1).
"""
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from fastapi import APIRouter, Request

from api.config import localize, read_exchange_rate
from db import get_table
from domain.currency import CANONICAL_CURRENCY, convert_fields, normalize_amount, parse_currency
from domain.models import Pledge
from domain.pledge_math import calculate_pledge_values
from domain.validation import validate_pledge_input
from utils.http import json_response

router = APIRouter()


# Fields the caller may see about their own pledge. The raw DynamoDB item is never
# returned wholesale — we project an explicit allowlist so internal bookkeeping
# fields can't leak. The email is intentionally NOT echoed: the caller supplied it
# in the lookup query, so returning it discloses nothing and keeps it minimal (H1).
PLEDGE_FIELDS = (
    "amount",
    "is_monthly",
    "campaign_total",
    "message",
    "end_month",
    "end_year",
)


def _jwt_claims(request: Request) -> dict | None:
    """The verified Cognito JWT claims when the request passed the API-Gateway
    authorizer (AUTH3), else ``None``.

    API Gateway puts the validated token claims at
    ``requestContext.authorizer.jwt.claims``; Mangum exposes the raw event on the ASGI
    scope as ``aws.event``. The return value distinguishes two regimes, so the handlers
    can fail **closed**:

    - ``None`` — the app is running **without** the authorizer (local dev / tests). Only
      then may a handler trust a client-supplied email.
    - a ``dict`` (possibly empty) — the request is **authenticated**; identity must come
      from these claims. A client-supplied email is never trusted here, and a token that
      lacks the ``email`` claim (e.g. an *access* token instead of the id token — the
      gateway admits both) yields no email, so the handler rejects rather than falling
      back to attacker-controlled input.
    """
    event = request.scope.get("aws.event")
    if not isinstance(event, dict):
        return None
    authorizer = event.get("requestContext", {}).get("authorizer")
    if not isinstance(authorizer, dict):
        return None
    claims = authorizer.get("jwt", {}).get("claims")
    return claims if isinstance(claims, dict) else {}


def _claim_email(claims: dict) -> str | None:
    """The verified email from JWT claims, lowercased — or ``None`` if absent.

    Only the ``email`` claim is used: this pool signs in by email (cognito.py), the id
    token always carries a verified ``email``, and ``cognito:username`` would be the
    opaque user id (not an email) for an email-alias pool, so it must never be a fallback.
    """
    email = claims.get("email")
    return email.strip().lower() if email else None


@router.get("/pledges")
def list_pledges(currency: str | None = None):
    currency = parse_currency(currency)
    table = get_table()
    try:
        items = table.scan().get("Items", [])
        # Exclude the sentinel rows (STATS totals, CONFIG settings) — they are not
        # pledges; without this they leak into the public list as phantom rows.
        pledges = [
            {
                "amount": item.get("amount", Decimal("0")),
                "is_monthly": item.get("is_monthly", False),
                "campaign_total": item.get("campaign_total", Decimal("0")),
                "end_month": item.get("end_month"),
                "end_year": item.get("end_year"),
                "created_at": item.get("created_at"),
                "message": item.get("message"),
            }
            for item in items
            if item.get("pledgeID") not in ("STATS", "CONFIG")
        ]
        pledges.sort(key=lambda pledge: pledge.get("created_at") or "", reverse=True)
        if currency != CANONICAL_CURRENCY:
            rate = read_exchange_rate(table)
            for pledge in pledges:
                convert_fields(pledge, ("amount", "campaign_total"), currency, rate)
        return json_response(200, {"pledges": pledges, "currency": currency})
    except ClientError:
        return json_response(500, {"error": "Failed to list pledges"})


@router.get("/pledges/by-email")
def get_pledge_by_email(
    request: Request, email: str | None = None, currency: str | None = None
):
    currency = parse_currency(currency)
    # AUTH3: behind the gateway authorizer the identity is the verified email claim and
    # the client-supplied ?email= is ignored — so the query param can't be used to read
    # someone else's pledge (effectively a "my pledge" lookup). An authenticated request
    # with no email claim (e.g. an access token) is rejected, not served from client
    # input. The ?email= path is reached only with no authorizer (local dev / tests).
    claims = _jwt_claims(request)
    if claims is not None:
        identity = _claim_email(claims)
        if not identity:
            return json_response(401, {"error": "Unauthorized"})
    else:
        identity = email.strip().lower() if email else None
    if not identity:
        return json_response(400, {"message": "email query parameter is required"})

    table = get_table()
    try:
        result = table.query(
            IndexName="EmailIndex",
            KeyConditionExpression=Key("email").eq(identity),
            Limit=1,
        )
    except ClientError:
        return json_response(500, {"error": "Failed to look up pledge"})

    items = result.get("Items", [])
    if not items:
        return json_response(404, {"message": "not found"})

    item = items[0]
    projected = {field: item[field] for field in PLEDGE_FIELDS if field in item}
    return json_response(200, localize(table, projected, ("amount", "campaign_total"), currency))


@router.post("/pledges")
async def create_or_update_pledge(request: Request):
    currency = parse_currency(request.query_params.get("currency"))
    try:
        body = json.loads(await request.body() or b"{}")
    except json.JSONDecodeError:
        return json_response(400, {"error": "Invalid JSON in request body"})

    # AUTH3: a pledge is keyed to the *authenticated* user. Behind the gateway authorizer
    # the email comes from the verified claims and the body's email is ignored — that's
    # what stops one user from creating or editing a pledge under someone else's email.
    # An authenticated request with no email claim (e.g. an access token) is rejected
    # rather than falling back to the attacker-controlled body. With no authorizer (local
    # dev / tests) the body email is used and validated below.
    claims = _jwt_claims(request)
    if claims is not None:
        identity = _claim_email(claims)
        if not identity:
            return json_response(401, {"error": "Unauthorized"})
        body["email"] = identity

    table = get_table()

    # Normalize the incoming amount to the canonical currency (CZK) before validating,
    # so the cap and the stored value are always in whole koruna (D22).
    if currency != CANONICAL_CURRENCY:
        try:
            rate = read_exchange_rate(table)
        except ClientError:
            return json_response(500, {"error": "Failed to process pledge"})
        normalize_amount(body, currency, rate)

    try:
        validated = validate_pledge_input(body)
    except ValueError as e:
        return json_response(400, {"error": str(e)})

    try:
        existing_pledge = _find_pledge_by_email(table, validated["email"])
        if existing_pledge:
            return _update_existing_pledge(table, existing_pledge, validated)
        return _create_new_pledge(table, validated)
    except ClientError:
        return json_response(500, {"error": "Failed to process pledge"})


def _find_pledge_by_email(table, email: str):
    # Same query style as get_pledge_by_email above (the typed condition builder).
    # ``email`` is already normalized (validate_pledge_input lowercases it).
    result = table.query(
        IndexName="EmailIndex",
        KeyConditionExpression=Key("email").eq(email),
    )
    items = [item for item in result.get("Items", []) if item.get("pledgeID") != "STATS"]
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

    return json_response(
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

    return json_response(
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
