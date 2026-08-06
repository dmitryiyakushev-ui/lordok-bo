"""
Acute Tonsillopharyngitis triage rules.

Evidence base:
  - Centor RM et al. (1981): original 4-item score.
  - McIsaac WJ et al. (1998): age-modified Centor.
  - Little P et al. (2013, Lancet): FeverPAIN derivation / validation.
  - Bakhit M et al. (2024, BJGP): head-to-head comparison; AUC ≈ 0.62
    for both — neither is highly discriminatory, but useful for
    stratifying management.
  - IDSA GAS Pharyngitis (Shulman ST et al. 2012): management algorithm.
  - Guntinas-Lichius O et al. (2023): tonsillectomy criteria.

v2 (April 2026): Centor + FeverPAIN dual scoring integrated.
The existing McIsaac calculation is preserved and extended.
FeverPAIN is computed in parallel for adults; both scores are
returned in the triage message for clinical transparency.
"""

from bot.services.scales import (
    build_centor_input,
    build_feverpain_input,
    centor_score,
    centor_action,
    centor_message_ru,
    feverpain_score,
    feverpain_action,
    feverpain_message_ru,
)

LEVEL_GREEN = "green"
LEVEL_YELLOW = "yellow"
LEVEL_RED = "red"


def calculate_mcisaac_score(
    tp_temp: int,
    tp_exudate: int,
    tp_lymph: int,
    tp_cough: int,
    age_group: str,
) -> int:
    """
    Calculate McIsaac score for streptococcal pharyngitis probability.

    Kept for backward compatibility. Internally delegates to scales.py.
    """
    from bot.services.scales import CentorInput
    inp = CentorInput(
        fever_over_38=tp_temp >= 2,
        no_cough=tp_cough == 0,
        tender_anterior_lymph=tp_lymph == 1,
        tonsillar_exudate=tp_exudate == 1,
        age_group=age_group,
    )
    return centor_score(inp)


