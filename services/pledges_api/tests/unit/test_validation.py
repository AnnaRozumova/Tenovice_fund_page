"""Unit tests for validation logic.

Rewritten in Phase B (B1): ``validate_pledge_input`` raises ``ValueError`` on bad
input and returns a validated dict; ``name`` is no longer accepted or required.
B3 adds the upper-bound caps (``MAX_AMOUNT``, ``MAX_CONTRIBUTORS_COUNT``,
``MAX_MESSAGE_LENGTH``).
"""
from decimal import Decimal

import pytest

from domain.validation import (
    MAX_AMOUNT,
    MAX_CONTRIBUTORS_COUNT,
    MAX_MESSAGE_LENGTH,
    validate_pledge_input,
)


class TestValidatePledgeInput:
    """Test validate_pledge_input function"""

    def test_valid_one_time_pledge(self):
        data = {
            "email": "john@example.com",
            "contributors_count": 2,
            "amount": 100,
            "is_monthly": False,
            "message": "Great cause!",
        }
        result = validate_pledge_input(data)
        assert "name" not in result
        assert result["email"] == "john@example.com"
        assert result["contributors_count"] == 2
        assert result["amount"] == Decimal("100")
        assert result["is_monthly"] is False
        assert result["message"] == "Great cause!"
        assert result["end_month"] is None
        assert result["end_year"] is None

    def test_valid_monthly_pledge(self):
        data = {
            "email": "jane@example.com",
            "contributors_count": 1,
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
            "contributors_count": 1,
            "amount": 100,
            "is_monthly": False,
        }
        result = validate_pledge_input(data)
        assert "name" not in result

    def test_email_required(self):
        data = {"contributors_count": 1, "amount": 100, "is_monthly": False}
        with pytest.raises(ValueError, match="email"):
            validate_pledge_input(data)

    def test_email_normalized_to_lowercase(self):
        data = {
            "email": "John.Doe@EXAMPLE.COM",
            "contributors_count": 1,
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
            "contributors_count": 1,
            "amount": 100,
            "is_monthly": False,
        }
        with pytest.raises(ValueError, match="email"):
            validate_pledge_input(data)

    def test_missing_amount(self):
        data = {"email": "john@example.com", "contributors_count": 1, "is_monthly": False}
        with pytest.raises(ValueError, match="amount"):
            validate_pledge_input(data)

    def test_amount_must_be_positive(self):
        data = {
            "email": "john@example.com",
            "contributors_count": 1,
            "amount": 0,
            "is_monthly": False,
        }
        with pytest.raises(ValueError, match="amount"):
            validate_pledge_input(data)

    def test_amount_not_a_number(self):
        data = {
            "email": "john@example.com",
            "contributors_count": 1,
            "amount": "not a number",
            "is_monthly": False,
        }
        with pytest.raises(ValueError, match="amount"):
            validate_pledge_input(data)

    def test_contributors_count_required(self):
        data = {"email": "john@example.com", "amount": 100, "is_monthly": False}
        with pytest.raises(ValueError, match="contributors_count"):
            validate_pledge_input(data)

    def test_contributors_count_must_be_at_least_one(self):
        data = {
            "email": "john@example.com",
            "contributors_count": 0,
            "amount": 100,
            "is_monthly": False,
        }
        with pytest.raises(ValueError, match="contributors_count"):
            validate_pledge_input(data)

    def test_is_monthly_must_be_boolean(self):
        data = {
            "email": "john@example.com",
            "contributors_count": 1,
            "amount": 100,
            "is_monthly": "yes",
        }
        with pytest.raises(ValueError, match="is_monthly"):
            validate_pledge_input(data)

    def test_monthly_requires_end_date(self):
        data = {
            "email": "john@example.com",
            "contributors_count": 1,
            "amount": 100,
            "is_monthly": True,
        }
        with pytest.raises(ValueError, match="end_month"):
            validate_pledge_input(data)

    def test_monthly_end_date_not_in_past(self):
        data = {
            "email": "john@example.com",
            "contributors_count": 1,
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
            "contributors_count": 1,
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
            "contributors_count": 1,
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

    def test_contributors_count_at_cap_is_accepted(self):
        result = validate_pledge_input(self._base(contributors_count=MAX_CONTRIBUTORS_COUNT))
        assert result["contributors_count"] == MAX_CONTRIBUTORS_COUNT

    def test_contributors_count_over_cap_rejected(self):
        with pytest.raises(ValueError, match="exceed"):
            validate_pledge_input(self._base(contributors_count=MAX_CONTRIBUTORS_COUNT + 1))

    def test_message_at_cap_is_accepted(self):
        result = validate_pledge_input(self._base(message="x" * MAX_MESSAGE_LENGTH))
        assert result["message"] == "x" * MAX_MESSAGE_LENGTH

    def test_message_over_cap_rejected(self):
        with pytest.raises(ValueError, match="message"):
            validate_pledge_input(self._base(message="x" * (MAX_MESSAGE_LENGTH + 1)))
