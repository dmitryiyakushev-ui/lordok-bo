# ЛОРдок — Clinical Decision Tree

> Rule-based triage system for chronic and acute ENT conditions.
> NOT a diagnostic tool. Determines urgency of medical consultation only.

**Evidence base:** AAO-HNS CPG, EPOS 2020, IDSA 2012, AAP 2013, ARIA 2020–2023.
**Explicitly excluded:** КР МЗ РФ (Russian clinical recommendations).

**Version:** 1.0 (2026-04-14)
**Clinical author:** Dmitrii Iakushev, MD — ENT surgeon, 10+ years clinical experience

---

## Architecture Overview

```
User input (daily symptom diary)
        │
        ▼
┌─────────────────────┐
│  RED FLAG SCREEN     │  ← Universal + nosology-specific
│  (always first)      │     If triggered → RED immediately
└─────────┬───────────┘
          │ no red flags
          ▼
┌─────────────────────┐
│  NOSOLOGY-SPECIFIC  │  ← Per-condition decision tree
│  TRIAGE RULES       │     Severity scoring + trend analysis
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  TREND ANALYSIS     │  ← 3-day rolling comparison
│  (temporal overlay) │     Worsening/stable/improving
└─────────┬───────────┘
          │
          ▼
    🟢 / 🟡 / 🔴
```

### Triage Levels

| Level | Label (RU) | Label (EN) | Meaning |
|-------|-----------|------------|---------|
| 🟢 | Наблюдайте | Observe | Stable or improving. Continue current management. |
| 🟡 | Запишитесь к врачу | Schedule visit | Worsening trend or concerning pattern. Visit within 1–3 days. |
| 🔴 | Обратитесь сегодня | See doctor today | Red flags or severe/rapid deterioration. Same-day consultation. |

---

## 0. Universal Red Flags

These override ALL nosology-specific logic. If ANY is present → 🔴 immediately.

| Red Flag | Clinical Basis | Guideline |
|----------|---------------|-----------|
| Temperature ≥ 39.5 °C | Risk of serious bacterial infection or complication | EPOS 2020, AAP 2013 |
| Periorbital edema or erythema | Orbital complication of sinusitis (subperiosteal abscess) | AAO-HNS 2015, EPOS 2020 |
| Visual disturbance (diplopia, vision loss) | Orbital apex syndrome, cavernous sinus thrombosis | EPOS 2020 |
| Severe headache + neck stiffness | Meningeal signs — intracranial complication | EPOS 2020 |
| Altered consciousness / confusion | Intracranial abscess, sepsis | EPOS 2020, AAP 2013 |
| Postauricular swelling + protruding pinna | Mastoiditis | AAP 2013 |
| Facial nerve palsy (asymmetric face) | COM complication, cholesteatoma, necrotizing OE | AAO-HNS OME 2016 |
| Inability to swallow / drooling | Peritonsillar abscess, deep neck space infection | IDSA 2012 |
| Trismus (cannot open mouth > 2 cm) | Peritonsillar or parapharyngeal abscess | IDSA 2012 |
| Stridor / respiratory difficulty | Airway compromise — any etiology | Universal |
| Rapid deterioration over < 24 hours | Aggressive infection, necrotizing process | Universal |

**Bot implementation:** Before running any nosology-specific logic, check universal red flags.
Red flag questions are embedded at the end of each diary entry as binary (yes/no).

---

## 1. Acute Rhinosinusitis (ARS)

### 1.1 Guidelines
- **AAO-HNS CPG Adult Sinusitis** (Rosenfeld RM et al., 2015). DOI: 10.1177/0194599815572097
- **EPOS 2020** (Fokkens WJ et al., Rhinology, 2020). PMID: 32226949

### 1.2 Symptom Parameters

| Parameter | ID | Scale | Clinical Rationale |
|-----------|-----|-------|-------------------|
| Nasal obstruction/congestion | `ars_obstruction` | 0–3 | Cardinal symptom per EPOS |
| Facial pain/pressure | `ars_facial_pain` | 0–3 | Localization suggests affected sinus |
| Nasal discharge (quality) | `ars_discharge` | 0=none, 1=clear, 2=yellow, 3=green/purulent | Purulent discharge = ABRS criterion (EPOS) |
| Smell reduction | `ars_smell` | 0–3 | EPOS core symptom |
| Temperature | `ars_temp` | 0=<37.5, 1=37.5–38, 2=38–39, 3=>39 | Fever >38°C = ABRS criterion (EPOS ≥3 criteria) |
| Headache | `ars_headache` | 0–3 | Frontal headache — complication screening |
| General malaise | `ars_malaise` | 0–3 | Overall illness severity |

