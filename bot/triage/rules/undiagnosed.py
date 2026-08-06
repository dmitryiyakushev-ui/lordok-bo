"""
Triage rules for UNDIAGNOSED patients — patients without an established
ENT diagnosis, grouped by anatomical complaint area.

Strategy (conservative, per general practice guidance):
- Heavy emphasis on red flag detection (handled upstream in engine via
  check_universal_red_flags — see bot/triage/red_flags.py).
- Default bias toward YELLOW (see rationale below) — any non-trivial
  symptoms without a working diagnosis warrant an initial ENT
  consultation.
- RED for any RF or high fever.
- GREEN only for clearly mild, short-duration picture.

This module does NOT attempt differential diagnosis. It answers only:
"Should this patient see a doctor?" and for undiagnosed presentations
the threshold is deliberately lower than for monitored chronic disease.

Engine contract: return dict with `triage_level` and `triage_message`.
SYMPTOM_PARAMS / RED_FLAGS for this nosology now live in
bot/triage/params.py (single source of truth for the log handler).
"""

from typing import Optional

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
    Triage for undiagnosed patients (any complaint area).

    Returns:
        dict with `triage_level` and `triage_message`.
    """
    # ── Ear-specific safety net (WHO IMCI): any ear discharge in an
    # undiagnosed patient warrants medical evaluation ──────────────
    ear_discharge = symptoms.get("un_ear_discharge", 0) or 0
    bloody_discharge = symptoms.get("bloody_discharge", 0) or 0

    if bloody_discharge >= 1:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": (
                "⚠️ Кровянистые выделения из уха требуют осмотра. "
                "Запишитесь к ЛОР-врачу в ближайшие 1\u20132 дня."
            ),
        }
    if ear_discharge >= 1:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": (
                "⚠️ Выделения из уха без установленного диагноза. "
                "Рекомендуем обратиться к ЛОР-врачу для оценки."
            ),
        }

    # Temperature keys we care about across all 'undiagnosed' areas.
    temp_keys = [k for k in symptoms if "temp" in k]
    has_fever = any(symptoms.get(k, 0) >= 2 for k in temp_keys)
    has_high_fever = any(symptoms.get(k, 0) >= 3 for k in temp_keys)

    # Severity maxima (skip duration buckets; 'duration' is not severity).
    numeric_symptom_items = [
        (k, v)
        for k, v in symptoms.items()
        if isinstance(v, (int, float)) and "duration" not in k
    ]
    has_severe = any(v >= 3 for _k, v in numeric_symptom_items)

    # Duration proxy: our 0–3 bucket keyboard for 'duration' maps to
    # 1–2d / 3–5d / 5–10d / >10d. Bucket ≥2 ≈ symptoms lasting ~5+ days.
    duration_keys = [k for k in symptoms if "duration" in k]
    long_duration = any(symptoms.get(k, 0) >= 2 for k in duration_keys)

    # ── RED: severe symptoms + fever (high fever alone is now handled
    # by the engine as a soft alarm with contextual logic) ─────────────
    # NOTE: has_high_fever is no longer auto-RED here.  The engine's
    # soft alarm evaluation handles temp>39 contextually.

    if has_severe and has_fever:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": (
                "⚠️ Выраженные симптомы с повышенной температурой. "
                "Рекомендуем обратиться к ЛОР-врачу в ближайшие 1\u20132 дня."
            ),
        }

    # ── YELLOW: moderate / long / fever / severe / worsening ───────────
    if (
        composite_score >= 5
        or has_fever
        or has_severe
        or long_duration
        or trend in ("worsening", "worsening_3d")
    ):
        if long_duration:
            msg = (
                "⚠️ Симптомы сохраняются продолжительное время. "
                "Рекомендуем записаться к ЛОР-врачу для первичной оценки."
            )
        elif has_fever:
            msg = (
                "⚠️ Повышенная температура в сочетании с ЛОР-симптомами. "
                "Рекомендуем обратиться к ЛОР-врачу в ближайшие 1–2 дня."
            )
        elif trend in ("worsening", "worsening_3d"):
            msg = (
                "⚠️ Симптомы нарастают. "
                "Запишитесь к ЛОР-врачу для оценки состояния."
            )
        else:
            msg = (
                "⚠️ Симптомы умеренной выраженности. "
                "Рекомендуем записаться к ЛОР-врачу для первичной консультации."
            )
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": msg,
        }

    # ── GREEN: mild, short, no alarms ──────────────────────────────────
    return {
        "triage_level": LEVEL_GREEN,
        "triage_message": (
            "✅ Симптомы лёгкие. Продолжайте наблюдение.\n\n"
            "Если состояние сохраняется дольше 5-7 дней или нарастает, "
            "запишитесь к ЛОР-врачу для первичной консультации."
        ),
    }
