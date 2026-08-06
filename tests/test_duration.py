"""Длительность болезни: со слов пациента и по истории дневника."""

import unittest
from datetime import datetime, timedelta, timezone

from bot.triage.engine import reported_duration_days, run_triage
from bot.triage.params import compute_composite_score

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)


class _Entry:
    def __init__(self, nosology, symptoms, score, recorded_at):
        self.nosology = nosology
        self.symptoms = symptoms
        self.composite_score = score
        self.recorded_at = recorded_at


ARS_MILD = {
    "ars_temp": 1,
    "ars_obstruction": 2,
    "ars_facial_pain": 1,
    "ars_discharge": 2,
    "ars_smell": 1,
    "ars_headache": 1,
    "ars_malaise": 1,
}


class TestReportedDuration(unittest.TestCase):
    def test_reads_days_from_answer(self):
        self.assertEqual(reported_duration_days({"ars_onset_days": 12}), 12)

    def test_no_answer_means_zero(self):
        self.assertEqual(reported_duration_days(ARS_MILD), 0)

    def test_fever_duration_is_not_illness_duration(self):
        self.assertEqual(reported_duration_days({"ars_fever_duration": 3}), 0)


class TestFirstEntry(unittest.TestCase):
    def test_twelfth_day_of_illness_is_not_green(self):
        """Человек болеет 12 дней и только сегодня нашёл бота."""
        symptoms = dict(ARS_MILD, ars_onset_days=12)
        entry = _Entry("ars", symptoms, 9, NOW)
        result = run_triage(entry, [], NOW)
        self.assertEqual(result["triage_level"], "yellow")
        self.assertIn("10 дней", result["triage_message"])

    def test_third_day_of_illness_stays_green(self):
        symptoms = dict(ARS_MILD, ars_onset_days=2)
        entry = _Entry("ars", symptoms, 9, NOW)
        self.assertEqual(run_triage(entry, [], NOW)["triage_level"], "green")


class TestFollowUp(unittest.TestCase):
    def test_onset_carries_over_to_later_entries(self):
        """Вопрос задан один раз, но дни продолжают считаться."""
        first = _Entry(
            "ars", dict(ARS_MILD, ars_onset_days=7), 9, NOW - timedelta(days=4)
        )
        # На повторном заполнении вопроса про длительность уже нет
        second = _Entry("ars", dict(ARS_MILD), 9, NOW)

        result = run_triage(second, [first, second], NOW)
        # 7 дней до дневника плюс 4 дня в дневнике это больше 10
        self.assertEqual(result["triage_level"], "yellow")
        self.assertIn("10 дней", result["triage_message"])


class TestAomWatchfulWaiting(unittest.TestCase):
    def test_no_improvement_after_two_days_is_yellow(self):
        symptoms = {
            "aom_ear_pain": 1,
            "aom_hearing": 1,
            "aom_discharge": 0,
            "aom_temp": 1,
            "aom_bilateral": 0,
            "aom_malaise": 1,
            "aom_age": "6-14y",
            "aom_onset_days": 4,
            "postauricular_swelling": 0,
            "protruding_pinna": 0,
        }
        entry = _Entry("aom", symptoms, 4, NOW)
        history = [_Entry("aom", symptoms, 4, NOW - timedelta(days=1))]
        result = run_triage(entry, history, NOW)
        self.assertEqual(result["triage_level"], "yellow")



class TestCompositeScore(unittest.TestCase):
    """Длительности не должны попадать в сумму баллов симптомов."""

    def test_onset_days_excluded(self):
        self.assertEqual(
            compute_composite_score({"ars_obstruction": 2, "ars_onset_days": 12}), 2
        )

    def test_effusion_duration_excluded(self):
        # value_map переводит бакет в дни, 240 в балле означал бы,
        # что шкала сломана
        self.assertEqual(
            compute_composite_score({"com_hearing": 2, "effusion_duration": 240}), 2
        )

    def test_fever_duration_excluded(self):
        self.assertEqual(
            compute_composite_score({"ars_temp": 3, "ars_fever_duration": 2}), 3
        )

    def test_age_group_and_unknown_answers_excluded(self):
        values = {"tp_throat_pain": 2, "tp_age": "6-14y", "tp_exudate": -1}
        self.assertEqual(compute_composite_score(values), 2)


if __name__ == "__main__":
    unittest.main()