**Composite severity score:** Sum of all parameters (range 0–21)

### 1.3 Triage Rules

#### Key clinical thresholds (AAO-HNS 2015 + EPOS 2020):

**Viral vs Bacterial differentiation:**
- Symptoms < 10 days AND improving → likely viral (AAO-HNS: "watchful waiting")
- Symptoms ≥ 10 days without improvement → meets ABRS criterion (AAO-HNS)
- "Double sickening": initial improvement then worsening → ABRS criterion (AAO-HNS, EPOS)
- ≥ 3 of: fever ≥38°C, severe facial pain, purulent discharge, double sickening, elevated inflammatory markers → probable ABRS (EPOS 2020)

#### Decision logic:

```
IF any universal red flag → 🔴

IF symptom_duration < 10 days:
    IF trend == improving AND severity_score ≤ 7:
        → 🟢 "Symptoms typical of viral URI. Continue observation."
    IF trend == stable AND severity_score ≤ 10:
        → 🟢 "Monitor for improvement. If no change by day 10, schedule visit."
    IF trend == worsening OR severity_score > 10:
        → 🟡 "Symptoms worsening. Schedule ENT visit within 2–3 days."
    IF double_sickening == true:
        → 🟡 "Worsening after initial improvement suggests bacterial infection. Schedule visit."

IF symptom_duration >= 10 days:
    IF trend == improving:
        → 🟢 "Prolonged but improving. Continue current management."
    IF trend == stable OR worsening:
        → 🟡 "Symptoms ≥10 days without improvement — meets criteria for medical evaluation (AAO-HNS)."

IF ars_temp >= 2 (38–39°C) AND ars_facial_pain >= 2 AND ars_discharge == 3:
    → 🟡 (upgrade to immediate if temp == 3)

IF ars_temp == 3 (>39°C) AND (ars_facial_pain >= 2 OR ars_headache == 3):
    → 🔴 "High fever with severe facial pain/headache. Rule out complications."
```

### 1.4 Nosology-Specific Red Flags

| Sign | Indicates | Action |
|------|-----------|--------|
| Periorbital swelling/erythema | Orbital complication | 🔴 Emergency |
| Severe unilateral facial swelling | Abscess | 🔴 Emergency |
| Visual changes | Orbital apex / cavernous sinus | 🔴 Emergency |
| Frontal severe headache + high fever | Frontal sinusitis complication | 🔴 Emergency |
| Bloody nasal discharge (unilateral, persistent) | Neoplastic process (not for acute triage, but flag) | 🟡 Schedule visit |

---

## 2. Chronic Rhinosinusitis (CRS)

### 2.1 Guidelines
- **EPOS 2020** (Fokkens WJ et al., Rhinology, 2020). PMID: 32226949
- CRS defined as symptoms ≥ 12 weeks (EPOS criterion)

### 2.2 Symptom Parameters

| Parameter | ID | Scale | Clinical Rationale |
|-----------|-----|-------|-------------------|
| Nasal obstruction | `crs_obstruction` | 0–3 | EPOS core symptom |
| Nasal discharge / postnasal drip | `crs_discharge` | 0–3 | EPOS core symptom |
| Facial pain/pressure | `crs_facial_pain` | 0–3 | EPOS core symptom |
| Smell reduction | `crs_smell` | 0–3 | EPOS core symptom; key for CRSwNP |
| Sleep quality impact | `crs_sleep` | 0–3 | Quality of life metric |
| Overall severity (VAS analog) | `crs_vas` | 0–10 | EPOS controlled/uncontrolled threshold |

### 2.3 Triage Rules

#### Key clinical threshold (EPOS 2020):
- **VAS ≤ 3** → controlled disease
- **VAS > 3.5** → uncontrolled disease (strong predictor)
- Monitoring focuses on **trend** (stable baseline vs. acute exacerbation)

