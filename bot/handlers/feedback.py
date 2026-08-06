"""Feedback collection handler + Premium stub.

Flow:
    'Обратная связь' menu tap
      → rating 1-5 (inline keyboard)
      → free-text comment (or 'Пропустить')
      → persist Feedback row + BotEvent
      → thank-you message

    'Премиум' menu tap
      → stub message + BotEvent (premium_click)
"""

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.config import get_settings
from bot.db.database import get_session
from bot.keyboards.reply import MENU_FEEDBACK, MENU_PREMIUM, main_menu_keyboard
from bot.models.feedback import Feedback
from bot.services.analytics import log_event

logger = logging.getLogger(__name__)
router = Router()


# ──────────────────────────────────────────────────────────────────────
# Premium stub
# ──────────────────────────────────────────────────────────────────────


@router.message(F.text == MENU_PREMIUM)
async def menu_premium(message: Message, state: FSMContext):
    await state.clear()
    await log_event(
        user_id=message.from_user.id,
        event_type="premium_click",
    )
    await message.answer(
        "⭐ Спасибо за интерес!\n\n"
        "Раздел «Премиум» сейчас в разработке. "
        "Мы обязательно сообщим, когда он будет готов.\n\n"
        "Если у вас есть пожелания — нажмите «💬 Обратная связь».",
        reply_markup=main_menu_keyboard(),
    )


# ──────────────────────────────────────────────────────────────────────
# Feedback collection
# ──────────────────────────────────────────────────────────────────────


class FeedbackState(StatesGroup):
    waiting_rating = State()
    waiting_comment = State()


def _rating_keyboard() -> InlineKeyboardMarkup:
    """1-5 star rating keyboard."""
    buttons = [
        [
            InlineKeyboardButton(text="1", callback_data="fb_rating:1"),
            InlineKeyboardButton(text="2", callback_data="fb_rating:2"),
            InlineKeyboardButton(text="3", callback_data="fb_rating:3"),
            InlineKeyboardButton(text="4", callback_data="fb_rating:4"),
            InlineKeyboardButton(text="5", callback_data="fb_rating:5"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _skip_comment_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="fb_skip_comment")]
        ]
    )


@router.message(F.text == MENU_FEEDBACK)
async def menu_feedback(message: Message, state: FSMContext):
    await state.clear()
    await log_event(
        user_id=message.from_user.id,
        event_type="feedback_start",
    )
    await message.answer(
        "Оцените приложение от 1 до 5:",
        reply_markup=_rating_keyboard(),
    )
    await state.set_state(FeedbackState.waiting_rating)


@router.callback_query(
    FeedbackState.waiting_rating, F.data.startswith("fb_rating:")
)
async def handle_rating(callback: CallbackQuery, state: FSMContext):
    rating = int(callback.data.split(":")[1])
    await state.update_data(fb_rating=rating)

    await log_event(
        user_id=callback.from_user.id,
        event_type="feedback_rating",
        payload={"rating": rating},
    )

    await callback.message.answer(
        "Спасибо! Напишите, что понравилось, что нужно доработать, "
        "чего не хватило — или нажмите «Пропустить».",
        reply_markup=_skip_comment_keyboard(),
    )
    await state.set_state(FeedbackState.waiting_comment)
    await callback.answer()


@router.callback_query(
    FeedbackState.waiting_comment, F.data == "fb_skip_comment"
)
async def handle_skip_comment(callback: CallbackQuery, state: FSMContext):
    await _save_feedback(callback.from_user.id, state, comment=None)
    await callback.message.answer(
        "Спасибо за оценку! Ваше мнение помогает нам стать лучше.",
        reply_markup=main_menu_keyboard(),
    )
    await state.clear()
    await callback.answer()


@router.message(FeedbackState.waiting_comment)
async def handle_comment_text(message: Message, state: FSMContext):
    comment = (message.text or "").strip() or None
    await _save_feedback(message.from_user.id, state, comment=comment)
    await message.answer(
        "Спасибо за отзыв! Мы обязательно его учтём.",
        reply_markup=main_menu_keyboard(),
    )
    await state.clear()


async def _notify_admins(user_id: int, rating: int, comment: str | None) -> None:
    """Forward feedback to admin Telegram accounts (fire-and-forget)."""
    try:
        from bot.main import get_bot
        bot = get_bot()
        admin_ids = get_settings().admin_ids
        if not admin_ids:
            return

        stars = "⭐" * rating + "☆" * (5 - rating)
        text = f"📩 Новый отзыв\n\n{stars} ({rating}/5)\nUser ID: {user_id}"
        if comment:
            text += f"\n\n💬 {comment}"

        for admin_id in admin_ids:
            try:
                await bot.send_message(admin_id, text)
            except Exception:
                logger.warning("Could not send feedback to admin %s", admin_id)
    except Exception:
        logger.warning("Failed to notify admins about feedback", exc_info=True)


async def _save_feedback(
    user_id: int, state: FSMContext, comment: str | None
) -> None:
    data = await state.get_data()
    rating = data.get("fb_rating", 3)

    async with get_session() as session:
        session.add(Feedback(
            user_id=user_id,
            rating=rating,
            comment=comment,
        ))

    await log_event(
        user_id=user_id,
        event_type="feedback_text",
        payload={"rating": rating, "has_comment": comment is not None},
        detail=comment,
    )

    await _notify_admins(user_id, rating, comment)
