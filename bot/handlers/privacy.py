"""Права субъекта персональных данных: /privacy, /my_data, /delete_me.

152-ФЗ даёт человеку право узнать, что о нём хранится, и отозвать
согласие. Раньше это делалось письмом на почту оператора, теперь
прямо в боте.

Отзыв согласия здесь означает полное удаление: профиль, пациенты,
дневник, шкалы, эпизоды, отзывы и события аналитики. Восстановить
нечего, поэтому шаг подтверждается отдельной кнопкой.
"""

import json
import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import delete, select

from bot.db.database import get_session
from bot.keyboards.reply import main_menu_keyboard, remove_reply_keyboard
from bot.models.episode import EpisodeLog
from bot.models.event import BotEvent
from bot.models.feedback import Feedback
from bot.models.patient import Patient
from bot.models.scale_score import ScaleScore
from bot.models.symptom import SymptomEntry
from bot.models.user import User
from bot.services.analytics import log_event

logger = logging.getLogger(__name__)
router = Router()

SITE_URL = "https://lor-dok.ru"


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🗑 Да, удалить все мои данные",
            callback_data="delete_me:confirm",
        )],
        [InlineKeyboardButton(text="Отмена", callback_data="delete_me:cancel")],
    ])


@router.message(Command("privacy"))
async def cmd_privacy(message: Message):
    """Что хранится, на каком основании и как это прекратить."""
    async with get_session() as session:
        user = await session.get(User, message.from_user.id)

    if user and user.consent_at:
        consent_line = (
            f"Согласие дано {user.consent_at:%d.%m.%Y}, "
            f"редакция документов от {user.consent_version}.\n\n"
        )
    else:
        consent_line = ""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📄 Политика конфиденциальности",
            url=f"{SITE_URL}/privacy.html",
        )],
        [InlineKeyboardButton(
            text="📋 Пользовательское соглашение",
            url=f"{SITE_URL}/terms.html",
        )],
    ])

    await message.answer(
        "🔒 Ваши данные\n\n"
        + consent_line
        + "Оператор: Якушев Дмитрий Игоревич, самозанятый, ИНН 781624864719.\n"
        "Данные хранятся на сервере в России и третьим лицам не передаются.\n\n"
        "/my_data выгружает всё, что о вас хранится, одним файлом\n"
        "/delete_me отзывает согласие и удаляет данные",
        reply_markup=keyboard,
    )