```
IF any universal red flag → 🔴

# Acute exacerbation on chronic background
IF crs_vas > 5 AND trend == worsening_3d:
    IF crs_temp >= 2 OR crs_discharge == 3 (purulent):
        → 🟡 "Acute exacerbation of CRS. Schedule visit within 1–2 days."
    ELSE:
        → 🟡 "Symptoms worsening. Consider scheduling visit."

# Controlled disease
IF crs_vas <= 3 AND trend == stable:
    → 🟢 "Disease well controlled (EPOS criteria). Continue current therapy."

# Uncontrolled but stable
IF crs_vas > 3.5 AND trend == stable:
    → 🟡 "Disease uncontrolled per EPOS criteria. Discuss therapy adjustment at next visit."

# Improving
IF trend == improving:
    → 🟢 "Improving trend. Continue current management."

# New alarming symptoms
IF crs_smell == 3 (complete anosmia, new onset):
    → 🟡 "New-onset complete anosmia. Schedule evaluation."
IF unilateral_symptoms AND bloody_discharge:
    → 🟡 "Unilateral symptoms with blood — schedule evaluation to rule out other pathology."
```

---

## 3. Acute Tonsillopharyngitis

### 3.1 Guidelines
- **IDSA GAS Pharyngitis** (Shulman ST et al., Clin Infect Dis, 2012). DOI: 10.1093/cid/cis629
- **Modified Centor Score (McIsaac)** — validated clinical prediction rule

### 3.2 Symptom Parameters

| Parameter | ID | Scale | Clinical Rationale |
|-----------|-----|-------|-------------------|
| Sore throat severity | `tp_throat_pain` | 0–3 | Chief complaint |
| Difficulty swallowing | `tp_dysphagia` | 0–3 | Severity marker; extreme = abscess |
| Fever | `tp_temp` | 0=no, 1=<38, 2=38–39, 3=>39 | Centor criterion: fever >38°C |
| Tonsillar exudate | `tp_exudate` | 0=no, 1=yes | Centor criterion |
| Cervical lymphadenopathy | `tp_lymph` | 0=no, 1=yes | Centor criterion: anterior cervical |
| Cough present | `tp_cough` | 0=no, 1=yes | Centor: ABSENCE of cough scores +1 |
| Age group | `tp_age` | categorical | McIsaac modifier |

### 3.3 McIsaac Score Calculation

```python
score = 0
if tp_temp >= 2:        score += 1   # Fever > 38°C
if tp_exudate == 1:     score += 1   # Tonsillar swelling/exudate
if tp_lymph == 1:       score += 1   # Tender anterior cervical LAD
if tp_cough == 0:       score += 1   # Absence of cough

# Age modifier (McIsaac)
if age < 15:            score += 1
elif age >= 45:         score -= 1
# age 15-44: no modifier

# Range: -1 to 5
```

### 3.4 Triage Rules

#### Key thresholds (IDSA 2012):
- McIsaac 0–1: Low probability GAS (< 10%), no testing recommended
- McIsaac 2–3: Moderate probability, recommend RADT/culture
- McIsaac 4–5: High probability GAS (40–60%), recommend testing + empiric treatment

```
IF any universal red flag → 🔴

# Peritonsillar abscess screening (ALWAYS check)
IF tp_dysphagia == 3 AND (trismus OR uvular_deviation OR drooling):
    → 🔴 "Signs consistent with peritonsillar abscess. Urgent evaluation."

IF tp_dysphagia == 3 AND neck_swelling:
    → 🔴 "Severe dysphagia with neck swelling. Rule out deep neck infection."

# McIsaac-based triage
IF mcisaac_score <= 1:
    IF trend == improving OR stable:
        → 🟢 "Low probability of bacterial pharyngitis. Symptomatic treatment."
    IF symptom_duration > 7 days:
        → 🟡 "Prolonged symptoms. Schedule evaluation."

IF mcisaac_score == 2 OR mcisaac_score == 3:
    → 🟡 "Moderate probability of streptococcal pharyngitis. Recommend testing (RADT)."

IF mcisaac_score >= 4:
    → 🟡 "High probability of streptococcal pharyngitis. Schedule visit for testing and treatment."
    IF tp_temp == 3 (>39°C):
        → 🔴 (upgrade) "High fever + high McIsaac score. See doctor today."

# Duration-based
IF symptom_duration > 5 days AND trend != improving:
    → 🟡 "Symptoms persisting > 5 days without improvement. Evaluation recommended."
```

---

## 4. Acute Otitis Media (AOM)

### 4.1 Guidelines
- **AAP/AAO-HNS Clinical Practice Guideline** (Lieberthal AS et al., Pediatrics, 2013). PMID: 23536528
- Primary focus: children, but applicable to adults with AOM

### 4.2 Symptom Parameters

