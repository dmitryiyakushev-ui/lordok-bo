"""
Adenoid Hypertrophy triage rules.

Evidence base: AAO-HNS Tonsillectomy in Children (Mitchell RB et al. 2019),
AAP Technical Report on Childhood OSA (Marcus CL et al. 2012).
Focus: pediatric sleep-disordered breathing (SDB) screening.
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
    Run adenoid hypertrophy-specific triage logic.

    Parameters expected in symptoms:
    - ah_obstruction: 0–3
    - ah_mouth_breathing: 0–3
    - ah_snoring: 0=no, 1=occasional, 2=most nights, 3=every night/loud
    - ah_apnea: 0=no, 1=suspected, 2=confirmed by parent
    - ah_sleep: 0–3
    - ah_daytime: 0–3
    - ah_ear_infections: 0=none, 1=1–2, 2=3–4, 3=5+ (past 6 months)
    - ah_sinusitis: 0=none, 1=1–2, 2=3–4, 3=5+ (past 12 months)
    - failure_to_thrive: 0=no, 1=yes
    - behavioral_regression: 0=no, 1=yes

    Args:
        symptoms: dict of parameter_id -> value
        composite_score: unused
        symptom_duration: days of symptoms
        trend: 'improving', 'stable', 'worsening', etc.
        previous_entries: list of prior SymptomEntry

    Returns:
        dict with keys:
        - triage_level: 'green', 'yellow', or 'red'
        - triage_message: user-facing Russian text
    """

    ah_obstruction = symptoms.get("ah_obstruction", 0)
    ah_mouth_breathing = symptoms.get("ah_mouth_breathing", 0)
    ah_snoring = symptoms.get("ah_snoring", 0)
    ah_apnea = symptoms.get("ah_apnea", 0)
    ah_sleep = symptoms.get("ah_sleep", 0)
    ah_daytime = symptoms.get("ah_daytime", 0)
    ah_ear_infections = symptoms.get("ah_ear_infections", 0)
    ah_sinusitis = symptoms.get("ah_sinusitis", 0)

    failure_to_thrive = symptoms.get("failure_to_thrive", 0)
    behavioral_regression = symptoms.get("behavioral_regression", 0)

    # --- Observed Apnea (AAO-HNS 2019: PSG referral, not emergency) ---

    if ah_apnea >= 1:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": (
                "Родитель наблюдал остановки дыхания во сне. "
                "Запишитесь к ЛОР-врачу для оценки и направления на полисомнографию (PSG)."
            ),
        }

    # --- Growth/Developmental Concern (AAP 2012: priority referral, not emergency) ---

    if failure_to_thrive == 1 or behavioral_regression == 1:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": (
                "Проблемы роста или развития на фоне нарушения дыхания во сне. "
                "Запишитесь к ЛОР-врачу в ближайшие дни для обследования."
            ),
        }

    # --- Severe Sleep-Disordered Breathing ---

    # Loud nightly snoring + daytime symptoms
    if ah_snoring == 3 and ah_daytime >= 2:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Громкий ночной храп с дневной сонливостью. Требуется оценка синдрома обструктивного апноэ сна.",
        }

    # Loud snoring + poor sleep quality (without apnea)
    if ah_snoring == 3 and ah_sleep >= 2 and ah_apnea == 0:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Значительный храп с нарушением сна. Запишитесь к ЛОР-врачу для обследования.",
        }

    # --- Moderate Nasal Obstruction with Mouth Breathing ---

    if ah_obstruction >= 2 and ah_mouth_breathing >= 2:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Выраженная заложенность носа с дыханием через рот. Требуется оценка врача.",
        }

    # --- Recurrent Ear Infections ---

    # 3+ episodes in 6 months (ah_ear_infections >= 2)
    if ah_ear_infections >= 2:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Повторные отиты (3+ за 6 месяцев). Требуется оценка роли аденоидов.",
        }

    # --- Recurrent Sinusitis ---

    # 3+ episodes in 12 months (ah_sinusitis >= 2)
    if ah_sinusitis >= 2:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Повторные синуситы (3+ за 12 месяцев). Требуется оценка роли аденоидов.",
        }

    # --- Mild Symptoms (Watchful Waiting) ---

    if ah_obstruction <= 1 and ah_snoring <= 1 and ah_sleep <= 1:
        return {
            "triage_level": LEVEL_GREEN,
            "triage_message": "Легкие симптомы. Рекомендуется наблюдение. Следите за развитием храпа или апноэ.",
        }

    # --- Moderate symptoms with some snoring ---

    if ah_snoring >= 1 or ah_obstruction >= 1:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Наличие симптомов требует консультации врача для оценки необходимости обследования.",
        }

    return {
        "triage_level": LEVEL_GREEN,
        "triage_message": "Минимальные или отсутствующие симптомы. Продолжайте наблюдение.",
    }
