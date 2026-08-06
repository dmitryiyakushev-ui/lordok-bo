"""
Triage rules for NON-ENT problems — patients who explicitly declared
their issue is outside the ENT scope but still want to use the diary.

IMPORTANT: The user has been shown a disclaimer at the start of the
flow in bot/handlers/log.py making it clear that ЛОРдок does NOT
analyse ENT-specific red flags for this pathway. Only universal
life-threatening signs (handled upstream via check_universal_red_flags)
can escalate to RED here.

Engine contract: return dict with `triage_level` and `triage_message`.
SYMPTOM_PARAMS / RED_FLAGS live in bot/triage/params.py.
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
    Minimal, conservative triage for non-ENT diary entries.

    Logic:
    - RED only if universal red flags upstream triggered (handled in engine).
      Here we additionally RED on very high VAS (≥9) + fever, as a safety net.
    - YELLOW on VAS ≥7, fever ≥37.5–38, or long-duration (>10 days), or worsening.
    - GREEN otherwise.
    """
    vas = symptoms.get("ne_overall_severity", 0) or 0
    temp = symptoms.get("ne_temp", 0) or 0
    sleep = symptoms.get("ne_sleep", 0) or 0
    activity = symptoms.get("ne_activity", 0) or 0
    duration_bucket = symptoms.get("ne_duration", 0) or 0

    high_fever = temp >= 3
    any_fever = temp >= 2
    very_severe = vas >= 9
    severe = vas >= 7
    moderate = vas >= 5
    long_duration = duration_bucket >= 2  # 5+ days
    very_long_duration = duration_bucket >= 3  # >10 days
    sleep_or_activity_impaired = sleep >= 2 or activity >= 2
    worsening = trend in ("worsening", "worsening_3d")

    # Safety net — extreme picture we don't want to let slide through.
    # NOTE: high_fever alone is now a soft alarm handled by the engine.
    # Here we only flag the combination as YELLOW; the engine's soft
    # alarm logic may escalate to RED if contextual signals warrant it.
    if high_fever and (severe or sleep_or_activity_impaired):
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": (
                "⚠️ Высокая температура в сочетании с выраженными симптомами. "
                "Рекомендуем обратиться к врачу в ближайшие 1\u20132 дня."
            ),
        }

    if very_severe:
        return {
            "triage_level": LEVEL_RED,
            "triage_message": (
                "🚨 Очень высокая выраженность симптомов. "
                "Рекомендуем обратиться к врачу сегодня."
            ),
        }

    # YELLOW
    if severe or any_fever or very_long_duration or worsening:
        if worsening:
            msg = (
                "⚠️ Симптомы нарастают. "
                "Рекомендуем обратиться к профильному врачу в ближайшие дни."
            )
        elif any_fever:
            msg = (
                "⚠️ Повышенная температура на фоне жалоб. "
                "Рекомендуем обратиться к терапевту / педиатру."
            )
        elif very_long_duration:
            msg = (
                "⚠️ Симптомы сохраняются более 10 дней. "
                "Рекомендуем обратиться к профильному врачу."
            )
        else:
            msg = (
                "⚠️ Симптомы выражены значимо. "
                "Рекомендуем обратиться к профильному врачу."
            )
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": (
                f"{msg}\n\n"
                "ℹ️ Напоминаем: это не ЛОР-проблема, и ЛОРдок не анализирует "
                "специфические «красные флаги» для не-ЛОР состояний. "
                "Обратитесь к врачу соответствующего профиля."
            ),
        }

    # GREEN
    if moderate or long_duration or sleep_or_activity_impaired:
        return {
            "triage_level": LEVEL_GREEN,
            "triage_message": (
                "🟢 Жалобы умеренной выраженности. Продолжайте наблюдение.\n\n"
                "Если в ближайшие несколько дней не будет улучшения — "
                "запишитесь к профильному врачу."
            ),
        }

    return {
        "triage_level": LEVEL_GREEN,
        "triage_message": (
            "✅ Жалобы лёгкие. Продолжайте наблюдение.\n\n"
            "ℹ️ Это не ЛОР-проблема — ЛОРдок ведёт дневник, но не ставит "
            "оценку по «красным флагам» для не-ЛОР состояний. "
            "Если состояние не улучшится — обратитесь к профильному врачу."
        ),
    }
