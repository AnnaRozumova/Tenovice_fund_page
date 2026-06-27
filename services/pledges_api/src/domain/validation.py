"""Validation logic for pledges"""
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Provisional input caps. These guard STATS against fat-finger / abusive values.
# The contributors cap is tentative — pending a product decision on whether the
# "one pledge on behalf of several people" feature stays at all. Moving these into
# the editable CONFIG row is planned (Phase C).
MAX_AMOUNT = Decimal("100000")
MAX_CONTRIBUTORS_COUNT = 5
MAX_MESSAGE_LENGTH = 500


def _require_non_empty_string(data: dict, field: str) -> str:
    value = data.get(field)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{field}' is required and must be a non-empty string")

    return value.strip()


def _require_positive_decimal(data: dict, field: str, maximum: Decimal | None = None) -> Decimal:
    value = data.get(field)

    if value is None:
        raise ValueError(f"'{field}' is required")

    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"'{field}' must be a valid number")

    if decimal_value <= 0:
        raise ValueError(f"'{field}' must be greater than 0")

    if maximum is not None and decimal_value > maximum:
        raise ValueError(f"'{field}' must not exceed {maximum:,.0f}")

    return decimal_value


def _require_positive_int(data: dict, field: str, maximum: int | None = None) -> int:
    value = data.get(field)

    if value is None:
        raise ValueError(f"'{field}' is required")

    try:
        int_value = int(value)
    except (ValueError, TypeError):
        raise ValueError(f"'{field}' must be an integer")

    if int_value < 1:
        raise ValueError(f"'{field}' must be at least 1")

    if maximum is not None and int_value > maximum:
        raise ValueError(f"'{field}' must not exceed {maximum}")

    return int_value


def _require_bool(data: dict, field: str) -> bool:
    value = data.get(field)

    if not isinstance(value, bool):
        raise ValueError(f"'{field}' is required and must be a boolean")

    return value

def validate_pledge_input(data: dict) -> dict:
    """
    Validate pledge creation input.
    """
    email = _require_non_empty_string(data, "email").lower()

    if not EMAIL_RE.match(email):
        raise ValueError("'email' must be a valid email address")

    contributors_count = _require_positive_int(
        data, "contributors_count", maximum=MAX_CONTRIBUTORS_COUNT
    )
    amount = _require_positive_decimal(data, "amount", maximum=MAX_AMOUNT)
    is_monthly = _require_bool(data, "is_monthly")

    message = data.get("message")
    if message is not None and not isinstance(message, str):
        raise ValueError("'message' must be a string if provided")
    if isinstance(message, str) and len(message) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"'message' must not exceed {MAX_MESSAGE_LENGTH} characters")

    validated = {
        "email": email,
        "contributors_count": contributors_count,
        "amount": amount,
        "is_monthly": is_monthly,
        "message": message.strip() if isinstance(message, str) and message.strip() else None,
    }

    if is_monthly:
        end_month = data.get("end_month")
        end_year = data.get("end_year")

        if end_month is None:
            raise ValueError("'end_month' is required when 'is_monthly' is true")
        if end_year is None:
            raise ValueError("'end_year' is required when 'is_monthly' is true")

        try:
            end_month = int(end_month)
        except (ValueError, TypeError):
            raise ValueError("'end_month' must be an integer")

        try:
            end_year = int(end_year)
        except (ValueError, TypeError):
            raise ValueError("'end_year' must be an integer")

        if end_month < 1 or end_month > 12:
            raise ValueError("'end_month' must be between 1 and 12")

        now = datetime.now(timezone.utc)
        current_year = now.year
        current_month = now.month

        if (end_year, end_month) < (current_year, current_month):
            raise ValueError("'end_month' and 'end_year' must not be in the past")

        validated["end_month"] = end_month
        validated["end_year"] = end_year
    else:
        if data.get("end_month") not in (None, ""):
            raise ValueError("'end_month' must not be provided when 'is_monthly' is false")
        if data.get("end_year") not in (None, ""):
            raise ValueError("'end_year' must not be provided when 'is_monthly' is false")

        validated["end_month"] = None
        validated["end_year"] = None

    return validated
