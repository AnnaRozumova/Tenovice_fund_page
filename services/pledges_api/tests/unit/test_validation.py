"""Unit tests for validation logic.

Rewritten in Phase B (B1): ``validate_pledge_input`` raises ``ValueError`` on bad
input and returns a validated dict; ``name`` is no longer accepted or required.
B3 added the upper-bound caps (``MAX_AMOUNT``, ``MAX_MESSAGE_LENGTH``). B4 removed
``contributors_count`` from the pledge — a saved pledge is one person — so it is no
longer required, validated, or capped (the "how many people" what-if lives in the
calculator/simulator, not the stored pledge).
"""
from decimal import Decimal

import pytest

from domain.validation import (
    MAX_AMOUNT,
    MAX_MESSAGE_LENGTH,
    validate_config_input,
    validate_pledge_input,
)


def _valid_config():
    return {
        "current_balance": 320000,
        "fundraising_goal": 2700000,
        "breakdown": [
            {"key": "new_gompa", "amount": 1200000},
            {"key": "sangha_house", "amount": 1200000},
            {"key": "basecamp_north", "amount": 320000},
        ],
    }


class TestValidateConfigInput:
    def test_valid_input_is_returned_normalized(self):
        result = validate_config_input(_valid_config())
        assert result["current_balance"] == 320000
        assert result["fundraising_goal"] == 2700000
        assert [b["key"] for b in result["breakdown"]] == [
            "new_gompa",
            "sangha_house",
            "basecamp_north",
        ]

    def test_zero_balance_allowed_but_zero_goal_rejected(self):
        cfg = _valid_config()
        cfg["current_balance"] = 0
        assert validate_config_input(cfg)["current_balance"] == 0

        cfg["fundraising_goal"] = 0
        with pytest.raises(ValueError, match="greater than 0"):
            validate_config_input(cfg)

    def test_negative_amount_rejected(self):
        cfg = _valid_config()
        cfg["breakdown"][0]["amount"] = -1
        with pytest.raises(ValueError, match="must not be negative"):
            validate_config_input(cfg)

    def test_unknown_breakdown_key_rejected(self):
        cfg = _valid_config()
        cfg["breakdown"][0]["key"] = "protective_forest"
        with pytest.raises(ValueError, match="must be one of"):
            validate_config_input(cfg)

    def test_missing_breakdown_key_rejected(self):
        cfg = _valid_config()
        cfg["breakdown"] = cfg["breakdown"][:2]
        with pytest.raises(ValueError, match="missing required key"):
            validate_config_input(cfg)

    def test_duplicate_breakdown_key_rejected(self):
        cfg = _valid_config()
        cfg["breakdown"][1]["key"] = "new_gompa"
        with pytest.raises(ValueError, match="duplicate"):
            validate_config_input(cfg)

    def test_breakdown_must_be_list(self):
        cfg = _valid_config()
        cfg["breakdown"] = {}
        with pytest.raises(ValueError, match="non-empty list"):
            validate_config_input(cfg)

    def test_missing_field_rejected(self):
        cfg = _valid_config()
        del cfg["fundraising_goal"]
        with pytest.raises(ValueError, match="'fundraising_goal' is required"):
            validate_config_input(cfg)


