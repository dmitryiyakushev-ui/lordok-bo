"""Central registry of SYMPTOM_PARAMS and RED_FLAGS per nosology.

Keeping this in one file so that `bot/handlers/log.py` has a single source
of truth and doesn't have to importlib rule modules (which caused the
"Модуль правил для 'com' не найден" bug — filenames ≠ nosology codes).

Each entry in SYMPTOM_PARAMS has:
    - id:          param key, consumed by the corresponding rule module
    - label_ru:    question text in Russian (patient-facing, accessible)
    - scale_type:  one of the keys in log.SCALE_TO_KEYBOARD
                   (severity_0_3 | discharge | binary | temp | vas_0_10
                    | duration | ome_duration)
    - (optional) value_map: {raw_value: converted_value} applied before
                 handing the symptoms dict to the triage engine.

Each entry in RED_FLAGS has:
    - id:          key that either matches a universal red flag (see
                   bot/triage/red_flags.py) or is consumed by the
                   nosology-specific rule (e.g. facial_asymmetry for COM)
    - question_ru: yes/no question (patient-facing, accessible)

Red-flag IDs used here MUST match either
    check_universal_red_flags() lookups (stridor, trismus,
    periorbital_edema, visual_disturbance, altered_consciousness,
    neck_stiffness, severe_headache, postauricular_swelling,
    protruding_pinna, facial_nerve_palsy, rapid_deterioration)
or fields the rule modules read directly (facial_asymmetry,
uvular_deviation, drooling, neck_swelling, bloody_discharge,
unilateral_symptoms, failure_to_thrive, behavioral_regression,
ah_apnea).

QUESTION ORDERING PRINCIPLE:
    General / systemic symptoms first (temperature, malaise, headache,
    sleep), then local / organ-specific symptoms. This mirrors the
    clinical review-of-systems logic and feels natural to patients.

Evidence base:
    ARS : AAO-HNS CPG 2015, EPOS 2020
    CRS : EPOS 2020 (VAS-driven control assessment)
    TP  : IDSA 2012 (Modified Centor / McIsaac)
    AOM : AAP/AAO-HNS 2013 (age-stratified + mastoiditis screen)
    COM : AAO-HNS OME 2016 + cholesteatoma / labyrinthine fistula safety
    AH  : AAO-HNS Tonsillectomy 2019 + AAP OSA 2012
    UND : lower threshold for YELLOW; anatomical-area grouping
    NENT: out-of-scope diary with universal safety screen only
"""

from __future__ import annotations

from typing import Any


# ══════════════════════════════════════════════════════════════════════
# Acute Rhinosinusitis (ARS)
# Order: temp → malaise → headache → obstruction → facial_pain →
#        discharge → smell
# ══════════════════════════════════════════════════════════════════════
ARS_PARAMS: list[dict[str, Any]] = [
    {
        "id": "ars_onset_days",
        "label_ru": "Сколько дней уже длятся симптомы?",
        "scale_type": "duration",
        "first_visit_only": True,
        "value_map": {0: 2, 1: 4, 2: 7, 3: 12},  # бакет → дни
    },
    {"id": "ars_temp", "label_ru": "Какая у вас температура?", "scale_type": "temp"},
    {
        "id": "ars_fever_duration",
        "label_ru": "Сколько дней температура держится 38°C и выше?",
        "scale_type": "fever_duration",
        "show_if": {"param": "ars_temp", "gte": 2},
    },
    {
        "id": "ars_antipyretic",
        "label_ru": "Как действует жаропонижающее?",
        "scale_type": "antipyretic_response",
        "show_if": {"param": "ars_temp", "gte": 1},
    },
    {"id": "ars_malaise", "label_ru": "Общая слабость, недомогание", "scale_type": "severity_0_3"},
    {"id": "ars_headache", "label_ru": "Головная боль", "scale_type": "severity_0_3", "is_pain": True},
    {"id": "ars_obstruction", "label_ru": "Насколько заложен нос?", "scale_type": "severity_0_3"},
    {"id": "ars_facial_pain", "label_ru": "Боль или давление в области щёк, лба, переносицы", "scale_type": "severity_0_3", "is_pain": True},
    {
        "id": "ars_analgesic",
        "label_ru": "Как действует обезболивающее?",
        "scale_type": "analgesic_response",
        "show_if": {"param": "ars_facial_pain", "gte": 2},
    },
    {"id": "ars_discharge", "label_ru": "Какие выделения из носа?", "scale_type": "discharge"},
    {"id": "ars_smell", "label_ru": "Стали хуже чувствовать запахи?", "scale_type": "severity_0_3"},
]
ARS_RED_FLAGS: list[dict[str, Any]] = [
    {"id": "periorbital_edema", "question_ru": "Есть заметный отёк вокруг одного глаза, кожа покраснела или горячая на ощупь?"},
    {"id": "visual_disturbance", "question_ru": "Стало хуже видеть, двоится в глазах или появилось ощущение давления на глаз изнутри?"},
    {"id": "neck_stiffness", "question_ru": "Шея стала жёсткой, не получается наклонить голову вперёд и прижать подбородок к груди?"},
    {"id": "severe_headache", "question_ru": "Появилась резкая, очень сильная головная боль, которой раньше не было, не похожая на обычную?", "scale": "severity"},
    {"id": "altered_consciousness", "question_ru": "Появилась заторможенность или спутанность: трудно сосредоточиться, путаете слова или слишком сонливы?"},
    {"id": "rapid_deterioration", "question_ru": "За последние сутки стало значительно хуже, чем было вчера?"},
]