| Parameter | ID | Scale | Clinical Rationale |
|-----------|-----|-------|-------------------|
| Ear pain severity | `aom_ear_pain` | 0–3 | Chief complaint; severity determines management |
| Hearing reduction | `aom_hearing` | 0–3 | Indicates MEE |
| Ear discharge | `aom_discharge` | 0=none, 1=serous, 2=mucoid, 3=purulent | Otorrhea = severe AOM criterion |
| Fever | `aom_temp` | 0=<37.5, 1=37.5–38, 2=38–39, 3=>39 | Severity stratification |
| Bilateral involvement | `aom_bilateral` | 0=no/unknown, 1=yes | Bilateral = more severe (AAP) |
| General malaise / irritability | `aom_malaise` | 0–3 | Especially important in children |
| Age group | `aom_age` | categorical | <6mo, 6-23mo, ≥2y — drives watchful waiting |

### 4.3 Triage Rules

#### Key thresholds (AAP 2013):
- **Watchful waiting** appropriate if: age ≥ 2 years + unilateral + mild symptoms (pain ≤ 1) + no otorrhea + temp < 39°C
- **Immediate treatment** if: age < 6 months, bilateral in 6–23 months, otorrhea, severe symptoms
- Safety net: reassess if no improvement in 48–72 hours

```
IF any universal red flag → 🔴

# Mastoiditis screening
IF postauricular_swelling OR protruding_pinna:
    → 🔴 "Signs of mastoiditis. Emergency evaluation."

# Age-based severity
IF aom_age == "<6 months" AND aom_temp >= 1:
    → 🔴 "Infant < 6 months with fever and ear symptoms. Immediate evaluation."

IF aom_age == "6-23 months" AND aom_bilateral == 1:
    → 🟡 "Bilateral AOM in infant — medical evaluation recommended (AAP)."

# Severity scoring
IF aom_discharge == 3 (purulent otorrhea):
    → 🟡 "Purulent ear discharge. Schedule visit within 24 hours."

IF aom_ear_pain >= 2 AND aom_temp >= 2:
    → 🟡 "Moderate-severe ear pain with fever. Medical evaluation recommended."

IF aom_ear_pain == 3 OR aom_temp == 3:
    → 🔴 "Severe ear pain or high fever. See doctor today."

# Watchful waiting criteria (AAP 2013)
IF aom_age == ">=2 years" AND aom_bilateral == 0 AND aom_ear_pain <= 1 AND aom_temp <= 1 AND aom_discharge == 0:
    → 🟢 "Mild unilateral symptoms, age ≥2. Observation appropriate per AAP guideline."
    # Safety net: "If no improvement in 48–72 hours, schedule visit."

# Duration-based
IF symptom_duration > 48 hours AND trend != improving:
    → 🟡 "No improvement after 48 hours. Reassessment recommended (AAP safety net)."
```

---

## 5. Chronic Otitis Media (COM) / Otitis Media with Effusion (OME)

### 5.1 Guidelines
- **AAO-HNS OME Guideline** (Rosenfeld RM et al., 2016). DOI: 10.1177/0194599815623467
- Covers both OME (effusion without acute infection) and chronic suppurative OM

### 5.2 Symptom Parameters

| Parameter | ID | Scale | Clinical Rationale |
|-----------|-----|-------|-------------------|
| Hearing reduction | `com_hearing` | 0–3 | Primary impact of OME/COM |
| Ear fullness / pressure | `com_fullness` | 0–3 | Effusion symptom |
| Ear discharge | `com_discharge` | 0=none, 1=serous, 2=mucoid, 3=purulent/fetid | Active COM indicator; fetid = cholesteatoma |
| Tinnitus | `com_tinnitus` | 0–3 | Inner ear involvement marker |
| Dizziness / vertigo | `com_vertigo` | 0–3 | Labyrinthine complication = RED |
| Ear pain | `com_pain` | 0–3 | Acute exacerbation or complication |

### 5.3 Triage Rules

#### Key thresholds (AAO-HNS OME 2016):
- OME persisting ≥ 3 months → hearing evaluation recommended
- Children at developmental risk → earlier intervention regardless of duration
- Cholesteatoma signs (fetid discharge, granulation) → urgent referral

