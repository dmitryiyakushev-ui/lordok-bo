"""
Triage engine: orchestrates the decision tree for ENT symptom triage.

Workflow:
1. Universal red flag check (hard flags -> immediate RED)
2. Soft alarm contextual evaluation (high_fever, rapid_deterioration)
3. Nosology-specific triage logic
4. ARVI expected pattern guard (prevents false worsening escalation)
5. Trend analysis overlay
6. Output: triage_level, triage_message, red_flags list

v2 (April 2026): Hard/soft alarm classification.
- Hard red flags (periorbital edema, meningeal signs, stridor, etc.)
  always trigger RED immediately.
- Soft alarms (high_fever, rapid_deterioration) are evaluated in
  context: fever duration, antipyretic response, composite score.
  This prevents false RED escalation for typical ARVI patients.

Evidence base:
  EPOS 2020, AAO-HNS 2025, IDSA 2012, AAP 2013, NICE NG237, WHO IMCI.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from bot.models.symptom import SymptomEntry
from bot.triage.models import TriageResult, TriageLevel  # noqa: F401 -- re-export
from bot.triage.red_flags import (
    check_universal_red_flags,
    RF_HIGH_FEVER,
    RF_RAPID_DETERIORATION,
)
from bot.triage.rules import (
    acute_rhinosinusitis,
    chronic_rhinosinusitis,
    acute_tonsillopharyngitis,
    acute_otitis_media,
    chronic_otitis_media,
    adenoid_hypertrophy,
    undiagnosed,
    non_ent,
)

# Mapping nosology -> triage rule module
NOSOLOGY_HANDLERS = {
    "ars": acute_rhinosinusitis,
    "crs": chronic_rhinosinusitis,
    "tonsillopharyngitis": acute_tonsillopharyngitis,
    "aom": acute_otitis_media,
    "com": chronic_otitis_media,
    "adenoid_hypertrophy": adenoid_hypertrophy,
    "undiagnosed_nose": undiagnosed,
    "undiagnosed_throat": undiagnosed,
    "undiagnosed_ear": undiagnosed,
    "undiagnosed_multiple": undiagnosed,
    "non_ent": non_ent,
}

# Triage levels
LEVEL_GREEN = "green"
LEVEL_YELLOW = "yellow"
LEVEL_RED = "red"

# Сколько тревожных признаков рядом с температурой выше 39 переводят
# оценку в красную. Решение Дмитрия от 06.08.2026: одного достаточно.
HIGH_FEVER_RED_SIGNALS = 1

# Nosologies where ARVI expected pattern logic applies.
_ARVI_NOSOLOGIES = frozenset({
    "ars",
    "tonsillopharyngitis",
    "aom",
    "undiagnosed_nose",
    "undiagnosed_throat",
    "undiagnosed_ear",
    "undiagnosed_multiple",
})


def calculate_symptom_duration(
    first_entry_date: Optional[datetime], now: Optional[datetime] = None
) -> int:
    """
    Calculate symptom duration in days from first entry to now.

    Args:
        first_entry_date: datetime of first symptom entry (or None if no history)
        now: reference timestamp (defaults to UTC now)

    Returns:
        Duration in days (0 if no entry or history empty)
    """
    if first_entry_date is None:
        return 0

    if now is None:
        now = datetime.now(timezone.utc)

    # Ensure both are timezone-aware
    if first_entry_date.tzinfo is None:
        first_entry_date = first_entry_date.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    delta = now - first_entry_date
    return delta.days


def reported_duration_days(symptoms: dict) -> int:
    """Длительность болезни со слов пациента, в днях.

    Вопрос «сколько дней уже длятся симптомы» задаётся при первом
    заполнении случая и через value_map приходит сюда уже в днях.
    Без него движок знал только, сколько дней человек ведёт дневник,
    и первый визит всегда выглядел как первый день болезни.
    """
    values = [
        v for k, v in symptoms.items()
        if k.endswith("_onset_days") and isinstance(v, (int, float))
    ]
    return int(max(values)) if values else 0


def get_last_n_entries(
    current_entry: SymptomEntry,
    all_entries: list[SymptomEntry],
    n: int = 3,
    exclude_current: bool = True,
) -> list[SymptomEntry]:
    """
    Get the last n entries before current (for trend analysis).

    Args:
        current_entry: the current symptom entry
        all_entries: all symptom entries for the user (sorted by recorded_at ascending)
        n: number of previous entries to retrieve
        exclude_current: if True, don't include current_entry in result

    Returns:
        List of entries, oldest first (up to n entries)
    """
    if not all_entries:
        return []

    if exclude_current:
        earlier_entries = [
            e for e in all_entries
            if e.recorded_at < current_entry.recorded_at
        ]
    else:
        earlier_entries = all_entries

    sorted_entries = sorted(earlier_entries, key=lambda e: e.recorded_at, reverse=True)
    return sorted_entries[:n]


def analyze_trend(
    current_score: int,
    previous_entries: list[SymptomEntry],
    threshold_percent: float = 0.20,
) -> str:
    """
    Analyze trend based on composite score changes.

    Trend types:
    - 'improving': score decreased >= threshold_percent
    - 'stable': score within +/- threshold_percent
    - 'worsening': score increased >= threshold_percent
    - 'worsening_3d': score increased for 3 consecutive days

    Args:
        current_score: composite score of current entry
        previous_entries: list of previous entries, sorted by recorded_at (most recent first)
        threshold_percent: sensitivity threshold (default 20%)

    Returns:
        trend string ('improving', 'stable', 'worsening', 'worsening_3d', or 'insufficient_data')
    """
    if not previous_entries:
        return "insufficient_data"

    previous_scores = [e.composite_score for e in previous_entries]
    mean_previous = sum(previous_scores) / len(previous_scores)

    # Check for 3-day consecutive worsening
    if len(previous_entries) >= 3:
        scores_ordered = [e.composite_score for e in reversed(previous_entries[-3:])]
        if all(scores_ordered[i] < scores_ordered[i + 1] for i in range(len(scores_ordered) - 1)):
            if current_score > scores_ordered[-1]:
                return "worsening_3d"

    delta_percent = (current_score - mean_previous) / mean_previous if mean_previous > 0 else 0

    if delta_percent >= threshold_percent:
        return "worsening"
    elif delta_percent <= -threshold_percent:
        return "improving"
    else:
        return "stable"


# ======================================================================
# Soft alarm contextual evaluation
# ======================================================================

def _count_soft_alarm_signals(symptoms: dict) -> int:
    """Count the number of 'soft alarm' signals in the symptom set.

    Soft alarm signals (each counts as 1):
    - Each severity_0_3 param == 3 (severe)
    - Any pain param >= 2 with poor analgesic response (analgesic >= 2)
    - Poor antipyretic response (antipyretic >= 2)
    - Fever duration >= 2 (5-7 days)
    - Purulent discharge (discharge == 3)

    v3 (август 2026): каждый тяжёлый симптом считается отдельно. Раньше
    цикл обрывался на первом, и «сильная боль плюс полная заложенность
    плюс гнойное отделяемое» весило столько же, сколько один симптом.
    """
    count = 0

    # Severe symptoms (value == 3, excluding temp/duration/response params).
    # Отделяемое исключено: у него ниже свой блок, иначе гнойное
    # отделяемое считалось бы дважды.
    skip_suffixes = ("_temp", "_fever_duration", "_antipyretic", "_analgesic",
                     "_duration", "_vas", "_bilateral", "_cough", "_exudate",
                     "_lymph", "_age", "_discharge")
    for k, v in symptoms.items():
        if isinstance(v, (int, float)) and v == 3:
            if not any(k.endswith(s) for s in skip_suffixes):
                count += 1

    # Poor antipyretic response
    antipyretic_keys = [k for k in symptoms if k.endswith("_antipyretic")]
    for k in antipyretic_keys:
        if symptoms[k] >= 2:  # barely works or not taken
            count += 1
            break

    # Poor analgesic response
    analgesic_keys = [k for k in symptoms if k.endswith("_analgesic")]
    for k in analgesic_keys:
        if symptoms[k] >= 2:
            count += 1
            break

    # Long fever duration
    fever_dur_keys = [k for k in symptoms if k.endswith("_fever_duration")]
    for k in fever_dur_keys:
        if symptoms[k] >= 2:  # 5-7 days or more
            count += 1
            break

    # Purulent discharge
    discharge_keys = [k for k in symptoms if "discharge" in k]
    for k in discharge_keys:
        if symptoms.get(k, 0) == 3:
            count += 1
            break

    return count


def _evaluate_soft_alarms(
    soft_alarms: list[str],
    symptoms: dict,
    composite_score: int,
    symptom_duration: int,
) -> tuple[str, str, list[str]]:
    """Evaluate soft alarms in context.

    Returns:
        (level, message, alarm_ids_that_contributed)
        level: 'red', 'yellow', or None (= no escalation)
    """
    result_flags: list[str] = list(soft_alarms)

    has_high_fever = RF_HIGH_FEVER in soft_alarms
    has_rapid_det = RF_RAPID_DETERIORATION in soft_alarms

    # -- High fever contextual logic --
    # temp >39 + >=1 soft alarm signal -> RED
    # temp >39 alone -> YELLOW (не auto-RED: обычная вирусная инфекция
    #                          с высокой температурой и без других
    #                          признаков не повод гнать к врачу сегодня)
    if has_high_fever:
        n_signals = _count_soft_alarm_signals(symptoms)
        if n_signals >= HIGH_FEVER_RED_SIGNALS:
            return (
                LEVEL_RED,
                "Высокая температура в сочетании с тревожными признаками. "
                "Рекомендуем обратиться к врачу сегодня.",
                result_flags,
            )
        # без других признаков -> YELLOW (handled below)

    # -- Rapid deterioration contextual filter --
    # If duration < 5 days AND composite < 10 AND no high fever:
    #   rapid_deterioration -> YELLOW (not RED)
    # Otherwise rapid_deterioration -> RED as before
    if has_rapid_det and not has_high_fever:
        if symptom_duration < 5 and composite_score < 10:
            # Contextual: early disease, low severity -> YELLOW
            pass  # will be YELLOW below
        else:
            return (
                LEVEL_RED,
                "Быстрое ухудшение состояния. Рекомендуем обратиться к врачу сегодня.",
                result_flags,
            )

    if has_rapid_det and has_high_fever:
        # Both together are always RED regardless of duration
        return (
            LEVEL_RED,
            "Высокая температура с быстрым ухудшением состояния. "
            "Обратитесь к врачу сегодня. При резком ухудшении — вызовите скорую.",
            result_flags,
        )

    # Remaining soft alarms -> at minimum YELLOW
    if soft_alarms:
        messages = []
        if has_high_fever:
            messages.append("Температура выше 39\u00b0C")
        if has_rapid_det:
            messages.append("Быстрое ухудшение за последние сутки")
        msg = ". ".join(messages) + ". Рекомендуем обратиться к врачу в ближайшие 1\u20132 дня."
        return LEVEL_YELLOW, msg, result_flags

    return None, "", []


# ======================================================================
# ARVI expected pattern logic
# ======================================================================

def _is_arvi_expected_pattern(
    symptoms: dict,
    composite_score: int,
    symptom_duration: int,
    hard_flags: list[str],
    soft_alarms: list[str],
) -> bool:
    """Check if the current picture matches an expected ARVI course.

    Criteria (all must be true):
    - symptom_duration < 7 days
    - all individual symptom params <= 2 (no severe symptoms)
    - temp <= 2 (no >39C fever)
    - no hard red flags triggered
    - no soft alarms triggered (no high fever, no rapid deterioration)

    When this returns True, the engine should NOT escalate GREEN->YELLOW
    on a worsening trend -- mild fluctuations in early ARVI are expected.
    """
    if symptom_duration >= 7:
        return False
    if hard_flags or soft_alarms:
        return False

    # Check all numeric symptom values
    skip_suffixes = ("_age",)
    for k, v in symptoms.items():
        if not isinstance(v, (int, float)):
            continue
        if any(k.endswith(s) for s in skip_suffixes):
            continue
        if v > 2:
            return False

    return True


# ======================================================================
# Treatment context evaluation
# ======================================================================

# Expected treatment response windows (in days) per nosology.
# If the patient is on prescribed treatment and has been waiting longer
# than this window without improvement, they should revisit the doctor.
#
# Evidence base:
#   AOM: AAP 2013 — expect improvement within 48-72h of antibiotics
#   ARS: EPOS 2020, IDSA 2012 — 3-5 days on antibiotics; 7-10 days watchful waiting
#   Tonsillopharyngitis: NICE NG84 — 24-48h on antibiotics
#   CRS: EPOS 2020 — 2-4 weeks on topical steroids / antibiotics
#   COM: no strict window, but 2 weeks is reasonable for re-evaluation
#   AH: chronic condition, 4 weeks for conservative treatment assessment
_EXPECTED_RESPONSE_DAYS = {
    "aom": 3,            # 48-72h
    "ars": 5,            # 3-5 days antibiotics
    "tonsillopharyngitis": 2,  # 24-48h
    "crs": 21,           # 2-4 weeks (use 3 weeks as midpoint)
    "com": 14,           # 2 weeks
    "adenoid_hypertrophy": 28,  # 4 weeks
}

# tx_last_visit values → approximate days since visit
_VISIT_TO_DAYS = {
    0: 3,    # <1 week → ~3 days
    1: 10,   # 1-2 weeks → ~10 days
    2: 21,   # 2-4 weeks → ~21 days
    3: 45,   # >1 month → ~45 days
    4: None, # never visited a doctor for this
}


def _evaluate_treatment_context(
    nosology: str,
    triage_level: str,
    triage_message: str,
    tx_last_visit: Optional[int],
    tx_status: Optional[str],
    trend: str,
    composite_score: int,
) -> tuple[str, str]:
    """Adjust triage based on treatment context.

    Rules:
    1. No doctor visit ever (tx_visit=4) OR >1 month ago (tx_visit=3)
       AND not improving → minimum YELLOW.
       Rationale: symptoms without medical evaluation warrant a visit.

    2. On prescribed treatment + past expected response window
       AND not improving → YELLOW with "revisit doctor" message.
       Rationale: treatment should have worked by now.

    3. Self-treating (tx_status=self) + not improving after 5+ days
       → YELLOW recommending professional evaluation.

    4. On prescribed treatment + within response window + improving
       → no change (let them continue).

    Returns:
        (adjusted_level, adjusted_message) — only changed if escalation needed
    """
    if tx_last_visit is None:
        return triage_level, triage_message

    LEVEL_RANK = {"green": 0, "yellow": 1, "red": 2}

    days_since_visit = _VISIT_TO_DAYS.get(tx_last_visit)
    expected_days = _EXPECTED_RESPONSE_DAYS.get(nosology)
    is_improving = trend == "improving"

    # Rule 1: Never been to doctor or >1 month without visit
    if tx_last_visit >= 3 and not is_improving:
        if LEVEL_RANK.get(triage_level, 0) < LEVEL_RANK[LEVEL_YELLOW]:
            if tx_last_visit == 4:
                return (
                    LEVEL_YELLOW,
                    "Вы ещё не обращались к врачу с этой проблемой. "
                    "Рекомендуем записаться на приём для постановки диагноза "
                    "и подбора лечения.",
                )
            else:
                return (
                    LEVEL_YELLOW,
                    "Последний визит к врачу был более месяца назад, "
                    "а улучшения нет. Рекомендуем повторный приём.",
                )

    # Rule 2: On prescribed treatment, past expected response window
    if (
        tx_status == "prescribed"
        and days_since_visit is not None
        and expected_days is not None
        and days_since_visit >= expected_days
        and not is_improving
    ):
        if LEVEL_RANK.get(triage_level, 0) < LEVEL_RANK[LEVEL_YELLOW]:
            return (
                LEVEL_YELLOW,
                f"Прошло более {expected_days} дней с начала лечения, "
                "но улучшения нет. Рекомендуем повторный визит к врачу "
                "для коррекции терапии.",
            )

    # Rule 3: Self-treating without improvement
    if (
        tx_status == "self"
        and days_since_visit is not None
        and days_since_visit >= 5
        and not is_improving
    ):
        if LEVEL_RANK.get(triage_level, 0) < LEVEL_RANK[LEVEL_YELLOW]:
            return (
                LEVEL_YELLOW,
                "Вы лечитесь самостоятельно более 5 дней без улучшения. "
                "Рекомендуем обратиться к ЛОР-врачу для профессиональной "
                "оценки и подбора лечения.",
            )

    # Rule 4: No treatment at all + symptoms present
    if tx_status == "none" and composite_score > 3 and not is_improving:
        if LEVEL_RANK.get(triage_level, 0) < LEVEL_RANK[LEVEL_YELLOW]:
            return (
                LEVEL_YELLOW,
                "Вы не получаете лечения при наличии симптомов. "
                "Рекомендуем обратиться к врачу.",
            )

    return triage_level, triage_message


# ======================================================================
# Main triage entry point
# ======================================================================

def run_triage(
    symptom_entry: SymptomEntry,
    user_history: list[SymptomEntry],
    now: Optional[datetime] = None,
    *,
    tx_last_visit: Optional[int] = None,
    tx_status: Optional[str] = None,
) -> dict:
    """
    Run the complete triage algorithm.

    Args:
        symptom_entry: the current SymptomEntry to triage
        user_history: all previous entries for this user (for trend analysis)
        now: reference timestamp (defaults to UTC now)

    Returns:
        dict with keys:
        - triage_level: 'green', 'yellow', or 'red'
        - triage_message: user-facing message
        - red_flags: list of triggered red flag IDs
        - trend: trend classification
        - composite_score: sum of all symptom values
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Step 1: Universal red flag check -- split into hard + soft
    hard_flags, soft_alarms = check_universal_red_flags(symptom_entry.symptoms)

    # Step 1a: Hard red flags -> immediate RED (unchanged)
    if hard_flags:
        return {
            "triage_level": LEVEL_RED,
            "triage_message": (
                "Обратитесь к врачу сегодня. "
                "Если состояние ухудшается быстро — вызовите скорую помощь."
            ),
            "red_flags": hard_flags + soft_alarms,
            "trend": None,
            "composite_score": symptom_entry.composite_score,
        }

    # Step 2: Get nosology handler
    nosology = symptom_entry.nosology
    if nosology not in NOSOLOGY_HANDLERS:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": f"Unknown nosology: {nosology}. Please contact support.",
            "red_flags": [],
            "trend": None,
            "composite_score": symptom_entry.composite_score,
        }

    handler = NOSOLOGY_HANDLERS[nosology]

    # Step 3: Calculate symptom duration.
    # Берём максимум из двух источников: сколько дней человек ведёт
    # дневник и сколько дней, по его словам, длится болезнь. Первое не
    # знает, что было до бота, второе спрашивается один раз за случай.
    # Вопрос о длительности задаётся один раз за случай, поэтому на
    # повторных заполнениях его берём из самой первой записи и
    # прибавляем прожитые с тех пор дни.
    if user_history:
        earliest_entry = min(user_history, key=lambda e: e.recorded_at)
        diary_duration = calculate_symptom_duration(earliest_entry.recorded_at, now)
        onset_before_diary = reported_duration_days(earliest_entry.symptoms)
    else:
        diary_duration = 0
        onset_before_diary = 0

    symptom_duration = max(
        diary_duration + onset_before_diary,
        reported_duration_days(symptom_entry.symptoms),
    )

    # Step 4: Evaluate soft alarms in context
    if soft_alarms:
        soft_level, soft_msg, soft_contributed = _evaluate_soft_alarms(
            soft_alarms,
            symptom_entry.symptoms,
            symptom_entry.composite_score,
            symptom_duration,
        )
        if soft_level == LEVEL_RED:
            return {
                "triage_level": LEVEL_RED,
                "triage_message": soft_msg,
                "red_flags": soft_contributed,
                "trend": None,
                "composite_score": symptom_entry.composite_score,
            }
        # If YELLOW from soft alarms, we remember it as a floor --
        # the nosology handler may raise it but never lower it.

    # Step 5: Analyze trend
    previous_entries = get_last_n_entries(symptom_entry, user_history, n=3)
    trend = analyze_trend(symptom_entry.composite_score, previous_entries)

    # Step 6: Run nosology-specific triage logic
    nosology_result = handler.run_triage(
        symptoms=symptom_entry.symptoms,
        composite_score=symptom_entry.composite_score,
        symptom_duration=symptom_duration,
        trend=trend,
        previous_entries=previous_entries,
    )

    # Step 7: Merge with soft alarm floor
    triage_level = nosology_result["triage_level"]
    triage_message = nosology_result["triage_message"]

    LEVEL_RANK = {"green": 0, "yellow": 1, "red": 2}

    if soft_alarms:
        soft_level_val = LEVEL_RANK.get(soft_level or "green", 0)
        noso_level_val = LEVEL_RANK.get(triage_level, 0)
        if soft_level_val > noso_level_val:
            triage_level = soft_level
            triage_message = soft_msg

    # Step 8: ARVI expected pattern guard
    # Prevents false GREEN->YELLOW escalation on worsening trend for
    # typical early ARVI (duration <7d, all params <=2, no alarms).
    arvi_pattern = (
        nosology in _ARVI_NOSOLOGIES
        and _is_arvi_expected_pattern(
            symptom_entry.symptoms,
            symptom_entry.composite_score,
            symptom_duration,
            hard_flags,
            soft_alarms,
        )
    )

    # Step 9: Trend override (if applicable)

    # Upgrade GREEN to YELLOW if worsening_3d (unless ARVI expected pattern)
    if triage_level == LEVEL_GREEN and trend == "worsening_3d":
        if not arvi_pattern:
            triage_level = LEVEL_YELLOW
            triage_message = (
                "Стабильно, но ухудшается последние 3 дня. "
                "Следите внимательно."
            )

    # Downgrade YELLOW to GREEN if improving (only if no soft alarms)
    # IMPORTANT: Never downgrade for undiagnosed/non_ent (any non-trivial
    # symptoms without a diagnosis warrant a doctor visit regardless of
    # trend).  For established diagnoses, only downgrade when composite
    # score is low (< 5) — otherwise the patient still needs attention.
    _NO_DOWNGRADE_NOSOLOGIES = frozenset({
        "undiagnosed_nose", "undiagnosed_throat",
        "undiagnosed_ear", "undiagnosed_multiple",
        "non_ent",
    })
    if (
        triage_level == LEVEL_YELLOW
        and trend == "improving"
        and not soft_alarms
        and nosology not in _NO_DOWNGRADE_NOSOLOGIES
        and symptom_entry.composite_score < 5
    ):
        if "улучшается" not in triage_message.lower():
            triage_message = "Показатели улучшаются. Продолжайте текущее лечение."
            triage_level = LEVEL_GREEN

    # RED is never downgraded

    # Step 10: Treatment context evaluation (diagnosed patients only).
    # Adjusts GREEN→YELLOW when treatment is absent, overdue, or failing.
    if tx_last_visit is not None and triage_level != LEVEL_RED:
        triage_level, triage_message = _evaluate_treatment_context(
            nosology=nosology,
            triage_level=triage_level,
            triage_message=triage_message,
            tx_last_visit=tx_last_visit,
            tx_status=tx_status,
            trend=trend,
            composite_score=symptom_entry.composite_score,
        )

    all_flags = hard_flags + [a for a in soft_alarms if a not in hard_flags]

    result = {
        "triage_level": triage_level,
        "triage_message": triage_message,
        "red_flags": all_flags if all_flags else [],
        "trend": trend,
        "composite_score": symptom_entry.composite_score,
    }

    # Forward extra keys from the nosology handler (e.g. centor_score,
    # feverpain_score) so that callers can persist them without
    # recomputing.
    _STANDARD_KEYS = {"triage_level", "triage_message"}
    for k, v in nosology_result.items():
        if k not in _STANDARD_KEYS and k not in result:
            result[k] = v

    return result