@router.message(Command("my_data"))
async def cmd_my_data(message: Message):
    """Выгрузка всех данных пользователя одним JSON-файлом."""
    user_id = message.from_user.id

    async with get_session() as session:
        user = await session.get(User, user_id)
        if user is None:
            await message.answer("Данных о вас нет. Начните с /start.")
            return

        patients = (await session.execute(
            select(Patient).where(Patient.user_id == user_id)
        )).scalars().all()

        entries = (await session.execute(
            select(SymptomEntry)
            .where(SymptomEntry.user_id == user_id)
            .order_by(SymptomEntry.recorded_at)
        )).scalars().all()

        scales = (await session.execute(
            select(ScaleScore).where(ScaleScore.user_id == user_id)
        )).scalars().all()

        episodes = (await session.execute(
            select(EpisodeLog).where(EpisodeLog.user_id == user_id)
        )).scalars().all()

        feedbacks = (await session.execute(
            select(Feedback).where(Feedback.user_id == user_id)
        )).scalars().all()

    payload = {
        "выгружено": datetime.now(timezone.utc).isoformat(),
        "профиль": {
            "telegram_id": user.id,
            "имя_в_telegram": user.first_name,
            "username": user.username,
            "фио": user.full_name,
            "телефон": user.phone,
            "часовой_пояс": user.user_tz,
            "время_напоминания": str(user.reminder_time),
            "источник": user.source,
            "согласие": {
                "редакция": user.consent_version,
                "дата": user.consent_at.isoformat() if user.consent_at else None,
            },
            "зарегистрирован": user.created_at.isoformat(),
        },
        "пациенты": [
            {
                "id": p.id,
                "имя": p.display_name,
                "кто": p.relation,
                "пол": p.sex,
                "дата_рождения": str(p.date_of_birth) if p.date_of_birth else None,
                "диагноз": p.nosology,
                "случай_закрыт": (
                    p.case_closed_at.isoformat() if p.case_closed_at else None
                ),
                "активен": p.is_active,
            }
            for p in patients
        ],
        "дневник": [
            {
                "дата": e.recorded_at.isoformat(),
                "пациент_id": e.patient_id,
                "диагноз": e.nosology,
                "симптомы": e.symptoms,
                "сумма_баллов": e.composite_score,
                "оценка": e.triage_level,
                "текст_оценки": e.triage_message,
                "красные_флаги": e.red_flags,
                "заметка": e.user_notes,
            }
            for e in entries
        ],
        "шкалы": [
            {
                "дата": s.created_at.isoformat() if s.created_at else None,
                "шкала": s.scale,
                "балл": s.score,
                "действие": s.action,
            }
            for s in scales
        ],
        "эпизоды": [
            {
                "тип": ep.episode_type,
                "начало": ep.started_at.isoformat() if ep.started_at else None,
                "конец": ep.ended_at.isoformat() if ep.ended_at else None,
                "подтверждён_врачом": ep.confirmed_by_doctor,
            }
            for ep in episodes
        ],
        "обратная_связь": [
            {
                "дата": f.created_at.isoformat(),
                "оценка": f.rating,
                "комментарий": f.comment,
            }
            for f in feedbacks
        ],
    }

    raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    filename = f"lordok_my_data_{datetime.now(timezone.utc):%Y%m%d}.json"

    await message.answer_document(
        BufferedInputFile(raw, filename=filename),
        caption=(
            "Здесь всё, что хранится о вас и ваших пациентах. "
            "Файл читается любым текстовым редактором."
        ),
    )
    await log_event(user_id=user_id, event_type="data_exported")


@router.message(Command("delete_me"))
async def cmd_delete_me(message: Message, state: FSMContext):
    """Первый шаг отзыва согласия: предупреждение и подтверждение."""
    await state.clear()

    async with get_session() as session:
        user = await session.get(User, message.from_user.id)

    if user is None:
        await message.answer("Данных о вас нет, удалять нечего.")
        return

    await message.answer(
        "⚠️ Отзыв согласия и удаление данных\n\n"
        "Будут удалены безвозвратно:\n"
        "• профиль и телефон;\n"
        "• все профили пациентов, включая детей;\n"
        "• весь дневник симптомов и оценки;\n"
        "• отчёты, шкалы, эпизоды и отзывы.\n\n"
        "Выгрузить копию перед удалением можно командой /my_data.\n\n"
        "Удалить?",
        reply_markup=_confirm_keyboard(),
    )


@router.callback_query(F.data == "delete_me:cancel")
async def handle_delete_cancel(callback: CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "Удаление отменено. Данные на месте.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "delete_me:confirm")
async def handle_delete_confirm(callback: CallbackQuery, state: FSMContext):
    """Полное удаление данных пользователя."""
    user_id = callback.from_user.id

    async with get_session() as session:
        # symptom_entries, scale_scores, episode_logs и patients уходят
        # каскадом за users; feedbacks и bot_events внешнего ключа не
        # имеют, поэтому удаляются явно.
        await session.execute(delete(Feedback).where(Feedback.user_id == user_id))
        await session.execute(delete(BotEvent).where(BotEvent.user_id == user_id))
        user = await session.get(User, user_id)
        if user is not None:
            await session.delete(user)
        await session.commit()

    await state.clear()

    # Снимаем персональное напоминание, иначе бот продолжит писать
    # человеку, который только что удалил профиль.
    try:
        from bot.main import get_reminder_scheduler

        scheduler = get_reminder_scheduler().scheduler
        job = scheduler.get_job(f"reminder_{user_id}")
        if job:
            scheduler.remove_job(f"reminder_{user_id}")
    except Exception:
        logger.warning("Could not remove reminder job for %s", user_id, exc_info=True)

    logger.info("User %s deleted their data", user_id)

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "Данные удалены, согласие отозвано.\n\n"
        "Если захотите вернуться, начните с /start заново.",
        reply_markup=remove_reply_keyboard(),
    )
    await callback.answer()
