"""
Universal red flags module.

"Hard" red flags trigger RED immediately regardless of context.
"Soft" alarms (high_fever, rapid_deterioration) are returned separately
so the engine can apply contextual logic (e.g. short-duration ARVI with
responding-to-antipyretics fever should not auto-escalate).

Architecture change (v2, April 2026):
- High fever (temp >= 3 / >39C) is NO LONGER an automatic RED flag.
  It is returned as a *soft alarm* for the engine to evaluate in context
  (combined with antipyretic response, fever duration, other alarms).
- rapid_deterioration is also a soft alarm -- the engine applies a
  contextual filter (duration < 5d, composite < 10, temp < 3 -> YELLOW).
"""

from typing import Optional

# -- Hard red flag IDs -- always trigger RED ----------------------------
RF_PERIORBITAL_EDEMA = "periorbital_edema"
RF_VISUAL_DISTURBANCE = "visual_disturbance"
RF_MENINGEAL_SIGNS = "meningeal_signs"
RF_ALTERED_CONSCIOUSNESS = "altered_consciousness"
RF_MASTOIDITIS = "mastoiditis"
RF_FACIAL_NERVE_PALSY = "facial_nerve_palsy"
RF_DYSPHAGIA_SEVERE = "dysphagia_severe"
RF_TRISMUS = "trismus"
RF_STRIDOR = "stridor"

# -- Soft alarm IDs -- contextual, handled by engine --------------------
RF_HIGH_FEVER = "high_fever"
RF_RAPID_DETERIORATION = "rapid_deterioration"

# Convenience sets for callers that need to distinguish.
HARD_RED_FLAGS = frozenset({
    RF_PERIORBITAL_EDEMA,
    RF_VISUAL_DISTURBANCE,
    RF_MENINGEAL_SIGNS,
    RF_ALTERED_CONSCIOUSNESS,
    RF_MASTOIDITIS,
    RF_FACIAL_NERVE_PALSY,
    RF_DYSPHAGIA_SEVERE,
    RF_TRISMUS,
    RF_STRIDOR,
})

SOFT_ALARMS = frozenset({
    RF_HIGH_FEVER,
    RF_RAPID_DETERIORATION,
})


def check_universal_red_flags(symptoms: dict) -> tuple[list[str], list[str]]:
    """
    Check for universal red flags and soft alarms.

    Returns:
        (hard_flags, soft_alarms)
        hard_flags:  list of triggered hard red flag IDs -> always RED
        soft_alarms: list of triggered soft alarm IDs -> engine decides
    """
    hard_flags: list[str] = []
    soft_alarms_list: list[str] = []

    # 1. High fever (>39C -> temp param = 3) -- NOW A SOFT ALARM
    temp_params = [
        "ars_temp", "crs_temp", "tp_temp", "aom_temp",
        "com_temp", "ah_temp", "temp",
        "un_nose_temp", "un_throat_temp", "un_ear_temp",
        "un_multi_temp", "ne_temp",
    ]
    for temp_param in temp_params:
        if temp_param in symptoms and symptoms[temp_param] >= 3:
            soft_alarms_list.append(RF_HIGH_FEVER)
            break

    # 2. Periorbital edema/erythema -- HARD
    if symptoms.get("periorbital_edema") == 1:
        hard_flags.append(RF_PERIORBITAL_EDEMA)

    # 3. Visual disturbance -- HARD
    if symptoms.get("visual_disturbance") == 1:
        hard_flags.append(RF_VISUAL_DISTURBANCE)

    # 4. Meningeal signs (severe headache + neck stiffness) -- HARD
    neck_stiffness = symptoms.get("neck_stiffness", 0)
    severe_headache = symptoms.get("severe_headache", 0)
    if neck_stiffness == 1 and severe_headache >= 2:
        hard_flags.append(RF_MENINGEAL_SIGNS)

    # 5. Altered consciousness / confusion -- HARD
    if symptoms.get("altered_consciousness") == 1:
        hard_flags.append(RF_ALTERED_CONSCIOUSNESS)

    # 6. Mastoiditis signs (postauricular swelling + protruding pinna) -- HARD
    postauricular_swelling = symptoms.get("postauricular_swelling", 0)
    protruding_pinna = symptoms.get("protruding_pinna", 0)
    if postauricular_swelling == 1 and protruding_pinna == 1:
        hard_flags.append(RF_MASTOIDITIS)

    # 7. Facial nerve palsy -- HARD
    if symptoms.get("facial_nerve_palsy") == 1:
        hard_flags.append(RF_FACIAL_NERVE_PALSY)

    # 8. Severe dysphagia (inability to swallow) -- HARD
    dysphagia_params = ["tp_dysphagia", "aom_dysphagia", "dysphagia"]
    for dysp_param in dysphagia_params:
        if dysp_param in symptoms and symptoms[dysp_param] == 3:
            hard_flags.append(RF_DYSPHAGIA_SEVERE)
            break

    # 9. Trismus -- HARD
    if symptoms.get("trismus") == 1:
        hard_flags.append(RF_TRISMUS)

    # 10. Stridor / respiratory difficulty -- HARD
    if symptoms.get("stridor") == 1:
        hard_flags.append(RF_STRIDOR)

    # 11. Rapid deterioration over <24 hours -- SOFT ALARM
    if symptoms.get("rapid_deterioration") == 1:
        soft_alarms_list.append(RF_RAPID_DETERIORATION)

    return list(set(hard_flags)), list(set(soft_alarms_list))


def get_red_flag_message(red_flag_id: str) -> str:
    """
    Get user-facing message for a red flag.

    Args:
        red_flag_id: one of the RF_* constants

    Returns:
        Russian-language explanation
    """
    messages = {
        RF_HIGH_FEVER: "Высокая температура (>39\u00b0C) требует внимания врача.",
        RF_PERIORBITAL_EDEMA: "Отек века \u2014 возможное осложнение синусита (орбитальный абсцесс). Срочно к врачу.",
        RF_VISUAL_DISTURBANCE: "Нарушение зрения требует немедленного обследования.",
        RF_MENINGEAL_SIGNS: "Сильная головная боль с жесткостью шеи \u2014 симптомы менингита. Вызовите скорую помощь.",
        RF_ALTERED_CONSCIOUSNESS: "Спутанность сознания указывает на серьезное осложнение. Вызовите скорую помощь.",
        RF_MASTOIDITIS: "Отек за ухом с выпячиванием ушной раковины \u2014 признаки мастоидита. Срочно к врачу.",
        RF_FACIAL_NERVE_PALSY: "Асимметрия лица \u2014 возможный паралич лицевого нерва. Требуется срочное обследование.",
        RF_DYSPHAGIA_SEVERE: "Невозможность глотать \u2014 признак абсцесса или инфекции глубоких пространств шеи. Срочно к врачу.",
        RF_TRISMUS: "Невозможность открыть рот полностью \u2014 риск абсцесса. Срочно к врачу.",
        RF_STRIDOR: "Затруднение дыхания со свистящими звуками требует неотложной помощи.",
        RF_RAPID_DETERIORATION: "Быстрое ухудшение состояния за <24 часа требует обращения к врачу.",
    }
    return messages.get(red_flag_id, "Unknown red flag")
