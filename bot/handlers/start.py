"""Onboarding handler for /start command.

Flow:
    /start
      → ask full name (text)
      → ask phone (share_contact or manual)
      → ask: 'for whom?' (self / child / both)
      → collect patient profile(s):
            sex → years → confirm age →
            has_diagnosis? → nosology OR complaint_area
         (name is reused from account for self; asked explicitly for child)
      → after each child: add_another_child? (yes/no)
      → reminder_time
      → set users.active_patient_id = first created patient
Legacy path:
    If a user returns with the old schema (no full_name), bot asks whether
    the old data was about them or about a child, then converts the
    legacy patient row accordingly.
"""

import logging
import re
from datetime import datetime, time, timezone

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Contact, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from bot.db.database import get_session
from bot.keyboards.inline import (
    add_another_child_keyboard,
    age_confirm_keyboard,
    complaint_area_keyboard,
    for_whom_keyboard,
    has_diagnosis_keyboard,
    legacy_resolution_keyboard,
    nosology_keyboard,
    reminder_time_keyboard,
    sex_keyboard,
    timezone_keyboard,
)
from bot.keyboards.reply import (
    main_menu_keyboard,
    remove_reply_keyboard,
    request_contact_keyboard,
    request_location_keyboard,
)
from bot.models.patient import Patient
from bot.models.user import User
from bot.services.analytics import log_event
from bot.utils.demographics import compute_dob, format_age_ru
from bot.utils.phone import normalize_phone

logger = logging.getLogger(__name__)
router = Router()

# Deep-link payload: t.me/<bot>?start=<source>.
# Telegram allows A-Z a-z 0-9 _ - up to 64 chars; anything else is dropped.
_SOURCE_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SOURCE_DIRECT = "direct"


def parse_source(payload: str | None) -> str:
    """Normalize a /start payload into an acquisition source label."""
    if not payload:
        return SOURCE_DIRECT
    candidate = payload.strip()
    if not _SOURCE_RE.match(candidate):
        return SOURCE_DIRECT
    return candidate.lower()

# Base URL for legal documents (update when domain is configured)
SITE_URL = "https://lor-dok.ru"

# Редакция политики и соглашения, под которой пользователь ставит галочку.
# Меняется вместе с текстом документов на сайте: тогда бот попросит
# согласие заново.
CONSENT_VERSION = "2026-04-18"

CONSENT_TEXT = (
    "👋 Добро пожаловать в ЛОРдок.\n\n"
    "Я помогаю отслеживать ЛОР-симптомы, ваши или ваших детей, и "
    "подсказываю, когда пора к врачу.\n\n"
    "🩺 Бот сделан практикующим оториноларингологом Якушевым Дмитрием.\n"
    "⚠️ Диагнозов не ставит и врача не заменяет.\n\n"
    "Прежде чем начать, нужно ваше согласие. Что и зачем я собираю:\n"
    "• ФИО и телефон, чтобы подписать отчёт для врача и восстановить доступ;\n"
    "• пол, возраст, диагноз и ежедневные симптомы, чтобы оценивать динамику;\n"
    "• данные ребёнка, если вы ведёте дневник за него.\n\n"
    "Симптомы и диагнозы это данные о здоровье, то есть специальная "
    "категория персональных данных. Отмечая согласие, вы разрешаете их "
    "обработку на условиях Политики, а за ребёнка подтверждаете, что "
    "действуете как его законный представитель.\n\n"
    "Согласие можно отозвать в любой момент командой /delete_me: профиль "
    "и все записи будут удалены."
)


