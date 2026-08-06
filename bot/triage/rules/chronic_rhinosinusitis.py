"""
Chronic Rhinosinusitis (CRS) triage rules.

Evidence base: EPOS 2020 (Fokkens WJ et al.)
CRS defined as symptoms ≥12 weeks.
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
    Run CRS-specific triage logic.

    Parameters expected in symptoms:
    - crs_obstruction: 0–3
    - crs_discharge: 0–3
    - crs_facial_pain: 0–3
    - crs_smell: 0–3
    - crs_sleep: 0–3
    - crs_vas: 0–10 (Visual Analog Scale for overall severity)
    - crs_temp: 0–3 (if present)

    Args:
        symptoms: dict of parameter_id -> value
        composite_score: sum of symptom scores (not used for VAS-based rules)
        symptom_duration: days since onset (CRS = ≥84 days by definition)
        trend: 'improving', 'stable', 'worsening', 'worsening_3d', or 'insufficient_data'
        previous_entries: list of prior SymptomEntry

    Returns:
        dict with keys:
        - triage_level: 'green', 'yellow', or 'red'
        - triage_message: user-facing Russian text
    """

    # VAS (Visual Analog Scale): key decision criterion per EPOS 2020
    # VAS ≤3 = controlled, VAS >3.5 = uncontrolled
    crs_vas = symptoms.get("crs_vas", 0)
    crs_temp = symptoms.get("crs_temp", 0)
    crs_discharge = symptoms.get("crs_discharge", 0)
    crs_smell = symptoms.get("crs_smell", 0)

    # --- Decision Logic ---

    # Acute exacerbation on chronic background
    # (VAS >5 + worsening trend + fever or purulent discharge)
    if crs_vas > 5 and trend == "worsening_3d":
        if crs_temp >= 2 or crs_discharge == 3:
            return {
                "triage_level": LEVEL_YELLOW,
                "triage_message": "Острое обострение хронического синусита. Запишитесь к врачу в ближайшие 1–2 дня.",
            }
        else:
            return {
                "triage_level": LEVEL_YELLOW,
                "triage_message": "Симптомы усиливаются. Рекомендую консультацию врача.",
            }

    # Controlled disease (VAS ≤3, stable trend)
    if crs_vas <= 3 and trend == "stable":
        return {
            "triage_level": LEVEL_GREEN,
            "triage_message": "Заболевание хорошо контролируется. Продолжайте текущую терапию (EPOS критерии).",
        }

    # Uncontrolled but stable disease (VAS >3.5, no acute change)
    if crs_vas > 3.5 and trend == "stable":
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Заболевание не контролируется (EPOS критерии). Обсудите корректировку терапии при следующем визите.",
        }

    # Improving trend (regardless of VAS)
    if trend == "improving":
        return {
            "triage_level": LEVEL_GREEN,
            "triage_message": "Симптомы улучшаются. Продолжайте текущее лечение.",
        }

    # New-onset complete anosmia
    if crs_smell == 3:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Новое полное отсутствие обоняния. Запишитесь к врачу для обследования.",
        }

    # Unilateral symptoms with blood (red flag for other pathology)
    if symptoms.get("unilateral_symptoms") == 1 and symptoms.get("bloody_discharge") == 1:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Односторонние симптомы с кровянистым отделяемым. Исключите другую патологию — запишитесь к врачу.",
        }

    # Worsening trend (any VAS)
    if trend == "worsening":
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Симптомы усиливаются. Рекомендую консультацию ЛОР-врача.",
        }

    # Default: if VAS uncontrolled
    if crs_vas > 3.5:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Заболевание не контролируется. Обратитесь к врачу для коррекции лечения.",
        }

    return {
        "triage_level": LEVEL_GREEN,
        "triage_message": "Симптомы управляемы. Продолжайте вести дневник наблюдения.",
    }
