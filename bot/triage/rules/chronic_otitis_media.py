"""
Chronic Otitis Media (COM) / Otitis Media with Effusion (OME) triage rules.

Evidence base: AAO-HNS OME Guideline (Rosenfeld RM et al. 2016)
Covers both OME (effusion without acute infection) and chronic suppurative OM.
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
    Run chronic otitis media-specific triage logic.

    Parameters expected in symptoms:
    - com_hearing: 0–3
    - com_fullness: 0–3
    - com_discharge: 0=none, 1=serous, 2=mucoid, 3=purulent/fetid
    - com_tinnitus: 0–3
    - com_vertigo: 0–3
    - com_pain: 0–3
    - effusion_duration: days or None (for OME monitoring)
    - facial_asymmetry: 0=no, 1=yes (CN VII involvement)

    Args:
        symptoms: dict of parameter_id -> value
        composite_score: unused
        symptom_duration: days (CRS defined as ≥84 days)
        trend: 'improving', 'stable', 'worsening', etc.
        previous_entries: list of prior SymptomEntry

    Returns:
        dict with keys:
        - triage_level: 'green', 'yellow', or 'red'
        - triage_message: user-facing Russian text
    """

    com_hearing = symptoms.get("com_hearing", 0)
    com_discharge = symptoms.get("com_discharge", 0)
    com_tinnitus = symptoms.get("com_tinnitus", 0)
    com_vertigo = symptoms.get("com_vertigo", 0)
    com_pain = symptoms.get("com_pain", 0)
    facial_asymmetry = symptoms.get("facial_asymmetry", 0)
    effusion_duration = symptoms.get("effusion_duration", 0)

    # --- Dangerous Complications (Emergency) ---

    # Vertigo with chronic ear disease (labyrinthine fistula risk)
    if com_vertigo >= 2:
        return {
            "triage_level": LEVEL_RED,
            "triage_message": "Головокружение с хроническим отитом — возможна лабиринтная фистула. Требуется срочное обследование.",
        }

    # Foul-smelling or bloody discharge (cholesteatoma risk)
    if com_discharge == 3:
        return {
            "triage_level": LEVEL_RED,
            "triage_message": "Зловонное или кровянистое отделяемое. Исключите холестеатому — срочно к врачу.",
        }

    # Facial nerve involvement (CN VII palsy)
    if facial_asymmetry == 1:
        return {
            "triage_level": LEVEL_RED,
            "triage_message": "Асимметрия лица указывает на вовлечение лицевого нерва. Требуется срочное обследование.",
        }

    # --- Active Infection (CSOM) ---

    # Active discharge with pain
    if com_discharge >= 2 and com_pain >= 2:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Активное отделяемое с болью. Запишитесь к врачу в ближайшие 1–2 дня.",
        }

    # New discharge after dry period
    if com_discharge >= 1 and trend == "worsening":
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Новое отделяемое из уха. Требуется оценка врача.",
        }

    # --- OME Monitoring (Effusion) ---

    # Hearing loss + effusion ≥3 months
    if com_hearing >= 2 and effusion_duration >= 84:  # 3 months ≈ 84 days
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Снижение слуха с выпотом ≥3 месяцев. Рекомендуется аудиометрия (AAO-HNS).",
        }

    # Mild symptoms, effusion <3 months (watchful waiting)
    if com_hearing <= 1 and effusion_duration < 84:
        return {
            "triage_level": LEVEL_GREEN,
            "triage_message": "Легкие симптомы, выпот <3 месяцев. Наблюдение рекомендуется (AAO-HNS). Повторная оценка каждые 3–6 месяцев.",
        }

    # --- Stable Chronic Disease ---

    # Dry ear, stable condition
    if com_discharge == 0 and trend == "stable":
        return {
            "triage_level": LEVEL_GREEN,
            "triage_message": "Сухое ухо, состояние стабильно. Продолжайте плановое наблюдение.",
        }

    # --- Tinnitus ---

    # New or worsening tinnitus
    if com_tinnitus >= 2 and trend == "worsening":
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Новый или усиливающийся звон в ушах. Требуется аудиологическое обследование.",
        }

    # --- Improving trend ---
    if trend == "improving":
        return {
            "triage_level": LEVEL_GREEN,
            "triage_message": "Тенденция к улучшению. Продолжайте текущее лечение.",
        }

    # --- Pain alone ---
    if com_pain >= 2:
        return {
            "triage_level": LEVEL_YELLOW,
            "triage_message": "Боль в ухе требует оценки врача.",
        }

    return {
        "triage_level": LEVEL_GREEN,
        "triage_message": "Симптомы минимальные. Продолжайте плановое наблюдение.",
    }
