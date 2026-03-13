"""Unit tests for validation logic"""
from domain.validation import validate_pledge_input


class TestValidatePledgeInput:
    """Test validate_pledge_input function"""

    def test_valid_pledge(self):
        """Test validation with valid pledge data"""
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "amount": 100,
            "is_monthly": True,
            "message": "Great cause!"
        }
        is_valid, error = validate_pledge_input(data)
        assert is_valid is True
        assert error is None

    def test_valid_pledge_without_message(self):
        """Test validation with valid pledge data (no message)"""
        data = {
            "name": "Jane Smith",
            "email": "jane@example.com",
            "amount": 50,
            "is_monthly": False,
        }
        is_valid, error = validate_pledge_input(data)
        assert is_valid is True
        assert error is None

    def test_missing_required_field(self):
        """Test validation fails when required field is missing"""
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "is_monthly": True,
        }
        is_valid, error = validate_pledge_input(data)
        assert is_valid is False
        assert "amount" in error

    def test_name_too_short(self):
        """Test validation fails when name is too short"""
        data = {
            "name": "A",
            "email": "john@example.com",
            "amount": 100,
            "is_monthly": True,
        }
        is_valid, error = validate_pledge_input(data)
        assert is_valid is False
        assert "at least 2 characters" in error

    def test_name_too_long(self):
        """Test validation fails when name is too long"""
        data = {
            "name": "A" * 101,
            "email": "john@example.com",
            "amount": 100,
            "is_monthly": True,
        }
        is_valid, error = validate_pledge_input(data)
        assert is_valid is False
        assert "less than 100 characters" in error

    def test_invalid_email_format(self):
        """Test validation fails with invalid email"""
        test_cases = [
            "notanemail",
            "missing@domain",
            "@nodomain.com",
            "no@domain",
            "spaces in@email.com",
        ]
        for email in test_cases:
            data = {
                "name": "John Doe",
                "email": email,
                "amount": 100,
                "is_monthly": True,
            }
            is_valid, error = validate_pledge_input(data)
            assert is_valid is False, f"Email {email} should be invalid"
            assert "email" in error.lower()

    def test_amount_too_low(self):
        """Test validation fails when amount is too low"""
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "amount": 0,
            "is_monthly": True,
        }
        is_valid, error = validate_pledge_input(data)
        assert is_valid is False
        assert "at least 1" in error

    def test_amount_too_high(self):
        """Test validation fails when amount is too high"""
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "amount": 1000001,
            "is_monthly": True,
        }
        is_valid, error = validate_pledge_input(data)
        assert is_valid is False
        assert "1,000,000" in error

    def test_amount_not_integer(self):
        """Test validation fails when amount is not an integer"""
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "amount": "not a number",
            "is_monthly": True,
        }
        is_valid, error = validate_pledge_input(data)
        assert is_valid is False
        assert "valid integer" in error

    def test_is_monthly_not_boolean(self):
        """Test validation fails when is_monthly is not boolean"""
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "amount": 100,
            "is_monthly": "yes",
        }
        is_valid, error = validate_pledge_input(data)
        assert is_valid is False
        assert "boolean" in error

    def test_message_too_long(self):
        """Test validation fails when message is too long"""
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "amount": 100,
            "is_monthly": True,
            "message": "x" * 501,
        }
        is_valid, error = validate_pledge_input(data)
        assert is_valid is False
        assert "500 characters" in error

    def test_message_not_string(self):
        """Test validation fails when message is not a string"""
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "amount": 100,
            "is_monthly": True,
            "message": 123,
        }
        is_valid, error = validate_pledge_input(data)
        assert is_valid is False
        assert "string" in error
