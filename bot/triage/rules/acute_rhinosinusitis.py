"""
Acute Rhinosinusitis (ARS) triage rules.

Evidence base: AAO-HNS CPG (Rosenfeld RM et al. 2015), EPOS 2020 (Fokkens WJ et al.)
"""

from typing import Optional

LEVEL_GREEN = "green"
LEVEL_YELLOW = "yellow"
LEVEL_RED = "red"


def detect_double_sickening(previous_entries: list, nosology: str = "ars") -> bool:
    """
    Detect "double sickening" pattern (improvement then worsening).

    Pattern: high score → low score → rising again
    Indicates secondary bacterial infection (AAO-HNS 2015).

    Args:
        previous_entries: list of SymptomEntry sorted by recorded_at (most recent first)
        nosology: for validation (should be 'ars')

    Returns:
        True if pattern detected, False otherwise
    """
    if len(previous_entries) < 3:
        return False

    # Reverse to chronological order
    entries = list(reversed(previous_entries))
    scores = [e.composite_score for e in entries]

    # Look for valley: high → low → high
    for i in range(len(scores) - 2):
        if scores[i] > scores[i + 1] < scores[i + 2]:
            # Found valley at i+1
            # Check if post-valley scores are increasing
            valley_idx = i + 1
            post_valley_scores = scores[valley_idx:]
            if len(post_valley_scores) >= 2:
                if all(post_valley_scores[j] <= post_valley_scores[j + 1] for j in range(len(post_valley_scores) - 1)):
                    return True
    return False


def run_triage(
    symptoms: dict,
    composite_score: int,
    symptom_duration: int,
    trend: str,
    previous_entries: list,
) -> dict:
    """
    Run ARS-specific triage logic.

    Parameters expected in symptoms:
    - ars_obstruction: 0–3
    - ars_facial_pain: 0–3
    - ars_discharge: 0=none, 1=clear, 2=yellow, 3=green/purulent
    - ars_smell: 0–3
    - ars_temp: 0=<37.5, 1=37.5–38, 2=38–39, 3=>39
    - ars_headache: 0–3
    - ars_malaise: 0–3

    Args:
        symptoms: dict of parameter_id -> value
        composite_score: sum of all parameters (0–21)
        symptom_duration: days since first symptom
        trend: 'improving', 'stable', 'worsening', 'worsening_3d', or 'insufficient_data'
        previous_entries: list of prior SymptomEntry for double sickening detection

    Returns:
        dict with keys:
        - triage_level: 'green', 'yellow', or 'red'
        - triage_message: user-facing Russian text
    """

    ars_temp = symptoms.get("ars_temp", 0)
    ars_facial_pain = symptoms.get("ars_facial_pain", 0)
    ars_discharge = symptoms.get("ars_discharge", 0)
    ars_headache = symptoms.get("ars_headache", 0)

    # Check for double sickening (worsening after initial improvement)
    double_sickening = detect_double_sickening(previous_entries)

    # --- Decision Logic ---

    # Criterion 1: Duration < 10 days (early acute phase)
    if symptom_duration < 10:
        # Double sickening MUST be checked before generic worsening —
        # it is a specific EPOS 2020 criterion for bacterial ARS and
        # carries a distinct clinical message.
        if double_sickening:
            return {
                "triage_level": LEVEL_YELLOW,
                "triage_message": "Вторичное ухудшение после улучшения — признак бактериальной инфекции (EPOS 2020). Запишитесь к врачу.",
            }

        if trend == "improving" and composite_score <= 7:
            return {
                "triage_level": LEVEL_GREEN,
                "triage_message": "Признаки острого вирусного респираторного инфекта. Продолжайте мониторинг, наблюдайте за развитием.",
            }

        if trend == "stable" and composite_score <= 10:
            return {
                "triage_level": LEVEL_GREEN,
                "triage_message": "Симптомы стабильны. Следите за их развитием. Если улучшения не будет к дню 10 — запишитесь к врачу.",
            }

        if trend == "worsening" or composite_score > 10:
            return {
                "triage_level": LEVEL_YELLOW,
                "triage_message": "Симптомы ухудшаются. Рекомендую записаться к ЛОР-врачу в ближайшие 2–3 дня.",
            }

    # Criterion 2: Duration >= 10 days (meets ABRS criterion)
    if symptom_duration >= 10:
        if trend == "improving":
            return {
                "triage_level": LEVEL_GREEN,
                "triage_message": "Симптомы длятся более 10 дней, но улучшаются. Продолжайте текущее лечение.",
            }

        if trend == "stable" or trend == "worsening":
            return {
                "triage_level": LEVEL_YELLOW,
                "triage_message": "Симптомы продолжаются более 10 дней без улучшения — показано обследование у ЛОР-врача (AAO-HNS).",
            }

    # Criterion 3: Fever + facial pain + purulent discharge
    # NOTE: temp==3 no longer auto-RED here -- the engine evaluates
    # high_fever as a soft alarm with contextual logic.
    if ars_temp >= 2 and ars_facial_pain >= 2 and ars_discharge == 3:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Лихорадка, лицевая боль и гнойное отделяемое требуют консультации врача в ближайшие 1\u20132 дня.",
        }

    # Criterion 4: Fever + severe facial pain/headache
    if ars_temp >= 2 and (ars_facial_pain >= 2 or ars_headache == 3):
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Лихорадка с выраженной головной или лицевой болью. Рекомендуем обратиться к ЛОР-врачу.",
        }

    # Default fallback
    if composite_score > 10:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Выраженные симптомы. Рекомендую консультацию ЛОР-врача в ближайшие дни.",
        }

    return {
        "triage_level": LEVEL_GREEN,
        "triage_message": "Симптомы легкие или умеренные. Продолжайте ведение дневника и мониторинг.",
    }