```
IF any universal red flag → 🔴

# Dangerous complications
IF com_vertigo >= 2:
    → 🔴 "Vertigo with chronic ear disease — possible labyrinthine fistula. Urgent evaluation."

IF com_discharge == 3 (fetid/bloody):
    → 🔴 "Foul-smelling or bloody discharge. Rule out cholesteatoma. Urgent evaluation."

IF facial_asymmetry:
    → 🔴 "Facial nerve involvement. Emergency evaluation."

# Active discharge (CSOM)
IF com_discharge >= 2 AND com_pain >= 2:
    → 🟡 "Active ear discharge with pain. Schedule visit within 1–2 days."

IF com_discharge >= 1 (new discharge after dry period):
    → 🟡 "New ear discharge. Schedule evaluation."

# OME monitoring
IF com_hearing >= 2 AND effusion_duration >= 3 months:
    → 🟡 "Hearing loss with effusion ≥ 3 months. Audiometry recommended (AAO-HNS)."

IF com_hearing <= 1 AND effusion_duration < 3 months:
    → 🟢 "Mild symptoms, effusion < 3 months. Watchful waiting appropriate (AAO-HNS)."
    # Safety net: recheck every 3–6 months

# Stable chronic
IF com_discharge == 0 AND trend == stable:
    → 🟢 "Dry ear, stable. Continue follow-up schedule."

IF com_tinnitus >= 2 (new or worsening):
    → 🟡 "New or worsening tinnitus. Schedule audiological evaluation."
```

---

## 6. Adenoid Hypertrophy

### 6.1 Guidelines
- **AAO-HNS Clinical Practice Guideline: Tonsillectomy in Children** (Mitchell RB et al., 2019). DOI: 10.1177/0194599818801757
- **Pediatric Sleep-Disordered Breathing** — PSQ (Pediatric Sleep Questionnaire), AAO-HNS recommendations
- **AAP Technical Report: Diagnosis and Management of Childhood OSA** (2012, reaffirmed)

### 6.2 Symptom Parameters

| Parameter | ID | Scale | Clinical Rationale |
|-----------|-----|-------|-------------------|
| Nasal obstruction severity | `ah_obstruction` | 0–3 | Primary symptom |
| Mouth breathing | `ah_mouth_breathing` | 0–3 | Consequence of nasal obstruction |
| Snoring | `ah_snoring` | 0=no, 1=occasional, 2=most nights, 3=every night/loud | SDB screening |
| Observed apnea episodes | `ah_apnea` | 0=no, 1=suspected, 2=confirmed by parent | Critical — OSA indicator |
| Sleep quality | `ah_sleep` | 0–3 | Restless sleep, frequent awakenings |
| Daytime sleepiness / behavioral issues | `ah_daytime` | 0–3 | Consequence of SDB |
| Recurrent ear infections (past 6 mo) | `ah_ear_infections` | 0=0, 1=1–2, 2=3–4, 3=5+ | Adenoid-related OME |
| Recurrent rhinosinusitis (past 12 mo) | `ah_sinusitis` | 0=0, 1=1–2, 2=3–4, 3=5+ | Adenoid as reservoir |

### 6.3 Triage Rules

#### Key thresholds:
- Observed apneic episodes → urgent evaluation (AAO-HNS 2019)
- PSG recommended before adenotonsillectomy if age < 2 or comorbidities
- Snoring + daytime symptoms = moderate-to-severe SDB screening

```
IF any universal red flag → 🔴

# Sleep apnea — urgent
IF ah_apnea >= 1 (parent-observed apnea):
    → 🔴 "Observed apneic episodes during sleep. Urgent ENT evaluation + PSG recommended."

IF ah_snoring == 3 AND ah_daytime >= 2:
    → 🟡 "Loud nightly snoring with daytime symptoms. Evaluate for obstructive sleep apnea."

IF ah_snoring == 3 AND ah_sleep >= 2 AND ah_apnea == 0:
    → 🟡 "Significant snoring with poor sleep quality. Schedule ENT evaluation."

# Moderate symptoms
IF ah_obstruction >= 2 AND ah_mouth_breathing >= 2:
    → 🟡 "Significant nasal obstruction with mouth breathing. Schedule evaluation."

IF ah_ear_infections >= 2 (3+ episodes in 6 months):
    → 🟡 "Recurrent ear infections. Evaluate adenoid contribution."

IF ah_sinusitis >= 2 (3+ episodes in 12 months):
    → 🟡 "Recurrent sinusitis. Evaluate adenoid hypertrophy."

# Mild / stable
IF ah_obstruction <= 1 AND ah_snoring <= 1 AND ah_sleep <= 1:
    → 🟢 "Mild symptoms. Continue observation."

# Growth/development concern
IF failure_to_thrive OR behavioral_regression:
    → 🔴 "Growth or developmental concern with SDB symptoms. Urgent evaluation."
```

