"""Тесты арифметики воронки: активация, retention, North Star."""

import unittest
from datetime import date, timedelta

from bot.services.funnel_math import (
    compute_activation,
    compute_north_star,
    compute_retention,
)

TODAY = date(2026, 8, 6)


def days_before(*offsets):
    """Множество дат: TODAY минус каждое смещение."""
    return {TODAY - timedelta(days=n) for n in offsets}


class TestActivation(unittest.TestCase):
    def test_three_days_in_window_counts(self):
        signup = TODAY - timedelta(days=10)
        entry_days = {1: {signup, signup + timedelta(days=2), signup + timedelta(days=6)}}
        self.assertEqual(compute_activation([(1, signup)], entry_days, TODAY), (1, 1))

    def test_third_day_outside_window_does_not_count(self):
        signup = TODAY - timedelta(days=10)
        entry_days = {1: {signup, signup + timedelta(days=2), signup + timedelta(days=7)}}
        self.assertEqual(compute_activation([(1, signup)], entry_days, TODAY), (0, 1))

    def test_fresh_user_not_in_denominator(self):
        signup = TODAY - timedelta(days=3)
        entry_days = {1: {signup, signup + timedelta(days=1), signup + timedelta(days=2)}}
        self.assertEqual(compute_activation([(1, signup)], entry_days, TODAY), (0, 0))

    def test_user_without_entries(self):
        signup = TODAY - timedelta(days=30)
        self.assertEqual(compute_activation([(1, signup)], {}, TODAY), (0, 1))


class TestRetention(unittest.TestCase):
    def test_returned_exactly_on_day_seven(self):
        signup = TODAY - timedelta(days=20)
        entry_days = {1: {signup + timedelta(days=7)}}
        self.assertEqual(compute_retention([(1, signup)], entry_days, TODAY, 7), (1, 1))

    def test_day_six_does_not_count_for_d7(self):
        signup = TODAY - timedelta(days=20)
        entry_days = {1: {signup + timedelta(days=6)}}
        self.assertEqual(compute_retention([(1, signup)], entry_days, TODAY, 7), (0, 1))

    def test_user_who_has_not_lived_to_day_n_is_excluded(self):
        signup = TODAY - timedelta(days=5)
        self.assertEqual(compute_retention([(1, signup)], {}, TODAY, 7), (0, 0))

    def test_d1_counts_next_day(self):
        signup = TODAY - timedelta(days=3)
        entry_days = {1: {signup + timedelta(days=1)}}
        self.assertEqual(compute_retention([(1, signup)], entry_days, TODAY, 1), (1, 1))


class TestNorthStar(unittest.TestCase):
    def test_five_days_each_of_four_weeks(self):
        days = set()
        for week in range(4):
            base = 7 * week
            days |= days_before(base + 1, base + 2, base + 3, base + 4, base + 5)
        self.assertEqual(compute_north_star({1: days}, TODAY), 1)

    def test_one_weak_week_breaks_the_streak(self):
        days = set()
        for week in range(4):
            base = 7 * week
            filled = 5 if week != 2 else 4
            days |= days_before(*[base + i for i in range(1, filled + 1)])
        self.assertEqual(compute_north_star({1: days}, TODAY), 0)

    def test_empty_history(self):
        self.assertEqual(compute_north_star({1: set()}, TODAY), 0)


if __name__ == "__main__":
    unittest.main()
