"""Тесты разбора свободной заметки пациента."""

import unittest

from bot.services.notes_scan import scan_notes


class TestRedFlags(unittest.TestCase):
    def test_cannot_breathe(self):
        level, matched = scan_notes("Ночью не могу дышать, страшно")
        self.assertEqual(level, "red")
        self.assertTrue(matched)

    def test_word_forms(self):
        # «задыхался» не совпадает с «задыхаюсь» по подстроке, но должно
        # ловиться по основе
        level, _ = scan_notes("Вчера вечером задыхался минут десять")
        self.assertEqual(level, "red")

    def test_bleeding(self):
        level, _ = scan_notes("Кровь течёт из носа второй час")
        self.assertEqual(level, "red")


class TestNegation(unittest.TestCase):
    def test_no_bleeding(self):
        level, matched = scan_notes("Выделения светлые, кровотечения нет")
        self.assertIsNone(level, matched)

    def test_symptom_in_next_clause_survives(self):
        # «не» относится к температуре, гной остаётся находкой
        level, matched = scan_notes("Гной есть, температура не снижается")
        self.assertEqual(level, "yellow")
        self.assertEqual(len(matched), 2)

    def test_fear_is_not_a_symptom(self):
        level, matched = scan_notes("Боюсь кровотечения, но пока всё спокойно")
        self.assertIsNone(level, matched)

    def test_vomiting_in_the_past(self):
        level, matched = scan_notes("Рвоты нет со вчерашнего дня")
        self.assertIsNone(level, matched)

    def test_no_pus(self):
        level, matched = scan_notes("Без гноя, налётов не вижу")
        self.assertIsNone(level, matched)

    def test_negation_inside_phrase_still_fires(self):
        # «не» здесь часть самой фразы, а не отрицание находки
        level, _ = scan_notes("Совсем не могу глотать даже воду")
        self.assertEqual(level, "red")

    def test_treatment_not_helping_fires(self):
        level, _ = scan_notes("Пятый день антибиотик не помогает")
        self.assertEqual(level, "yellow")


class TestYellowFlags(unittest.TestCase):
    def test_got_worse(self):
        level, _ = scan_notes("К вечеру стало хуже")
        self.assertEqual(level, "yellow")

    def test_dizziness_word_form(self):
        level, _ = scan_notes("Утром кружилась голова")
        self.assertEqual(level, "yellow")

    def test_red_beats_yellow(self):
        level, _ = scan_notes("Стало хуже, задыхаюсь")
        self.assertEqual(level, "red")

    def test_several_yellow_groups(self):
        level, matched = scan_notes("Сильная боль, гной, температура не снижается")
        self.assertEqual(level, "yellow")
        self.assertGreaterEqual(len(matched), 3)


class TestNeutralText(unittest.TestCase):
    def test_plain_note(self):
        level, matched = scan_notes("Сегодня лучше, спал нормально")
        self.assertIsNone(level)
        self.assertEqual(matched, [])

    def test_empty(self):
        self.assertEqual(scan_notes(""), (None, []))

    def test_only_punctuation(self):
        self.assertEqual(scan_notes("..."), (None, []))


if __name__ == "__main__":
    unittest.main()