---

## 7. Trend Analysis Module

Applied as an overlay on top of nosology-specific scores.

### 7.1 Methodology

- **Window:** Last 3 completed diary entries
- **Comparison:** Current entry composite score vs. mean of previous 3 entries
- **Delta threshold:** ≥ 20% increase = worsening; ≥ 20% decrease = improving

### 7.2 Trend Categories

| Trend | Definition | Modifier |
|-------|-----------|----------|
| `improving` | Score decreased ≥ 20% vs 3-day mean | May downgrade 🟡 → 🟢 |
| `stable` | Score within ± 20% of 3-day mean | No change |
| `worsening` | Score increased ≥ 20% vs 3-day mean | May upgrade 🟢 → 🟡 |
| `worsening_3d` | Score increased for 3 consecutive days | Stronger upgrade signal |

### 7.3 Trend Override Rules

```
# Trend can modify the nosology-specific result:
IF nosology_result == 🟢 AND trend == worsening_3d:
    → 🟡 "Stable overall but worsening for 3 consecutive days. Monitor closely."

IF nosology_result == 🟡 AND trend == improving:
    → 🟢 "Concerning pattern but improving. Continue current management."
    # Only if no red flags and severity_score below threshold

IF nosology_result == 🟡 AND trend == worsening_3d:
    → 🟡 (keep, but add urgency to message: "within 24 hours")

# 🔴 is NEVER downgraded by trend
IF nosology_result == 🔴:
    → 🔴 (always)
```

---

## 8. Double Sickening Detection (ARS-specific)

Per AAO-HNS 2015 and EPOS 2020, "double sickening" is a key ABRS criterion.

### Detection Algorithm

```
IF nosology == ARS AND symptom_duration >= 5 days:
    scores = last 7 days of composite scores
    IF has_valley(scores):
        # Found a pattern: high → low → high
        valley_idx = find_valley(scores)
        post_valley_scores = scores[valley_idx:]
        if len(post_valley_scores) >= 2 AND all_increasing(post_valley_scores):
            double_sickening = True
            → 🟡 "Pattern consistent with secondary bacterial infection (AAO-HNS)."
```

---

## 9. Safety Net Messages

Every triage result includes a safety net instruction:

| Level | Safety Net |
|-------|-----------|
| 🟢 | "Продолжайте вести дневник. Если симптомы усилятся — я сообщу." |
| 🟡 | "Рекомендую записаться к ЛОР-врачу в ближайшие 1–3 дня. Могу подготовить PDF-сводку для приёма." |
| 🔴 | "Обратитесь к врачу сегодня. Если состояние ухудшается быстро — вызовите скорую помощь." |

---

## 10. Guideline Reference Table

| Guideline | Authors | Year | Journal | DOI/PMID |
|-----------|---------|------|---------|----------|
| AAO-HNS CPG: Adult Sinusitis | Rosenfeld RM et al. | 2015 | Otolaryngol Head Neck Surg | 10.1177/0194599815572097 |
| EPOS 2020 | Fokkens WJ et al. | 2020 | Rhinology | PMID: 32226949 |
| IDSA GAS Pharyngitis | Shulman ST et al. | 2012 | Clin Infect Dis | 10.1093/cid/cis629 |
| AAP/AAO-HNS AOM | Lieberthal AS et al. | 2013 | Pediatrics | PMID: 23536528 |
| AAO-HNS OME | Rosenfeld RM et al. | 2016 | Otolaryngol Head Neck Surg | 10.1177/0194599815623467 |
| AAO-HNS Tonsillectomy in Children | Mitchell RB et al. | 2019 | Otolaryngol Head Neck Surg | 10.1177/0194599818801757 |
| ARIA 2020 update | Bousquet J et al. | 2020 | Allergy | 10.1111/all.14049 |
| ICAR Allergic Rhinitis 2023 | Wise SK et al. | 2023 | Int Forum Allergy Rhinol | 10.1002/alr.23090 |
| AAP OSA in Children (Tech Report) | Marcus CL et al. | 2012 | Pediatrics | 10.1542/peds.2012-1672 |

---

## 11. Disclaimer (embedded in every triage output)

> ЛОРдок — информационный сервис для мониторинга симптомов.
> Не является медицинским изделием.
> Не предназначен для постановки диагноза или назначения лечения.
> При ухудшении состояния всегда обращайтесь к врачу.