def consent_keyboard() -> InlineKeyboardMarkup:
    """Согласие + ссылки на документы."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📄 Политика конфиденциальности",
                url=f"{SITE_URL}/privacy.html",
            ),
        ],
        [
            InlineKeyboardButton(
                text="📋 Пользовательское соглашение",
                url=f"{SITE_URL}/terms.html",
            ),
        ],
        [
            InlineKeyboardButton(
                text="✅ Согласен, продолжить",
                callback_data="consent:accept",
            ),
        ],
    ])


COMPLAINT_TO_NOSOLOGY = {
    "nose": "undiagnosed_nose",
    "throat": "undiagnosed_throat",
    "ear": "undiagnosed_ear",
    "multiple": "undiagnosed_multiple",
    "non_ent": "non_ent",
}


# ──────────────────────────────────────────────────────────────────────
# FSM states
# ──────────────────────────────────────────────────────────────────────


class OnboardingState(StatesGroup):
    awaiting_consent = State()
    awaiting_name = State()
    awaiting_phone = State()
    awaiting_phone_manual = State()
    legacy_resolution = State()
    legacy_self_age = State()
    choosing_for_whom = State()

    # Per-patient collection
    patient_entering_child_name = State()
    patient_choosing_sex = State()
    patient_entering_years = State()
    patient_entering_months = State()
    patient_confirming_age = State()
    patient_has_diagnosis = State()
    patient_choosing_nosology = State()
    patient_choosing_complaint = State()

    add_another_child = State()
    choosing_timezone = State()
    choosing_timezone_manual = State()
    choosing_reminder = State()


# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext):
    """Dispatch: new user → full flow, legacy user → resolution, onboarded → note."""
    await state.clear()
    user_id = message.from_user.id
    source = parse_source(command.args)

    async with get_session() as session:
        user = await session.get(User, user_id)
        # First capture wins: a later click from another link must not
        # rewrite the source the user originally came from.
        if user is not None and user.source is None and source != SOURCE_DIRECT:
            user.source = source
            user.updated_at = datetime.now(timezone.utc)
        # Человек вернулся, значит блокировки больше нет.
        if user is not None and user.blocked_at is not None:
            user.blocked_at = None
            user.updated_at = datetime.now(timezone.utc)
            unblocked = True
        else:
            unblocked = False

    if unblocked:
        # Напоминание снималось при блокировке, возвращаем его обратно.
        try:
            from bot.main import get_reminder_scheduler

            await get_reminder_scheduler().update_user_reminder(user)
        except Exception:
            logger.warning("Could not restore reminder for %s", user_id, exc_info=True)

    # Logged before the User row exists, so starts that never finish
    # onboarding still show up in the funnel.
    await log_event(
        user_id=user_id,
        event_type="start",
        detail=source,
        payload={"is_new": user is None},
    )
    await state.update_data(source=source)

    # Consent gate: nothing is collected until the user taps "Согласен".
    if user is None or user.consent_at is None:
        await message.answer(CONSENT_TEXT, reply_markup=consent_keyboard())
        await state.set_state(OnboardingState.awaiting_consent)
        return

    await _route_after_consent(message, state, user)


async def _route_after_consent(message: Message, state: FSMContext, user: User | None):
    """Send the user to the branch that matches their profile."""
    # Existing user with completed new-style profile
    if user and user.full_name and user.phone:
        await message.answer(
            "👋 Рад снова видеть вас.\n\n"
            "Профиль уже создан. Выберите действие в меню ниже.",
            reply_markup=main_menu_keyboard(),
        )
        return

    # Legacy user: old nosology, no full_name yet
    if user and not user.full_name and user.nosology:
        await state.update_data(is_legacy=True)
        await message.answer(
            "👋 Здравствуйте.\n\n"
            "Бот обновился: теперь он умеет вести несколько пациентов "
            "в одном аккаунте (например, вас и ваших детей).\n\n"
            "Начнём с короткого уточнения. Как вас зовут?\n"
            "Пожалуйста, введите ФИО одной строкой."
        )
        await state.set_state(OnboardingState.awaiting_name)
        return

    # New user
    await message.answer(
        "Чтобы начать, представьтесь, пожалуйста. "
        "Введите ваше ФИО одной строкой."
    )
    await state.set_state(OnboardingState.awaiting_name)


@router.callback_query(
    OnboardingState.awaiting_consent, F.data == "consent:accept"
)
async def handle_consent(callback: CallbackQuery, state: FSMContext):
    """Record the consent and continue onboarding."""
    user_id = callback.from_user.id
    data = await state.get_data()
    source = data.get("source", SOURCE_DIRECT)
    now = datetime.now(timezone.utc)

    async with get_session() as session:
        user = await session.get(User, user_id)
        if user is None:
            user = User(
                id=user_id,
                username=callback.from_user.username,
                first_name=callback.from_user.first_name or "Пользователь",
                language_code="ru",
                source=None if source == SOURCE_DIRECT else source,
                created_at=now,
                updated_at=now,
            )
            session.add(user)
        user.consent_version = CONSENT_VERSION
        user.consent_at = now
        user.updated_at = now
        await session.commit()
        await session.refresh(user)
        consented_user = user

    await log_event(
        user_id=user_id,
        event_type="consent_accepted",
        detail=CONSENT_VERSION,
    )

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Согласие записано")
    await _route_after_consent(callback.message, state, consented_user)


@router.message(OnboardingState.awaiting_consent)
async def handle_consent_pending(message: Message):
    """Пока согласия нет, дальше не идём."""
    await message.answer(
        "Чтобы продолжить, нажмите «✅ Согласен, продолжить» в сообщении выше."
    )


# ──────────────────────────────────────────────────────────────────────
# Full name
# ──────────────────────────────────────────────────────────────────────


@router.message(OnboardingState.awaiting_name, F.text)
async def handle_full_name(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    if len(raw) < 2 or len(raw) > 150 or not any(ch.isalpha() for ch in raw):
        await message.answer(
            "Пожалуйста, введите ФИО текстом (минимум фамилия и имя)."
        )
        return

    await state.update_data(full_name=raw)
    await message.answer(
        f"Спасибо, {raw}.\n\n"
        "Теперь, пожалуйста, поделитесь номером телефона. "
        "Он нужен для связи и восстановления доступа. "
        "Нажмите кнопку ниже или введите номер вручную.",
        reply_markup=request_contact_keyboard(),
    )
    await state.set_state(OnboardingState.awaiting_phone)


# ──────────────────────────────────────────────────────────────────────
# Phone
# ──────────────────────────────────────────────────────────────────────


@router.message(OnboardingState.awaiting_phone, F.contact)
async def handle_phone_contact(message: Message, state: FSMContext):
    contact: Contact = message.contact
    # Telegram only allows sharing own contact via request_contact button,
    # but double-check in case a user attaches someone else's card.
    if contact.user_id and contact.user_id != message.from_user.id:
        await message.answer(
            "Пожалуйста, поделитесь своим собственным номером через кнопку."
        )
        return

    normalized = normalize_phone(contact.phone_number)
    if not normalized:
        await message.answer(
            "Не удалось распознать номер. Введите его вручную, например +79991234567.",
            reply_markup=remove_reply_keyboard(),
        )
        await state.set_state(OnboardingState.awaiting_phone_manual)
        return

    await state.update_data(phone=normalized)
    await message.answer(
        f"Номер сохранён: {normalized}",
        reply_markup=remove_reply_keyboard(),
    )
    await _after_phone_saved(message, state)


@router.message(OnboardingState.awaiting_phone, F.text == "✍️ Ввести номер вручную")
async def handle_phone_manual_switch(message: Message, state: FSMContext):
    await message.answer(
        "Введите номер в международном формате, например +79991234567",
        reply_markup=remove_reply_keyboard(),
    )
    await state.set_state(OnboardingState.awaiting_phone_manual)


@router.message(OnboardingState.awaiting_phone, F.text)
async def handle_phone_awaiting_text(message: Message, state: FSMContext):
    await _process_manual_phone(message, state)


@router.message(OnboardingState.awaiting_phone_manual, F.text)
async def handle_phone_manual(message: Message, state: FSMContext):
    await _process_manual_phone(message, state)


async def _process_manual_phone(message: Message, state: FSMContext):
    normalized = normalize_phone(message.text or "")
    if not normalized:
        await message.answer(
            "Не удалось распознать номер. Проверьте формат и попробуйте ещё раз.\n"
            "Пример: +79991234567"
        )
        await state.set_state(OnboardingState.awaiting_phone_manual)
        return

    await state.update_data(phone=normalized)
    await message.answer(f"Номер сохранён: {normalized}")
    await _after_phone_saved(message, state)


async def _after_phone_saved(message: Message, state: FSMContext):
    data = await state.get_data()

    if data.get("is_legacy"):
        await message.answer(
            "В предыдущей версии вы уже вводили симптомы. "
            "Уточните, пожалуйста: эти данные относились к вам или к ребёнку?",
            reply_markup=legacy_resolution_keyboard(),
        )
        await state.set_state(OnboardingState.legacy_resolution)
        return

    await message.answer(
        "Теперь расскажите, о ком будем вести дневник.\n"
        "Это можно изменить позже в /patients.",
        reply_markup=for_whom_keyboard(),
    )
    await state.set_state(OnboardingState.choosing_for_whom)


# ──────────────────────────────────────────────────────────────────────
# Legacy resolution
# ──────────────────────────────────────────────────────────────────────


@router.callback_query(
    OnboardingState.legacy_resolution, F.data.startswith("legacy_resolve:")
)
async def handle_legacy_resolution(callback: CallbackQuery, state: FSMContext):
    choice = callback.data.split(":")[1]
    data = await state.get_data()
    full_name = data.get("full_name")
    phone = data.get("phone")
    user_id = callback.from_user.id

    async with get_session() as session:
        user = await session.get(User, user_id)
        user.full_name = full_name
        user.phone = phone
        user.updated_at = datetime.now(timezone.utc)

        stmt = (
            select(Patient)
            .where(Patient.user_id == user_id)
            .where(Patient.source == "legacy_migration")
            .where(Patient.is_active.is_(True))
        )
        result = await session.execute(stmt)
        legacy_patient = result.scalar_one_or_none()

        if not legacy_patient:
            await callback.message.answer(
                "Не нашёл старые данные. Продолжим как новый пользователь."
            )
            await session.commit()
            await state.set_state(OnboardingState.choosing_for_whom)
            await callback.message.answer(
                "О ком будем вести дневник?",
                reply_markup=for_whom_keyboard(),
            )
            await callback.answer()
            return

        if choice == "self":
            legacy_patient.relation = "self"
            legacy_patient.display_name = full_name
            legacy_patient.needs_resolution = False
            user.active_patient_id = legacy_patient.id
            await session.commit()

            await state.update_data(resolved_patient_id=legacy_patient.id)
            await callback.message.answer(
                "Уточним ваш возраст, чтобы обновить профиль.\n"
                "Сколько вам полных лет? Введите число."
            )
            await state.set_state(OnboardingState.legacy_self_age)
            await callback.answer()
            return

        # choice == "child" — archive legacy row, run child collection
        legacy_patient.is_active = False
        legacy_patient.needs_resolution = False
        await session.commit()

    await state.update_data(
        for_whom="child",
        self_pending=False,
        child_pending=True,
    )
    await callback.message.answer(
        "Понял, старые данные отнесены к ребёнку (сохранены в истории, "
        "но больше не активны). Давайте заведём профиль ребёнка заново."
    )
    await _start_child_collection(callback.message, state)
    await callback.answer()


@router.message(OnboardingState.legacy_self_age, F.text)
async def handle_legacy_self_age(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("Введите число полных лет (например, 42).")
        return
    years = int(raw)
    if years < 0 or years > 120:
        await message.answer("Возраст должен быть от 0 до 120 лет.")
        return

    await state.update_data(
        current_years=years,
        current_relation="self",
        legacy_self_finalizing=True,
    )

    # Compute date of birth from years only (months=0).
    dob = compute_dob(years, 0)
    pretty = format_age_ru(dob)
    await state.update_data(current_months=0, current_dob_iso=dob.isoformat())
    await message.answer(
        f"Проверим возраст: {pretty}. Всё верно?",
        reply_markup=age_confirm_keyboard(),
    )
    await state.set_state(OnboardingState.patient_confirming_age)


# ──────────────────────────────────────────────────────────────────────
# 'For whom' branching
# ──────────────────────────────────────────────────────────────────────


@router.callback_query(
    OnboardingState.choosing_for_whom, F.data.startswith("for_whom:")
)
async def handle_for_whom(callback: CallbackQuery, state: FSMContext):
    choice = callback.data.split(":")[1]  # self | child | both

    await state.update_data(
        for_whom=choice,
        self_pending=(choice in ("self", "both")),
        child_pending=(choice in ("child", "both")),
    )

    if choice in ("self", "both"):
        await _start_self_collection(callback.message, state)
    else:
        await _start_child_collection(callback.message, state)

    await callback.answer()


# ──────────────────────────────────────────────────────────────────────
# Patient collection
# ──────────────────────────────────────────────────────────────────────


async def _start_self_collection(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(
        current_relation="self",
        current_name=data.get("full_name"),
        current_sex=None,
        current_years=None,
        current_months=None,
        current_nosology=None,
        current_dob_iso=None,
        legacy_self_finalizing=False,
    )
    await message.answer(
        "Соберу пару деталей о вас как о пациенте.\n"
        "Укажите, пожалуйста, ваш пол (можно пропустить).",
        reply_markup=sex_keyboard(prefix="sex_self", allow_skip=True),
    )
    await state.set_state(OnboardingState.patient_choosing_sex)


async def _start_child_collection(message: Message, state: FSMContext):
    await state.update_data(
        current_relation="child",
        current_name=None,
        current_sex=None,
        current_years=None,
        current_months=None,
        current_nosology=None,
        current_dob_iso=None,
        legacy_self_finalizing=False,
    )
    await message.answer(
        "Как зовут ребёнка? Введите имя одной строкой (можно без фамилии)."
    )
    await state.set_state(OnboardingState.patient_entering_child_name)


@router.message(OnboardingState.patient_entering_child_name, F.text)
async def handle_child_name(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    if len(raw) < 1 or len(raw) > 100:
        await message.answer("Введите имя ребёнка (от 1 до 100 символов).")
        return

    await state.update_data(current_name=raw)
    await message.answer(
        f"Укажите пол: {raw}.",
        reply_markup=sex_keyboard(prefix="sex_child", allow_skip=False),
    )
    await state.set_state(OnboardingState.patient_choosing_sex)


@router.callback_query(
    OnboardingState.patient_choosing_sex, F.data.startswith("sex_")
)
async def handle_sex(callback: CallbackQuery, state: FSMContext):
    # callback_data is like 'sex_self:m' / 'sex_child:f' / 'sex_self:skip'
    _, value = callback.data.split(":")
    sex = None if value == "skip" else value

    await state.update_data(current_sex=sex)
    await callback.message.answer("Сколько полных лет? Введите число.")
    await state.set_state(OnboardingState.patient_entering_years)
    await callback.answer()


@router.message(OnboardingState.patient_entering_years, F.text)
async def handle_years(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("Введите число полных лет (0–120).")
        return
    years = int(raw)
    data = await state.get_data()
    relation = data.get("current_relation", "self")

    max_years = 17 if relation == "child" else 120
    if years < 0 or years > max_years:
        if relation == "child":
            await message.answer("Возраст ребёнка должен быть от 0 до 17 лет.")
        else:
            await message.answer("Возраст должен быть от 0 до 120 лет.")
        return

    await state.update_data(current_years=years)

    # Compute date of birth from years only (months=0).
    dob = compute_dob(years, 0)
    pretty = format_age_ru(dob)
    await state.update_data(current_months=0, current_dob_iso=dob.isoformat())
    await message.answer(
        f"Проверим возраст: {pretty}. Всё верно?",
        reply_markup=age_confirm_keyboard(),
    )
    await state.set_state(OnboardingState.patient_confirming_age)


@router.callback_query(
    OnboardingState.patient_confirming_age, F.data.startswith("age_confirm:")
)
async def handle_age_confirm(callback: CallbackQuery, state: FSMContext):
    answer = callback.data.split(":")[1]
    if answer == "no":
        await callback.message.answer("Хорошо, введите число полных лет ещё раз.")
        await state.set_state(OnboardingState.patient_entering_years)
        await callback.answer()
        return

    data = await state.get_data()
    if data.get("legacy_self_finalizing"):
        await _finalize_legacy_self(callback, state)
        return

    relation = data.get("current_relation", "self")
    patient_name = data.get("current_name")

    if relation == "child" and patient_name:
        question = f"У {patient_name} уже есть диагноз ЛОР-заболевания?"
        kb = has_diagnosis_keyboard(patient_name=patient_name)
    else:
        question = "У пациента уже есть диагноз ЛОР-заболевания?"
        kb = has_diagnosis_keyboard()

    await callback.message.answer(question, reply_markup=kb)
    await state.set_state(OnboardingState.patient_has_diagnosis)
    await callback.answer()


async def _finalize_legacy_self(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    patient_id = data.get("resolved_patient_id")
    dob_iso = data.get("current_dob_iso")
    sex = data.get("current_sex")

    from datetime import date as _date

    dob = _date.fromisoformat(dob_iso) if dob_iso else None

    async with get_session() as session:
        patient = await session.get(Patient, patient_id)
        if patient:
            patient.date_of_birth = dob
            patient.sex = sex
            patient.legacy_age_group = None
            patient.updated_at = datetime.now(timezone.utc)
            await session.commit()

    await callback.message.answer(
        "Профиль обновлён. Завершим настройкой напоминаний.",
        reply_markup=reminder_time_keyboard(),
    )
    await state.set_state(OnboardingState.choosing_reminder)
    await callback.answer()


@router.callback_query(
    OnboardingState.patient_has_diagnosis, F.data.startswith("has_dx:")
)
async def handle_has_diagnosis(callback: CallbackQuery, state: FSMContext):
    answer = callback.data.split(":")[1]

    if answer == "yes":
        await callback.message.answer(
            "Выберите диагноз:", reply_markup=nosology_keyboard()
        )
        await state.set_state(OnboardingState.patient_choosing_nosology)
    else:
        await callback.message.answer(
            "Что больше всего беспокоит?",
            reply_markup=complaint_area_keyboard(),
        )
        await state.set_state(OnboardingState.patient_choosing_complaint)
    await callback.answer()


@router.callback_query(
    OnboardingState.patient_choosing_nosology, F.data.startswith("nosology:")
)
async def handle_nosology_choice(callback: CallbackQuery, state: FSMContext):
    nosology = callback.data.split(":")[1]
    await state.update_data(current_nosology=nosology)
    await _save_current_patient(callback, state)


@router.callback_query(
    OnboardingState.patient_choosing_complaint, F.data.startswith("complaint:")
)
async def handle_complaint_choice(callback: CallbackQuery, state: FSMContext):
    area = callback.data.split(":")[1]
    nosology = COMPLAINT_TO_NOSOLOGY.get(area, "undiagnosed_multiple")
    await state.update_data(current_nosology=nosology)
    await _save_current_patient(callback, state)


async def _save_current_patient(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id

    from datetime import date as _date

    dob = (
        _date.fromisoformat(data["current_dob_iso"])
        if data.get("current_dob_iso")
        else None
    )

    async with get_session() as session:
        user = await session.get(User, user_id)
        if not user:
            user = User(
                id=user_id,
                username=callback.from_user.username,
                first_name=callback.from_user.first_name or "Пользователь",
                full_name=data.get("full_name"),
                phone=data.get("phone"),
                source=(
                    data.get("source")
                    if data.get("source") != SOURCE_DIRECT
                    else None
                ),
                language_code="ru",
                reminder_time=time(20, 0),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(user)
            await session.flush()
        else:
            if not user.full_name:
                user.full_name = data.get("full_name")
            if not user.phone:
                user.phone = data.get("phone")
            user.updated_at = datetime.now(timezone.utc)

        patient = Patient(
            user_id=user_id,
            relation=data["current_relation"],
            source="user_added",
            needs_resolution=False,
            display_name=data["current_name"],
            sex=data.get("current_sex"),
            date_of_birth=dob,
            legacy_age_group=None,
            nosology=data["current_nosology"],
            is_active=True,
        )
        session.add(patient)
        await session.flush()

        if user.active_patient_id is None:
            user.active_patient_id = patient.id

        await session.commit()
        saved_name = patient.display_name

    await callback.message.answer(f"✅ Профиль сохранён: {saved_name}.")

    relation = data["current_relation"]

    if relation == "self":
        await state.update_data(self_pending=False)
        data = await state.get_data()
        if data.get("child_pending"):
            await _start_child_collection(callback.message, state)
        else:
            await _ask_timezone(callback.message, state)
        await callback.answer()
        return

    await callback.message.answer(
        "Добавим ещё одного ребёнка?",
        reply_markup=add_another_child_keyboard(),
    )
    await state.set_state(OnboardingState.add_another_child)
    await callback.answer()


@router.callback_query(
    OnboardingState.add_another_child, F.data.startswith("add_child:")
)
async def handle_add_another_child(callback: CallbackQuery, state: FSMContext):
    answer = callback.data.split(":")[1]
    if answer == "yes":
        await _start_child_collection(callback.message, state)
    else:
        await state.update_data(child_pending=False)
        await _ask_timezone(callback.message, state)
    await callback.answer()


async def _ask_timezone(message: Message, state: FSMContext):
    """Ask user for timezone before asking reminder time."""
    await message.answer(
        "Почти готово. Определим ваш часовой пояс, "
        "чтобы напоминания приходили вовремя.",
        reply_markup=request_location_keyboard(),
    )
    await state.set_state(OnboardingState.choosing_timezone)


# ──────────────────────────────────────────────────────────────────────
# Timezone detection
# ──────────────────────────────────────────────────────────────────────


@router.message(OnboardingState.choosing_timezone, F.location)
async def handle_timezone_location(message: Message, state: FSMContext):
    """Detect timezone from shared location."""
    from timezonefinder import TimezoneFinder

    tf = TimezoneFinder()
    tz_name = tf.timezone_at(
        lat=message.location.latitude,
        lng=message.location.longitude,
    )
    if not tz_name:
        tz_name = "Europe/Moscow"

    await state.update_data(user_tz=tz_name)

    # Map IANA timezone to human-readable Russian label
    tz_labels = {
        "Europe/Moscow": "Москва (МСК)",
        "Europe/Kaliningrad": "Калининград (МСК−1)",
        "Europe/Samara": "Самара (МСК+1)",
        "Asia/Yekaterinburg": "Екатеринбург (МСК+2)",
        "Asia/Omsk": "Омск (МСК+3)",
        "Asia/Krasnoyarsk": "Красноярск (МСК+4)",
        "Asia/Irkutsk": "Иркутск (МСК+5)",
        "Asia/Yakutsk": "Якутск (МСК+6)",
        "Asia/Vladivostok": "Владивосток (МСК+7)",
        "Asia/Magadan": "Магадан (МСК+8)",
        "Asia/Kamchatka": "Камчатка (МСК+9)",
    }
    label = tz_labels.get(tz_name, tz_name)

    await message.answer(
        f"🕐 Часовой пояс: {label}\n\n"
        "В какое время вам удобнее заполнять дневник?",
        reply_markup=reminder_time_keyboard(),
    )
    await state.set_state(OnboardingState.choosing_reminder)


@router.message(
    OnboardingState.choosing_timezone, F.text == "🕐 Выбрать часовой пояс вручную"
)
async def handle_timezone_manual_request(message: Message, state: FSMContext):
    """User chose manual timezone selection."""
    await message.answer(
        "Выберите ваш часовой пояс:",
        reply_markup=remove_reply_keyboard(),
    )
    await message.answer(
        "🕐 Часовые пояса России:",
        reply_markup=timezone_keyboard(),
    )
    await state.set_state(OnboardingState.choosing_timezone_manual)


@router.callback_query(
    OnboardingState.choosing_timezone_manual, F.data.startswith("tz:")
)
async def handle_timezone_manual(callback: CallbackQuery, state: FSMContext):
    """Handle manual timezone selection from inline keyboard."""
    tz_name = callback.data.split(":", 1)[1]
    await state.update_data(user_tz=tz_name)

    await callback.message.answer(
        "В какое время вам удобнее заполнять дневник?",
        reply_markup=reminder_time_keyboard(),
    )
    await state.set_state(OnboardingState.choosing_reminder)
    await callback.answer()


# ──────────────────────────────────────────────────────────────────────
# Reminder
# ──────────────────────────────────────────────────────────────────────


@router.callback_query(
    OnboardingState.choosing_reminder, F.data.startswith("reminder:")
)
async def handle_reminder_time(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    hour, minute = int(parts[1]), int(parts[2])
    reminder_time_obj = time(hour, minute)
    user_id = callback.from_user.id

    data = await state.get_data()
    user_tz = data.get("user_tz", "Europe/Moscow")

    async with get_session() as session:
        user = await session.get(User, user_id)
        if user:
            user.reminder_time = reminder_time_obj
            user.user_tz = user_tz
            user.updated_at = datetime.now(timezone.utc)
            await session.commit()

            # Register the cron job in the running ReminderScheduler.
            try:
                from bot.main import get_reminder_scheduler
                rs = get_reminder_scheduler()
                await rs.update_user_reminder(user)
            except Exception:
                pass  # scheduler may not be ready yet; jobs load on next restart

    await log_event(
        user_id=user_id,
        event_type="onboarding_done",
        detail=data.get("source", SOURCE_DIRECT),
    )

    time_str = f"{hour:02d}:{minute:02d}"
    await callback.message.answer(
        "✅ Всё готово.\n\n"
        f"🔔 Напоминание: {time_str}\n\n"
        "Меню внизу экрана поможет быстро перейти к дневнику, истории, "
        "пациентам или настройкам.",
        reply_markup=main_menu_keyboard(),
    )
    await state.clear()
    await callback.answer()
