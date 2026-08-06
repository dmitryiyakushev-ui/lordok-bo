"""Demographics helpers: age computation, age_group derivation, DoB handling."""

from datetime import date, datetime, timezone
from typing import Optional

# Age group codes used by the triage engine (kept in sync with inline keyboards).
AGE_GROUPS = ("<6mo", "6-23mo", "2-5y", "6-14y", "15-44y", ">=45y")


def compute_dob(years: int, months: int, today: Optional[date] = None) -> date:
    """
    Given declared age (years + months), return a synthetic date_of_birth.

    We don't know the exact day, so we use the 1st of the month for stability.
    This is sufficient for age_group derivation and re-computation on re-login.
    """
    if today is None:
        today = datetime.now(timezone.utc).date()

    # Total months back from today
    total_months = years * 12 + months

    year = today.year
    month = today.month - total_months

    while month <= 0:
        month += 12
        year -= 1

    return date(year, month, 1)


def age_in_months(dob: date, today: Optional[date] = None) -> int:
    """Return age in full months on `today`."""
    if today is None:
        today = datetime.now(timezone.utc).date()

    months = (today.year - dob.year) * 12 + (today.month - dob.month)
    if today.day < dob.day:
        months -= 1
    return max(0, months)


def age_in_years(dob: date, today: Optional[date] = None) -> int:
    """Return age in completed years on `today`."""
    if today is None:
        today = datetime.now(timezone.utc).date()

    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return max(0, years)


def derive_age_group(
    dob: Optional[date],
    legacy_fallback: Optional[str] = None,
    today: Optional[date] = None,
) -> str:
    """
    Return age_group code from date_of_birth.

    If DoB is unknown (e.g., legacy record pre-resolution) fall back to
    the stored legacy_age_group. If that is also absent, return '15-44y'
    as a conservative adult default.
    """
    if dob is None:
        if legacy_fallback in AGE_GROUPS:
            return legacy_fallback
        return "15-44y"

    months = age_in_months(dob, today)

    if months < 6:
        return "<6mo"
    if months < 24:
        return "6-23mo"

    years = age_in_years(dob, today)
    if years < 6:
        return "2-5y"
    if years < 15:
        return "6-14y"
    if years < 45:
        return "15-44y"
    return ">=45y"


def format_age_ru(dob: Optional[date], today: Optional[date] = None) -> str:
    """Human-readable age, e.g., '3 года 4 месяца' or '8 месяцев'."""
    if dob is None:
        return "возраст не указан"

    total_months = age_in_months(dob, today)
    years = total_months // 12
    months = total_months % 12

    parts = []
    if years:
        parts.append(f"{years} {_plural_ru(years, 'год', 'года', 'лет')}")
    if months or not years:
        parts.append(f"{months} {_plural_ru(months, 'месяц', 'месяца', 'месяцев')}")
    return " ".join(parts)


def _plural_ru(n: int, one: str, few: str, many: str) -> str:
    n = abs(n) % 100
    if 10 < n < 20:
        return many
    n = n % 10
    if n == 1:
        return one
    if 1 < n < 5:
        return few
    return many
