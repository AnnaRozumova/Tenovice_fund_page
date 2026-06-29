"""Documented default campaign numbers, used until the CONFIG row is seeded.

Shared by the config read route (``GET /config``) and the calculate simulator so
both fall back to the *same* goal. The breakdown stores stable identifier keys
(not display names) — the localized CZ/EN labels live in the frontend i18n
dictionary (D3), keeping content out of the data layer. The goal and per-direction
amounts are provisional pending Anna's confirmation (seeded for real in F2).

Lives in its own module (was in ``handlers/get_config``) so both the config route
and the calculate route can import it without depending on each other (D19).
"""
from decimal import Decimal

DEFAULT_CURRENT_BALANCE = Decimal("320000")
DEFAULT_FUNDRAISING_GOAL = Decimal("2700000")
DEFAULT_BREAKDOWN = [
    {"key": "new_gompa", "amount": Decimal("1200000")},
    {"key": "sangha_house", "amount": Decimal("1200000")},
    {"key": "basecamp_north", "amount": Decimal("320000")},
]