# ══════════════════════════════════════════════════════════════════════
# Chronic Rhinosinusitis (CRS) — EPOS 2020 VAS-driven
# Order: temp → sleep → VAS → obstruction → discharge → facial_pain →
#        smell → unilateral → bloody
# ══════════════════════════════════════════════════════════════════════
CRS_PARAMS: list[dict[str, Any]] = [
    {"id": "crs_temp", "label_ru": "Какая у вас температура?", "scale_type": "temp"},
    {
        "id": "crs_fever_duration",
        "label_ru": "Сколько дней температура держится 38°C и выше?",
        "scale_type": "fever_duration",
        "show_if": {"param": "crs_temp", "gte": 2},
    },
    {
        "id": "crs_antipyretic",
        "label_ru": "Как действует жаропонижающее?",
        "scale_type": "antipyretic_response",
        "show_if": {"param": "crs_temp", "gte": 1},
    },
    {"id": "crs_sleep", "label_ru": "Мешают ли симптомы спать?", "scale_type": "severity_0_3"},
    {"id": "crs_vas", "label_ru": "Оцените общую тяжесть симптомов сегодня, где 0 это нет, а 10 невыносимо", "scale_type": "vas_0_10"},
    {"id": "crs_obstruction", "label_ru": "Насколько заложен нос?", "scale_type": "severity_0_3"},
    {"id": "crs_discharge", "label_ru": "Какие выделения из носа?", "scale_type": "discharge"},
    {"id": "crs_facial_pain", "label_ru": "Боль или давление в области лица", "scale_type": "severity_0_3", "is_pain": True},
    {
        "id": "crs_analgesic",
        "label_ru": "Как действует обезболивающее?",
        "scale_type": "analgesic_response",
        "show_if": {"param": "crs_facial_pain", "gte": 2},
    },
    {"id": "crs_smell", "label_ru": "Стали хуже чувствовать запахи?", "scale_type": "severity_0_3"},
    {"id": "unilateral_symptoms", "label_ru": "Симптомы только с одной стороны?", "scale_type": "binary"},
    {"id": "bloody_discharge", "label_ru": "Есть ли кровь в выделениях из носа?", "scale_type": "binary"},
    {"id": "crs_systemic_course", "label_ru": "Получали ли вы курс системных ГКС или антибиотиков за последние 2 недели?", "scale_type": "binary"},
]
CRS_RED_FLAGS: list[dict[str, Any]] = [
    {"id": "periorbital_edema", "question_ru": "Есть заметный отёк вокруг одного глаза, кожа покраснела или горячая на ощупь?"},
    {"id": "visual_disturbance", "question_ru": "Стало хуже видеть, двоится в глазах или появилось ощущение давления на глаз изнутри?"},
    {"id": "altered_consciousness", "question_ru": "Появилась заторможенность или спутанность: трудно сосредоточиться, путаете слова или слишком сонливы?"},
    {"id": "rapid_deterioration", "question_ru": "За последние сутки стало значительно хуже, чем было вчера?"},
]

