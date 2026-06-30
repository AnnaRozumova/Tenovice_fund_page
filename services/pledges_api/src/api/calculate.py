"""``POST /calculate`` — read-only what-if simulator (writes nothing, D15).

Computes how a group's intended giving would move the campaign total toward the
goal, using the shared pledge math (D8) — the same code the save path uses, so the
preview and a saved pledge can never disagree. Reads the ``STATS`` total and the
``CONFIG`` goal/rate for the projection.

Currency (D22): the incoming per-person ``amount`` is normalized to canonical CZK with
**full precision** (``round_result=False``) — rounding per person before multiplying by
people/months would amplify the error — and the output amounts are rounded once, on the
way out, by ``convert_fields``/``to_display``. Percentages are currency-invariant.

Input  ``{ people, amount, is_monthly, end_month?, end_year? }`` (+ ``?currency=``)
Output ``{ people, amount, is_monthly, remaining_months, total_impact,
           monthly_effect, current_total, goal, projected_total,
           baseline_progress_pct, projected_progress_pct, scenario_progress_pct,
           currency }``
where ``total_impact = people * amount * (remaining_months if monthly else 1)``.
"""
import json
from decimal import Decimal

from botocore.exceptions import ClientError
from fastapi import APIRouter, Request

from api.config import exchange_rate_of
from config_defaults import DEFAULT_FUNDRAISING_GOAL
from db import get_table
from domain.currency import CANONICAL_CURRENCY, convert_fields, normalize_amount, parse_currency
from domain.pledge_math import calculate_pledge_values, calculate_remaining_months
from domain.validation import validate_calculate_input
from utils.http import json_response

router = APIRouter()

# Output money fields converted from canonical CZK to the requested display currency.
_MONEY_FIELDS = (
    "amount",
    "total_impact",
    "monthly_effect",
    "current_total",
    "goal",
    "projected_total",
)


@router.post("/calculate")
async def calculate(request: Request):
    currency = parse_currency(request.query_params.get("currency"))
    try:
        body = json.loads(await request.body() or b"{}")
    except json.JSONDecodeError:
        return json_response(400, {"error": "Invalid JSON in request body"})

    # Read STATS + CONFIG once each (current total, goal, and rate all come from here).
    try:
        current_total, goal, rate = _read_baseline()
    except ClientError:
        return json_response(500, {"error": "Failed to read campaign totals"})

    # Normalize the incoming per-person amount to canonical CZK, keeping full precision
    # (round only the outputs); a non-numeric amount is left for the validator to reject.
    normalize_amount(body, currency, rate, round_result=False)

    try:
        validated = validate_calculate_input(body)
    except ValueError as e:
        return json_response(400, {"error": str(e)})

    people = validated["people"]
    amount = validated["amount"]
    is_monthly = validated["is_monthly"]
    end_month = validated["end_month"]
    end_year = validated["end_year"]

    per_person_impact, per_person_monthly = calculate_pledge_values(
        amount=amount,
        is_monthly=is_monthly,
        end_month=end_month,
        end_year=end_year,
    )

    people_dec = Decimal(people)
    total_impact = per_person_impact * people_dec
    monthly_effect = per_person_monthly * people_dec
    remaining_months = (
        calculate_remaining_months(end_month, end_year) if is_monthly else 0
    )

    projected_total = current_total + total_impact
    baseline_pct = _progress_pct(current_total, goal)
    projected_pct = _progress_pct(projected_total, goal)

    result = {
        "people": people,
        "amount": amount,
        "is_monthly": is_monthly,
        "remaining_months": remaining_months,
        "total_impact": total_impact,
        "monthly_effect": monthly_effect,
        "current_total": current_total,
        "goal": goal,
        "projected_total": projected_total,
        "baseline_progress_pct": baseline_pct,
        "projected_progress_pct": projected_pct,
        "scenario_progress_pct": projected_pct - baseline_pct,
        "currency": currency,
    }
    if currency != CANONICAL_CURRENCY:
        convert_fields(result, _MONEY_FIELDS, currency, rate)
    return json_response(200, result)


def _read_baseline() -> tuple[Decimal, Decimal, Decimal]:
    """Current pledged total (STATS) plus the goal and exchange rate (CONFIG).

    Reads each row once. Both rows may be absent before the first deploy/seed (Phase F);
    fall back to 0, the documented goal default, and the documented rate so the simulator
    stays consistent with the rest of the site.
    """
    table = get_table()
    stats = table.get_item(Key={"pledgeID": "STATS"}).get("Item") or {}
    current_total = stats.get("pledged_total", Decimal("0"))

    config = table.get_item(Key={"pledgeID": "CONFIG"}).get("Item") or {}
    goal = config.get("fundraising_goal", DEFAULT_FUNDRAISING_GOAL)

    return current_total, goal, exchange_rate_of(config)


def _progress_pct(total: Decimal, goal: Decimal) -> Decimal:
    """Progress toward the goal as a percentage, to one decimal place."""
    if goal <= 0:
        return Decimal("0")
    pct = (Decimal(total) / Decimal(goal)) * Decimal("100")
    return pct.quantize(Decimal("0.1"))
