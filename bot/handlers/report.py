"""/report — PDF report for the active patient."""

import logging
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import select

from bot.db.database import get_session
from bot.keyboards.inline import report_period_keyboard
from bot.keyboards.reply import main_menu_keyboard
from bot.models.episode import EpisodeLog
from bot.models.patient import Patient
from bot.models.scale_score import ScaleScore
from bot.models.symptom import SymptomEntry
from bot.models.user import User
from bot.services.episodes import (
    tonsillectomy_criteria_met,
    aom_tube_criteria_met,
    crs_surgery_criteria_met,
)
from bot.utils.demographics import derive_age_group

logger = logging.getLogger(__name__)
router = Router()


class ReportState(StatesGroup):
    choosing_period = State()


@router.message(Command("report"))
async def cmd_report(message: Message, state: FSMContext):
    user_id = message.from_user.id

    async with get_session() as session:
        user = await session.get(User, user_id)
        if not user or not user.full_name:
            await message.answer("❌ Сначала выполните /start")
            return
        if not user.active_patient_id:
            await message.answer(
                "Активный пациент не выбран. "
                "Выберите через кнопку «👥 Пациенты».",
                reply_markup=main_menu_keyboard(),
            )
            return

    await message.answer(
        "📄 Выберите период для отчёта:",
        reply_markup=report_period_keyboard(),
    )
    await state.set_state(ReportState.choosing_period)


@router.callback_query(
    ReportState.choosing_period, F.data.startswith("report:")
)
async def handle_period_selection(callback: CallbackQuery, state: FSMContext):
    period_days = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    async with get_session() as session:
        user = await session.get(User, user_id)
        patient: Patient | None = (
            await session.get(Patient, user.active_patient_id)
            if user and user.active_patient_id
            else None
        )
        if not patient:
            await callback.message.answer(
                "Активный пациент не выбран. "
                "Выберите через кнопку «👥 Пациенты».",
                reply_markup=main_menu_keyboard(),
            )
            await state.clear()
            await callback.answer()
            return

        cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)

        # Symptom entries
        stmt = (
            select(SymptomEntry)
            .where(SymptomEntry.patient_id == patient.id)
            .where(SymptomEntry.recorded_at >= cutoff)
            .order_by(SymptomEntry.recorded_at.desc())
        )
        result = await session.execute(stmt)
        entries = result.scalars().all()

        # Scale scores (Centor, FeverPAIN, etc.)
        scale_stmt = (
            select(ScaleScore)
            .where(ScaleScore.patient_id == patient.id)
            .where(ScaleScore.created_at >= cutoff)
            .order_by(ScaleScore.created_at.desc())
        )
        scale_result = await session.execute(scale_stmt)
        scale_scores = scale_result.scalars().all()

        # Episodes (all time — needed for cumulative criteria)
        episode_stmt = (
            select(EpisodeLog)
            .where(EpisodeLog.patient_id == patient.id)
            .order_by(EpisodeLog.started_at.desc())
        )
        episode_result = await session.execute(episode_stmt)
        episodes = episode_result.scalars().all()

        # Clinical criteria checks
        recommendations: list[str] = []
        nosology = patient.nosology or ""

        if nosology == "tonsillopharyngitis":
            met, reason = await tonsillectomy_criteria_met(
                session, user_id=user_id, patient_id=patient.id,
            )
            if met:
                recommendations.append(
                    f"Тонзиллэктомия: критерии выполнены ({reason}). "
                    "Рекомендовано обсудить с пациентом."
                )

        if nosology == "aom":
            met, reason = await aom_tube_criteria_met(
                session, user_id=user_id, patient_id=patient.id,
            )
            if met:
                recommendations.append(
                    f"Рецидивирующий ОСО: {reason}. "
                    "Рассмотрите установку вентиляционных трубок / аденотомию."
                )

        if nosology == "crs":
            met, reason = await crs_surgery_criteria_met(
                session, user_id=user_id, patient_id=patient.id,
            )
            if met:
                recommendations.append(
                    f"Частые обострения ХРС: {reason}. "
                    "Рассмотрите FESS или биологическую терапию."
                )

    if not entries:
        await callback.message.answer(
            f"📋 Нет данных за последние {period_days} дней "
            f"({patient.display_name}).",
            reply_markup=main_menu_keyboard(),
        )
        await state.clear()
        await callback.answer()
        return

    try:
        from bot.services.pdf_report import generate_pdf_report

        # `pdf_report.generate_pdf_report` expects:
        #   user_data: dict {first_name, nosology, age_group}
        #   entries:   list[dict] with keys recorded_at / composite_score /
        #              triage_level / triage_message / red_flags / symptoms /
        #              nosology
        #   returns:   PDF bytes (NOT a file path)
        # so we convert ORM → dicts here and send the bytes via
        # BufferedInputFile.
        entries_dicts = [
            {
                "recorded_at": e.recorded_at,
                "composite_score": e.composite_score or 0,
                "triage_level": e.triage_level or "green",
                "triage_message": e.triage_message or "",
                "symptoms": e.symptoms or {},
                "red_flags": e.red_flags or [],
                "nosology": e.nosology,
                "user_notes": e.user_notes or "",
            }
            for e in entries
        ]

        scale_dicts = [
            {
                "scale": s.scale,
                "score": s.score,
                "action": s.action,
                "details": s.details or {},
                "created_at": s.created_at,
            }
            for s in scale_scores
        ]

        episode_dicts = [
            {
                "episode_type": ep.episode_type,
                "started_at": ep.started_at,
                "scale_score": ep.scale_score,
                "notes": ep.notes or "",
            }
            for ep in episodes
        ]

        user_data = {
            "first_name": patient.display_name or "Пациент",
            "nosology": patient.nosology or "",
            "age_group": derive_age_group(
                patient.date_of_birth, patient.legacy_age_group
            ),
        }

        pdf_bytes = await generate_pdf_report(
            user_data=user_data,
            entries=entries_dicts,
            period_days=period_days,
            scale_scores=scale_dicts,
            episodes=episode_dicts,
            recommendations=recommendations,
        )

        doc = BufferedInputFile(
            pdf_bytes,
            filename=f"lordok_report_{period_days}d.pdf",
        )
        await callback.message.answer_document(
            doc,
            caption=f"📊 Отчёт за {period_days} дней — {patient.display_name}",
        )
        # Separate trailing message so the main menu is visible.
        await callback.message.answer(
            "Готово. Выберите следующее действие в меню.",
            reply_markup=main_menu_keyboard(),
        )

        # Analytics
        try:
            from bot.services.analytics import log_event
            await log_event(
                user_id=user_id,
                event_type="report_generated",
                payload={
                    "period_days": period_days,
                    "entries_count": len(entries),
                    "nosology": patient.nosology,
                },
            )
        except Exception:
            pass

    except (ImportError, NotImplementedError) as e:
        logger.warning(f"PDF report generation not available: {e}")
        await callback.message.answer(
            "📝 PDF-генерация будет доступна в ближайшем обновлении.",
            reply_markup=main_menu_keyboard(),
        )
    except Exception as e:
        logger.error(f"Report generation error: {e}", exc_info=True)
        await callback.message.answer(
            "❌ Ошибка при создании отчёта. Попробуйте позже.",
            reply_markup=main_menu_keyboard(),
        )

    await state.clear()
    await callback.answer()
