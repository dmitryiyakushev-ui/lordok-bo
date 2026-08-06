"""Symptom logging handler.

Flow:
    /log (or 'start_log' callback)
      → ensure user has onboarded
      → determine patient:
            if active_patient_id is set and valid → use it
            elif exactly one active patient exists → auto-select it
            else → show patient_select_keyboard
      → load SYMPTOM_PARAMS + RED_FLAGS from bot.triage.params (single
        source of truth — NOT importlib)
      → for non_ent: show disclaimer first
      → ask symptoms → ask red flags (with short-circuit on YES) →
        run triage → persist SymptomEntry

Design notes:
- Red-flag short-circuit: if the user answers YES to ANY red flag, we
  stop asking the remaining red-flag questions and immediately run
  triage; because the red-flag key is lifted into `symptoms`, the
  universal checker in `engine.run_triage` catches it and returns RED.
  This matches Dmitrii's requirement that the bot fires the emergency
  message automatically without an extra prompt.
- value_maps (see params.py) are applied to keyboard-bucket values
  before handing off to the engine so the rule modules see the units
  they expect (e.g. COM effusion_duration in days, not buckets).
- age_group is injected under tp_age / aom_age because those rule
  modules reference those keys for age-stratified decisions.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from aiogram import F, Router
from aiogram.exceptions import TelegramNetworkError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from bot.db.database import get_session
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.keyboards.inline import (
    analgesic_response_keyboard,
    antipyretic_response_keyboard,
    binary_keyboard,
    discharge_keyboard,
    duration_keyboard,
    episode_frequency_keyboard,
    fever_duration_keyboard,
    last_doctor_visit_keyboard,
    ome_duration_keyboard,
    patient_select_keyboard,
    severity_keyboard,
    temp_keyboard,
    treatment_status_keyboard,
    vas_keyboard,
    yes_no_keyboard,
)
from bot.keyboards.reply import main_menu_keyboard
from bot.models.patient import Patient
from bot.models.symptom import SymptomEntry
from bot.models.scale_score import ScaleScore
from bot.models.user import User
from bot.services.notes_scan import scan_notes
from bot.services.episodes import (
    register_episode,
    tonsillectomy_criteria_met,
    aom_tube_criteria_met,
    crs_surgery_criteria_met,
)
from bot.triage.engine import run_triage
from bot.triage.params import (
    RED_FLAG_VALUE_OVERRIDES,
    apply_value_maps,
    compute_composite_score,
    get_params,
    get_red_flags,
)
from bot.triage.red_flags import get_red_flag_message
from bot.utils.demographics import derive_age_group

logger = logging.getLogger(__name__)
router = Router()


class LogState(StatesGroup):
    selecting_patient = State()
    collecting_treatment_visit = State()
    collecting_treatment_status = State()
    collecting_symptoms = State()
    collecting_red_flags = State()
    collecting_notes = State()
    processing = State()


SCALE_TO_KEYBOARD = {
    "severity_0_3": severity_keyboard,
    "discharge": discharge_keyboard,
    "binary": binary_keyboard,
    "temp": temp_keyboard,
    "vas_0_10": vas_keyboard,
    "duration": duration_keyboard,
    "episode_frequency": episode_frequency_keyboard,
    "ome_duration": ome_duration_keyboard,
    "antipyretic_response": antipyretic_response_keyboard,
    "analgesic_response": analgesic_response_keyboard,
    "fever_duration": fever_duration_keyboard,
}

TRIAGE_LEVEL_EMOJI = {
    "green": "🟢",
    "yellow": "🟡",
    "orange": "🟠",
    "red": "🔴",
}

# Age groups representing children under 6 years old.
# Used to show the "Сложно оценить из-за возраста ребёнка" button.
_UNDER_6_AGE_GROUPS = {"<6mo", "6-23mo", "2-5y"}


# Nosology-specific disclaimer shown before the first question.
# Patients on the non_ent pathway explicitly declared the problem is
# outside ENT scope — they still get a diary, but we must be clear that
# we do NOT screen for ENT red flags here.
# Nosologies with established diagnoses — treatment context questions apply.
_DIAGNOSED_NOSOLOGIES = frozenset({
    "ars", "crs", "tonsillopharyngitis", "aom", "com", "adenoid_hypertrophy",
})

NON_ENT_DISCLAIMER = (
    "ℹ️ Вы выбрали путь «Это не ЛОР-проблема».\n\n"
    "ЛОРдок будет вести дневник симптомов, но НЕ анализирует "
    "специфические «красные флаги» для не-ЛОР заболеваний. "
    "При ухудшении состояния — обратитесь к терапевту, педиатру "
    "или профильному врачу.\n\n"
    "Если у вас появятся угрожающие жизни признаки "
    "(затруднение дыхания, спутанность сознания, резкое ухудшение), "
    "бот всё равно выдаст предупреждение и порекомендует экстренное "
    "обращение."
)


# ──────────────────────────────────────────────────────────────────────
# Network-safe message sending
# ──────────────────────────────────────────────────────────────────────


async def _safe_reply(
    message: Message,
    state: FSMContext,
    text: str,
    *,
    reply_markup=None,
    callback: CallbackQuery | None = None,
) -> bool:
    """Send a message; on network error clear FSM state and return False.

    This prevents the user from getting stuck in a half-transitioned FSM
    state when the VPS ↔ Telegram API connection drops.
    """
    try:
        await message.answer(text, reply_markup=reply_markup)
        if callback is not None:
            await callback.answer()
        return True
    except TelegramNetworkError:
        logger.error(
            "TelegramNetworkError while sending message to user %s. "
            "Clearing FSM state to prevent stuck session.",
            message.chat.id,
            exc_info=True,
        )
        await state.clear()
        return False


# ──────────────────────────────────────────────────────────────────────
# Entry points
# ──────────────────────────────────────────────────────────────────────


@router.message(Command("log"))
async def cmd_log(message: Message, state: FSMContext):
    await state.clear()  # reset any stuck state
    await handle_log_start(message.from_user.id, message, state)


@router.callback_query(F.data == "start_log")
async def callback_log(callback: CallbackQuery, state: FSMContext):
    await state.clear()  # reset any stuck state
    await handle_log_start(callback.from_user.id, callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "log_later")
async def callback_log_later(callback: CallbackQuery, state: FSMContext):
    """User chose to postpone the diary. Leave them on the main menu."""
    await callback.message.answer(
        "Хорошо, вернёмся к этому позже. Главное меню ниже.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


async def handle_log_start(user_id: int, message: Message, state: FSMContext):
    async with get_session() as session:
        user = await session.get(User, user_id)
        if not user:
            await message.answer(
                "❌ Пожалуйста, сначала выполните /start",
                reply_markup=main_menu_keyboard(),
            )
            return

        if not user.full_name or not user.phone:
            await message.answer(
                "Сначала, пожалуйста, завершите знакомство: /start"
            )
            return

        active_patient: Optional[Patient] = None
        if user.active_patient_id:
            active_patient = await session.get(Patient, user.active_patient_id)
            if active_patient and not active_patient.is_active:
                active_patient = None

        if active_patient is not None:
            await _begin_collection(message, state, active_patient)
            return

        stmt = (
            select(Patient)
            .where(Patient.user_id == user_id)
            .where(Patient.is_active.is_(True))
            .order_by(Patient.created_at)
        )
        result = await session.execute(stmt)
        patients = result.scalars().all()

    if not patients:
        await message.answer(
            "У вас пока нет активных пациентов. "
            "Добавьте профиль через кнопку «👥 Пациенты».",
            reply_markup=main_menu_keyboard(),
        )
        return

    if len(patients) == 1:
        only = patients[0]
        async with get_session() as session:
            user = await session.get(User, user_id)
            user.active_patient_id = only.id
            user.updated_at = datetime.now(timezone.utc)
            await session.commit()
        await _begin_collection(message, state, only)
        return

    await message.answer(
        "У вас несколько пациентов. По кому будем заполнять дневник?",
        reply_markup=patient_select_keyboard(patients, action="select"),
    )
    await state.set_state(LogState.selecting_patient)


@router.callback_query(
    LogState.selecting_patient, F.data.startswith("patient:select:")
)
async def handle_patient_select(callback: CallbackQuery, state: FSMContext):
    patient_id = int(callback.data.split(":")[2])
    user_id = callback.from_user.id

    async with get_session() as session:
        patient = await session.get(Patient, patient_id)
        if not patient or patient.user_id != user_id or not patient.is_active:
            await callback.answer("Пациент недоступен.", show_alert=True)
            return

        user = await session.get(User, user_id)
        user.active_patient_id = patient.id
        user.updated_at = datetime.now(timezone.utc)
        await session.commit()

    await _begin_collection(callback.message, state, patient)
    await callback.answer()


# ──────────────────────────────────────────────────────────────────────
# Treatment context collection (diagnosed patients only)
# ──────────────────────────────────────────────────────────────────────


@router.callback_query(
    LogState.collecting_treatment_visit, F.data.startswith("tx_visit:")
)
async def handle_treatment_visit(callback: CallbackQuery, state: FSMContext):
    """Handle 'when did you last see a doctor?' answer."""
    visit_value = int(callback.data.split(":")[1])
    await state.update_data(tx_last_doctor_visit=visit_value)

    await state.set_state(LogState.collecting_treatment_status)
    await _safe_reply(
        callback.message,
        state,
        "💊 Получаете ли вы сейчас лечение по этому поводу?",
        reply_markup=treatment_status_keyboard(),
        callback=callback,
    )


@router.callback_query(
    LogState.collecting_treatment_status, F.data.startswith("tx_status:")
)
async def handle_treatment_status(callback: CallbackQuery, state: FSMContext):
    """Handle 'are you receiving treatment?' answer, then proceed to symptoms."""
    status_value = callback.data.split(":")[1]  # prescribed / self / none
    await state.update_data(tx_treatment_status=status_value)

    data = await state.get_data()
    symptom_params = data.get("symptom_params", [])
    is_first_visit = data.get("is_first_visit", True)

    # Find the first visible param (may skip first_visit_only on follow-ups).
    first_idx = _next_visible_index(
        symptom_params, 0, {}, is_first_visit=is_first_visit,
    )
    if first_idx is None:
        first_idx = 0
    await state.update_data(current_symptom_index=first_idx)

    await state.set_state(LogState.collecting_symptoms)
    try:
        await _ask_symptom(
            callback.message,
            symptom_params[first_idx],
            age_group=data.get("age_group"),
            patient_relation=data.get("patient_relation"),
        )
        await callback.answer()
    except TelegramNetworkError:
        logger.error(
            "TelegramNetworkError in handle_treatment_status for user %s. "
            "Clearing FSM state.",
            callback.from_user.id,
            exc_info=True,
        )
        await state.clear()


# ──────────────────────────────────────────────────────────────────────
# Symptom collection
# ──────────────────────────────────────────────────────────────────────


async def _begin_collection(message: Message, state: FSMContext, patient: Patient):
    nosology = patient.nosology
    if not nosology:
        await message.answer(
            "У этого пациента не указан диагноз/жалоба. "
            "Откройте «👥 Пациенты» → «Изменить жалобу/диагноз».",
            reply_markup=main_menu_keyboard(),
        )
        return

    age_group = derive_age_group(patient.date_of_birth, patient.legacy_age_group)

    symptom_params = get_params(nosology)
    red_flags = get_red_flags(nosology)

    if not symptom_params:
        await message.answer(
            f"❌ Для этого профиля ({nosology}) не найдены параметры. "
            "Пожалуйста, напишите в поддержку — support@lordok.ru.",
            reply_markup=main_menu_keyboard(),
        )
        return

    # Check if this patient already has diary entries (follow-up vs first visit).
    # A case marked as closed (case_closed_at is set) means the next fill
    # is a new case — treat as first visit and clear the flag.
    is_first_visit = True
    async with get_session() as session:
        from sqlalchemy import select, func
        from bot.models.symptom import SymptomEntry

        fresh_patient = await session.get(Patient, patient.id)
        if fresh_patient and fresh_patient.case_closed_at is not None:
            # Case was explicitly closed — this is a new case.
            is_first_visit = True
            fresh_patient.case_closed_at = None
            await session.commit()
        else:
            count_stmt = (
                select(func.count())
                .select_from(SymptomEntry)
                .where(SymptomEntry.patient_id == patient.id)
            )
            result = await session.execute(count_stmt)
            existing_count = result.scalar() or 0
            is_first_visit = existing_count == 0

    await state.update_data(
        user_id=patient.user_id,
        patient_id=patient.id,
        patient_display_name=patient.display_name,
        patient_relation=patient.relation,
        nosology=nosology,
        age_group=age_group,
        symptom_params=symptom_params,
        red_flags=red_flags,
        symptom_values={},
        red_flag_values={},
        current_symptom_index=0,
        is_first_visit=is_first_visit,
    )

    # Non-ENT explicitly needs the disclaimer before the first question.
    try:
        if nosology == "non_ent":
            await message.answer(NON_ENT_DISCLAIMER)

        await message.answer(f"📋 Заполняем дневник для: {patient.display_name}.")

        # For diagnosed patients: ask treatment context before symptoms.
        if nosology in _DIAGNOSED_NOSOLOGIES:
            await state.set_state(LogState.collecting_treatment_visit)
            await message.answer(
                "🩺 Когда вы последний раз были у врача по этому поводу?",
                reply_markup=last_doctor_visit_keyboard(),
            )
            return

        # Undiagnosed / non_ent — skip treatment context, go to symptoms.
        # Find the first visible param (may skip first_visit_only on follow-ups).
        first_idx = _next_visible_index(
            symptom_params, 0, {}, is_first_visit=is_first_visit,
        )
        if first_idx is None:
            # Shouldn't happen — means all params are first_visit_only.
            first_idx = 0
        await state.update_data(current_symptom_index=first_idx)
        await state.set_state(LogState.collecting_symptoms)
        await _ask_symptom(
            message,
            symptom_params[first_idx],
            age_group=age_group,
            patient_relation=patient.relation,
        )
    except TelegramNetworkError:
        logger.error(
            "TelegramNetworkError in _begin_collection for user %s. "
            "Clearing FSM state.",
            patient.user_id,
            exc_info=True,
        )
        await state.clear()


async def _ask_symptom(
    message: Message,
    param: Dict[str, Any],
    *,
    age_group: str | None = None,
    patient_relation: str | None = None,
):
    param_id = param.get("id")
    label = param.get("label_ru", "Симптом")
    scale_type = param.get("scale_type", "binary")
    is_pain = param.get("is_pain", False)

    keyboard_func = SCALE_TO_KEYBOARD.get(scale_type, binary_keyboard)

    if scale_type == "severity_0_3":
        # Contextual buttons: "Не болит" for pain params,
        # "Сложно оценить" for children < 6 years.
        show_cant_assess = (
            patient_relation == "child"
            and age_group in _UNDER_6_AGE_GROUPS
        )
        keyboard = keyboard_func(
            param_id,
            is_pain=is_pain,
            show_cant_assess=show_cant_assess,
        )
    else:
        keyboard = keyboard_func(param_id)

    await message.answer(f"❓ {label}", reply_markup=keyboard)


def _should_show_param(
    param: dict, symptom_values: dict, *, is_first_visit: bool = True,
) -> bool:
    """Check if a conditional param should be displayed.

    ``show_if`` format: ``{"param": "<param_id>", "gte": <int>}``
    — the param is shown only when the referenced param's collected value
    is ≥ the threshold.  If there is no ``show_if`` key the param is
    always shown.

    ``first_visit_only`` — if True, the param is only shown when this is the
    patient's first diary entry (no prior SymptomEntry records).
    """
    # Skip onset/duration questions on follow-up visits.
    if param.get("first_visit_only") and not is_first_visit:
        return False

    condition = param.get("show_if")
    if not condition:
        return True
    ref_param = condition.get("param", "")
    threshold = condition.get("gte", 0)
    return symptom_values.get(ref_param, 0) >= threshold


def _next_visible_index(
    symptom_params: list[dict],
    start_index: int,
    symptom_values: dict,
    *,
    is_first_visit: bool = True,
) -> int | None:
    """Return the index of the next param that should be shown, or None."""
    idx = start_index
    while idx < len(symptom_params):
        if _should_show_param(
            symptom_params[idx], symptom_values, is_first_visit=is_first_visit,
        ):
            return idx
        idx += 1
    return None


@router.callback_query(
    LogState.collecting_symptoms, F.data.startswith("symptom:")
)
async def handle_symptom_response(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    parts = callback.data.split(":")
    param_id = parts[1]
    value = int(parts[2])

    symptom_values = data.get("symptom_values", {})
    symptom_values[param_id] = value
    await state.update_data(symptom_values=symptom_values)

    current_index = data.get("current_symptom_index", 0)
    symptom_params = data.get("symptom_params", [])

    # Find the next visible param (skipping those whose show_if is unmet
    # or that are first_visit_only on a follow-up visit).
    is_first_visit = data.get("is_first_visit", True)
    next_idx = _next_visible_index(
        symptom_params, current_index + 1, symptom_values,
        is_first_visit=is_first_visit,
    )

    try:
        if next_idx is not None:
            await state.update_data(current_symptom_index=next_idx)
            next_param = symptom_params[next_idx]
            await _ask_symptom(
                callback.message,
                next_param,
                age_group=data.get("age_group"),
                patient_relation=data.get("patient_relation"),
            )
        else:
            await state.set_state(LogState.collecting_red_flags)
            await state.update_data(current_red_flag_index=0)
            red_flags = data.get("red_flags", [])
            if red_flags:
                await _ask_red_flag(callback.message, red_flags[0])
            else:
                await _ask_user_notes(callback.message, state)

        await callback.answer()
    except TelegramNetworkError:
        logger.error(
            "TelegramNetworkError in handle_symptom_response for user %s. "
            "Clearing FSM state.",
            callback.from_user.id,
            exc_info=True,
        )
        await state.clear()


async def _ask_red_flag(message: Message, flag: Dict[str, Any]):
    flag_id = flag.get("id")
    label = (
        flag.get("question_ru")
        or flag.get("label_ru")
        or "Опасный признак"
    )
    await message.answer(f"⚠️ {label}", reply_markup=yes_no_keyboard(flag_id))


@router.callback_query(
    LogState.collecting_red_flags, F.data.startswith("redflag:")
)
async def handle_red_flag_response(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    parts = callback.data.split(":")
    flag_id = parts[1]
    value = int(parts[2])

    red_flag_values = data.get("red_flag_values", {})
    red_flag_values[flag_id] = value
    await state.update_data(red_flag_values=red_flag_values)

    try:
        # ── Short-circuit: any YES on a red flag → skip remaining red-flag
        # questions but ALWAYS offer the free-text notes step before triage.
        # The engine's universal red-flag check will see the flag in the
        # combined symptoms dict and return RED.
        if value == 1:
            await callback.answer()
            await _ask_user_notes(callback.message, state)
            return

        current_index = data.get("current_red_flag_index", 0)
        red_flags = data.get("red_flags", [])
        current_index += 1

        if current_index < len(red_flags):
            await state.update_data(current_red_flag_index=current_index)
            await _ask_red_flag(callback.message, red_flags[current_index])
        else:
            await _ask_user_notes(callback.message, state)

        await callback.answer()
    except TelegramNetworkError:
        logger.error(
            "TelegramNetworkError in handle_red_flag_response for user %s. "
            "Clearing FSM state.",
            callback.from_user.id,
            exc_info=True,
        )
        await state.clear()


# ──────────────────────────────────────────────────────────────────────
# Free-text notes step ("Хотите что-то дополнить?")
# ──────────────────────────────────────────────────────────────────────

def _skip_notes_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard with a single 'Пропустить' button."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="notes:skip")]
        ]
    )


async def _ask_user_notes(message: Message, state: FSMContext) -> None:
    """Transition to the free-text notes state."""
    await state.set_state(LogState.collecting_notes)
    await message.answer(
        "✏️ Хотите что-то дополнить? "
        "Напишите текстом или нажмите «Пропустить».",
        reply_markup=_skip_notes_keyboard(),
    )


@router.callback_query(LogState.collecting_notes, F.data == "notes:skip")
async def handle_notes_skip(callback: CallbackQuery, state: FSMContext):
    """User chose to skip the free-text step."""
    await callback.answer()
    await _process_triage(callback.message, state)


@router.message(LogState.collecting_notes)
async def handle_notes_text(message: Message, state: FSMContext):
    """User typed free-text notes."""
    text = (message.text or "").strip()
    if not text:
        # Empty message — treat as skip
        await _process_triage(message, state)
        return

    await state.update_data(user_notes=text)

    # Keyword analysis — may escalate triage level later in _process_triage
    escalation, matched = scan_notes(text)
    if escalation:
        await state.update_data(
            notes_escalation=escalation,
            notes_matched_keywords=matched,
        )
        logger.info(
            "User notes keyword escalation: level=%s matched=%s",
            escalation, matched,
        )

    await _process_triage(message, state)


# ──────────────────────────────────────────────────────────────────────
# Triage processing
# ──────────────────────────────────────────────────────────────────────


async def _process_triage(message: Message, state: FSMContext):
    data = await state.get_data()

    symptom_values: Dict[str, Any] = dict(data.get("symptom_values", {}) or {})
    red_flag_values: Dict[str, Any] = dict(data.get("red_flag_values", {}) or {})
    nosology: str = data.get("nosology", "")
    age_group: str = data.get("age_group") or "15-44y"

    # Apply value_maps (e.g. COM effusion_duration bucket → days).
    symptom_values = apply_value_maps(nosology, symptom_values)

    # Merge red-flag answers into symptoms:
    # - YES answers become a value of 1 by default, or a nosology-specific
    #   override from RED_FLAG_VALUE_OVERRIDES (e.g. com_vertigo → 2 so
    #   the rule's ≥2 threshold fires).
    # - NO answers stay as 0 so the universal checker doesn't misfire.
    combined_symptoms: Dict[str, Any] = dict(symptom_values)
    for flag_id, raw_value in red_flag_values.items():
        if raw_value == 1:
            combined_symptoms[flag_id] = RED_FLAG_VALUE_OVERRIDES.get(flag_id, 1)
        else:
            # Only set explicit zeros when we haven't set them from symptoms.
            combined_symptoms.setdefault(flag_id, 0)

    # Inject age_group for rules that need it (tonsillopharyngitis,
    # acute_otitis_media, adenoid_hypertrophy). Harmless for others.
    if nosology == "tonsillopharyngitis":
        combined_symptoms["tp_age"] = age_group
    elif nosology == "aom":
        combined_symptoms["aom_age"] = age_group
    elif nosology == "adenoid_hypertrophy":
        combined_symptoms["ah_age"] = age_group

    # Балл тяжести: только выраженность симптомов, без сроков и
    # красных флагов, чтобы записи оставались сравнимыми между собой.
    composite = compute_composite_score(symptom_values)

    # Load prior entries for this patient (ascending for trend analysis).
    async with get_session() as session:
        hist_stmt = (
            select(SymptomEntry)
            .where(SymptomEntry.patient_id == data["patient_id"])
            .order_by(SymptomEntry.recorded_at.asc())
        )
        history_result = await session.execute(hist_stmt)
        history: list[SymptomEntry] = list(history_result.scalars().all())

    # Treatment context (diagnosed patients only)
    tx_last_visit: int | None = data.get("tx_last_doctor_visit")
    tx_status: str | None = data.get("tx_treatment_status")

    recorded_at = datetime.now(timezone.utc)
    transient_entry = SymptomEntry(
        user_id=data["user_id"],
        patient_id=data["patient_id"],
        nosology=nosology,
        symptoms=combined_symptoms,
        composite_score=composite,
        last_doctor_visit=tx_last_visit,
        treatment_status=tx_status,
        recorded_at=recorded_at,
    )

    try:
        result = run_triage(
            transient_entry,
            history,
            tx_last_visit=tx_last_visit,
            tx_status=tx_status,
        )
    except Exception as e:
        logger.error(f"Triage error: {e}", exc_info=True)
        await message.answer(
            "❌ Ошибка при обработке результатов. Попробуйте позже.",
            reply_markup=main_menu_keyboard(),
        )
        await state.clear()
        return

    level = result.get("triage_level", "green")
    triage_text = result.get("triage_message", "") or ""
    red_flags_triggered = list(result.get("red_flags", []) or [])

    # ── Keyword escalation from free-text notes ──
    user_notes: str | None = data.get("user_notes")
    notes_escalation: str | None = data.get("notes_escalation")
    notes_matched: list[str] = data.get("notes_matched_keywords", [])

    LEVEL_RANK = {"green": 0, "yellow": 1, "orange": 2, "red": 3}

    if notes_escalation and LEVEL_RANK.get(notes_escalation, 0) > LEVEL_RANK.get(level, 0):
        level = notes_escalation
        kw_joined = ", ".join(notes_matched)
        if notes_escalation == "red":
            triage_text = (
                "В вашем комментарии есть признаки, "
                "требующие экстренного обращения к врачу. "
                "Если состояние ухудшается — вызовите скорую помощь."
            )
        else:
            triage_text = (
                "В вашем комментарии упомянуты симптомы, "
                "на которые стоит обратить внимание. "
                "Рекомендуем обратиться к врачу."
            )
        logger.info(
            "Triage escalated by user_notes keywords: %s → %s (matched: %s)",
            result.get("triage_level"), level, kw_joined,
        )

    # Persist the entry with the triage outcome.
    async with get_session() as session:
        entry = SymptomEntry(
            user_id=data["user_id"],
            patient_id=data["patient_id"],
            nosology=nosology,
            symptoms=combined_symptoms,
            composite_score=composite,
            triage_level=str(level),
            triage_message=triage_text,
            red_flags=red_flags_triggered,
            last_doctor_visit=tx_last_visit,
            treatment_status=tx_status,
            user_notes=user_notes,
            recorded_at=recorded_at,
        )
        session.add(entry)
        await session.commit()

    # ── Centor/FeverPAIN scale persistence + episode tracking ──
    # (tonsillopharyngitis only; other nosologies will be added later)
    tonsillectomy_note = ""
    if nosology == "tonsillopharyngitis":
        try:
            async with get_session() as session:
                c_score = result.get("centor_score")
                c_action = result.get("centor_action")
                fp_score = result.get("feverpain_score")
                fp_action = result.get("feverpain_action")

                # Save Centor score
                if c_score is not None:
                    session.add(ScaleScore(
                        user_id=data["user_id"],
                        patient_id=data["patient_id"],
                        scale="centor",
                        score=c_score,
                        action=c_action,
                        details={
                            "tp_temp": symptom_values.get("tp_temp"),
                            "tp_cough": symptom_values.get("tp_cough"),
                            "tp_lymph": symptom_values.get("tp_lymph"),
                            "tp_exudate": symptom_values.get("tp_exudate"),
                            "age_group": age_group,
                        },
                    ))

                # Save FeverPAIN score (adults only)
                if fp_score is not None:
                    session.add(ScaleScore(
                        user_id=data["user_id"],
                        patient_id=data["patient_id"],
                        scale="feverpain",
                        score=fp_score,
                        action=fp_action,
                        details={
                            "tp_temp": symptom_values.get("tp_temp"),
                            "tp_exudate": symptom_values.get("tp_exudate"),
                            "tp_dysphagia": symptom_values.get("tp_dysphagia"),
                            "tp_cough": symptom_values.get("tp_cough"),
                        },
                    ))

                # Register tonsillitis episode (if ≥14 days since last)
                episode = await register_episode(
                    session,
                    user_id=data["user_id"],
                    patient_id=data["patient_id"],
                    episode_type="tonsillitis",
                    scale_score=c_score,
                )

                # Check tonsillectomy criteria
                met, reason = await tonsillectomy_criteria_met(
                    session,
                    user_id=data["user_id"],
                    patient_id=data["patient_id"],
                )
                if met:
                    tonsillectomy_note = (
                        "\n\n📋 У вас накопились критерии, при которых ЛОР "
                        "может обсудить тонзиллэктомию "
                        f"({reason}). "
                        "Покажите врачу журнал эпизодов из бота."
                    )

                await session.commit()
        except Exception:
            logger.exception(
                "Failed to persist scale scores / episode for user %s",
                data["user_id"],
            )
            # Non-fatal: the main SymptomEntry is already saved.

    # ── AOM episode tracking ──
    # Every new diary session ≥14 days apart = new AOM episode.
    # Criteria: ≥3/6mo or ≥4/12mo → adenoidectomy / tubes discussion.
    aom_note = ""
    if nosology == "aom":
        try:
            async with get_session() as session:
                episode = await register_episode(
                    session,
                    user_id=data["user_id"],
                    patient_id=data["patient_id"],
                    episode_type="aom",
                )

                met, reason = await aom_tube_criteria_met(
                    session,
                    user_id=data["user_id"],
                    patient_id=data["patient_id"],
                )
                if met:
                    aom_note = (
                        "\n\n📋 Рецидивирующий средний отит "
                        f"({reason}). "
                        "Обсудите с ЛОР-врачом вопрос установки "
                        "вентиляционных трубок или аденотомии."
                    )

                await session.commit()
        except Exception:
            logger.exception(
                "Failed to persist AOM episode for user %s",
                data["user_id"],
            )

    # ── CRS flare episode tracking ──
    # Registered only when the patient reports a systemic GCS/AB course.
    # Criteria: ≥4 flares/12mo → FESS / biologics discussion.
    crs_note = ""
    if nosology == "crs" and combined_symptoms.get("crs_systemic_course") == 1:
        try:
            async with get_session() as session:
                episode = await register_episode(
                    session,
                    user_id=data["user_id"],
                    patient_id=data["patient_id"],
                    episode_type="crs_flare",
                    notes="systemic GCS/AB course reported",
                )

                met, reason = await crs_surgery_criteria_met(
                    session,
                    user_id=data["user_id"],
                    patient_id=data["patient_id"],
                )
                if met:
                    crs_note = (
                        "\n\n📋 Частые обострения ХРС "
                        f"({reason}). "
                        "Обсудите с ЛОР-врачом возможность "
                        "эндоскопической операции или биологической терапии."
                    )

                await session.commit()
        except Exception:
            logger.exception(
                "Failed to persist CRS flare episode for user %s",
                data["user_id"],
            )

    emoji = TRIAGE_LEVEL_EMOJI.get(str(level), "❓")
    lines = [
        f"{emoji} Результат — {data.get('patient_display_name')}",
        f"Уровень: {str(level).upper()}",
    ]
    if triage_text:
        lines.append(f"💬 {triage_text}")

    if red_flags_triggered:
        lines.append("")
        lines.append("⚠️ Тревожные признаки:")
        for rf in red_flags_triggered:
            lines.append(f"• {get_red_flag_message(rf)}")

    if user_notes:
        lines.append("")
        lines.append(f"📝 Ваш комментарий: {user_notes}")

    if tonsillectomy_note:
        lines.append(tonsillectomy_note)
    if aom_note:
        lines.append(aom_note)
    if crs_note:
        lines.append(crs_note)

    lines.append("")
    lines.append(
        "ℹ️ Это не медицинский диагноз. "
        "Если симптомы усиливаются — обратитесь к ЛОР-врачу."
    )

    try:
        await message.answer("\n".join(lines), reply_markup=main_menu_keyboard())
    except TelegramNetworkError:
        logger.error(
            "TelegramNetworkError sending triage result to user %s. "
            "Entry was saved (id=%s) but user did not receive it.",
            data["user_id"],
            entry.id if hasattr(entry, "id") else "?",
        )
        # Entry is already persisted — user just didn't see the result.
        # State will be cleared below regardless.

    # Analytics: log completed diary session
    try:
        from bot.services.analytics import log_event
        await log_event(
            user_id=data["user_id"],
            event_type="log_complete",
            payload={
                "nosology": nosology,
                "triage_level": str(level),
                "composite_score": composite,
                "has_red_flags": bool(red_flags_triggered),
                "has_user_notes": bool(user_notes),
                "patient_id": data.get("patient_id"),
            },
        )
    except Exception:
        pass  # analytics must never break the main flow

    await state.clear()
