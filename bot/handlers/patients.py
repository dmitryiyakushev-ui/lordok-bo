"""/patients — manage patient profiles attached to the account.

Actions:
  - view list
  - switch active patient
  - change condition (nosology/complaint) for a patient
  - add a new patient (self or child)
  - archive a patient
"""

import logging
from datetime import date as _date, datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from bot.db.database import get_session
from bot.keyboards.inline import (
    age_confirm_keyboard,
    complaint_area_keyboard,
    for_whom_keyboard,
    has_diagnosis_keyboard,
    nosology_keyboard,
    patient_select_keyboard,
    patients_menu_keyboard,
    sex_keyboard,
    start_log_or_later_keyboard,
    switch_active_confirm_keyboard,
)
from bot.keyboards.reply import main_menu_keyboard
from bot.models.patient import Patient
from bot.models.user import User
from bot.utils.demographics import compute_dob, derive_age_group, format_age_ru

logger = logging.getLogger(__name__)
router = Router()


COMPLAINT_TO_NOSOLOGY = {
    "nose": "undiagnosed_nose",
    "throat": "undiagnosed_throat",
    "ear": "undiagnosed_ear",
    "multiple": "undiagnosed_multiple",
    "non_ent": "non_ent",
}

NOSOLOGY_DISPLAY = {
    "ars": "Острый риносинусит",
    "crs": "Хронический риносинусит",
    "tonsillopharyngitis": "Острый тонзиллофарингит",
    "aom": "Острый средний отит",
    "com": "Хронический средний отит",
    "adenoid_hypertrophy": "Гипертрофия аденоидов",
    "undiagnosed_nose": "Без диагноза — нос",
    "undiagnosed_throat": "Без диагноза — горло",
    "undiagnosed_ear": "Без диагноза — ухо",
    "undiagnosed_multiple": "Без диагноза — несколько областей",
    "non_ent": "Не ЛОР-проблема (дневник, без анализа «красных флагов»)",
}


class PatientsState(StatesGroup):
    viewing = State()
    switching = State()
    choosing_for_change_cond = State()
    change_cond_has_dx = State()
    change_cond_nosology = State()
    change_cond_complaint = State()
    archiving = State()

    # Add-patient mini-flow
    add_choosing_relation = State()
    add_entering_child_name = State()
    add_choosing_sex = State()
    add_entering_years = State()
    add_entering_months = State()
    add_confirming_age = State()
    add_has_diagnosis = State()
    add_choosing_nosology = State()
    add_choosing_complaint = State()


def _patient_card_line(p: Patient, active_id: int | None) -> str:
    icon = "👤" if p.relation == "self" else "🧒"
    marker = " ⭐" if p.id == active_id else ""
    name = p.display_name or "Без имени"
    age = format_age_ru(p.date_of_birth) if p.date_of_birth else (
        p.legacy_age_group or "возраст не указан"
    )
    nos = NOSOLOGY_DISPLAY.get(p.nosology, p.nosology or "—")
    return f"{icon} {name}{marker} · {age} · {nos}"


async def _load_active_patients(user_id: int) -> tuple[User | None, list[Patient]]:
    async with get_session() as session:
        user = await session.get(User, user_id)
        stmt = (
            select(Patient)
            .where(Patient.user_id == user_id)
            .where(Patient.is_active.is_(True))
            .order_by(Patient.created_at)
        )
        result = await session.execute(stmt)
        patients = result.scalars().all()
    return user, patients


# ──────────────────────────────────────────────────────────────────────
# Entry
# ──────────────────────────────────────────────────────────────────────


