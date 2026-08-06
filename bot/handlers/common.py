"""Common handlers: /help, /settings, /reset, /cancel + catch-all fallback."""

import logging
from datetime import datetime, time, timezone

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from bot.db.database import get_session
from bot.keyboards.inline import reminder_time_keyboard
from bot.keyboards.reply import main_menu_keyboard, remove_reply_keyboard
from bot.models.patient import Patient
from bot.models.user import User
from bot.utils.demographics import format_age_ru

logger = logging.getLogger(__name__)
router = Router()


class SettingsState(StatesGroup):
    choosing_setting = State()
    updating_reminder = State()


@router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "📖 **Справка по ЛОРдоку**\n\n"
        "Пользуйтесь кнопками внизу экрана:\n"
        "📝 Дневник — заполнить запись о симптомах\n"
        "📋 История — последние записи (7–30 дней)\n"
        "📊 Отчёт — PDF-отчёт за выбранный период\n"
        "👥 Пациенты — профили, активный пациент, изменить жалобу/диагноз\n"
        "⚙️ Настройки — профиль и время напоминания\n\n"
        "Команды (работают параллельно с меню):\n"
        "/start · /log · /history · /report · /patients · /settings · "
        "/change_condition · /reset · /help\n\n"
        "⚠️ Бот не ставит диагнозы и не заменяет врача. "
        "При ухудшении симптомов обратитесь к ЛОР-врачу.\n\n"
        "💬 Поддержка: support@lordok.ru"
    )
    await message.answer(text, reply_markup=main_menu_keyboard())


@router.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    async with get_session() as session:
        user = await session.get(User, user_id)
        if not user or not user.full_name:
            await message.answer(
                "❌ Сначала завершите знакомство через /start",
                reply_markup=remove_reply_keyboard(),
            )
            return

        active_patient = None
        if user.active_patient_id:
            active_patient = await session.get(Patient, user.active_patient_id)

    lines = [
        "⚙️ **Ваш профиль**",
        "",
        f"👤 ФИО: {user.full_name}",
        f"📱 Телефон: {user.phone or '—'}",
        f"🔔 Напоминание: {user.reminder_time.strftime('%H:%M') if user.reminder_time else '—'}",
    ]
    if active_patient:
        age = (
            format_age_ru(active_patient.date_of_birth)
            if active_patient.date_of_birth
            else (active_patient.legacy_age_group or "—")
        )
        lines += [
            "",
            "📋 **Активный пациент**",
            f"Имя: {active_patient.display_name}",
            f"Возраст: {age}",
            f"Диагноз/жалоба: {active_patient.nosology or '—'}",
        ]
    else:
        lines += ["", "Активный пациент не выбран. Настройте через /patients."]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔔 Изменить напоминание", callback_data="setting:reminder")],
            [InlineKeyboardButton(text="👥 Управление пациентами", callback_data="setting:patients")],
        ]
    )
    await message.answer("\n".join(lines), reply_markup=keyboard)
    await state.set_state(SettingsState.choosing_setting)


@router.callback_query(
    SettingsState.choosing_setting, F.data.startswith("setting:")
)
async def handle_setting_choice(callback: CallbackQuery, state: FSMContext):
    setting = callback.data.split(":")[1]

    if setting == "reminder":
        await callback.message.answer(
            "Выберите новое время напоминания:",
            reply_markup=reminder_time_keyboard(),
        )
        await state.set_state(SettingsState.updating_reminder)
    elif setting == "patients":
        await callback.message.answer(
            "Откройте меню пациентов кнопкой «👥 Пациенты».",
            reply_markup=main_menu_keyboard(),
        )
        await state.clear()
    await callback.answer()


@router.callback_query(
    SettingsState.updating_reminder, F.data.startswith("reminder:")
)
async def handle_update_reminder(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    hour, minute = int(parts[1]), int(parts[2])
    reminder_time_obj = time(hour, minute)

    async with get_session() as session:
        user = await session.get(User, user_id)
        if user:
            user.reminder_time = reminder_time_obj
            user.updated_at = datetime.now(timezone.utc)
            await session.commit()

    await callback.message.answer(
        f"✅ Напоминание установлено на {hour:02d}:{minute:02d}",
        reply_markup=main_menu_keyboard(),
    )
    await state.clear()
    await callback.answer()


# ──────────────────────────────────────────────────────────────────────
# /reset — full profile rebuild (keeps symptom history)
# ──────────────────────────────────────────────────────────────────────


@router.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext):
    """Clear account profile fields so /start triggers full onboarding again."""
    await state.clear()
    user_id = message.from_user.id
    async with get_session() as session:
        user = await session.get(User, user_id)
        if not user:
            await message.answer(
                "Нет данных для сброса. Используйте /start.",
                reply_markup=remove_reply_keyboard(),
            )
            return
        # Archive all patients; keep symptom_entries for audit
        stmt = (
            select(Patient)
            .where(Patient.user_id == user_id)
            .where(Patient.is_active.is_(True))
        )
        result = await session.execute(stmt)
        for p in result.scalars():
            p.is_active = False
            p.updated_at = datetime.now(timezone.utc)

        user.full_name = None
        user.phone = None
        user.active_patient_id = None
        user.nosology = None
        user.age_group = None
        user.updated_at = datetime.now(timezone.utc)
        await session.commit()

    await message.answer(
        "Профиль сброшен. История симптомов сохранена.\n"
        "Запустите /start, чтобы пройти регистрацию заново.",
        reply_markup=remove_reply_keyboard(),
    )


# ──────────────────────────────────────────────────────────────────────
# /cancel — universal escape hatch from any FSM state
# ──────────────────────────────────────────────────────────────────────


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Clear any active FSM state and return the user to the main menu."""
    current = await state.get_state()
    await state.clear()
    if current:
        text = "✅ Действие отменено. Выберите следующий шаг в меню ниже."
    else:
        text = "Нечего отменять. Главное меню ниже."
    await message.answer(text, reply_markup=main_menu_keyboard())


# ──────────────────────────────────────────────────────────────────────
# Catch-all text fallback
#
# Registered LAST (this router is included last in main.py and this
# handler is defined at the bottom of the file). It only fires when:
#   - no FSM state is active (so onboarding text inputs aren't eaten)
#   - the message is plain text (not a command, contact, photo, etc.)
# Purpose: if the user types something random after finishing a flow,
# we nudge them back to the main menu instead of silently ignoring it.
# ──────────────────────────────────────────────────────────────────────


@router.message(StateFilter(None), F.text)
async def catch_all_text(message: Message):
    text = (message.text or "").strip()
    # Don't eat slash commands — those should have been caught upstream;
    # if they reached here, it means the command isn't registered.
    if text.startswith("/"):
        await message.answer(
            "Такой команды я не знаю. Нажмите /help или выберите "
            "действие в меню ниже.",
            reply_markup=main_menu_keyboard(),
        )
        return
    await message.answer(
        "Я понимаю команды и кнопки меню. Выберите действие ниже или "
        "напишите /help.",
        reply_markup=main_menu_keyboard(),
    )
