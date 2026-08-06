"""/history — redirects to /report (PDF report)."""

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.handlers.report import cmd_report

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("history"))
async def cmd_history(message: Message, state: FSMContext):
    """Redirect /history to /report — all history is now in the PDF."""
    await message.answer(
        "📋 → 📊 История теперь доступна в формате PDF-отчёта."
    )
    await cmd_report(message, state)
