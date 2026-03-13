"""Validation logic for pledges"""
import re
from typing import Optional, Tuple


def validate_pledge_input(data: dict) -> Tuple[bool, Optional[str]]:
    """
    Validate pledge creation input.

    Returns:
        (is_valid, error_message)
    """
    required_fields = ["name", "email", "amount", "is_monthly"]

    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"

    # Validate name
    name = data.get("name", "").strip()
    if not name or len(name) < 2:
        return False, "Name must be at least 2 characters"
    if len(name) > 100:
        return False, "Name must be less than 100 characters"

    # Validate email
    email = data.get("email", "").strip()
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False, "Invalid email format"

    # Validate amount
    try:
        amount = int(data.get("amount"))
        if amount < 1:
            return False, "Amount must be at least 1"
        if amount > 1000000:
            return False, "Amount must be less than 1,000,000"
    except (ValueError, TypeError):
        return False, "Amount must be a valid integer"

    # Validate is_monthly
    is_monthly = data.get("is_monthly")
    if not isinstance(is_monthly, bool):
        return False, "is_monthly must be a boolean"

    # Validate optional message
    message = data.get("message")
    if message is not None:
        if not isinstance(message, str):
            return False, "Message must be a string"
        if len(message) > 500:
            return False, "Message must be less than 500 characters"

    return True, None