class TestValidatePledgeInput:
    """Test validate_pledge_input function"""

    def test_valid_one_time_pledge(self):
        data = {
            "email": "john@example.com",
            "amount": 100,
            "is_monthly": False,
            "message": "Great cause!",
        }
        result = validate_pledge_input(data)
        assert "name" not in result
        assert "contributors_count" not in result
        assert result["email"] == "john@example.com"
        assert result["amount"] == Decimal("100")
        assert result["is_monthly"] is False
        assert result["message"] == "Great cause!"
        assert result["end_month"] is None
        assert result["end_year"] is None

    def test_valid_monthly_pledge(self):
        data = {
            "email": "jane@example.com",
            "amount": 50,
            "is_monthly": True,
            "end_month": 12,
            "end_year": 2030,
        }
        result = validate_pledge_input(data)
        assert result["is_monthly"] is True
        assert result["end_month"] == 12
        assert result["end_year"] == 2030

    def test_name_is_ignored(self):
        """A ``name`` in the payload is silently dropped, not stored."""
        data = {
            "name": "Should Be Ignored",
            "email": "john@example.com",
            "amount": 100,
            "is_monthly": False,
        }
        result = validate_pledge_input(data)
        assert "name" not in result

    def test_contributors_count_is_ignored(self):
        """B4: a ``contributors_count`` in the payload is silently dropped, not stored."""
        data = {
            "email": "john@example.com",
            "contributors_count": 7,
            "amount": 100,
            "is_monthly": False,
        }
        result = validate_pledge_input(data)
        assert "contributors_count" not in result

    def test_email_required(self):
        data = {"amount": 100, "is_monthly": False}
        with pytest.raises(ValueError, match="email"):
            validate_pledge_input(data)

    def test_email_normalized_to_lowercase(self):
        data = {
            "email": "John.Doe@EXAMPLE.COM",
            "amount": 100,
            "is_monthly": False,
        }
        result = validate_pledge_input(data)
        assert result["email"] == "john.doe@example.com"

    @pytest.mark.parametrize(
        "email",
        ["notanemail", "missing@domain", "@nodomain.com", "spaces in@email.com"],
    )
    def test_invalid_email_format(self, email):
        data = {
            "email": email,
            "amount": 100,
            "is_monthly": False,
        }
        with pytest.raises(ValueError, match="email"):
            validate_pledge_input(data)

    def test_missing_amount(self):
        data = {"email": "john@example.com", "is_monthly": False}
        with pytest.raises(ValueError, match="amount"):
            validate_pledge_input(data)

    def test_amount_must_be_positive(self):
        data = {
            "email": "john@example.com",
            "amount": 0,
            "is_monthly": False,
        }
        with pytest.raises(ValueError, match="amount"):
            validate_pledge_input(data)

    def test_amount_not_a_number(self):
        data = {
            "email": "john@example.com",
            "amount": "not a number",
            "is_monthly": False,
        }
        with pytest.raises(ValueError, match="amount"):
            validate_pledge_input(data)

    def test_is_monthly_must_be_boolean(self):
        data = {
            "email": "john@example.com",
            "amount": 100,
            "is_monthly": "yes",
        }
        with pytest.raises(ValueError, match="is_monthly"):
            validate_pledge_input(data)

    def test_monthly_requires_end_date(self):
        data = {
            "email": "john@example.com",
            "amount": 100,
            "is_monthly": True,
        }
        with pytest.raises(ValueError, match="end_month"):
            validate_pledge_input(data)

    def test_monthly_end_date_not_in_past(self):
        data = {
            "email": "john@example.com",
            "amount": 100,
            "is_monthly": True,
            "end_month": 1,
            "end_year": 2000,
        }
        with pytest.raises(ValueError, match="past"):
            validate_pledge_input(data)

    def test_message_must_be_string(self):
        data = {
            "email": "john@example.com",
            "amount": 100,
            "is_monthly": False,
            "message": 123,
        }
        with pytest.raises(ValueError, match="message"):
            validate_pledge_input(data)

    # --- B3: upper-bound caps ---

    def _base(self, **overrides):
        data = {
            "email": "john@example.com",
            "amount": 100,
            "is_monthly": False,
        }
        data.update(overrides)
        return data

    def test_amount_at_cap_is_accepted(self):
        result = validate_pledge_input(self._base(amount=int(MAX_AMOUNT)))
        assert result["amount"] == MAX_AMOUNT

    def test_amount_over_cap_rejected(self):
        with pytest.raises(ValueError, match="exceed"):
            validate_pledge_input(self._base(amount=int(MAX_AMOUNT) + 1))

    def test_message_at_cap_is_accepted(self):
        result = validate_pledge_input(self._base(message="x" * MAX_MESSAGE_LENGTH))
        assert result["message"] == "x" * MAX_MESSAGE_LENGTH

    def test_message_over_cap_rejected(self):
        with pytest.raises(ValueError, match="message"):
            validate_pledge_input(self._base(message="x" * (MAX_MESSAGE_LENGTH + 1)))
