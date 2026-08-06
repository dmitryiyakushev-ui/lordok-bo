"""Политика по температуре выше 39 (решение от 06.08.2026).

Одна высокая температура сама по себе даёт жёлтый: обычная вирусная
инфекция так и выглядит. Любой второй тревожный признак рядом с ней
переводит оценку в красный.
"""

import unittest
from datetime import datetime, timedelta, timezone

from bot.triage.engine import run_triage


class _Entry:
    """Минимальная замена SymptomEntry для чистой проверки движка."""

    def __init__(self, symptoms, composite_score, recorded_at):
        self.nosology = "ars"
        self.symptoms = symptoms
        self.composite_score = composite_score
        self.recorded_at = recorded_at


NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)


def _run(symptoms, score):
    entry = _Entry(symptoms, score, NOW)
    history = [_Entry(symptoms, score, NOW - timedelta(days=2))]
    return run_triage(entry, history, NOW)


BASE = {
    "ars_obstruction": 2,
    "ars_facial_pain": 1,
    "ars_discharge": 1,
    "ars_smell": 1,
    "ars_headache": 1,
    "ars_malaise": 2,
}


class TestHighFeverPolicy(unittest.TestCase):
    def test_fever_alone_is_yellow(self):
        symptoms = dict(BASE, ars_temp=3)
        self.assertEqual(_run(symptoms, 11)["triage_level"], "yellow")

    def test_fever_plus_severe_symptom_is_red(self):
        symptoms = dict(BASE, ars_temp=3, ars_facial_pain=3)
        self.assertEqual(_run(symptoms, 13)["triage_level"], "red")

    def test_fever_plus_purulent_discharge_is_red(self):
        symptoms = dict(BASE, ars_temp=3, ars_discharge=3)
        self.assertEqual(_run(symptoms, 13)["triage_level"], "red")

    def test_fever_plus_failing_antipyretic_is_red(self):
        symptoms = dict(BASE, ars_temp=3, ars_antipyretic=2)
        self.assertEqual(_run(symptoms, 13)["triage_level"], "red")

    def test_moderate_fever_is_not_escalated(self):
        symptoms = dict(BASE, ars_temp=2, ars_facial_pain=3)
        self.assertNotEqual(_run(symptoms, 12)["triage_level"], "red")


class TestSignalCounting(unittest.TestCase):
    def test_purulent_discharge_counts_once(self):
        from bot.triage.engine import _count_soft_alarm_signals

        self.assertEqual(
            _count_soft_alarm_signals(dict(BASE, ars_discharge=3)), 1
        )

    def test_each_severe_symptom_counts(self):
        from bot.triage.engine import _count_soft_alarm_signals

        symptoms = dict(BASE, ars_facial_pain=3, ars_obstruction=3, ars_smell=3)
        self.assertEqual(_count_soft_alarm_signals(symptoms), 3)


if __name__ == "__main__":
    unittest.main()
