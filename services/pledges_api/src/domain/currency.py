"""Currency conversion at the API boundary (decision D22).

DynamoDB stores every amount in the **canonical currency CZK** — the campaign's real
bank account is in koruna. The API converts to the currency the caller asks for, keyed
by a ``?currency=`` query param that the frontend sends per page language (CZ → ``czk``,
EN → ``eur``):

- **read** endpoints convert canonical CZK → the requested display currency;
- **write** endpoints normalize the incoming amount → canonical CZK before storing.

Keeping the conversion here, once, means no route reimplements it (D19). Amounts are
rounded to whole units (money displays as integers). **Percentages are never converted**
— a ratio is currency-invariant. The exchange rate itself (CZK per EUR) is admin-set in
the ``CONFIG`` row (D22-storage); callers pass it in, so this module stays pure.
"""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# The currency amounts are stored in. No conversion happens for this one.
CANONICAL_CURRENCY = "czk"
SUPPORTED_CURRENCIES = ("czk", "eur")


def parse_currency(value: str | None) -> str:
    """Normalize the ``?currency=`` param to a supported code, defaulting to canonical.

    Missing or unrecognized → ``czk`` (D22: "no param / czk → original koruny"). A read
    must never break the page over a stray currency param; worst case it shows CZK.
    """
    if value is None:
        return CANONICAL_CURRENCY
    code = value.strip().lower()
    return code if code in SUPPORTED_CURRENCIES else CANONICAL_CURRENCY


def _round_whole(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def to_display(amount: Decimal, currency: str, rate: Decimal) -> Decimal:
    """Canonical CZK → the display ``currency`` (whole units)."""
    if currency == CANONICAL_CURRENCY or rate <= 0:
        return amount
    return _round_whole(Decimal(amount) / rate)


def to_canonical(amount: Decimal, currency: str, rate: Decimal, *, round_result: bool = True) -> Decimal:
    """An incoming amount in ``currency`` → canonical CZK.

    ``round_result=True`` (the save path) rounds to a whole koruna — a stored pledge is
    a single canonical value, kept whole so it stays consistent in CZK. The read-only
    simulator passes ``round_result=False``: rounding the per-person amount *before*
    multiplying by people/months would amplify the rounding error, so it keeps full
    precision and rounds only the final output fields (via ``to_display``).
    """
    if currency == CANONICAL_CURRENCY or rate <= 0:
        return amount
    result = Decimal(amount) * rate
    return _round_whole(result) if round_result else result


def convert_fields(obj: dict, fields, currency: str, rate: Decimal) -> dict:
    """Convert the named canonical-CZK money fields in ``obj`` to ``currency``, in place.

    A no-op when ``currency`` is canonical (or the rate is unusable). Fields that are
    absent or ``None`` are skipped. Returns ``obj`` for convenience. Callers add the
    top-level ``currency`` tag themselves (it isn't always at this dict's level — e.g.
    list items).
    """
    if currency == CANONICAL_CURRENCY or rate <= 0:
        return obj
    for field in fields:
        value = obj.get(field)
        if value is not None:
            obj[field] = to_display(Decimal(value), currency, rate)
    return obj


def normalize_amount(body: dict, currency: str, rate: Decimal, *, round_result: bool = True) -> None:
    """Convert ``body['amount']`` from ``currency`` to canonical CZK, in place.

    Shared by the write paths (``POST /pledges`` rounds to whole CZK; ``/calculate``
    keeps precision via ``round_result=False``). A no-op when ``currency`` is canonical
    or ``amount`` is absent; a non-numeric amount is left untouched for the validator to
    reject with a clear message.
    """
    if currency == CANONICAL_CURRENCY or "amount" not in body:
        return
    try:
        body["amount"] = to_canonical(
            Decimal(str(body["amount"])), currency, rate, round_result=round_result
        )
    except (InvalidOperation, TypeError):
        pass
