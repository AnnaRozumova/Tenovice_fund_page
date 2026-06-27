"""Pledge math — the single source of truth for campaign impact (decision D8).

Both the save path (``handlers/create_pledge.py``) and the read-only simulator
(``handlers/calculate.py``, the ``POST /calculate`` endpoint) compute impact
through these helpers, so a saved pledge's totals and the live calculator preview
can never drift apart. Kept framework-free in the domain layer.

- **One-time:** campaign impact = ``amount``; monthly effect = 0.
- **Monthly** (now until ``end_month``/``end_year`` inclusive):
  ``remaining_months = (end_year - cur_year)*12 + (end_month - cur_month) + 1``
  (floored at 0); campaign impact = ``amount * remaining_months``; monthly effect
  = ``amount``.
"""
from datetime import datetime, timezone
from decimal import Decimal


def calculate_remaining_months(end_month: int, end_year: int) -> int:
    """Inclusive count of months from the current month to ``end_month``/``end_year``.

    "Until this month" == 1. Floored at 0 so a past end date yields no impact (the
    calculator's zero-months case); the pledge save path rejects past dates in
    validation, so it never reaches the floor.
    """
    now = datetime.now(timezone.utc)
    months = (end_year - now.year) * 12 + (end_month - now.month) + 1
    return max(0, months)


def calculate_pledge_values(
    amount: Decimal,
    is_monthly: bool,
    end_month: int | None,
    end_year: int | None,
) -> tuple[Decimal, Decimal]:
    """Return ``(campaign_total, monthly_value)`` for one person's pledge."""
    if not is_monthly:
        return amount, Decimal("0")

    if end_month is None or end_year is None:
        raise ValueError("Monthly pledge requires end_month and end_year")

    remaining_months = calculate_remaining_months(end_month, end_year)
    return amount * Decimal(remaining_months), amount
