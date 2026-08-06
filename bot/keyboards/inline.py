from typing import Iterable

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def has_diagnosis_keyboard(
    patient_name: str | None = None,
) -> InlineKeyboardMarkup:
    """Onboarding question: does the patient have a diagnosis?

    When *patient_name* is supplied the button text is personalised
    (e.g. "У Маши уже есть диагноз") — used for child patients.
    """
    if patient_name:
        yes_text = "Да, есть диагноз"
        no_text = "Нет, ещё не обращались к врачу"
    else:
        yes_text = "Да, у меня есть диагноз"
        no_text = "Нет, я ещё не был(а) у врача"

    buttons = [
        [InlineKeyboardButton(text=yes_text, callback_data="has_dx:yes")],
        [InlineKeyboardButton(text=no_text, callback_data="has_dx:no")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def nosology_keyboard() -> InlineKeyboardMarkup:
    """ENT conditions selection keyboard (for patients WITH diagnosis)."""
    buttons = [
        [InlineKeyboardButton(text="Острый риносинусит", callback_data="nosology:ars")],
        [InlineKeyboardButton(text="Хронический риносинусит", callback_data="nosology:crs")],
        [InlineKeyboardButton(text="Острый тонзиллофарингит", callback_data="nosology:tonsillopharyngitis")],
        [InlineKeyboardButton(text="Острый средний отит", callback_data="nosology:aom")],
        [InlineKeyboardButton(text="Хронический средний отит", callback_data="nosology:com")],
        [InlineKeyboardButton(text="Гипертрофия аденоидов", callback_data="nosology:adenoid_hypertrophy")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def complaint_area_keyboard() -> InlineKeyboardMarkup:
    """Complaint area selection (for patients WITHOUT diagnosis)."""
    buttons = [
        [InlineKeyboardButton(text="👃 Нос — заложенность, выделения", callback_data="complaint:nose")],
        [InlineKeyboardButton(text="🗣 Горло — боль, першение", callback_data="complaint:throat")],
        [InlineKeyboardButton(text="👂 Ухо — боль, снижение слуха", callback_data="complaint:ear")],
        [InlineKeyboardButton(text="📋 Несколько областей", callback_data="complaint:multiple")],
        [InlineKeyboardButton(text="🩺 Это не ЛОР-проблема", callback_data="complaint:non_ent")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def age_group_keyboard() -> InlineKeyboardMarkup:
    """Age group selection keyboard."""
    buttons = [
        [InlineKeyboardButton(text="< 6 месяцев", callback_data="age:<6mo")],
        [InlineKeyboardButton(text="6-23 месяца", callback_data="age:6-23mo")],
        [InlineKeyboardButton(text="2-5 лет", callback_data="age:2-5y")],
        [InlineKeyboardButton(text="6-14 лет", callback_data="age:6-14y")],
        [InlineKeyboardButton(text="15-44 года", callback_data="age:15-44y")],
        [InlineKeyboardButton(text="≥ 45 лет", callback_data="age:>=45y")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def severity_keyboard(
    param_id: str,
    *,
    is_pain: bool = False,
    show_cant_assess: bool = False,
) -> InlineKeyboardMarkup:
    """0-3 severity scale keyboard.

    Parameters
    ----------
    is_pain : bool
        When True the zero-value button reads "Не болит" instead of "Нет".
    show_cant_assess : bool
        When True an extra button "Сложно оценить из-за возраста ребенка"
        is appended (for children < 6 years).
    """
    zero_label = "Не болит" if is_pain else "Нет"
    buttons = [
        [InlineKeyboardButton(text=zero_label, callback_data=f"symptom:{param_id}:0")],
        [InlineKeyboardButton(text="Слабо", callback_data=f"symptom:{param_id}:1")],
        [InlineKeyboardButton(text="Умеренно", callback_data=f"symptom:{param_id}:2")],
        [InlineKeyboardButton(text="Сильно", callback_data=f"symptom:{param_id}:3")],
    ]
    if show_cant_assess:
        buttons.append([
            InlineKeyboardButton(
                text="Сложно оценить из-за возраста ребёнка",
                callback_data=f"symptom:{param_id}:-1",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def discharge_keyboard(param_id: str) -> InlineKeyboardMarkup:
    """Nasal/otologic discharge character keyboard."""
    buttons = [
        [InlineKeyboardButton(text="Нет", callback_data=f"symptom:{param_id}:0")],
        [InlineKeyboardButton(text="Прозрачные", callback_data=f"symptom:{param_id}:1")],
        [InlineKeyboardButton(text="Жёлтые", callback_data=f"symptom:{param_id}:2")],
        [InlineKeyboardButton(text="Зелёные/гнойные", callback_data=f"symptom:{param_id}:3")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def binary_keyboard(param_id: str) -> InlineKeyboardMarkup:
    """Yes/no binary keyboard."""
    buttons = [
        [InlineKeyboardButton(text="Нет", callback_data=f"symptom:{param_id}:0")],
        [InlineKeyboardButton(text="Да", callback_data=f"symptom:{param_id}:1")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def temp_keyboard(param_id: str) -> InlineKeyboardMarkup:
    """Temperature range keyboard."""
    buttons = [
        [InlineKeyboardButton(text="< 37.5°C", callback_data=f"symptom:{param_id}:0")],
        [InlineKeyboardButton(text="37.5-38°C", callback_data=f"symptom:{param_id}:1")],
        [InlineKeyboardButton(text="38-39°C", callback_data=f"symptom:{param_id}:2")],
        [InlineKeyboardButton(text="> 39°C", callback_data=f"symptom:{param_id}:3")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def vas_keyboard(param_id: str) -> InlineKeyboardMarkup:
    """VAS 0-10 pain scale keyboard."""
    buttons = [
        [
            InlineKeyboardButton(text="0", callback_data=f"symptom:{param_id}:0"),
            InlineKeyboardButton(text="1", callback_data=f"symptom:{param_id}:1"),
            InlineKeyboardButton(text="2", callback_data=f"symptom:{param_id}:2"),
            InlineKeyboardButton(text="3", callback_data=f"symptom:{param_id}:3"),
            InlineKeyboardButton(text="4", callback_data=f"symptom:{param_id}:4"),
        ],
        [
            InlineKeyboardButton(text="5", callback_data=f"symptom:{param_id}:5"),
            InlineKeyboardButton(text="6", callback_data=f"symptom:{param_id}:6"),
            InlineKeyboardButton(text="7", callback_data=f"symptom:{param_id}:7"),
            InlineKeyboardButton(text="8", callback_data=f"symptom:{param_id}:8"),
            InlineKeyboardButton(text="9", callback_data=f"symptom:{param_id}:9"),
        ],
        [InlineKeyboardButton(text="10", callback_data=f"symptom:{param_id}:10")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def yes_no_keyboard(flag_id: str) -> InlineKeyboardMarkup:
    """Red flag yes/no keyboard."""
    buttons = [
        [InlineKeyboardButton(text="Нет", callback_data=f"redflag:{flag_id}:0")],
        [InlineKeyboardButton(text="Да", callback_data=f"redflag:{flag_id}:1")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def timezone_keyboard() -> InlineKeyboardMarkup:
    """Russian timezone selection keyboard."""
    buttons = [
        [InlineKeyboardButton(text="МСК (Москва, СПб)", callback_data="tz:Europe/Moscow")],
        [InlineKeyboardButton(text="МСК+1 (Самара)", callback_data="tz:Europe/Samara")],
        [InlineKeyboardButton(text="МСК+2 (Екатеринбург)", callback_data="tz:Asia/Yekaterinburg")],
        [InlineKeyboardButton(text="МСК+3 (Омск)", callback_data="tz:Asia/Omsk")],
        [InlineKeyboardButton(text="МСК+4 (Красноярск)", callback_data="tz:Asia/Krasnoyarsk")],
        [InlineKeyboardButton(text="МСК+5 (Иркутск)", callback_data="tz:Asia/Irkutsk")],
        [InlineKeyboardButton(text="МСК+6 (Якутск)", callback_data="tz:Asia/Yakutsk")],
        [InlineKeyboardButton(text="МСК+7 (Владивосток)", callback_data="tz:Asia/Vladivostok")],
        [InlineKeyboardButton(text="МСК+9 (Камчатка)", callback_data="tz:Asia/Kamchatka")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def episode_frequency_keyboard(param_id: str) -> InlineKeyboardMarkup:
    """Episode count keyboard (e.g. otitis/sinusitis frequency)."""
    buttons = [
        [InlineKeyboardButton(text="Ни разу", callback_data=f"symptom:{param_id}:0")],
        [InlineKeyboardButton(text="1–2 раза", callback_data=f"symptom:{param_id}:1")],
        [InlineKeyboardButton(text="3–4 раза", callback_data=f"symptom:{param_id}:2")],
        [InlineKeyboardButton(text="5 и более", callback_data=f"symptom:{param_id}:3")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def duration_keyboard(param_id: str) -> InlineKeyboardMarkup:
    """Symptom duration in days keyboard."""
    buttons = [
        [InlineKeyboardButton(text="1–2 дня", callback_data=f"symptom:{param_id}:0")],
        [InlineKeyboardButton(text="3–5 дней", callback_data=f"symptom:{param_id}:1")],
        [InlineKeyboardButton(text="5–10 дней", callback_data=f"symptom:{param_id}:2")],
        [InlineKeyboardButton(text="Более 10 дней", callback_data=f"symptom:{param_id}:3")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def ome_duration_keyboard(param_id: str) -> InlineKeyboardMarkup:
    """Effusion / OME duration keyboard (COM.effusion_duration).

    Buckets 0..3 — mapped to days (15 / 60 / 120 / 240) via value_map in
    bot/triage/params.py so the rule's ≥84-day threshold fires correctly.
    """
    buttons = [
        [InlineKeyboardButton(text="Менее 1 месяца", callback_data=f"symptom:{param_id}:0")],
        [InlineKeyboardButton(text="1–3 месяца", callback_data=f"symptom:{param_id}:1")],
        [InlineKeyboardButton(text="3–6 месяцев", callback_data=f"symptom:{param_id}:2")],
        [InlineKeyboardButton(text="Более 6 месяцев", callback_data=f"symptom:{param_id}:3")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def antipyretic_response_keyboard(param_id: str) -> InlineKeyboardMarkup:
    """How well does the antipyretic work? (patient-friendly language)."""
    buttons = [
        [InlineKeyboardButton(
            text="Хорошо снижает, хватает надолго",
            callback_data=f"symptom:{param_id}:0",
        )],
        [InlineKeyboardButton(
            text="Снижает, но ненадолго",
            callback_data=f"symptom:{param_id}:1",
        )],
        [InlineKeyboardButton(
            text="Почти не снижает",
            callback_data=f"symptom:{param_id}:2",
        )],
        [InlineKeyboardButton(
            text="Не принимал(а)",
            callback_data=f"symptom:{param_id}:3",
        )],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def analgesic_response_keyboard(param_id: str) -> InlineKeyboardMarkup:
    """How well does the analgesic (painkiller) work?"""
    buttons = [
        [InlineKeyboardButton(
            text="Хорошо помогает, хватает надолго",
            callback_data=f"symptom:{param_id}:0",
        )],
        [InlineKeyboardButton(
            text="Помогает, но ненадолго",
            callback_data=f"symptom:{param_id}:1",
        )],
        [InlineKeyboardButton(
            text="Почти не помогает",
            callback_data=f"symptom:{param_id}:2",
        )],
        [InlineKeyboardButton(
            text="Не принимал(а)",
            callback_data=f"symptom:{param_id}:3",
        )],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def fever_duration_keyboard(param_id: str) -> InlineKeyboardMarkup:
    """How many days has the fever (≥38°C) lasted?"""
    buttons = [
        [InlineKeyboardButton(
            text="1–2 дня",
            callback_data=f"symptom:{param_id}:0",
        )],
        [InlineKeyboardButton(
            text="3–4 дня",
            callback_data=f"symptom:{param_id}:1",
        )],
        [InlineKeyboardButton(
            text="5–7 дней",
            callback_data=f"symptom:{param_id}:2",
        )],
        [InlineKeyboardButton(
            text="Более 7 дней",
            callback_data=f"symptom:{param_id}:3",
        )],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def last_doctor_visit_keyboard() -> InlineKeyboardMarkup:
    """When did the patient last see a doctor for this condition?"""
    buttons = [
        [InlineKeyboardButton(text="Менее недели назад", callback_data="tx_visit:0")],
        [InlineKeyboardButton(text="1–2 недели назад", callback_data="tx_visit:1")],
        [InlineKeyboardButton(text="2–4 недели назад", callback_data="tx_visit:2")],
        [InlineKeyboardButton(text="Более месяца назад", callback_data="tx_visit:3")],
        [InlineKeyboardButton(text="Не обращался с этим", callback_data="tx_visit:4")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def treatment_status_keyboard() -> InlineKeyboardMarkup:
    """Is the patient currently receiving treatment?"""
    buttons = [
        [InlineKeyboardButton(text="Да, назначено врачом", callback_data="tx_status:prescribed")],
        [InlineKeyboardButton(text="Да, лечусь сам(а)", callback_data="tx_status:self")],
        [InlineKeyboardButton(text="Нет", callback_data="tx_status:none")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def reminder_time_keyboard() -> InlineKeyboardMarkup:
    """Daily reminder time selection keyboard."""
    buttons = [
        [InlineKeyboardButton(text="08:00", callback_data="reminder:08:00")],
        [InlineKeyboardButton(text="09:00", callback_data="reminder:09:00")],
        [InlineKeyboardButton(text="12:00", callback_data="reminder:12:00")],
        [InlineKeyboardButton(text="18:00", callback_data="reminder:18:00")],
        [InlineKeyboardButton(text="20:00", callback_data="reminder:20:00")],
        [InlineKeyboardButton(text="21:00", callback_data="reminder:21:00")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def report_period_keyboard() -> InlineKeyboardMarkup:
    """Report period selection keyboard."""
    buttons = [
        [InlineKeyboardButton(text="7 дней", callback_data="report:7")],
        [InlineKeyboardButton(text="14 дней", callback_data="report:14")],
        [InlineKeyboardButton(text="30 дней", callback_data="report:30")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def start_log_keyboard() -> InlineKeyboardMarkup:
    """Quick start logging keyboard."""
    buttons = [
        [InlineKeyboardButton(text="Заполнить дневник", callback_data="start_log")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def start_log_or_later_keyboard() -> InlineKeyboardMarkup:
    """Offer the user to fill the diary, change condition, or postpone.

    Used after adding a new patient or switching the active patient —
    both actions imply the user is about to start logging for that
    profile, so we surface the diary and a quick path to change the
    condition without forcing them to dig through the menu.
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="📝 Заполнить дневник сейчас",
                callback_data="start_log",
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 Изменить жалобу/диагноз",
                callback_data="change_cond_active",
            )
        ],
        [
            InlineKeyboardButton(
                text="Позже",
                callback_data="log_later",
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def switch_active_confirm_keyboard(target_patient_id: int) -> InlineKeyboardMarkup:
    """Confirm switching the active profile to a specific target patient.

    Shown when:
      - a new patient was added and another one is already active;
      - the condition of a non-active patient was updated.

    Callback format:
      'switch_active:yes:{target_patient_id}' — switch, then offer diary
      'switch_active:no'                      — keep current active,
                                                still offer diary/menu
                                                for the unchanged active
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="🔀 Да, переключить",
                callback_data=f"switch_active:yes:{target_patient_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="Остаться на текущем",
                callback_data="switch_active:no",
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ──────────────────────────────────────────────────────────────────────
# New onboarding / patient-management keyboards
# ──────────────────────────────────────────────────────────────────────


def for_whom_keyboard() -> InlineKeyboardMarkup:
    """Onboarding: who is the user going to track?"""
    buttons = [
        [InlineKeyboardButton(text="👤 О себе", callback_data="for_whom:self")],
        [InlineKeyboardButton(text="🧒 О ребёнке", callback_data="for_whom:child")],
        [
            InlineKeyboardButton(
                text="👥 О себе и ребёнке",
                callback_data="for_whom:both",
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sex_keyboard(prefix: str = "sex", allow_skip: bool = False) -> InlineKeyboardMarkup:
    """Sex selection keyboard. `prefix` controls callback_data namespace."""
    rows = [
        [
            InlineKeyboardButton(text="👦 Мальчик / мужской", callback_data=f"{prefix}:m"),
            InlineKeyboardButton(text="👧 Девочка / женский", callback_data=f"{prefix}:f"),
        ],
    ]
    if allow_skip:
        rows.append(
            [InlineKeyboardButton(text="Пропустить", callback_data=f"{prefix}:skip")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def add_another_child_keyboard() -> InlineKeyboardMarkup:
    """After a child is added: add another or finish?"""
    buttons = [
        [InlineKeyboardButton(text="➕ Добавить ещё ребёнка", callback_data="add_child:yes")],
        [InlineKeyboardButton(text="✅ Закончить", callback_data="add_child:no")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def age_confirm_keyboard() -> InlineKeyboardMarkup:
    """Confirm entered age."""
    buttons = [
        [InlineKeyboardButton(text="✅ Всё верно", callback_data="age_confirm:yes")],
        [InlineKeyboardButton(text="↺ Ввести заново", callback_data="age_confirm:no")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def legacy_resolution_keyboard() -> InlineKeyboardMarkup:
    """First-login prompt for legacy users: was the old data about you or a child?"""
    buttons = [
        [
            InlineKeyboardButton(
                text="👤 Данные были про меня",
                callback_data="legacy_resolve:self",
            )
        ],
        [
            InlineKeyboardButton(
                text="🧒 Данные были про ребёнка",
                callback_data="legacy_resolve:child",
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def patient_select_keyboard(
    patients: Iterable,
    action: str = "select",
) -> InlineKeyboardMarkup:
    """
    Build a list of patients as buttons.

    `action` is inserted into callback_data: 'patient:{action}:{patient_id}'.
    Common actions:
      - 'select'     — choose active patient for /log
      - 'change_cnd' — change condition for patient
      - 'archive'    — archive patient
    """
    buttons = []
    for p in patients:
        # Support both ORM objects and dicts
        pid = getattr(p, "id", None) if not isinstance(p, dict) else p.get("id")
        name = (
            getattr(p, "display_name", None)
            if not isinstance(p, dict)
            else p.get("display_name")
        )
        relation = (
            getattr(p, "relation", "self")
            if not isinstance(p, dict)
            else p.get("relation", "self")
        )
        icon = "👤" if relation == "self" else "🧒"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{icon} {name}",
                    callback_data=f"patient:{action}:{pid}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def patients_menu_keyboard() -> InlineKeyboardMarkup:
    """Top-level /patients menu."""
    buttons = [
        [
            InlineKeyboardButton(
                text="➕ Добавить пациента",
                callback_data="patients:add",
            )
        ],
        [
            InlineKeyboardButton(
                text="🔀 Сменить активного",
                callback_data="patients:switch",
            )
        ],
        [
            InlineKeyboardButton(
                text="📝 Изменить жалобу/диагноз",
                callback_data="patients:change_cond",
            )
        ],
        [
            InlineKeyboardButton(
                text="✅ Завершить случай",
                callback_data="patients:close_case",
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