# ══════════════════════════════════════════════════════════════════════
# Acute Tonsillopharyngitis (TP) — IDSA / McIsaac
# Order: temp → cough → throat_pain → dysphagia → exudate → lymph
# ══════════════════════════════════════════════════════════════════════
TP_PARAMS: list[dict[str, Any]] = [
    {
        "id": "tp_onset_days",
        "label_ru": "Сколько дней уже длятся симптомы?",
        "scale_type": "duration",
        "first_visit_only": True,
        "value_map": {0: 2, 1: 4, 2: 7, 3: 12},  # бакет → дни
    },
    {"id": "tp_temp", "label_ru": "Какая у вас температура?", "scale_type": "temp"},
    {
        "id": "tp_fever_duration",
        "label_ru": "Сколько дней температура держится 38°C и выше?",
        "scale_type": "fever_duration",
        "show_if": {"param": "tp_temp", "gte": 2},
    },
    {
        "id": "tp_antipyretic",
        "label_ru": "Как действует жаропонижающее?",
        "scale_type": "antipyretic_response",
        "show_if": {"param": "tp_temp", "gte": 1},
    },
    {"id": "tp_cough", "label_ru": "Есть ли кашель?", "scale_type": "binary"},
    {"id": "tp_throat_pain", "label_ru": "Насколько болит горло?", "scale_type": "severity_0_3", "is_pain": True},
    {
        "id": "tp_analgesic",
        "label_ru": "Как действует обезболивающее?",
        "scale_type": "analgesic_response",
        "show_if": {"param": "tp_throat_pain", "gte": 2},
    },
    {"id": "tp_dysphagia", "label_ru": "Трудно ли глотать?", "scale_type": "severity_0_3"},
    {"id": "tp_exudate", "label_ru": "Видны ли белые налёты или гной на миндалинах?", "scale_type": "binary"},
    {"id": "tp_lymph", "label_ru": "Есть увеличенные болезненные лимфоузлы на шее под челюстью?", "scale_type": "binary"},
]
TP_RED_FLAGS: list[dict[str, Any]] = [
    {"id": "trismus", "question_ru": "Не получается открыть рот так же широко, как обычно, челюсть «заклинило»?"},
    {"id": "uvular_deviation", "question_ru": "Если посмотреть в зеркало: одна сторона горла заметно больше другой или язычок смещён в сторону?"},
    {"id": "drooling", "question_ru": "Слюна скапливается, не получается её проглотить?"},
    {"id": "neck_swelling", "question_ru": "Появился плотный отёк или уплотнение на шее сбоку или спереди?"},
    {"id": "stridor", "question_ru": "Стало тяжело дышать: слышен свист, хрип или ощущение, что воздух с трудом проходит?"},
    {"id": "rapid_deterioration", "question_ru": "За последние сутки стало значительно хуже, чем было вчера?"},
]

# ══════════════════════════════════════════════════════════════════════
# Acute Otitis Media (AOM) — AAP/AAO-HNS 2013
# Order: temp → malaise → ear_pain → hearing → discharge → bilateral
# ══════════════════════════════════════════════════════════════════════
AOM_PARAMS: list[dict[str, Any]] = [
    {
        "id": "aom_onset_days",
        "label_ru": "Сколько дней уже длятся симптомы?",
        "scale_type": "duration",
        "first_visit_only": True,
        "value_map": {0: 2, 1: 4, 2: 7, 3: 12},  # бакет → дни
    },
    {"id": "aom_temp", "label_ru": "Какая у вас температура?", "scale_type": "temp"},
    {
        "id": "aom_fever_duration",
        "label_ru": "Сколько дней температура держится 38°C и выше?",
        "scale_type": "fever_duration",
        "show_if": {"param": "aom_temp", "gte": 2},
    },
    {
        "id": "aom_antipyretic",
        "label_ru": "Как действует жаропонижающее?",
        "scale_type": "antipyretic_response",
        "show_if": {"param": "aom_temp", "gte": 1},
    },
    {"id": "aom_malaise", "label_ru": "Общая слабость, недомогание", "scale_type": "severity_0_3"},
    {"id": "aom_ear_pain", "label_ru": "Насколько болит ухо?", "scale_type": "severity_0_3", "is_pain": True},
    {
        "id": "aom_analgesic",
        "label_ru": "Как действует обезболивающее?",
        "scale_type": "analgesic_response",
        "show_if": {"param": "aom_ear_pain", "gte": 2},
    },
    {"id": "aom_hearing", "label_ru": "Стали хуже слышать?", "scale_type": "severity_0_3"},
    {"id": "aom_discharge", "label_ru": "Есть ли выделения из уха? Какие?", "scale_type": "discharge"},
    {"id": "aom_bilateral", "label_ru": "Болят оба уха?", "scale_type": "binary"},
]
AOM_RED_FLAGS: list[dict[str, Any]] = [
    {"id": "postauricular_swelling", "question_ru": "Есть припухлость или покраснение на кости за ушной раковиной, болезненная при нажатии?"},
    {"id": "protruding_pinna", "question_ru": "Ушная раковина стала оттопыриваться больше обычного, это заметно при взгляде в зеркало?"},
    {"id": "facial_nerve_palsy", "question_ru": "Одна сторона лица стала менее подвижной: трудно улыбнуться, закрыть глаз или надуть щёку?"},
    {"id": "neck_stiffness", "question_ru": "Шея стала жёсткой, не получается наклонить голову вперёд и прижать подбородок к груди?"},
    {"id": "altered_consciousness", "question_ru": "Появилась заторможенность или спутанность: трудно сосредоточиться, путаете слова или слишком сонливы?"},
    {"id": "rapid_deterioration", "question_ru": "За последние сутки стало значительно хуже, чем было вчера?"},
]

