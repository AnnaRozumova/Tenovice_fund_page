"""Durable tests for the locked pledge math (decision D8).

The formula lives once per side (``web/pledge.js`` preview ↔ this handler's save)
and must stay in lockstep. These tests target the stable math helpers, so they
survive the Phase B rework of validation/model/handlers.
"""
from datetime import datetime, timezone
from decimal import Decimal

from handlers.create_pledge import (
    _calculate_pledge_values,
    _calculate_remaining_months,
)


def test_one_time_pledge_impact_equals_amount():
    campaign_total, monthly_value = _calculate_pledge_values(
        Decimal("100"), is_monthly=False, end_month=None, end_year=None
    )
    assert campaign_total == Decimal("100")
    assert monthly_value == Decimal("0")


def test_remaining_months_current_month_is_one():
    now = datetime.now(timezone.utc)
    # The window is inclusive of the current month, so "until this month" = 1.
    assert _calculate_remaining_months(now.month, now.year) == 1


def test_monthly_impact_multiplies_amount_by_remaining_months():
    now = datetime.now(timezone.utc)
    # Three-month inclusive window starting this month (handles year wrap).
    end_month = now.month + 2
    end_year = now.year
    if end_month > 12:
        end_month -= 12
        end_year += 1

    months = _calculate_remaining_months(end_month, end_year)
    campaign_total, monthly_value = _calculate_pledge_values(
        Decimal("50"), is_monthly=True, end_month=end_month, end_year=end_year
    )

    assert months == 3
    assert campaign_total == Decimal("50") * months
    assert monthly_value == Decimal("50")
