"""Read-only campaign simulator: ``POST /calculate``.

Computes a "what-if" — how a group's intended giving would move the campaign
total toward the goal — and **writes nothing**. The impact formula is the shared
domain math (decision D8), the same code the save path (``create_pledge``) uses,
so the calculator preview and a saved pledge can never disagree. The projection
reads the live ``STATS`` total and the ``CONFIG`` goal so the frontend only
displays the result (no JS math, D15).

Input  ``{ people, amount, is_monthly, end_month?, end_year? }``
Output ``{ people, amount, is_monthly, remaining_months, total_impact,
           monthly_effect, current_total, goal, projected_total,
           baseline_progress_pct, projected_progress_pct, scenario_progress_pct }``
where ``total_impact = people * amount * (remaining_months if monthly else 1)``.
"""
import json
import os
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from domain.pledge_math import calculate_pledge_values, calculate_remaining_months
from domain.validation import validate_calculate_input
from handlers.get_config import DEFAULT_FUNDRAISING_GOAL
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
        validated = validate_calculate_input(body)
    except ValueError as e:
        return response(400, {"error": str(e)})

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

    try:
        current_total, goal = _read_baseline(table)
    except ClientError as e:
        return response(
            500, {"error": "Failed to read campaign totals", "detail": str(e)}
        )

    projected_total = current_total + total_impact
    baseline_pct = _progress_pct(current_total, goal)
    projected_pct = _progress_pct(projected_total, goal)

    return response(
        200,
        {
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
        },
    )


def _read_baseline(table) -> tuple[Decimal, Decimal]:
    """Current pledged total (STATS) and fundraising goal (CONFIG).

    Both rows may be absent before the first deploy/seed (Phase F); fall back to 0
    and the same documented goal default ``get_config`` serves, so the simulator
    stays consistent with the rest of the site.
    """
    stats = table.get_item(Key={"pledgeID": "STATS"}).get("Item") or {}
    current_total = stats.get("pledged_total", Decimal("0"))

    config = table.get_item(Key={"pledgeID": "CONFIG"}).get("Item") or {}
    goal = config.get("fundraising_goal", DEFAULT_FUNDRAISING_GOAL)

    return current_total, goal


def _progress_pct(total: Decimal, goal: Decimal) -> Decimal:
    """Progress toward the goal as a percentage, to one decimal place."""
    if goal <= 0:
        return Decimal("0")
    pct = (Decimal(total) / Decimal(goal)) * Decimal("100")
    return pct.quantize(Decimal("0.1"))
