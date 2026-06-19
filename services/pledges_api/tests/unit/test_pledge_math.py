"""Durable tests for the locked pledge math (decision D8).

The formula lives once, in ``domain/pledge_math.py``, shared by the save path
(``handlers/create_pledge.py``) and the read-only simulator (``handlers/calculate.py``)
so they can never drift. These tests target the stable math helpers directly.
"""
from datetime import datetime, timezone
from decimal import Decimal

from domain.pledge_math import (
    calculate_pledge_values,
    calculate_remaining_months,
)


def test_one_time_pledge_impact_equals_amount():
    campaign_total, monthly_value = calculate_pledge_values(
        Decimal("100"), is_monthly=False, end_month=None, end_year=None
    )
    assert campaign_total == Decimal("100")
    assert monthly_value == Decimal("0")


def test_remaining_months_current_month_is_one():
    now = datetime.now(timezone.utc)
    # The window is inclusive of the current month, so "until this month" = 1.
    assert calculate_remaining_months(now.month, now.year) == 1


def test_monthly_impact_multiplies_amount_by_remaining_months():
    now = datetime.now(timezone.utc)
    # Three-month inclusive window starting this month (handles year wrap).
    end_month = now.month + 2
    end_year = now.year
    if end_month > 12:
        end_month -= 12
        end_year += 1

    months = calculate_remaining_months(end_month, end_year)
    campaign_total, monthly_value = calculate_pledge_values(
        Decimal("50"), is_monthly=True, end_month=end_month, end_year=end_year
    )

    assert months == 3
    assert campaign_total == Decimal("50") * months
    assert monthly_value == Decimal("50")


def test_past_end_date_floors_remaining_months_at_zero():
    """The zero-months case: a past end date yields no campaign impact, not a negative.

    The pledge save path rejects past dates in validation, but the calculator
    (POST /calculate) allows them and relies on this floor.
    """
    assert calculate_remaining_months(1, 2000) == 0

    campaign_total, monthly_value = calculate_pledge_values(
        Decimal("50"), is_monthly=True, end_month=1, end_year=2000
    )
    assert campaign_total == Decimal("0")
    # The per-month figure is still the amount — there are simply zero months left.
    assert monthly_value == Decimal("50")
