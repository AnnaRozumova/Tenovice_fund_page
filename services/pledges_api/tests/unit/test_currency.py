"""Unit tests for the currency conversion layer (decision D22).

Pure functions: parse the ``?currency=`` param, convert canonical CZK ⇄ a display
currency (whole units, half-up), and convert named money fields in a dict. The
exchange rate is passed in (the module is AWS-free).
"""
from decimal import Decimal

from domain.currency import (
    CANONICAL_CURRENCY,
    convert_fields,
    parse_currency,
    to_canonical,
    to_display,
)

RATE = Decimal("24.22")


class TestParseCurrency:
    def test_missing_defaults_to_canonical(self):
        assert parse_currency(None) == CANONICAL_CURRENCY == "czk"

    def test_known_codes_pass_through_case_insensitively(self):
        assert parse_currency("eur") == "eur"
        assert parse_currency("EUR") == "eur"
        assert parse_currency(" Czk ") == "czk"

    def test_unknown_code_falls_back_to_canonical(self):
        # A read must never break the page over a stray currency param.
        assert parse_currency("gbp") == "czk"
        assert parse_currency("") == "czk"


class TestToDisplay:
    def test_czk_is_unchanged(self):
        assert to_display(Decimal("2422"), "czk", RATE) == Decimal("2422")

    def test_eur_divides_by_rate(self):
        assert to_display(Decimal("2422"), "eur", RATE) == Decimal("100")

    def test_eur_rounds_half_up_to_whole(self):
        # 121 / 24.22 = 4.996… → 5
        assert to_display(Decimal("121"), "eur", RATE) == Decimal("5")

    def test_non_positive_rate_is_a_no_op(self):
        assert to_display(Decimal("2422"), "eur", Decimal("0")) == Decimal("2422")


class TestToCanonical:
    def test_czk_is_unchanged(self):
        assert to_canonical(Decimal("100"), "czk", RATE) == Decimal("100")

    def test_eur_multiplies_by_rate(self):
        assert to_canonical(Decimal("100"), "eur", RATE) == Decimal("2422")

    def test_eur_rounds_half_up_to_whole(self):
        # 107 * 24.22 = 2591.54 → 2592
        assert to_canonical(Decimal("107"), "eur", RATE) == Decimal("2592")


class TestConvertFields:
    def test_converts_only_named_fields(self):
        obj = {"amount": Decimal("2422"), "count": 7, "campaign_total": Decimal("4844")}
        convert_fields(obj, ("amount", "campaign_total"), "eur", RATE)
        assert obj["amount"] == Decimal("100")
        assert obj["campaign_total"] == Decimal("200")
        assert obj["count"] == 7  # untouched

    def test_skips_absent_and_none_fields(self):
        obj = {"amount": None}
        convert_fields(obj, ("amount", "missing"), "eur", RATE)
        assert obj["amount"] is None
        assert "missing" not in obj

    def test_czk_is_a_no_op(self):
        obj = {"amount": Decimal("2422")}
        convert_fields(obj, ("amount",), "czk", RATE)
        assert obj["amount"] == Decimal("2422")

    def test_returns_the_same_object(self):
        obj = {"amount": Decimal("2422")}
        assert convert_fields(obj, ("amount",), "eur", RATE) is obj
