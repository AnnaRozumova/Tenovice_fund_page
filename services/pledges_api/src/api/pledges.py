"""Pledge endpoints: list, create, edit/delete your own, and read your own pledges.

Since Phase M one account (email) may hold **several** pledges (D23), added, edited,
and deleted independently over the multi-year campaign — the old "one pledge per
email" upsert is gone. Storage is unchanged: each pledge is its own DynamoDB item
(``pledgeID`` PK), grouped by the non-unique ``email`` attribute via the ``EmailIndex``
GSI (variant B).

- ``GET /pledges`` — anonymous public list (no identity fields), every pledge row.
- ``POST /pledges`` — **always create** a new pledge for the caller. The supporter
  tally (``STATS.contributors_count``) counts **distinct emails**: +1 only on an
  account's *first* pledge, +0 for further ones.
- ``PUT /pledges/{id}`` — edit one of the caller's own pledges (owner-checked).
- ``DELETE /pledges/{id}`` — delete one of the caller's own pledges (owner-checked);
  −1 supporter only when it was the account's *last* pledge.
- ``GET /pledges/by-email`` — the caller's **own pledges** as a list, each projected to
  an explicit allowlist plus its ``pledge_id`` (so the owner can address edit/delete).
  The email is never echoed; ``pledge_id`` stays off the public list (B1/H1).
"""
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from fastapi import APIRouter, Request

from api.config import read_exchange_rate
from db import get_table
from domain.currency import CANONICAL_CURRENCY, convert_fields, normalize_amount, parse_currency
from domain.models import Pledge
from domain.pledge_math import calculate_pledge_values
from domain.validation import validate_pledge_input
from utils.http import json_response

router = APIRouter()

# Rows that are not pledges. They carry no ``email`` attribute, so they never appear in
# the EmailIndex — but the by-email/list paths filter defensively anyway.
_SENTINEL_IDS = ("STATS", "CONFIG")

# Anti-abuse cap on how many pledges one account (email) may hold. Since D23 there is no
# upsert — every POST creates a new row whose campaign_total is ADDed into the public
# STATS.pledged_total — so without a cap one self-registered account could loop
# POST /pledges to inflate the public "raised" headline. 20 is far above any real use
# (a person managing a few pledges) while bounding the abuse (security review 2026-07-02).
MAX_PLEDGES_PER_ACCOUNT = 20

