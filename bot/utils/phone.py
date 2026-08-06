"""Phone number parsing and validation (RU-leaning, international-tolerant)."""

import re

_DIGIT_RE = re.compile(r"\D+")


def normalize_phone(raw: str) -> str | None:
    """
    Normalize a user-entered phone to E.164-ish format.

    Rules:
    - Strip all non-digit characters except a leading '+'.
    - If the result starts with '8' and has 11 digits — convert to '+7…'.
    - If it starts with '7' and has 11 digits — add '+'.
    - Otherwise, accept only values that begin with '+' and contain 10–15 digits.

    Returns the normalized string (e.g., '+79991234567') or None if invalid.
    """
    if raw is None:
        return None

    s = raw.strip()
    has_plus = s.startswith("+")
    digits = _DIGIT_RE.sub("", s)

    if not digits:
        return None

    # Russian conveniences
    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
        has_plus = True
    elif len(digits) == 11 and digits[0] == "7":
        has_plus = True
    elif len(digits) == 10 and not has_plus:
        # Local Russian 10-digit — assume +7
        digits = "7" + digits
        has_plus = True

    if not has_plus:
        return None

    if not (10 <= len(digits) <= 15):
        return None

    return "+" + digits


def is_valid_phone(raw: str) -> bool:
    return normalize_phone(raw) is not None
