"""Тесты напоминаний: когда бот пишет, а когда молчит."""

from datetime import datetime, time, timedelta, timezone

import pytest

from bot.models.patient import Patient
from bot.models.symptom import SymptomEntry
from bot.models.user import User
from bot.services.scheduler import ReminderScheduler


class FakeBot:
    """Бот, который никуда не ходит, а записывает отправленное."""

    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, reply_markup=None):
        self.sent.append((chat_id, text))


async def _seed(session_maker, *, entry_offsets=(), case_closed=False):
    """Пользователь с активным пациентом и записями в дневнике."""
    now = datetime.now(timezone.utc)

    async with session_maker() as session:
        user = User(
            id=100,
            first_name="Тест",
            full_name="Тестов Тест",
            phone="+79990000000",
            reminder_time=time(20, 0),
            user_tz="Europe/Moscow",
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        await session.flush()

        patient = Patient(
            user_id=user.id,
            relation="self",
            display_name="Тестов Тест",
            nosology="ars",
            is_active=True,
            case_closed_at=now if case_closed else None,
        )
        session.add(patient)
        await session.flush()

        user.active_patient_id = patient.id

        for offset in entry_offsets:
            session.add(
                SymptomEntry(
                    user_id=user.id,
                    patient_id=patient.id,
                    nosology="ars",
                    recorded_at=now - timedelta(days=offset),
                    symptoms={},
                    composite_score=3,
                    triage_level="green",
                    triage_message="",
                    red_flags=[],
                )
            )

        await session.commit()


@pytest.fixture
def scheduler():
    instance = ReminderScheduler()
    instance.bot = FakeBot()
    return instance


async def test_reminder_sent_when_diary_is_empty(db, scheduler):
    await _seed(db)
    await scheduler._send_reminder(100)
    assert len(scheduler.bot.sent) == 1


async def test_reminder_skipped_when_already_logged_today(db, scheduler):
    await _seed(db, entry_offsets=(0,))
    await scheduler._send_reminder(100)
    assert scheduler.bot.sent == []


async def test_reminder_sent_when_last_entry_was_yesterday(db, scheduler):
    await _seed(db, entry_offsets=(1,))
    await scheduler._send_reminder(100)
    assert len(scheduler.bot.sent) == 1


async def test_reminder_skipped_for_closed_case(db, scheduler):
    await _seed(db, case_closed=True)
    await scheduler._send_reminder(100)
    assert scheduler.bot.sent == []


async def test_reactivation_fires_on_day_seven(db, scheduler):
    await _seed(db, entry_offsets=(7,))
    await scheduler._reactivation_sweep()
    assert len(scheduler.bot.sent) == 1
    assert "Неделя без записей" in scheduler.bot.sent[0][1]


async def test_reactivation_silent_on_day_five(db, scheduler):
    await _seed(db, entry_offsets=(5,))
    await scheduler._reactivation_sweep()
    assert scheduler.bot.sent == []


async def test_weekly_digest_counts_filled_days(db, scheduler):
    await _seed(db, entry_offsets=(0, 1, 2, 3, 4))
    await scheduler._weekly_digest()
    assert len(scheduler.bot.sent) == 1
    assert "Заполнено дней: 5 из 7" in scheduler.bot.sent[0][1]


async def test_weekly_digest_skips_silent_week(db, scheduler):
    await _seed(db, entry_offsets=(20,))
    await scheduler._weekly_digest()
    assert scheduler.bot.sent == []