# ══════════════════════════════════════════════════════════════════════
# Chronic Otitis Media / OME (COM) — AAO-HNS 2016
# Order: pain → hearing → fullness → discharge → tinnitus →
#        effusion_duration
# ══════════════════════════════════════════════════════════════════════
COM_PARAMS: list[dict[str, Any]] = [
    {"id": "com_pain", "label_ru": "Есть ли боль в ухе?", "scale_type": "severity_0_3", "is_pain": True},
    {"id": "com_hearing", "label_ru": "Стали хуже слышать больным ухом?", "scale_type": "severity_0_3"},
    {"id": "com_fullness", "label_ru": "Ощущение заложенности или давления в ухе", "scale_type": "severity_0_3"},
    {
        "id": "com_discharge",
        "label_ru": "Есть ли выделения из уха? Какие?",
        "scale_type": "discharge",
    },
    {"id": "com_tinnitus", "label_ru": "Беспокоит шум или звон в ухе?", "scale_type": "severity_0_3"},
    {
        "id": "effusion_duration",
        "label_ru": "Как давно беспокоят эти симптомы?",
        "scale_type": "ome_duration",
        "value_map": {0: 15, 1: 60, 2: 120, 3: 240},  # → days
    },
]
COM_RED_FLAGS: list[dict[str, Any]] = [
    {"id": "com_vertigo", "question_ru": "Появилось сильное головокружение, ощущение, что всё вокруг вращается (не просто лёгкая неустойчивость)?", "persist_as_symptom": True},
    {"id": "facial_asymmetry", "question_ru": "Одна сторона лица стала менее подвижной: трудно улыбнуться или закрыть глаз?", "persist_as_symptom": True},
    {"id": "postauricular_swelling", "question_ru": "Есть припухлость или покраснение на кости за ушной раковиной, болезненная при нажатии?"},
    {"id": "protruding_pinna", "question_ru": "Ушная раковина стала оттопыриваться больше обычного?"},
    {"id": "altered_consciousness", "question_ru": "Появилась заторможенность или спутанность: трудно сосредоточиться, путаете слова или слишком сонливы?"},
    {"id": "rapid_deterioration", "question_ru": "За последние сутки стало значительно хуже, чем было вчера?"},
]
# Note: com_vertigo and facial_asymmetry are both *asked as red flags*
# (because the rule treats vertigo ≥2 and facial_asymmetry==1 as RED)
# and stored back into the symptoms dict — `persist_as_symptom` flag
# tells log.py to lift the YES answer into the symptoms map with value=2
# (com_vertigo) or value=1 (facial_asymmetry) so the rule fires.

