"""Main menu button dispatcher.

Binds the five ReplyKeyboard buttons (📝 Дневник / 📋 История / 📊 Отчёт /
👥 Пациенты / ⚙️ Настройки) to their slash-command entry points.

This router must be included FIRST in main.py so that a tapped menu button
is always caught here, regardless of any leftover FSM state. Each handler
clears state, then delegates to the existing command handler.
"""

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.keyboards.reply import (
    MENU_HISTORY,
    MENU_LOG,
    MENU_PATIENTS,
    MENU_REPORT,
    MENU_SETTINGS,
)
from bot.services.analytics import log_event

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == MENU_LOG)
async def menu_log(message: Message, state: FSMContext):
    await state.clear()
    await log_event(message.from_user.id, "menu_tap", detail="Дневник")
    from bot.handlers.log import handle_log_start
    await handle_log_start(message.from_user.id, message, state)


@router.message(F.text == MENU_HISTORY)
async def menu_history(message: Message, state: FSMContext):
    await state.clear()
    await log_event(message.from_user.id, "menu_tap", detail="История")
    from bot.handlers.history import cmd_history
    await cmd_history(message, state)


@router.message(F.text == MENU_REPORT)
async def menu_report(message: Message, state: FSMContext):
    await state.clear()
    await log_event(message.from_user.id, "menu_tap", detail="Отчёт")
    from bot.handlers.report import cmd_report
    await cmd_report(message, state)


@router.message(F.text == MENU_PATIENTS)
async def menu_patients(message: Message, state: FSMContext):
    await state.clear()
    await log_event(message.from_user.id, "menu_tap", detail="Пациенты")
    from bot.handlers.patients import cmd_patients
    await cmd_patients(message, state)


@router.message(F.text == MENU_SETTINGS)
async def menu_settings(message: Message, state: FSMContext):
    await state.clear()
    await log_event(message.from_user.id, "menu_tap", detail="Настройки")
    from bot.handlers.common import cmd_settings
    await cmd_settings(message, state)
