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

# Safety backstop on the inclusive month count. The validation layer already caps
# ``end_year`` (MAX_END_YEAR), so a legitimate monthly pledge never approaches this — it
# only bounds the ``amount * months`` multiply if a huge month-count ever reaches here
# another way (e.g. this helper called without going through validation). 600 months
# (50 years) is far beyond any real campaign horizon (security review 2026-07-02).
MAX_REMAINING_MONTHS = 600


def calculate_remaining_months(
    end_month: int, end_year: int, reference: datetime | None = None
) -> int:
    """Inclusive count of months from a reference month to ``end_month``/``end_year``.

    "Until this month" == 1. Floored at 0 so a past end date yields no impact (the
    calculator's zero-months case); the pledge save path rejects past dates in
    validation, so it never reaches the floor. Also capped at ``MAX_REMAINING_MONTHS`` as
    a safety backstop — the validation layer bounds ``end_year`` (MAX_END_YEAR) so this
    never bites a real pledge; it just keeps the downstream ``amount * months`` multiply
    bounded if a huge count ever reaches here another way.

    ``reference`` defaults to *now* — the correct anchor when a pledge is first created
    or previewed. When **editing** an existing pledge, pass the pledge's ``created_at``
    instead: a monthly pledge's ``campaign_total`` is frozen at create time (it "stays
    stable as months pass"), so recomputing it against *now* on edit would diff two
    different time baselines and silently corrupt ``STATS.pledged_total`` — even on a
    no-op edit. Anchoring to ``created_at`` keeps the edit on the same baseline as the
    stored value, so an unchanged pledge recomputes to the same total (delta 0).
    """
    ref = reference or datetime.now(timezone.utc)
    months = (end_year - ref.year) * 12 + (end_month - ref.month) + 1
    return max(0, min(months, MAX_REMAINING_MONTHS))


def calculate_pledge_values(
    amount: Decimal,
    is_monthly: bool,
    end_month: int | None,
    end_year: int | None,
    reference: datetime | None = None,
) -> tuple[Decimal, Decimal]:
    """Return ``(campaign_total, monthly_value)`` for one person's pledge.

    ``reference`` anchors the monthly month-count (see ``calculate_remaining_months``):
    omit it on create/preview (defaults to now); pass the pledge's ``created_at`` when
    recomputing on edit so the frozen ``campaign_total`` baseline is preserved.
    """
    if not is_monthly:
        return amount, Decimal("0")

    if end_month is None or end_year is None:
        raise ValueError("Monthly pledge requires end_month and end_year")

    remaining_months = calculate_remaining_months(end_month, end_year, reference)
    return amount * Decimal(remaining_months), amount