def run_triage(
    symptoms: dict,
    composite_score: int,
    symptom_duration: int,
    trend: str,
    previous_entries: list,
) -> dict:
    """
    Run acute tonsillopharyngitis-specific triage logic with
    integrated Centor and FeverPAIN scoring.

    Parameters expected in symptoms:
    - tp_throat_pain: 0–3
    - tp_dysphagia: 0–3
    - tp_temp: 0=no, 1=<38, 2=38–39, 3=>39
    - tp_exudate: 0=no, 1=yes
    - tp_lymph: 0=no, 1=yes
    - tp_cough: 0=no, 1=yes
    - tp_age: age_group string (for McIsaac modifier)
    - trismus: 0=no, 1=yes (for peritonsillar abscess screening)
    - uvular_deviation: 0=no, 1=yes
    - drooling: 0=no, 1=yes
    - neck_swelling: 0=no, 1=yes

    Returns:
        dict with keys:
        - triage_level: 'green', 'yellow', or 'red'
        - triage_message: user-facing Russian text
        - centor_score: int (for persistence in ScaleScore)
        - centor_action: str
        - feverpain_score: int | None (None if child — FeverPAIN not validated <15y)
        - feverpain_action: str | None
    """
    tp_dysphagia = symptoms.get("tp_dysphagia", 0)
    tp_temp = symptoms.get("tp_temp", 0)
    tp_exudate = symptoms.get("tp_exudate", 0)
    tp_lymph = symptoms.get("tp_lymph", 0)
    tp_cough = symptoms.get("tp_cough", 0)
    tp_age = symptoms.get("tp_age", "15-44y")

    trismus = symptoms.get("trismus", 0)
    uvular_deviation = symptoms.get("uvular_deviation", 0)
    drooling = symptoms.get("drooling", 0)
    neck_swelling = symptoms.get("neck_swelling", 0)

    # --- Peritonsillar Abscess Screening (always check first) ---
    if tp_dysphagia == 3 and (trismus == 1 or uvular_deviation == 1 or drooling == 1):
        return {
            "triage_level": LEVEL_RED,
            "triage_message": (
                "Признаки перитонзиллярного абсцесса "
                "(невозможность глотать, тризм). "
                "Требуется срочное обследование."
            ),
            "centor_score": None,
            "centor_action": None,
            "feverpain_score": None,
            "feverpain_action": None,
        }

    if tp_dysphagia == 3 and neck_swelling == 1:
        return {
            "triage_level": LEVEL_RED,
            "triage_message": (
                "Сильная боль при глотании с отеком шеи. "
                "Исключите глубокую шейную инфекцию — срочно к врачу."
            ),
            "centor_score": None,
            "centor_action": None,
            "feverpain_score": None,
            "feverpain_action": None,
        }

    # --- Centor / McIsaac Score ---
    c_input = build_centor_input(symptoms, tp_age)
    c_score = centor_score(c_input)
    c_action = centor_action(c_score)

    # --- FeverPAIN (adults only: validated for ≥15y) ---
    adult_groups = {"15-44y", ">=45y"}
    is_adult = tp_age in adult_groups

    fp_score = None
    fp_action = None
    if is_adult:
        fp_input = build_feverpain_input(symptoms, symptom_duration)
        fp_score = feverpain_score(fp_input)
        fp_action = feverpain_action(fp_score)

    # --- Triage decision ---
    # We use the HIGHER-risk action between Centor and FeverPAIN.
    # Action ranking: green_no_ab < yellow_test ≈ yellow_delayed_or_test
    #                 < yellow_test_or_ab ≈ yellow_or_red_ab
    _ACTION_RANK = {
        "green_no_ab": 0,
        "yellow_test": 1,
        "yellow_delayed_or_test": 1,
        "yellow_test_or_ab": 2,
        "yellow_or_red_ab": 2,
    }

    effective_action = c_action
    if fp_action is not None:
        if _ACTION_RANK.get(fp_action, 0) > _ACTION_RANK.get(c_action, 0):
            effective_action = fp_action

    # --- Build triage message ---
    if effective_action == "green_no_ab":
        # Low probability — check for duration-based escalation
        if symptom_duration > 7 and trend != "improving":
            triage_level = LEVEL_YELLOW
            msg = _build_message(
                c_score, c_action, fp_score, fp_action,
                suffix=(
                    "Однако симптомы продолжаются более 7 дней. "
                    "Рекомендуем консультацию врача."
                ),
            )
        else:
            triage_level = LEVEL_GREEN
            msg = _build_message(c_score, c_action, fp_score, fp_action)

    elif effective_action in ("yellow_test", "yellow_delayed_or_test"):
        triage_level = LEVEL_YELLOW
        msg = _build_message(c_score, c_action, fp_score, fp_action)

    elif effective_action in ("yellow_test_or_ab", "yellow_or_red_ab"):
        triage_level = LEVEL_YELLOW
        msg = _build_message(c_score, c_action, fp_score, fp_action)

    else:
        # Fallback: duration-based
        if symptom_duration > 5 and trend != "improving":
            triage_level = LEVEL_YELLOW
            msg = (
                "Симптомы без улучшения более 5 дней. "
                "Запишитесь к врачу для обследования."
            )
        else:
            triage_level = LEVEL_GREEN
            msg = "Симптомы лёгкие. Следите за состоянием."

    return {
        "triage_level": triage_level,
        "triage_message": msg,
        "centor_score": c_score,
        "centor_action": c_action,
        "feverpain_score": fp_score,
        "feverpain_action": fp_action,
    }


def _build_message(
    c_score: int,
    c_action: str,
    fp_score: int | None,
    fp_action: str | None,
    suffix: str = "",
) -> str:
    """Build a unified triage message showing both scales."""
    parts = [centor_message_ru(c_score, c_action)]

    if fp_score is not None and fp_action is not None:
        parts.append(feverpain_message_ru(fp_score, fp_action))

    if suffix:
        parts.append(suffix)

    return "\n\n".join(parts)
