"""
Clinical scoring scales for triage.

Centor / McIsaac — streptococcal pharyngitis probability.
FeverPAIN — sore throat antibiotic decision aid.

Evidence base:
  - Centor RM et al. (1981): original 4-item score.
  - McIsaac WJ et al. (1998): age-modified Centor.
  - Little P et al. (2013, Lancet): FeverPAIN derivation and validation.
  - Bakhit M et al. (2024, BJGP): head-to-head comparison showing
    AUC ≈ 0.62 for both — neither is highly discriminatory, but useful
    for stratifying management.

These functions operate on raw symptom values already collected by the
existing tonsillopharyngitis diary (bot/triage/params.py TP_PARAMS).
No new questions are needed — we map existing params to scale inputs.
"""

from __future__ import annotations

from dataclasses import dataclass


# ═══════════════════════════════════════════════════════════════════════
# Centor / McIsaac
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class CentorInput:
    """Input values for modified Centor (McIsaac) score."""
    fever_over_38: bool        # tp_temp >= 2
    no_cough: bool             # tp_cough == 0
    tender_anterior_lymph: bool  # tp_lymph == 1
    tonsillar_exudate: bool    # tp_exudate == 1
    age_group: str             # from patient demographics


def centor_score(inp: CentorInput) -> int:
    """Calculate modified Centor (McIsaac) score.

    Range: -1 to 5.
    - 0–1: GAS probability <10%
    - 2–3: GAS probability 15–35%
    - 4–5: GAS probability 40–60%

    Age modifier (McIsaac 1998):
    - 3–14 years: +1
    - 15–44 years: 0
    - ≥45 years: -1
    """
    base = sum([
        inp.fever_over_38,
        inp.no_cough,
        inp.tender_anterior_lymph,
        inp.tonsillar_exudate,
    ])

    # Age modifier
    child_groups = {"<6mo", "6-23mo", "2-5y", "6-14y"}
    if inp.age_group in child_groups:
        base += 1
    elif inp.age_group == ">=45y":
        base -= 1

    return base


def centor_action(score: int) -> str:
    """Map Centor score to clinical action.

    Based on Bakhit 2024 and IDSA 2012 guidelines:
    - 0–1: Symptomatic treatment, no testing needed (GAS unlikely).
    - 2:   RADT recommended; antibiotics only if positive.
    - 3+:  RADT recommended; empirical antibiotics reasonable if positive.
    """
    if score <= 1:
        return "green_no_ab"
    if score == 2:
        return "yellow_test"
    return "yellow_test_or_ab"


def centor_message_ru(score: int, action: str) -> str:
    """Generate patient-facing Russian text for Centor result."""
    messages = {
        "green_no_ab": (
            f"Шкала Центора: {score} балл(а/ов). "
            "Вероятность стрептококковой инфекции низкая (<10%). "
            "Антибиотики не показаны, рекомендовано симптоматическое лечение."
        ),
        "yellow_test": (
            f"Шкала Центора: {score} балл(а/ов). "
            "Умеренная вероятность стрептококковой инфекции. "
            "Рекомендуется экспресс-тест на стрептококк (RADT). "
            "Антибиотики — только при положительном результате."
        ),
        "yellow_test_or_ab": (
            f"Шкала Центора: {score} балл(а/ов). "
            "Повышенная вероятность стрептококковой инфекции. "
            "Рекомендуется тестирование и консультация врача для решения "
            "вопроса об антибактериальной терапии."
        ),
    }
    return messages.get(action, f"Шкала Центора: {score}.")


# ═══════════════════════════════════════════════════════════════════════
# FeverPAIN
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class FeverPainInput:
    """Input values for FeverPAIN score.

    F — Fever in last 24h
    P — Purulence (tonsillar exudate)
    A — Attend rapidly (≤3 days from onset)
    I — Inflamed tonsils (severely)
    N — No cough or coryza
    """
    fever_24h: bool            # tp_temp >= 2
    purulent_tonsils: bool     # tp_exudate == 1
    attended_rapidly: bool     # symptom_duration <= 3
    inflamed_tonsils: bool     # tp_dysphagia >= 2 (proxy: severe inflammation)
    no_cough_no_coryza: bool   # tp_cough == 0