# ══════════════════════════════════════════════════════════════════════
# Adenoid Hypertrophy (AH) — pediatric OSA / SDB screen
# Order: sleep → daytime → mouth_breathing → snoring → obstruction →
#        ear_infections → sinusitis
# ══════════════════════════════════════════════════════════════════════
AH_PARAMS: list[dict[str, Any]] = [
    {"id": "ah_sleep", "label_ru": "Ребёнок плохо спит, часто просыпается?", "scale_type": "severity_0_3"},
    {"id": "ah_daytime", "label_ru": "Сонливость днём, трудности с вниманием?", "scale_type": "severity_0_3"},
    {"id": "ah_mouth_breathing", "label_ru": "Ребёнок дышит ртом?", "scale_type": "severity_0_3"},
    {
        "id": "ah_snoring",
        "label_ru": "Храпит ли ребёнок?",
        "scale_type": "severity_0_3",
    },
    {"id": "ah_obstruction", "label_ru": "Насколько заложен нос?", "scale_type": "severity_0_3"},
    {
        "id": "ah_ear_infections",
        "label_ru": "Сколько отитов было за последние полгода?",
        "scale_type": "episode_frequency",
    },
    {
        "id": "ah_sinusitis",
        "label_ru": "Сколько раз за последний год болел(а) синуситом?",
        "scale_type": "episode_frequency",
    },
]
AH_RED_FLAGS: list[dict[str, Any]] = [
    {"id": "ah_apnea", "question_ru": "Вы замечали, что ребёнок перестаёт дышать во сне, пусть даже на несколько секунд, а потом шумно вздыхает?", "persist_as_symptom": True},
    {"id": "failure_to_thrive", "question_ru": "Ребёнок плохо набирает вес или заметно отстаёт в росте по сравнению со сверстниками?", "persist_as_symptom": True},
    {"id": "behavioral_regression", "question_ru": "Появились новые проблемы с поведением, вниманием или развитием, чего раньше не было?", "persist_as_symptom": True},
    {"id": "stridor", "question_ru": "В покое (не во время простуды) слышно шумное или свистящее дыхание?"},
]

# ══════════════════════════════════════════════════════════════════════
# Undiagnosed — by anatomical area
# Order: general (temp, headache, duration) → local
# ══════════════════════════════════════════════════════════════════════
UND_NOSE_PARAMS: list[dict[str, Any]] = [
    {"id": "un_nose_temp", "label_ru": "Какая у вас температура?", "scale_type": "temp"},
    {
        "id": "un_nose_fever_duration",
        "label_ru": "Сколько дней температура держится 38°C и выше?",
        "scale_type": "fever_duration",
        "show_if": {"param": "un_nose_temp", "gte": 2},
    },
    {
        "id": "un_nose_antipyretic",
        "label_ru": "Как действует жаропонижающее?",
        "scale_type": "antipyretic_response",
        "show_if": {"param": "un_nose_temp", "gte": 1},
    },
    {"id": "un_nose_headache", "label_ru": "Головная боль", "scale_type": "severity_0_3", "is_pain": True},
    {"id": "un_nose_duration", "label_ru": "Сколько дней беспокоят симптомы?", "scale_type": "duration", "first_visit_only": True},
    {"id": "un_nose_obstruction", "label_ru": "Насколько заложен нос?", "scale_type": "severity_0_3"},
    {"id": "un_nose_discharge", "label_ru": "Какие выделения из носа?", "scale_type": "discharge"},
    {"id": "un_nose_facial_pain", "label_ru": "Боль или давление в области лица", "scale_type": "severity_0_3", "is_pain": True},
    {
        "id": "un_nose_analgesic",
        "label_ru": "Как действует обезболивающее?",
        "scale_type": "analgesic_response",
        "show_if": {"param": "un_nose_facial_pain", "gte": 2},
    },
    {"id": "un_nose_smell", "label_ru": "Стали хуже чувствовать запахи?", "scale_type": "severity_0_3"},
]

UND_THROAT_PARAMS: list[dict[str, Any]] = [
    {"id": "un_throat_temp", "label_ru": "Какая у вас температура?", "scale_type": "temp"},
    {
        "id": "un_throat_fever_duration",
        "label_ru": "Сколько дней температура держится 38°C и выше?",
        "scale_type": "fever_duration",
        "show_if": {"param": "un_throat_temp", "gte": 2},
    },
    {
        "id": "un_throat_antipyretic",
        "label_ru": "Как действует жаропонижающее?",
        "scale_type": "antipyretic_response",
        "show_if": {"param": "un_throat_temp", "gte": 1},
    },
    {"id": "un_throat_duration", "label_ru": "Сколько дней беспокоят симптомы?", "scale_type": "duration", "first_visit_only": True},
    {"id": "un_throat_pain", "label_ru": "Насколько болит горло?", "scale_type": "severity_0_3", "is_pain": True},
    {
        "id": "un_throat_analgesic",
        "label_ru": "Как действует обезболивающее?",
        "scale_type": "analgesic_response",
        "show_if": {"param": "un_throat_pain", "gte": 2},
    },
    {"id": "un_throat_dysphagia", "label_ru": "Трудно ли глотать?", "scale_type": "severity_0_3"},
    {"id": "un_throat_lymph", "label_ru": "Есть увеличенные болезненные лимфоузлы на шее?", "scale_type": "binary"},
    {"id": "un_throat_voice", "label_ru": "Изменился голос, появилась осиплость?", "scale_type": "severity_0_3"},
    {"id": "un_throat_cough", "label_ru": "Есть ли кашель?", "scale_type": "binary"},
]

