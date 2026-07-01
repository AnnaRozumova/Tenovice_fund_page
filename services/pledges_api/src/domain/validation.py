"""Validation logic for pledges"""
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Provisional input caps. These guard STATS against fat-finger / abusive values.
# The amount cap is in the canonical currency CZK (D22): an EUR pledge is normalized to
# CZK before validation, so the cap applies to the stored koruna amount (~€100k at a
# typical rate). There is no contributors cap: a saved pledge represents one person
# (B4); the "how many people" what-if lives in the calculator/simulator.
MAX_AMOUNT = Decimal("2500000")
MAX_MESSAGE_LENGTH = 500

# Upper bound on a monthly pledge's end year (security review 2026-07-02). Without it
# ``end_year`` is unbounded above: a monthly pledge with a huge year makes
# ``remaining_months`` — and thus ``campaign_total``, which is ADDed into the public
# ``STATS.pledged_total`` — astronomically large, poisoning the "raised" headline every
# visitor sees; on the simulator it also turns the month-count into unbounded big-integer
# work on the shared Lambda. 2035 gives generous headroom over the 2026–2030 campaign.
MAX_END_YEAR = 2035

# Caps for the read-only calculator (``POST /calculate``). It stores nothing, so these
# don't guard STATS — they bound ``total_impact = people * amount * months`` so a crafted
# request can't force huge-number arithmetic on the shared Lambda. ``people`` up to 7000
# covers any realistic what-if group; the per-person amount reuses the save-path cap.
MAX_PEOPLE = 7000
MAX_CALCULATE_AMOUNT = MAX_AMOUNT

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

    # Reject NaN / Infinity / -Infinity. They construct fine but blow up later: a
    # NaN comparison raises InvalidOperation, and Infinity slips past an uncapped
    # path (the simulator) and crashes in the JSON encoder. Catch them as a 400.
    if not decimal_value.is_finite():
        raise ValueError(f"'{field}' must be a finite number")

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

    # A fractional float (e.g. 10.5) would be silently truncated by int(); reject it.
    # is_integer() is also False for inf/nan, so this catches those before int() can
    # raise an uncaught OverflowError (Infinity → 500).
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"'{field}' must be a whole number")

    try:
        int_value = int(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f"'{field}' must be an integer") from exc

    if int_value < 0:
        raise ValueError(f"'{field}' must not be negative")

    return int_value


def _require_positive_int(data: dict, field: str, maximum: int | None = None) -> int:
    value = data.get(field)

    if value is None:
        raise ValueError(f"'{field}' is required")

    # bool is a subclass of int — reject it explicitly so True/False don't sneak through.
    if isinstance(value, bool):
        raise ValueError(f"'{field}' must be an integer")

    # Reject fractional floats (silent int() truncation) and inf/nan up front.
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"'{field}' must be a whole number")

    try:
        int_value = int(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f"'{field}' must be an integer") from exc

    if int_value < 1:
        raise ValueError(f"'{field}' must be greater than 0")

    if maximum is not None and int_value > maximum:
        raise ValueError(f"'{field}' must not exceed {maximum:,}")

    return int_value


def _require_bool(data: dict, field: str) -> bool:
    value = data.get(field)

    if not isinstance(value, bool):
        raise ValueError(f"'{field}' is required and must be a boolean")

    return value


def _validate_end_date(data: dict, *, reject_past: bool) -> tuple[int, int]:
    """Parse and validate a monthly end month/year, returning ``(end_month, end_year)``.

    Shared by the pledge save (``reject_past=True`` — a saved monthly pledge can't
    already be over) and the calculator (``reject_past=False`` — a past date simply
    yields zero remaining months in the read-only simulation, not an error).
    """
    end_month = data.get("end_month")
    end_year = data.get("end_year")

    if end_month is None:
        raise ValueError("'end_month' is required when 'is_monthly' is true")
    if end_year is None:
        raise ValueError("'end_year' is required when 'is_monthly' is true")

    try:
        end_month = int(end_month)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("'end_month' must be an integer") from exc

    try:
        end_year = int(end_year)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("'end_year' must be an integer") from exc

    if end_month < 1 or end_month > 12:
        raise ValueError("'end_month' must be between 1 and 12")

    # Upper-bound the year on BOTH paths (save + calculate). This is what stops a crafted
    # ``end_year`` from poisoning STATS / exploding the month-count (see MAX_END_YEAR).
    if end_year > MAX_END_YEAR:
        raise ValueError(f"'end_year' must not be later than {MAX_END_YEAR}")

    if reject_past:
        now = datetime.now(timezone.utc)
        if (end_year, end_month) < (now.year, now.month):
            raise ValueError("'end_month' and 'end_year' must not be in the past")

    return end_month, end_year


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
        end_month, end_year = _validate_end_date(data, reject_past=True)
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


def validate_calculate_input(data: dict) -> dict:
    """Validate calculator/simulator input for the read-only ``POST /calculate``.

    Differs from a saved pledge: it carries ``people`` (a what-if group size) and
    ``amount`` is the per-person amount; there is no email or message. A monthly end date
    in the past is **not** rejected — the simulation floors remaining months at 0 (the
    zero-months case).

    ``people`` and ``amount`` are bounded (MAX_PEOPLE / MAX_CALCULATE_AMOUNT) even though
    the simulator stores nothing: the result ``people * amount * months`` must stay a
    finite, sanely-sized number so a crafted request can't force huge-integer arithmetic
    on the shared Lambda (security review 2026-07-02). ``end_year`` is bounded in
    ``_validate_end_date`` (MAX_END_YEAR), same as the save path.
    """
    people = _require_positive_int(data, "people", maximum=MAX_PEOPLE)
    amount = _require_positive_decimal(data, "amount", maximum=MAX_CALCULATE_AMOUNT)
    is_monthly = _require_bool(data, "is_monthly")

    validated = {
        "people": people,
        "amount": amount,
        "is_monthly": is_monthly,
        "end_month": None,
        "end_year": None,
    }

    if is_monthly:
        end_month, end_year = _validate_end_date(data, reject_past=False)
        validated["end_month"] = end_month
        validated["end_year"] = end_year

    return validated


def validate_config_input(data: dict) -> dict:
    """Validate an admin CONFIG update: balance, goal, breakdown, and (optionally) rate.

    Amounts are whole **CZK** ints (the canonical currency, D22). ``current_balance``
    may be 0; ``fundraising_goal`` must be > 0. The breakdown must list exactly the
    known direction keys, each with a non-negative amount — display labels are not
    stored (they live in the i18n dict). ``exchange_rate`` (CZK per EUR) is optional:
    when omitted the write path preserves the existing rate, so an admin tool that only
    edits the numbers can't clobber it; when present it must be a positive number.
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

    validated = {
        "current_balance": current_balance,
        "fundraising_goal": fundraising_goal,
        "breakdown": breakdown,
    }

    # The exchange rate is optional (CZK per EUR). When provided it must be a positive
    # number; when omitted the write path keeps the existing rate (so admin tools that
    # only edit the numbers don't reset it). It is a rate, not a whole-koruna amount, so
    # a fractional value (e.g. 24.22) is allowed.
    if data.get("exchange_rate") is not None:
        validated["exchange_rate"] = _require_positive_decimal(
            data, "exchange_rate", maximum=Decimal("100000")
        )

    return validated