# Fields the owner may see about each of their own pledges. The raw DynamoDB item is
# never returned wholesale — we project an explicit allowlist. ``pledge_id`` is added
# separately (the owner needs it to edit/delete a specific pledge); it is the owner's
# own data, so unlike the public list this is fine to expose here. The email is NOT
# echoed: the caller is the owner, so returning it discloses nothing (H1).
MY_PLEDGE_FIELDS = (
    "amount",
    "is_monthly",
    "campaign_total",
    "message",
    "end_month",
    "end_year",
    "created_at",
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


def _resolve_identity(request: Request, client_email: str | None) -> tuple[str | None, bool]:
    """Resolve the caller's identity email, returning ``(email, authenticated)``.

    Behind the gateway authorizer (``authenticated=True``) the identity is the verified
    ``email`` claim and any client-supplied email is ignored — that is what stops one
    user from acting on someone else's pledge. An authenticated request whose token has
    no ``email`` claim yields ``(None, True)`` so the handler fails closed. With no
    authorizer (local dev / tests) the client-supplied email is used (``authenticated``
    is ``False``), lowercased.
    """
    claims = _jwt_claims(request)
    if claims is not None:
        return _claim_email(claims), True
    return (client_email.strip().lower() if client_email else None), False


def _parse_reference(created_at: str | None) -> datetime | None:
    """Parse a stored ISO ``created_at`` into a datetime for anchoring an edit's
    recompute (see ``_update_existing_pledge``). Returns ``None`` — falling back to
    *now* — if it is missing or unparseable, which is safe (worst case: the old
    behaviour) and never raises."""
    if not created_at:
        return None
    try:
        return datetime.fromisoformat(created_at)
    except ValueError:
        return None


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
            if item.get("pledgeID") not in _SENTINEL_IDS
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
def get_my_pledges(
    request: Request, email: str | None = None, currency: str | None = None
):
    """Return the caller's own pledges as a list (empty list if they have none).

    AUTH3: behind the authorizer the identity is the verified email claim and the
    client-supplied ``?email=`` is ignored — so the query param can't be used to read
    someone else's pledges. An authenticated request with no email claim (e.g. an access
    token) is rejected. The ``?email=`` path is reached only with no authorizer.
    """
    currency = parse_currency(currency)
    identity, authenticated = _resolve_identity(request, email)
    if authenticated and not identity:
        return json_response(401, {"error": "Unauthorized"})
    if not identity:
        return json_response(400, {"message": "email query parameter is required"})

    table = get_table()
    try:
        result = table.query(
            IndexName="EmailIndex",
            KeyConditionExpression=Key("email").eq(identity),
        )
    except ClientError:
        return json_response(500, {"error": "Failed to look up pledges"})

    items = [i for i in result.get("Items", []) if i.get("pledgeID") not in _SENTINEL_IDS]

    pledges = []
    for item in items:
        projected = {field: item[field] for field in MY_PLEDGE_FIELDS if field in item}
        projected["pledge_id"] = item["pledgeID"]
        pledges.append(projected)

    pledges.sort(key=lambda pledge: pledge.get("created_at") or "", reverse=True)

    if currency != CANONICAL_CURRENCY:
        try:
            rate = read_exchange_rate(table)
        except ClientError:
            return json_response(500, {"error": "Failed to look up pledges"})
        for pledge in pledges:
            convert_fields(pledge, ("amount", "campaign_total"), currency, rate)

    return json_response(200, {"pledges": pledges, "currency": currency})


@router.post("/pledges")
async def create_pledge(request: Request):
    currency = parse_currency(request.query_params.get("currency"))
    try:
        body = json.loads(await request.body() or b"{}")
    except json.JSONDecodeError:
        return json_response(400, {"error": "Invalid JSON in request body"})

    # AUTH3: a pledge is keyed to the *authenticated* user. Behind the authorizer the
    # email comes from the verified claims and the body's email is ignored (no
    # impersonation). An authenticated request with no email claim (e.g. an access token)
    # is rejected rather than trusting the body. With no authorizer (local dev / tests)
    # the body email is used and validated below.
    identity, authenticated = _resolve_identity(request, body.get("email"))
    if authenticated:
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
        # One account may hold at most MAX_PLEDGES_PER_ACCOUNT pledges (anti-abuse). The
        # count is taken once here and reused by _create_new_pledge for the supporter tally.
        existing_count = _count_email_pledges(table, validated["email"])
        if existing_count >= MAX_PLEDGES_PER_ACCOUNT:
            return json_response(
                409,
                {"error": f"An account may hold at most {MAX_PLEDGES_PER_ACCOUNT} pledges"},
            )
        return _create_new_pledge(table, validated, existing_count=existing_count)
    except ClientError:
        return json_response(500, {"error": "Failed to process pledge"})


@router.put("/pledges/{pledge_id}")
async def update_pledge(pledge_id: str, request: Request):
    currency = parse_currency(request.query_params.get("currency"))
    try:
        body = json.loads(await request.body() or b"{}")
    except json.JSONDecodeError:
        return json_response(400, {"error": "Invalid JSON in request body"})

    identity, authenticated = _resolve_identity(request, body.get("email"))
    if authenticated:
        if not identity:
            return json_response(401, {"error": "Unauthorized"})
        body["email"] = identity

    table = get_table()

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
        existing_item = _get_pledge_item(table, pledge_id)
        if existing_item is None:
            return json_response(404, {"message": "not found"})
        # Owner check: you may only edit a pledge whose email is your identity. Behind
        # the authorizer ``validated["email"]`` was forced to the verified claim, so this
        # rejects editing anyone else's pledge; locally it checks the supplied email.
        # Compare case-insensitively so a legacy row with a non-lowercased email can't
        # lock its true owner out (identity is always lowercased).
        if existing_item["email"].lower() != validated["email"]:
            return json_response(403, {"error": "Forbidden"})

        existing_pledge = Pledge.from_dynamodb_item(existing_item)
        return _update_existing_pledge(table, existing_pledge, validated)
    except ClientError:
        return json_response(500, {"error": "Failed to process pledge"})


@router.delete("/pledges/{pledge_id}")
def delete_pledge(pledge_id: str, request: Request, email: str | None = None):
    identity, authenticated = _resolve_identity(request, email)
    if authenticated and not identity:
        return json_response(401, {"error": "Unauthorized"})
    if not identity:
        return json_response(400, {"message": "email query parameter is required"})

    table = get_table()
    try:
        existing_item = _get_pledge_item(table, pledge_id)
        if existing_item is None:
            return json_response(404, {"message": "not found"})
        # Case-insensitive owner check (identity is lowercased; a legacy row may not be).
        if existing_item["email"].lower() != identity:
            return json_response(403, {"error": "Forbidden"})
        return _delete_existing_pledge(table, existing_item)
    except ClientError:
        return json_response(500, {"error": "Failed to delete pledge"})


def _get_pledge_item(table, pledge_id: str):
    """Fetch a single pledge item by id, or ``None`` if it is absent or a sentinel
    row (STATS/CONFIG are addressable by ``pledgeID`` but are not pledges)."""
    if pledge_id in _SENTINEL_IDS:
        return None
    item = table.get_item(Key={"pledgeID": pledge_id}).get("Item")
    if not item or "email" not in item:
        return None
    return item


def _count_email_pledges(table, email: str) -> int:
    """How many pledge rows this email currently has. Used to decide the supporter
    tally: an email's *first* create is +1 and its *last* delete is −1 (distinct-email
    count, D23). Sentinel rows carry no ``email`` so they aren't in EmailIndex, but we
    filter defensively."""
    result = table.query(
        IndexName="EmailIndex",
        KeyConditionExpression=Key("email").eq(email),
    )
    return len([i for i in result.get("Items", []) if i.get("pledgeID") not in _SENTINEL_IDS])


def _create_new_pledge(table, data: dict, existing_count: int):
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

    # Supporters = distinct emails (D23): bump the tally only when this account had no
    # pledge yet. ``existing_count`` was taken (once) by the caller before this create.
    is_first_for_email = existing_count == 0

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

    _adjust_stats(
        table,
        pledged_total_delta=campaign_total,
        supporters_delta=1 if is_first_for_email else 0,
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

    # Recompute the new campaign_total on the pledge's ORIGINAL create-time baseline, not
    # "now": a monthly campaign_total is frozen at create, so anchoring the edit to
    # created_at keeps an unchanged pledge at the same total (delta 0) and reflects only
    # what the user actually changed — recomputing against now would corrupt STATS as
    # months elapse (see calculate_remaining_months).
    new_campaign_total, new_monthly_value = calculate_pledge_values(
        amount=new_amount,
        is_monthly=new_is_monthly,
        end_month=new_end_month,
        end_year=new_end_year,
        reference=_parse_reference(existing_pledge.created_at),
    )

    pledged_total_delta = new_campaign_total - old_campaign_total
    monthly_total_delta = new_monthly_value - old_monthly_value
    # Editing a pledge doesn't change the supporter count — same account, same person.

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


def _delete_existing_pledge(table, item: dict):
    email = item["email"]
    campaign_total: Decimal = item.get("campaign_total", Decimal("0"))
    monthly_value: Decimal = (
        item.get("amount", Decimal("0")) if item.get("is_monthly") else Decimal("0")
    )

    # −1 supporter only if this was the account's last pledge (distinct-email count,
    # D23). Count BEFORE deleting: 1 means the row we're about to remove is the last one.
    is_last_for_email = _count_email_pledges(table, email) <= 1

    table.delete_item(Key={"pledgeID": item["pledgeID"]})

    _adjust_stats(
        table,
        pledged_total_delta=-campaign_total,
        supporters_delta=-1 if is_last_for_email else 0,
        monthly_total_delta=-monthly_value,
    )

    return json_response(
        200,
        {
            "pledge_id": item["pledgeID"],
            "message": "Pledge deleted successfully",
        },
    )


def _adjust_stats(
    table,
    pledged_total_delta: Decimal,
    supporters_delta: int,
    monthly_total_delta: Decimal,
):
    # The STATS supporter tally is stored under ``contributors_count`` (the field the
    # frontend reads). Since D23 it counts **distinct emails**: +1 on an account's first
    # pledge, −1 on deleting its last, +0 on further pledges and on edits.
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