UND_EAR_PARAMS: list[dict[str, Any]] = [
    {"id": "un_ear_temp", "label_ru": "Какая у вас температура?", "scale_type": "temp"},
    {
        "id": "un_ear_fever_duration",
        "label_ru": "Сколько дней температура держится 38°C и выше?",
        "scale_type": "fever_duration",
        "show_if": {"param": "un_ear_temp", "gte": 2},
    },
    {
        "id": "un_ear_antipyretic",
        "label_ru": "Как действует жаропонижающее?",
        "scale_type": "antipyretic_response",
        "show_if": {"param": "un_ear_temp", "gte": 1},
    },
    {"id": "un_ear_pain", "label_ru": "Насколько болит ухо?", "scale_type": "severity_0_3", "is_pain": True},
    {
        "id": "un_ear_analgesic",
        "label_ru": "Как действует обезболивающее?",
        "scale_type": "analgesic_response",
        "show_if": {"param": "un_ear_pain", "gte": 2},
    },
    {"id": "un_ear_hearing", "label_ru": "Стали хуже слышать?", "scale_type": "severity_0_3"},
    {"id": "un_ear_discharge", "label_ru": "Есть ли выделения из уха?", "scale_type": "discharge"},
    {"id": "un_ear_fullness", "label_ru": "Ощущение заложенности в ухе", "scale_type": "severity_0_3"},
    {"id": "un_ear_tinnitus", "label_ru": "Шум или звон в ухе", "scale_type": "severity_0_3"},
    {"id": "un_ear_dizziness", "label_ru": "Кружится голова?", "scale_type": "severity_0_3"},
]

UND_MULTIPLE_PARAMS: list[dict[str, Any]] = [
    {"id": "un_multi_temp", "label_ru": "Какая у вас температура?", "scale_type": "temp"},
    {
        "id": "un_multi_fever_duration",
        "label_ru": "Сколько дней температура держится 38°C и выше?",
        "scale_type": "fever_duration",
        "show_if": {"param": "un_multi_temp", "gte": 2},
    },
    {
        "id": "un_multi_antipyretic",
        "label_ru": "Как действует жаропонижающее?",
        "scale_type": "antipyretic_response",
        "show_if": {"param": "un_multi_temp", "gte": 1},
    },
    {"id": "un_multi_malaise", "label_ru": "Общая слабость, недомогание", "scale_type": "severity_0_3"},
    {"id": "un_multi_headache", "label_ru": "Головная боль", "scale_type": "severity_0_3", "is_pain": True},
    {"id": "un_multi_duration", "label_ru": "Сколько дней беспокоят симптомы?", "scale_type": "duration", "first_visit_only": True},
    {"id": "un_multi_nose", "label_ru": "Заложенность или выделения из носа", "scale_type": "severity_0_3"},
    {"id": "un_multi_throat", "label_ru": "Боль в горле", "scale_type": "severity_0_3", "is_pain": True},
    {"id": "un_multi_ear", "label_ru": "Боль или заложенность уха", "scale_type": "severity_0_3", "is_pain": True},
]

# ── Area-specific red flags for undiagnosed pathways ──
# Each set contains only clinically relevant flags for that area,
# plus universal safety flags (altered_consciousness, rapid_deterioration).

UND_NOSE_RED_FLAGS: list[dict[str, Any]] = [
    {"id": "periorbital_edema", "question_ru": "Есть заметный отёк вокруг одного глаза, кожа покраснела или горячая на ощупь?"},
    {"id": "visual_disturbance", "question_ru": "Стало хуже видеть, двоится в глазах или появилось ощущение давления на глаз изнутри?"},
    {"id": "bloody_discharge", "question_ru": "Есть кровянистые или бурые выделения из носа (не просто прожилки при сморкании)?", "persist_as_symptom": True},
    {"id": "neck_stiffness", "question_ru": "Шея стала жёсткой, не получается наклонить голову вперёд и прижать подбородок к груди?"},
    {"id": "altered_consciousness", "question_ru": "Появилась заторможенность или спутанность: трудно сосредоточиться, путаете слова или слишком сонливы?"},
    {"id": "rapid_deterioration", "question_ru": "За последние сутки стало значительно хуже, чем было вчера?"},
]

