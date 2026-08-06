"""Тесты сборки воронки из базы."""

from datetime import datetime, time, timedelta, timezone

from bot.models.event import BotEvent
from bot.models.patient import Patient
from bot.models.symptom import SymptomEntry
from bot.models.user import User
from bot.services.metrics import collect_funnel

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)


async def _add_user(session, user_id: int, days_ago: int, source=None):
    created = NOW - timedelta(days=days_ago)
    user = User(
        id=user_id,
        first_name=f"Юзер {user_id}",
        full_name=f"Юзер {user_id}",
        phone="+79990000000",
        source=source,
        reminder_time=time(20, 0),
        created_at=created,
        updated_at=created,
    )
    session.add(user)
    await session.flush()

    patient = Patient(
        user_id=user_id,
        relation="self",
        display_name=f"Юзер {user_id}",
        nosology="ars",
        is_active=True,
    )
    session.add(patient)
    await session.flush()
    user.active_patient_id = patient.id
    return user, patient


async def _add_entries(session, user, patient, day_offsets):
    """Записи дневника на указанных днях после регистрации."""
    for offset in day_offsets:
        session.add(
            SymptomEntry(
                user_id=user.id,
                patient_id=patient.id,
                nosology="ars",
                recorded_at=user.created_at + timedelta(days=offset),
                symptoms={},
                composite_score=2,
                triage_level="green",
                triage_message="",
                red_flags=[],
            )
        )


async def test_activation_and_retention(db):
    async with db() as session:
        # Дошёл до активации: три дня записей в первую неделю, вернулся на 7-й
        user_a, patient_a = await _add_user(session, 1, days_ago=40, source="reels")
        await _add_entries(session, user_a, patient_a, [0, 1, 7])

        # Записался один раз и пропал
        user_b, patient_b = await _add_user(session, 2, days_ago=40)
        await _add_entries(session, user_b, patient_b, [0])

        # Зарегистрировался вчера: в знаменатель активации не попадает
        user_c, patient_c = await _add_user(session, 3, days_ago=1)
        await _add_entries(session, user_c, patient_c, [0])

        session.add(BotEvent(
            user_id=1, event_type="start", detail="reels",
            created_at=NOW - timedelta(days=40),
        ))
        session.add(BotEvent(
            user_id=2, event_type="start", detail="direct",
            created_at=NOW - timedelta(days=40),
        ))
        await session.commit()

        data = await collect_funnel(session, NOW)

    assert data["activation"] == (1, 2)
    assert data["retention"][7] == (1, 2)
    assert data["retention"][1] == (1, 3)
    assert data["starts"] == 2
    assert dict(data["sources_started"])["reels"] == 1


async def test_north_star_counts_regular_users(db):
    async with db() as session:
        user, patient = await _add_user(session, 1, days_ago=60)
        # Пять дней в каждой из последних четырёх недель
        offsets = []
        for week in range(4):
            for day in range(1, 6):
                offsets.append(60 - (7 * week + day))
        await _add_entries(session, user, patient, offsets)
        await session.commit()

        data = await collect_funnel(session, NOW)

    assert data["nsm"] == 1


async def test_empty_database(db):
    async with db() as session:
        data = await collect_funnel(session, NOW)

    assert data["starts"] == 0
    assert data["registered"] == 0
    assert data["activation"] == (0, 0)
    assert data["nsm"] == 0
