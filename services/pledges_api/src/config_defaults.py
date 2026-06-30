"""Documented default campaign numbers, used until the CONFIG row is seeded.

Amounts are in the **canonical currency CZK** (decision D22): the campaign's real bank
account is in koruna, so DynamoDB stores CZK and the API converts to EUR at the
response/request boundary (``domain/currency.py``) by the ``?currency=`` param. The goal
is a clean 70,000,000 CZK (≈ €2.89M at the default rate); the balance is provisional
(≈ €320k). The real figures **and** the live exchange rate are admin-set in the CONFIG
row (D22-storage; seeded for real in F2) — these defaults only apply until then.

Shared by the config read route (``GET /config``), the calculate simulator, and the
currency layer (the default rate) so they all fall back to the same numbers. The
breakdown stores stable identifier keys (not display names) — the localized CZ/EN labels
live in the frontend i18n dictionary (D3), keeping content out of the data layer. Lives
in its own module so the config and calculate routes can import it without depending on
each other (D19).
"""
from decimal import Decimal

# CZK per 1 EUR. Admin-editable in the CONFIG row (D22-storage); the API divides amounts
# by this to display EUR. This default holds until the admin sets the live rate.
DEFAULT_EXCHANGE_RATE = Decimal("24.22")

DEFAULT_CURRENT_BALANCE = Decimal("7750400")  # CZK, provisional (≈ €320,000)
DEFAULT_FUNDRAISING_GOAL = Decimal("70000000")  # CZK (≈ €2.89M) — the campaign goal
DEFAULT_BREAKDOWN = [
    {"key": "new_gompa", "amount": Decimal("29064000")},  # CZK (≈ €1.2M)
    {"key": "sangha_house", "amount": Decimal("29064000")},  # CZK (≈ €1.2M)
    {"key": "basecamp_north", "amount": Decimal("7750400")},  # CZK (≈ €320k)
]