UND_THROAT_RED_FLAGS: list[dict[str, Any]] = [
    {"id": "stridor", "question_ru": "Стало тяжело дышать: слышен свист, хрип или ощущение, что воздух с трудом проходит?"},
    {"id": "dysphagia", "question_ru": "Совсем не получается глотать, даже слюну?", "persist_as_symptom": True},
    {"id": "trismus", "question_ru": "Не получается открыть рот так же широко, как обычно, челюсть «заклинило»?"},
    {"id": "neck_swelling", "question_ru": "Появился плотный отёк или уплотнение на шее сбоку или спереди?"},
    {"id": "altered_consciousness", "question_ru": "Появилась заторможенность или спутанность: трудно сосредоточиться, путаете слова или слишком сонливы?"},
    {"id": "rapid_deterioration", "question_ru": "За последние сутки стало значительно хуже, чем было вчера?"},
]

UND_EAR_RED_FLAGS: list[dict[str, Any]] = [
    {"id": "postauricular_swelling", "question_ru": "Есть припухлость или покраснение на кости за ушной раковиной, болезненная при нажатии?"},
    {"id": "facial_nerve_palsy", "question_ru": "Одна сторона лица стала менее подвижной: трудно улыбнуться, закрыть глаз или надуть щёку?"},
    {"id": "bloody_discharge", "question_ru": "Есть кровянистые выделения из уха (не после чистки)?", "persist_as_symptom": True},
    {"id": "altered_consciousness", "question_ru": "Появилась заторможенность или спутанность: трудно сосредоточиться, путаете слова или слишком сонливы?"},
    {"id": "rapid_deterioration", "question_ru": "За последние сутки стало значительно хуже, чем было вчера?"},
]

UND_MULTIPLE_RED_FLAGS: list[dict[str, Any]] = [
    {"id": "stridor", "question_ru": "Стало тяжело дышать: слышен свист, хрип или ощущение, что воздух с трудом проходит?"},
    {"id": "periorbital_edema", "question_ru": "Есть заметный отёк вокруг одного глаза, кожа покраснела или горячая на ощупь?"},
    {"id": "visual_disturbance", "question_ru": "Стало хуже видеть, двоится в глазах или появилось ощущение давления на глаз изнутри?"},
    {"id": "dysphagia", "question_ru": "Совсем не получается глотать, даже слюну?", "persist_as_symptom": True},
    {"id": "bloody_discharge", "question_ru": "Есть кровянистые выделения из носа или уха (не просто прожилки при сморкании)?", "persist_as_symptom": True},
    {"id": "facial_nerve_palsy", "question_ru": "Одна сторона лица стала менее подвижной: трудно улыбнуться, закрыть глаз или надуть щёку?"},
    {"id": "altered_consciousness", "question_ru": "Появилась заторможенность или спутанность: трудно сосредоточиться, путаете слова или слишком сонливы?"},
    {"id": "rapid_deterioration", "question_ru": "За последние сутки стало значительно хуже, чем было вчера?"},
]

# Treat the dysphagia YES as severity=3 so universal check fires.
UND_RED_FLAG_VALUE_OVERRIDES = {"dysphagia": 3}

# ══════════════════════════════════════════════════════════════════════
# Non-ENT (problem outside ENT scope) — minimal diary, generic safety
# Order: temp → VAS → sleep → activity → duration
# ══════════════════════════════════════════════════════════════════════
NON_ENT_PARAMS: list[dict[str, Any]] = [
    {"id": "ne_temp", "label_ru": "Какая у вас температура?", "scale_type": "temp"},
    {"id": "ne_overall_severity", "label_ru": "Оцените общую тяжесть симптомов сегодня, где 0 это нет, а 10 невыносимо", "scale_type": "vas_0_10"},
    {"id": "ne_sleep", "label_ru": "Мешают ли симптомы спать?", "scale_type": "severity_0_3"},
    {"id": "ne_activity", "label_ru": "Приходится ли ограничивать обычные дела?", "scale_type": "severity_0_3"},
    {"id": "ne_duration", "label_ru": "Сколько дней беспокоят симптомы?", "scale_type": "duration", "first_visit_only": True},
]
# Only life-threatening signs here — since the app declared it doesn't
# analyse ENT-specific red flags for this pathway.
NON_ENT_RED_FLAGS: list[dict[str, Any]] = [
    {"id": "stridor", "question_ru": "Стало тяжело дышать: слышен свист, хрип или ощущение, что воздух с трудом проходит?"},
    {"id": "altered_consciousness", "question_ru": "Появилась заторможенность или спутанность: трудно сосредоточиться, путаете слова или слишком сонливы?"},
    {"id": "rapid_deterioration", "question_ru": "За последние сутки стало значительно хуже, чем было вчера?"},
    {"id": "severe_chest_pain", "question_ru": "Появилась сильная боль в груди, или стало тяжело дышать в покое (без физической нагрузки)?", "persist_as_symptom": True},
]
NON_ENT_RED_FLAG_VALUE_OVERRIDES = {"severe_chest_pain": 1}


