"""Чистая арифметика воронки: активация, retention, North Star.

Модуль намеренно не знает ни про базу, ни про aiogram: сюда приходят
даты регистрации и множества дней с записями, отсюда уходят числа.
Так метрики можно проверить тестами без поднятия Postgres.
"""

from datetime import date, timedelta
from typing import Dict, List, Set, Tuple

ACTIVATION_WINDOW_DAYS = 7
ACTIVATION_MIN_DAYS = 3
NSM_WEEKS = 4
NSM_DAYS_PER_WEEK = 5
RETENTION_DAYS = (1, 7, 30)


def compute_activation(
    signup_days: List[Tuple[int, date]],
    entry_days: Dict[int, Set[date]],
    today: date,
) -> Tuple[int, int]:
    """(активированных, тех, кто прожил окно активации).

    Активация — ACTIVATION_MIN_DAYS дней с записями внутри первых
    ACTIVATION_WINDOW_DAYS дней после регистрации.
    """
    activated = 0
    eligible = 0
    for user_id, signup_day in signup_days:
        if (today - signup_day).days < ACTIVATION_WINDOW_DAYS:
            continue  # окно ещё не закрылось, считать рано
        eligible += 1
        window_end = signup_day + timedelta(days=ACTIVATION_WINDOW_DAYS)
        in_window = sum(
            1 for d in entry_days.get(user_id, ()) if signup_day <= d < window_end
        )
        if in_window >= ACTIVATION_MIN_DAYS:
            activated += 1
    return activated, eligible


def compute_retention(
    signup_days: List[Tuple[int, date]],
    entry_days: Dict[int, Set[date]],
    today: date,
    day_n: int,
) -> Tuple[int, int]:
    """(вернувшихся ровно на N-й день, тех, кто до этого дня дожил)."""
    returned = 0
    eligible = 0
    for user_id, signup_day in signup_days:
        if (today - signup_day).days < day_n:
            continue
        eligible += 1
        if signup_day + timedelta(days=day_n) in entry_days.get(user_id, ()):
            returned += 1
    return returned, eligible


def compute_north_star(entry_days: Dict[int, Set[date]], today: date) -> int:
    """Сколько пользователей держат 5 дней в неделю 4 недели подряд."""
    count = 0
    for days in entry_days.values():
        if not days:
            continue
        weeks_ok = True
        for week in range(NSM_WEEKS):
            week_end = today - timedelta(days=7 * week)
            week_start = week_end - timedelta(days=7)
            filled = sum(1 for d in days if week_start < d <= week_end)
            if filled < NSM_DAYS_PER_WEEK:
                weeks_ok = False
                break
        if weeks_ok:
            count += 1
    return count