@router.message(Command("patients"))
async def cmd_patients(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    user, patients = await _load_active_patients(user_id)
    if not user or not user.full_name:
        await message.answer("❌ Сначала завершите знакомство через /start")
        return

    if not patients:
        text = "У вас пока нет пациентов."
    else:
        lines = [_patient_card_line(p, user.active_patient_id) for p in patients]
        text = "👥 Ваши пациенты:\n\n" + "\n".join(lines) + "\n\nВыберите действие:"

    await message.answer(text, reply_markup=patients_menu_keyboard())
    await state.set_state(PatientsState.viewing)


@router.message(Command("change_condition"))
async def cmd_change_condition(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    _, patients = await _load_active_patients(user_id)
    if not patients:
        await message.answer(
            "Нет активных пациентов. Добавьте через кнопку «👥 Пациенты».",
            reply_markup=main_menu_keyboard(),
        )
        return
    if len(patients) == 1:
        p = patients[0]
        await state.update_data(change_cond_patient_id=p.id)
        name = p.display_name
        if p.relation == "child" and name:
            q = f"У {name} есть установленный диагноз?"
            kb = has_diagnosis_keyboard(patient_name=name)
        else:
            q = "У пациента есть установленный диагноз?"
            kb = has_diagnosis_keyboard()
        await message.answer(
            f"Меняем жалобу/диагноз для: {name}.\n\n{q}",
            reply_markup=kb,
        )
        await state.set_state(PatientsState.change_cond_has_dx)
        return

    await message.answer(
        "По какому пациенту меняем жалобу/диагноз?",
        reply_markup=patient_select_keyboard(patients, action="change_cnd"),
    )
    await state.set_state(PatientsState.choosing_for_change_cond)


# ──────────────────────────────────────────────────────────────────────
# Menu actions
# ──────────────────────────────────────────────────────────────────────


@router.callback_query(PatientsState.viewing, F.data == "patients:switch")
async def menu_switch(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    _, patients = await _load_active_patients(user_id)
    if len(patients) <= 1:
        await callback.answer(
            "У вас только один активный пациент.", show_alert=True
        )
        return
    await callback.message.answer(
        "Выберите активного пациента:",
        reply_markup=patient_select_keyboard(patients, action="set_active"),
    )
    await state.set_state(PatientsState.switching)
    await callback.answer()


@router.callback_query(
    PatientsState.switching, F.data.startswith("patient:set_active:")
)
async def do_switch(callback: CallbackQuery, state: FSMContext):
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
    await callback.message.answer(
        f"✅ Активный пациент: {patient.display_name}.\n\n"
        "Заполним дневник симптомов по этому пациенту прямо сейчас?",
        reply_markup=start_log_or_later_keyboard(),
    )
    await state.clear()
    await callback.answer()


@router.callback_query(PatientsState.viewing, F.data == "patients:change_cond")
async def menu_change_cond(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    _, patients = await _load_active_patients(user_id)
    if not patients:
        await callback.answer("Нет пациентов.", show_alert=True)
        return
    if len(patients) == 1:
        p = patients[0]
        await state.update_data(change_cond_patient_id=p.id)
        name = p.display_name
        if p.relation == "child" and name:
            q = f"У {name} есть установленный диагноз?"
            kb = has_diagnosis_keyboard(patient_name=name)
        else:
            q = "У пациента есть установленный диагноз?"
            kb = has_diagnosis_keyboard()
        await callback.message.answer(
            f"Меняем жалобу/диагноз для: {name}.\n\n{q}",
            reply_markup=kb,
        )
        await state.set_state(PatientsState.change_cond_has_dx)
        await callback.answer()
        return
    await callback.message.answer(
        "По какому пациенту меняем?",
        reply_markup=patient_select_keyboard(patients, action="change_cnd"),
    )
    await state.set_state(PatientsState.choosing_for_change_cond)
    await callback.answer()


@router.callback_query(PatientsState.viewing, F.data == "patients:close_case")
async def menu_close_case(callback: CallbackQuery, state: FSMContext):
    """Close the current case for the active patient."""
    user_id = callback.from_user.id

    async with get_session() as session:
        user = await session.get(User, user_id)
        if not user or not user.active_patient_id:
            await callback.answer("Нет активного пациента.", show_alert=True)
            return

        patient = await session.get(Patient, user.active_patient_id)
        if not patient:
            await callback.answer("Пациент не найден.", show_alert=True)
            return

        if patient.case_closed_at is not None:
            await callback.answer(
                f"Случай для {patient.display_name} уже завершён.",
                show_alert=True,
            )
            await state.clear()
            return

        patient.case_closed_at = datetime.now(timezone.utc)
        patient.updated_at = datetime.now(timezone.utc)
        await session.commit()

    await callback.message.answer(
        f"✅ Случай для {patient.display_name} завершён.\n\n"
        "При следующем заполнении дневника бот расценит это "
        "как новое обращение.",
        reply_markup=main_menu_keyboard(),
    )
    await state.clear()
    await callback.answer()


@router.callback_query(
    PatientsState.choosing_for_change_cond, F.data.startswith("patient:change_cnd:")
)
async def picked_for_change_cond(callback: CallbackQuery, state: FSMContext):
    patient_id = int(callback.data.split(":")[2])
    async with get_session() as session:
        patient = await session.get(Patient, patient_id)
        if not patient or patient.user_id != callback.from_user.id:
            await callback.answer("Недоступно.", show_alert=True)
            return
    await state.update_data(change_cond_patient_id=patient_id)
    name = patient.display_name
    if patient.relation == "child" and name:
        q = f"У {name} есть установленный диагноз?"
        kb = has_diagnosis_keyboard(patient_name=name)
    else:
        q = "У пациента есть установленный диагноз?"
        kb = has_diagnosis_keyboard()
    await callback.message.answer(
        f"Меняем жалобу/диагноз для: {name}.\n\n{q}",
        reply_markup=kb,
    )
    await state.set_state(PatientsState.change_cond_has_dx)
    await callback.answer()


@router.callback_query(
    PatientsState.change_cond_has_dx, F.data.startswith("has_dx:")
)
async def change_cond_has_dx(callback: CallbackQuery, state: FSMContext):
    answer = callback.data.split(":")[1]
    if answer == "yes":
        await callback.message.answer(
            "Выберите диагноз:", reply_markup=nosology_keyboard()
        )
        await state.set_state(PatientsState.change_cond_nosology)
    else:
        await callback.message.answer(
            "Что больше всего беспокоит?",
            reply_markup=complaint_area_keyboard(),
        )
        await state.set_state(PatientsState.change_cond_complaint)
    await callback.answer()


@router.callback_query(
    PatientsState.change_cond_nosology, F.data.startswith("nosology:")
)
async def change_cond_nosology(callback: CallbackQuery, state: FSMContext):
    nosology = callback.data.split(":")[1]
    await _save_changed_condition(callback, state, nosology)


@router.callback_query(
    PatientsState.change_cond_complaint, F.data.startswith("complaint:")
)
async def change_cond_complaint(callback: CallbackQuery, state: FSMContext):
    area = callback.data.split(":")[1]
    nosology = COMPLAINT_TO_NOSOLOGY.get(area, "undiagnosed_multiple")
    await _save_changed_condition(callback, state, nosology)


async def _save_changed_condition(
    callback: CallbackQuery, state: FSMContext, nosology: str
):
    """Save the new nosology.

    Activation logic:
      - edited patient is ALREADY active → just persist the new nosology
        and offer the diary (nothing to confirm);
      - user has only one active patient → the edited patient is that one
        by definition, same path as above;
      - user has multiple patients and edited a NON-active one → DO NOT
        switch silently; ask for explicit confirmation via
        switch_active_confirm_keyboard.
    """
    data = await state.get_data()
    patient_id = data.get("change_cond_patient_id")
    user_id = callback.from_user.id

    edited_name: str | None = None
    edited_label = NOSOLOGY_DISPLAY.get(nosology, nosology)
    should_ask_switch = False
    previous_active_name: str | None = None
    previous_nosology_label: str | None = None

    async with get_session() as session:
        patient = await session.get(Patient, patient_id)
        if not (patient and patient.user_id == user_id):
            await callback.message.answer(
                "❌ Не удалось обновить.",
                reply_markup=main_menu_keyboard(),
            )
            await state.clear()
            await callback.answer()
            return

        patient.nosology = nosology
        patient.updated_at = datetime.now(timezone.utc)
        edited_name = patient.display_name

        user = await session.get(User, user_id)
        prev_active_id = user.active_patient_id if user else None

        # Count active patients for this account.
        stmt = (
            select(Patient)
            .where(Patient.user_id == user_id)
            .where(Patient.is_active.is_(True))
        )
        active_result = await session.execute(stmt)
        total_active = len(active_result.scalars().all())

        already_active = prev_active_id == patient.id
        only_one_active = total_active <= 1

        if already_active or only_one_active:
            # No confirmation needed. Make sure active points at the
            # edited patient (trivially true when already_active).
            if user and not already_active:
                user.active_patient_id = patient.id
                user.updated_at = datetime.now(timezone.utc)
        else:
            # Multiple patients AND edited the non-active one →
            # the user must explicitly confirm the switch.
            should_ask_switch = True
            prev = (
                await session.get(Patient, prev_active_id)
                if prev_active_id
                else None
            )
            if prev:
                previous_active_name = prev.display_name
                previous_nosology_label = NOSOLOGY_DISPLAY.get(
                    prev.nosology, prev.nosology or "—"
                )

        await session.commit()

    await state.clear()

    if not should_ask_switch:
        await callback.message.answer(
            f"✅ Обновлено: {edited_name} → {edited_label}.\n\n"
            "Заполним дневник симптомов прямо сейчас?",
            reply_markup=start_log_or_later_keyboard(),
        )
    else:
        await callback.message.answer(
            f"✅ Обновлено: {edited_name} → {edited_label}.\n\n"
            f"Сейчас запись ведётся по: {previous_active_name}"
            f" ({previous_nosology_label}).\n\n"
            f"Переключить активный профиль на {edited_name}?",
            reply_markup=switch_active_confirm_keyboard(patient_id),
        )

    await callback.answer()


# ──────────────────────────────────────────────────────────────────────
# Add patient (mini-flow)
# ──────────────────────────────────────────────────────────────────────


@router.callback_query(PatientsState.viewing, F.data == "patients:add")
async def menu_add(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Кого добавим?", reply_markup=for_whom_keyboard()
    )
    await state.set_state(PatientsState.add_choosing_relation)
    await callback.answer()


@router.callback_query(
    PatientsState.add_choosing_relation, F.data.startswith("for_whom:")
)
async def add_picked_relation(callback: CallbackQuery, state: FSMContext):
    choice = callback.data.split(":")[1]
    if choice == "both":
        await callback.answer(
            "За один раз можно добавить только одного. Сначала — кого именно?",
            show_alert=True,
        )
        return

    user_id = callback.from_user.id
    async with get_session() as session:
        user = await session.get(User, user_id)

    if choice == "self":
        # Pre-fill from account
        await state.update_data(
            current_relation="self",
            current_name=user.full_name if user else "Пациент",
        )
        await callback.message.answer(
            "Укажите пол (можно пропустить).",
            reply_markup=sex_keyboard(prefix="sex_self", allow_skip=True),
        )
        await state.set_state(PatientsState.add_choosing_sex)
    else:
        await state.update_data(current_relation="child")
        await callback.message.answer("Как зовут ребёнка?")
        await state.set_state(PatientsState.add_entering_child_name)

    await callback.answer()


@router.message(PatientsState.add_entering_child_name, F.text)
async def add_child_name(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    if len(raw) < 1 or len(raw) > 100:
        await message.answer("Введите имя ребёнка (от 1 до 100 символов).")
        return
    await state.update_data(current_name=raw)
    await message.answer(
        f"Укажите пол: {raw}.",
        reply_markup=sex_keyboard(prefix="sex_child", allow_skip=False),
    )
    await state.set_state(PatientsState.add_choosing_sex)


@router.callback_query(
    PatientsState.add_choosing_sex, F.data.startswith("sex_")
)
async def add_sex(callback: CallbackQuery, state: FSMContext):
    _, value = callback.data.split(":")
    sex = None if value == "skip" else value
    await state.update_data(current_sex=sex)
    await callback.message.answer("Сколько полных лет? Введите число.")
    await state.set_state(PatientsState.add_entering_years)
    await callback.answer()


@router.message(PatientsState.add_entering_years, F.text)
async def add_years(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("Введите число полных лет.")
        return
    years = int(raw)
    data = await state.get_data()
    max_y = 17 if data.get("current_relation") == "child" else 120
    if years < 0 or years > max_y:
        await message.answer(
            f"Возраст должен быть от 0 до {max_y} лет."
        )
        return
    await state.update_data(current_years=years)

    # Compute date of birth from years only (months=0).
    dob = compute_dob(years, 0)
    await state.update_data(current_months=0, current_dob_iso=dob.isoformat())
    await message.answer(
        f"Проверим: возраст — {format_age_ru(dob)}. Всё верно?",
        reply_markup=age_confirm_keyboard(),
    )
    await state.set_state(PatientsState.add_confirming_age)


@router.callback_query(
    PatientsState.add_confirming_age, F.data.startswith("age_confirm:")
)
async def add_confirm_age(callback: CallbackQuery, state: FSMContext):
    if callback.data.split(":")[1] == "no":
        await callback.message.answer("Введите число полных лет ещё раз.")
        await state.set_state(PatientsState.add_entering_years)
        await callback.answer()
        return

    data = await state.get_data()
    relation = data.get("current_relation", "self")
    patient_name = data.get("current_name")

    if relation == "child" and patient_name:
        question = f"У {patient_name} уже есть диагноз ЛОР-заболевания?"
        kb = has_diagnosis_keyboard(patient_name=patient_name)
    else:
        question = "У пациента есть установленный диагноз?"
        kb = has_diagnosis_keyboard()

    await callback.message.answer(question, reply_markup=kb)
    await state.set_state(PatientsState.add_has_diagnosis)
    await callback.answer()


@router.callback_query(
    PatientsState.add_has_diagnosis, F.data.startswith("has_dx:")
)
async def add_has_diagnosis(callback: CallbackQuery, state: FSMContext):
    answer = callback.data.split(":")[1]
    if answer == "yes":
        await callback.message.answer(
            "Выберите диагноз:", reply_markup=nosology_keyboard()
        )
        await state.set_state(PatientsState.add_choosing_nosology)
    else:
        await callback.message.answer(
            "Что больше всего беспокоит?",
            reply_markup=complaint_area_keyboard(),
        )
        await state.set_state(PatientsState.add_choosing_complaint)
    await callback.answer()


@router.callback_query(
    PatientsState.add_choosing_nosology, F.data.startswith("nosology:")
)
async def add_pick_nosology(callback: CallbackQuery, state: FSMContext):
    nosology = callback.data.split(":")[1]
    await _persist_new_patient(callback, state, nosology)


@router.callback_query(
    PatientsState.add_choosing_complaint, F.data.startswith("complaint:")
)
async def add_pick_complaint(callback: CallbackQuery, state: FSMContext):
    area = callback.data.split(":")[1]
    nosology = COMPLAINT_TO_NOSOLOGY.get(area, "undiagnosed_multiple")
    await _persist_new_patient(callback, state, nosology)


async def _persist_new_patient(
    callback: CallbackQuery, state: FSMContext, nosology: str
):
    """Persist a freshly added patient.

    Activation logic:
      - This is the first patient on the account (or no active one is
        set) → auto-activate silently and offer the diary.
      - There is already a different active patient → DO NOT switch
        silently; ask explicit confirmation via
        switch_active_confirm_keyboard.
    """
    data = await state.get_data()
    user_id = callback.from_user.id

    dob = (
        _date.fromisoformat(data["current_dob_iso"])
        if data.get("current_dob_iso")
        else None
    )

    new_id: int | None = None
    new_name: str | None = None
    should_ask_switch = False
    previous_active_name: str | None = None
    previous_nosology_label: str | None = None

    async with get_session() as session:
        patient = Patient(
            user_id=user_id,
            relation=data["current_relation"],
            source="user_added",
            needs_resolution=False,
            display_name=data["current_name"],
            sex=data.get("current_sex"),
            date_of_birth=dob,
            legacy_age_group=None,
            nosology=nosology,
            is_active=True,
        )
        session.add(patient)
        await session.flush()
        new_id = patient.id
        new_name = patient.display_name

        user = await session.get(User, user_id)
        prev_active_id = user.active_patient_id if user else None

        # Count ACTIVE patients (including the one we just added).
        stmt = (
            select(Patient)
            .where(Patient.user_id == user_id)
            .where(Patient.is_active.is_(True))
        )
        active_result = await session.execute(stmt)
        total_active = len(active_result.scalars().all())

        if (
            prev_active_id is None
            or prev_active_id == new_id
            or total_active <= 1
        ):
            # First patient ever (or no active one) → just activate.
            if user:
                user.active_patient_id = new_id
                user.updated_at = datetime.now(timezone.utc)
        else:
            # Another active patient already exists → need confirmation.
            should_ask_switch = True
            prev = await session.get(Patient, prev_active_id)
            if prev:
                previous_active_name = prev.display_name
                previous_nosology_label = NOSOLOGY_DISPLAY.get(
                    prev.nosology, prev.nosology or "—"
                )

        await session.commit()

    await state.clear()

    if not should_ask_switch:
        await callback.message.answer(
            f"✅ Пациент добавлен: {new_name}.\n"
            f"Он теперь активный профиль.\n\n"
            "Заполним дневник симптомов по нему прямо сейчас?",
            reply_markup=start_log_or_later_keyboard(),
        )
    else:
        await callback.message.answer(
            f"✅ Пациент добавлен: {new_name}.\n\n"
            f"Сейчас запись ведётся по: {previous_active_name}"
            f" ({previous_nosology_label}).\n\n"
            f"Переключить активный профиль на {new_name}?",
            reply_markup=switch_active_confirm_keyboard(new_id),
        )

    await callback.answer()


# ──────────────────────────────────────────────────────────────────────
# Explicit switch-confirmation callbacks (used after add_patient /
# change_condition when another patient is already active).
#
# These handlers run OUTSIDE the PatientsState FSM — by the time the
# user sees the confirmation keyboard, we have already called
# `state.clear()`. Keep them router-level (no state filter) so they
# work regardless of what the user did in between.
# ──────────────────────────────────────────────────────────────────────


@router.callback_query(F.data.startswith("switch_active:yes:"))
async def confirm_switch_active(callback: CallbackQuery, state: FSMContext):
    """User confirmed the switch → set active = target, offer diary."""
    try:
        target_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Некорректный выбор.", show_alert=True)
        return

    user_id = callback.from_user.id
    async with get_session() as session:
        patient = await session.get(Patient, target_id)
        if not patient or patient.user_id != user_id or not patient.is_active:
            await callback.answer("Пациент недоступен.", show_alert=True)
            return
        user = await session.get(User, user_id)
        if user:
            user.active_patient_id = patient.id
            user.updated_at = datetime.now(timezone.utc)
            await session.commit()
        name = patient.display_name

    await callback.message.answer(
        f"🔀 Активный профиль: {name}.\n\n"
        "Заполним дневник симптомов по нему прямо сейчас?",
        reply_markup=start_log_or_later_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "switch_active:no")
async def decline_switch_active(callback: CallbackQuery, state: FSMContext):
    """User kept the previously-active profile → still offer the diary
    (for that unchanged active patient) or the main menu."""
    user_id = callback.from_user.id
    async with get_session() as session:
        user = await session.get(User, user_id)
        active_name: str | None = None
        if user and user.active_patient_id:
            active = await session.get(Patient, user.active_patient_id)
            if active and active.is_active:
                active_name = active.display_name

    if active_name:
        text = (
            f"Хорошо, активный профиль остаётся прежним: {active_name}.\n\n"
            "Заполним дневник симптомов по нему прямо сейчас?"
        )
    else:
        text = (
            "Хорошо, активный профиль не менялся.\n\n"
            "Заполним дневник симптомов сейчас?"
        )

    await callback.message.answer(
        text,
        reply_markup=start_log_or_later_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "change_cond_active")
async def change_cond_for_active(callback: CallbackQuery, state: FSMContext):
    """Quick path: change condition for the currently active patient.

    Triggered from the start_log_or_later_keyboard shown after switching
    the active patient. Skips the patient selection step and goes straight
    to 'has diagnosis?' for the active patient.
    """
    user_id = callback.from_user.id
    async with get_session() as session:
        user = await session.get(User, user_id)
        if not user or not user.active_patient_id:
            await callback.answer(
                "Нет активного пациента.", show_alert=True
            )
            return
        patient = await session.get(Patient, user.active_patient_id)
        if not patient or not patient.is_active:
            await callback.answer(
                "Пациент недоступен.", show_alert=True
            )
            return

    await state.update_data(change_cond_patient_id=patient.id)
    name = patient.display_name
    if patient.relation == "child" and name:
        q = f"У {name} есть установленный диагноз?"
        kb = has_diagnosis_keyboard(patient_name=name)
    else:
        q = "У пациента есть установленный диагноз?"
        kb = has_diagnosis_keyboard()
    await callback.message.answer(
        f"Меняем жалобу/диагноз для: {name}.\n\n{q}",
        reply_markup=kb,
    )
    await state.set_state(PatientsState.change_cond_has_dx)
    await callback.answer()