# ══════════════════════════════════════════════════════════════════════
# Registry
# ══════════════════════════════════════════════════════════════════════

PARAMS_BY_NOSOLOGY: dict[str, list[dict[str, Any]]] = {
    "ars": ARS_PARAMS,
    "crs": CRS_PARAMS,
    "tonsillopharyngitis": TP_PARAMS,
    "aom": AOM_PARAMS,
    "com": COM_PARAMS,
    "adenoid_hypertrophy": AH_PARAMS,
    "undiagnosed_nose": UND_NOSE_PARAMS,
    "undiagnosed_throat": UND_THROAT_PARAMS,
    "undiagnosed_ear": UND_EAR_PARAMS,
    "undiagnosed_multiple": UND_MULTIPLE_PARAMS,
    "non_ent": NON_ENT_PARAMS,
}

RED_FLAGS_BY_NOSOLOGY: dict[str, list[dict[str, Any]]] = {
    "ars": ARS_RED_FLAGS,
    "crs": CRS_RED_FLAGS,
    "tonsillopharyngitis": TP_RED_FLAGS,
    "aom": AOM_RED_FLAGS,
    "com": COM_RED_FLAGS,
    "adenoid_hypertrophy": AH_RED_FLAGS,
    "undiagnosed_nose": UND_NOSE_RED_FLAGS,
    "undiagnosed_throat": UND_THROAT_RED_FLAGS,
    "undiagnosed_ear": UND_EAR_RED_FLAGS,
    "undiagnosed_multiple": UND_MULTIPLE_RED_FLAGS,
    "non_ent": NON_ENT_RED_FLAGS,
}

# Red-flag IDs whose YES answer should be lifted into symptoms dict with
# a non-binary value (see persist_as_symptom flag in the entries above).
# This matters when a nosology rule expects e.g. com_vertigo ≥2 to fire.
RED_FLAG_VALUE_OVERRIDES: dict[str, int] = {
    "com_vertigo": 2,
    "facial_asymmetry": 1,
    "ah_apnea": 1,
    "failure_to_thrive": 1,
    "behavioral_regression": 1,
    **UND_RED_FLAG_VALUE_OVERRIDES,
    **NON_ENT_RED_FLAG_VALUE_OVERRIDES,
}


def get_params(nosology: str) -> list[dict[str, Any]]:
    """Return SYMPTOM_PARAMS for a given nosology, or [] if unknown."""
    return PARAMS_BY_NOSOLOGY.get(nosology, [])


def get_red_flags(nosology: str) -> list[dict[str, Any]]:
    """Return RED_FLAGS for a given nosology, or [] if unknown."""
    return RED_FLAGS_BY_NOSOLOGY.get(nosology, [])


def apply_value_maps(
    nosology: str,
    symptom_values: dict[str, Any],
) -> dict[str, Any]:
    """Convert raw keyboard values to the units the rule module expects.

    E.g. for COM, `effusion_duration` is collected as a 0–3 bucket but
    the rule checks `>= 84` days — value_map on the param converts it.
    """
    mapped = dict(symptom_values)
    for param in get_params(nosology):
        vmap = param.get("value_map")
        if not vmap:
            continue
        pid = param["id"]
        if pid in mapped and mapped[pid] in vmap:
            mapped[pid] = vmap[mapped[pid]]
    return mapped


# Параметры, которые измеряют срок, а не тяжесть, и потому в сумму
# баллов не входят. После value_map они приходят в днях: экссудат
# дольше полугода это 240, и в сумме симптомов такому числу не место.
NON_SEVERITY_SUFFIXES = ("_onset_days", "_duration")


def compute_composite_score(symptom_values: dict[str, Any]) -> int:
    """Суммарный балл тяжести по ответам дневника.

    Считаются только числовые ответы про выраженность симптомов.
    Пропускаются строки (возрастная группа), сроки и ответы «сложно
    оценить» (-1), чтобы балл оставался сравнимым между записями.
    """
    return sum(
        v for k, v in symptom_values.items()
        if isinstance(v, (int, float))
        and v >= 0
        and not k.endswith(NON_SEVERITY_SUFFIXES)
    )
