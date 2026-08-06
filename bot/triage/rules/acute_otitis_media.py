"""
Acute Otitis Media (AOM) triage rules.

Evidence base: AAP/AAO-HNS CPG (Lieberthal AS et al. 2013)
Focuses on age-stratified management and watchful waiting criteria.
"""

LEVEL_GREEN = "green"
LEVEL_YELLOW = "yellow"
LEVEL_RED = "red"


def run_triage(
    symptoms: dict,
    composite_score: int,
    symptom_duration: int,
    trend: str,
    previous_entries: list,
) -> dict:
    """
    Run acute otitis media-specific triage logic.

    Parameters expected in symptoms:
    - aom_ear_pain: 0–3
    - aom_hearing: 0–3
    - aom_discharge: 0=none, 1=serous, 2=mucoid, 3=purulent
    - aom_temp: 0=<37.5, 1=37.5–38, 2=38–39, 3=>39
    - aom_bilateral: 0=no, 1=yes
    - aom_malaise: 0–3
    - aom_age: age_group string ("<6mo", "6-23mo", "2-5y", "6-14y", "15-44y", ">=45y")
    - postauricular_swelling: 0=no, 1=yes (mastoiditis screening)
    - protruding_pinna: 0=no, 1=yes (mastoiditis screening)

    Args:
        symptoms: dict of parameter_id -> value
        composite_score: sum of all parameters
        symptom_duration: hours or days since onset
        trend: 'improving', 'stable', 'worsening', etc.
        previous_entries: list of prior SymptomEntry

    Returns:
        dict with keys:
        - triage_level: 'green', 'yellow', or 'red'
        - triage_message: user-facing Russian text
    """

    aom_ear_pain = symptoms.get("aom_ear_pain", 0)
    aom_hearing = symptoms.get("aom_hearing", 0)
    aom_discharge = symptoms.get("aom_discharge", 0)
    aom_temp = symptoms.get("aom_temp", 0)
    aom_bilateral = symptoms.get("aom_bilateral", 0)
    aom_age = symptoms.get("aom_age", "15-44y")

    postauricular_swelling = symptoms.get("postauricular_swelling", 0)
    protruding_pinna = symptoms.get("protruding_pinna", 0)

    # --- Mastoiditis Screening ---
    if postauricular_swelling == 1 and protruding_pinna == 1:
        return {
            "triage_level": LEVEL_RED,
            "triage_message": "Признаки мастоидита (отек за ухом, выпячивание раковины). Требуется срочное обследование.",
        }

    # --- Age-Based Severity Assessment ---

    # Infant <6 months with fever (high risk)
    if aom_age == "<6mo" and aom_temp >= 1:
        return {
            "triage_level": LEVEL_RED,
            "triage_message": "Ребенок <6 месяцев с лихорадкой и симптомами отита. Требуется немедленное обследование.",
        }

    # Infant 6–23 months with bilateral AOM
    if aom_age == "6-23mo" and aom_bilateral == 1:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Двусторонний отит у ребенка 6–23 месяцев (AAP). Медицинское обследование рекомендуется.",
        }

    # --- Severity Scoring ---
    # NOTE: Severe checks MUST come before moderate checks (bug fix v2).
    # NOTE: temp == 3 (>39C) is no longer auto-RED here -- the engine
    #       handles it as a soft alarm with contextual evaluation.

    # Severe pain (=3) → YELLOW (urgent visit, not RED since no
    # complication sign per se; the engine will escalate to RED
    # if combined with soft alarms like high_fever).
    if aom_ear_pain == 3:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Сильная боль в ухе. Рекомендуем обратиться к ЛОР-врачу сегодня.",
        }

    # Purulent otorrhea (severe)
    if aom_discharge == 3:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Гнойное отделяемое из уха. Запишитесь к врачу в течение 24 часов.",
        }

    # Moderate-severe pain + fever
    if aom_ear_pain >= 2 and aom_temp >= 2:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Умеренно-сильная боль в ухе с лихорадкой. Рекомендуем обратиться к врачу.",
        }

    # --- Duration-Based Safety Net ---
    # symptom_duration приходит в днях, а порог AAP это 48 часов.
    # Раньше здесь стояло 48, то есть правило ждало 48 дней и при
    # остром отите не срабатывало никогда.
    #
    # Проверка стоит перед наблюдательной тактикой намеренно: сама
    # тактика и звучит как «наблюдаем 48–72 часа, дальше к врачу»,
    # а в прежнем порядке лёгкий односторонний отит оставался зелёным
    # хоть на десятый день.
    if symptom_duration > 2 and trend != "improving":
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Отсутствие улучшения после 48 часов. Переоценка и консультация врача рекомендуются (AAP).",
        }

    # --- Watchful Waiting Criteria (AAP 2013) ---
    # Age ≥2y + unilateral + mild pain + no otorrhea + no fever
    if (aom_age in ["2-5y", "6-14y", "15-44y", ">=45y"] and
        aom_bilateral == 0 and
        aom_ear_pain <= 1 and
        aom_temp <= 1 and
        aom_discharge == 0):
        return {
            "triage_level": LEVEL_GREEN,
            "triage_message": "Легкие односторонние симптомы, возраст ≥2 лет. Наблюдение допустимо (AAP). Если нет улучшения через 48-72 часа, запишитесь к врачу.",
        }

    # --- Moderate pain or temp without discharge ---
    if aom_ear_pain >= 1 or aom_temp >= 1:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Боль в ухе или лихорадка. Рекомендую наблюдение в течение 48–72 часов с готовностью к визиту при отсутствии улучшения.",
        }

    return {
        "triage_level": LEVEL_GREEN,
        "triage_message": "Минимальные симптомы. Продолжайте наблюдение.",
    }