def feverpain_score(inp: FeverPainInput) -> int:
    """Calculate FeverPAIN score (0–5)."""
    return sum([
        inp.fever_24h,
        inp.purulent_tonsils,
        inp.attended_rapidly,
        inp.inflamed_tonsils,
        inp.no_cough_no_coryza,
    ])


def feverpain_action(score: int) -> str:
    """Map FeverPAIN score to clinical action.

    Little et al. 2013 (Lancet):
    - 0–1: 13–18% strep — no antibiotics.
    - 2–3: 34–40% strep — delayed prescription or RADT.
    - 4–5: 62–65% strep — antibiotics or immediate RADT.
    """
    if score <= 1:
        return "green_no_ab"
    if score in (2, 3):
        return "yellow_delayed_or_test"
    return "yellow_or_red_ab"


def feverpain_message_ru(score: int, action: str) -> str:
    """Generate patient-facing Russian text for FeverPAIN result."""
    messages = {
        "green_no_ab": (
            f"Шкала FeverPAIN: {score} балл(а/ов). "
            "Вероятность бактериальной инфекции низкая. "
            "Антибиотики не нужны."
        ),
        "yellow_delayed_or_test": (
            f"Шкала FeverPAIN: {score} балл(а/ов). "
            "Умеренная вероятность бактериальной инфекции. "
            "Рекомендуется экспресс-тест или отложенный рецепт на антибиотик."
        ),
        "yellow_or_red_ab": (
            f"Шкала FeverPAIN: {score} балл(а/ов). "
            "Высокая вероятность бактериальной инфекции. "
            "Обратитесь к врачу для назначения антибиотика."
        ),
    }
    return messages.get(action, f"Шкала FeverPAIN: {score}.")


# ═══════════════════════════════════════════════════════════════════════
# Mapping helpers: TP_PARAMS → scale inputs
# ═══════════════════════════════════════════════════════════════════════

def build_centor_input(symptoms: dict, age_group: str) -> CentorInput:
    """Build CentorInput from collected tonsillopharyngitis symptoms."""
    return CentorInput(
        fever_over_38=symptoms.get("tp_temp", 0) >= 2,
        no_cough=symptoms.get("tp_cough", 0) == 0,
        tender_anterior_lymph=symptoms.get("tp_lymph", 0) == 1,
        tonsillar_exudate=symptoms.get("tp_exudate", 0) == 1,
        age_group=age_group,
    )


def build_feverpain_input(
    symptoms: dict, symptom_duration: int
) -> FeverPainInput:
    """Build FeverPainInput from collected tonsillopharyngitis symptoms.

    Notes on proxy mapping:
    - "Inflamed tonsils" (I): we use tp_dysphagia >= 2 as a proxy for
      severely inflamed tonsils, since we don't ask patients to
      visually inspect their tonsils separately. Severe dysphagia
      strongly correlates with tonsillar inflammation (Little 2013).
    - "Attend rapidly" (A): True when symptom_duration <= 3 days.
    """
    return FeverPainInput(
        fever_24h=symptoms.get("tp_temp", 0) >= 2,
        purulent_tonsils=symptoms.get("tp_exudate", 0) == 1,
        attended_rapidly=symptom_duration <= 3,
        inflamed_tonsils=symptoms.get("tp_dysphagia", 0) >= 2,
        no_cough_no_coryza=symptoms.get("tp_cough", 0) == 0,
    )


def compute_tp_scales(
    symptoms: dict, age_group: str, symptom_duration: int
) -> dict:
    """Compute both Centor and FeverPAIN for a tonsillitis episode.

    Returns a dict with all computed values for downstream use:
    {
        "centor_score": int,
        "centor_action": str,
        "centor_message": str,
        "feverpain_score": int,
        "feverpain_action": str,
        "feverpain_message": str,
    }
    """
    c_inp = build_centor_input(symptoms, age_group)
    c_score = centor_score(c_inp)
    c_action = centor_action(c_score)

    fp_inp = build_feverpain_input(symptoms, symptom_duration)
    fp_score = feverpain_score(fp_inp)
    fp_action = feverpain_action(fp_score)

    return {
        "centor_score": c_score,
        "centor_action": c_action,
        "centor_message": centor_message_ru(c_score, c_action),
        "feverpain_score": fp_score,
        "feverpain_action": fp_action,
        "feverpain_message": feverpain_message_ru(fp_score, fp_action),
    }
