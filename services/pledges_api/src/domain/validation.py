"""Validation logic for pledges"""
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Provisional input caps. These guard STATS against fat-finger / abusive values.
# Moving these into the editable CONFIG row is planned (Phase C). There is no
# contributors cap: a saved pledge represents one person (B4); the "how many
# people" what-if lives in the calculator/simulator, not the stored pledge.
MAX_AMOUNT = Decimal("100000")
MAX_MESSAGE_LENGTH = 500

# The campaign breakdown directions, by stable identifier key. The CONFIG row
# (read by get_config, written by update_config) stores these keys + amounts;
# the localized CZ/EN labels live in the frontend i18n dictionary, not the DB.
BREAKDOWN_KEYS = ("new_gompa", "sangha_house", "basecamp_north")


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
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"'{field}' must be a valid number") from exc

    if decimal_value <= 0:
        raise ValueError(f"'{field}' must be greater than 0")

    if maximum is not None and decimal_value > maximum:
        raise ValueError(f"'{field}' must not exceed {maximum:,.0f}")

    return decimal_value


def _require_non_negative_int(data: dict, field: str) -> int:
    value = data.get(field)

    if value is None:
        raise ValueError(f"'{field}' is required")

    # bool is a subclass of int — reject it explicitly so True/False don't sneak through.
    if isinstance(value, bool):
        raise ValueError(f"'{field}' must be an integer")

    try:
        int_value = int(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"'{field}' must be an integer") from exc

    if int_value < 0:
        raise ValueError(f"'{field}' must not be negative")

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

    amount = _require_positive_decimal(data, "amount", maximum=MAX_AMOUNT)
    is_monthly = _require_bool(data, "is_monthly")

    message = data.get("message")
    if message is not None and not isinstance(message, str):
        raise ValueError("'message' must be a string if provided")
    if isinstance(message, str) and len(message) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"'message' must not exceed {MAX_MESSAGE_LENGTH} characters")

    validated = {
        "email": email,
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
        except (ValueError, TypeError) as exc:
            raise ValueError("'end_month' must be an integer") from exc

        try:
            end_year = int(end_year)
        except (ValueError, TypeError) as exc:
            raise ValueError("'end_year' must be an integer") from exc

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


def validate_config_input(data: dict) -> dict:
    """Validate an admin CONFIG update: balance, goal, and the 3-direction breakdown.

    Amounts are whole EUR (ints). ``current_balance`` may be 0; ``fundraising_goal``
    must be > 0. The breakdown must list exactly the known direction keys, each with
    a non-negative amount — display labels are not stored (they live in the i18n dict).
    """
    current_balance = _require_non_negative_int(data, "current_balance")

    fundraising_goal = _require_non_negative_int(data, "fundraising_goal")
    if fundraising_goal < 1:
        raise ValueError("'fundraising_goal' must be greater than 0")

    breakdown_raw = data.get("breakdown")
    if not isinstance(breakdown_raw, list) or not breakdown_raw:
        raise ValueError("'breakdown' is required and must be a non-empty list")

    breakdown = []
    seen_keys = set()
    for item in breakdown_raw:
        if not isinstance(item, dict):
            raise ValueError("each 'breakdown' item must be an object with 'key' and 'amount'")

        key = item.get("key")
        if key not in BREAKDOWN_KEYS:
            raise ValueError(f"'breakdown' key must be one of: {', '.join(BREAKDOWN_KEYS)}")
        if key in seen_keys:
            raise ValueError(f"duplicate 'breakdown' key: {key}")
        seen_keys.add(key)

        amount = _require_non_negative_int(item, "amount")
        breakdown.append({"key": key, "amount": amount})

    if seen_keys != set(BREAKDOWN_KEYS):
        missing = ", ".join(k for k in BREAKDOWN_KEYS if k not in seen_keys)
        raise ValueError(f"'breakdown' is missing required key(s): {missing}")

    return {
        "current_balance": current_balance,
        "fundraising_goal": fundraising_goal,
        "breakdown": breakdown,
    }
