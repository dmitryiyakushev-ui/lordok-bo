"""
Clinical verification test suite for ЛОРдок triage system.

Tests 20 clinical scenarios against international guidelines:
- AAO-HNS CPG for rhinosinusitis and otitis
- EPOS 2020 for chronic rhinosinusitis
- IDSA for tonsillopharyngitis (McIsaac)
- AAP for pediatric otitis media
"""

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bot.models.symptom import SymptomEntry
from bot.triage.engine import run_triage, LEVEL_GREEN, LEVEL_YELLOW, LEVEL_RED


def create_symptom_entry(
    nosology: str,
    symptoms: dict,
    recorded_at: datetime,
    composite_score: int = None,
) -> SymptomEntry:
    """Helper to create SymptomEntry objects."""
    if composite_score is None:
        composite_score = sum(v for v in symptoms.values() if isinstance(v, int))

    return SymptomEntry(
        user_id="test_user",
        nosology=nosology,
        symptoms=symptoms,
        composite_score=composite_score,
        recorded_at=recorded_at,
    )


# =============================================================================
# TEST SCENARIOS
# =============================================================================

class TestARS:
    """Acute Rhinosinusitis scenarios (AAO-HNS ABRS criteria)."""

    def test_scenario_1_day3_mild_improving(self):
        """
        Scenario 1: Day 3, mild symptoms (score 5), improving
        Expected: GREEN
        Rationale: <10 days, improving trend, low score
        """
        now = datetime.now(timezone.utc)
        day1 = now - timedelta(days=3)
        day2 = now - timedelta(days=2)
        day3 = now

        entry1 = create_symptom_entry(
            "ars",
            {
                "ars_obstruction": 2,
                "ars_facial_pain": 1,
                "ars_discharge": 1,
                "ars_smell": 1,
                "ars_temp": 0,
                "ars_headache": 0,
                "ars_malaise": 0,
            },
            day1,
            composite_score=5,
        )
        entry2 = create_symptom_entry(
            "ars",
            {
                "ars_obstruction": 1,
                "ars_facial_pain": 1,
                "ars_discharge": 1,
                "ars_smell": 1,
                "ars_temp": 0,
                "ars_headache": 0,
                "ars_malaise": 0,
            },
            day2,
            composite_score=4,
        )
        entry3 = create_symptom_entry(
            "ars",
            {
                "ars_obstruction": 1,
                "ars_facial_pain": 0,
                "ars_discharge": 1,
                "ars_smell": 1,
                "ars_temp": 0,
                "ars_headache": 0,
                "ars_malaise": 0,
            },
            day3,
            composite_score=3,
        )

        result = run_triage(entry3, [entry1, entry2, entry3], now)
        assert result["triage_level"] == LEVEL_GREEN, f"Scenario 1 failed: expected GREEN, got {result['triage_level']}"
        return True

    def test_scenario_2_day12_moderate_stable(self):
        """
        Scenario 2: Day 12, moderate symptoms, stable
        Expected: YELLOW
        Rationale: ≥10 days without improvement = ABRS per AAO-HNS
        """
        now = datetime.now(timezone.utc)
        day1 = now - timedelta(days=12)

        entry1 = create_symptom_entry(
            "ars",
            {
                "ars_obstruction": 2,
                "ars_facial_pain": 1,
                "ars_discharge": 2,
                "ars_smell": 1,
                "ars_temp": 1,
                "ars_headache": 1,
                "ars_malaise": 1,
            },
            day1,
            composite_score=9,
        )

        result = run_triage(entry1, [entry1], now)
        assert result["triage_level"] == LEVEL_YELLOW, f"Scenario 2 failed: expected YELLOW, got {result['triage_level']}"
        return True

    def test_scenario_3_day7_high_fever_severe_pain(self):
        """
        Scenario 3: Day 7, high fever >39°C + severe facial pain
        Expected: RED
        Rationale: Temp=3 (>39°C) + facial_pain≥2 triggers RED
        """
        now = datetime.now(timezone.utc)
        day1 = now - timedelta(days=7)

        entry1 = create_symptom_entry(
            "ars",
            {
                "ars_obstruction": 2,
                "ars_facial_pain": 3,
                "ars_discharge": 2,
                "ars_smell": 1,
                "ars_temp": 3,  # >39°C
                "ars_headache": 2,
                "ars_malaise": 1,
            },
            day1,
            composite_score=14,
        )

        result = run_triage(entry1, [entry1], now)
        assert result["triage_level"] == LEVEL_RED, f"Scenario 3 failed: expected RED, got {result['triage_level']}"
        return True

    def test_scenario_4_day8_double_sickening(self):
        """
        Scenario 4: Day 8, improvement then worsening (double sickening)
        Expected: YELLOW
        Rationale: Pattern of high→low→high indicates secondary bacterial infection
        """
        now = datetime.now(timezone.utc)
        day1 = now - timedelta(days=8)
        day2 = now - timedelta(days=5)
        day3 = now

        entry1 = create_symptom_entry("ars", {"ars_obstruction": 3, "ars_facial_pain": 2, "ars_discharge": 2, "ars_smell": 1, "ars_temp": 1, "ars_headache": 2, "ars_malaise": 1}, day1, composite_score=12)
        entry2 = create_symptom_entry("ars", {"ars_obstruction": 1, "ars_facial_pain": 1, "ars_discharge": 1, "ars_smell": 0, "ars_temp": 0, "ars_headache": 0, "ars_malaise": 0}, day2, composite_score=3)
        entry3 = create_symptom_entry("ars", {"ars_obstruction": 2, "ars_facial_pain": 2, "ars_discharge": 2, "ars_smell": 1, "ars_temp": 1, "ars_headache": 1, "ars_malaise": 1}, day3, composite_score=10)

        result = run_triage(entry3, [entry1, entry2, entry3], now)
        assert result["triage_level"] == LEVEL_YELLOW, f"Scenario 4 failed: expected YELLOW, got {result['triage_level']}"
        return True


class TestCRS:
    """Chronic Rhinosinusitis scenarios (EPOS 2020)."""

    def test_scenario_5_vas2_stable_controlled(self):
        """
        Scenario 5: VAS 2, stable trend
        Expected: GREEN
        Rationale: VAS ≤3 with stable = controlled disease per EPOS
        """
        now = datetime.now(timezone.utc)
        day1 = now - timedelta(days=3)

        entry1 = create_symptom_entry(
            "crs",
            {
                "crs_obstruction": 1,
                "crs_discharge": 0,
                "crs_facial_pain": 0,
                "crs_smell": 0,
                "crs_sleep": 1,
                "crs_vas": 2,
                "crs_temp": 0,
            },
            day1,
            composite_score=2,
        )

        result = run_triage(entry1, [entry1], now)
        assert result["triage_level"] == LEVEL_GREEN, f"Scenario 5 failed: expected GREEN, got {result['triage_level']}"
        return True

    def test_scenario_6_vas6_worsening_fever(self):
        """
        Scenario 6: VAS 6, worsening 3 days, fever
        Expected: YELLOW
        Rationale: VAS>5 + worsening_3d + temp≥2 = acute exacerbation
        """
        now = datetime.now(timezone.utc)
        day1 = now - timedelta(days=3)
        day2 = now - timedelta(days=2)
        day3 = now

        entry1 = create_symptom_entry("crs", {"crs_obstruction": 1, "crs_discharge": 0, "crs_facial_pain": 1, "crs_smell": 0, "crs_sleep": 1, "crs_vas": 4, "crs_temp": 0}, day1, composite_score=3)
        entry2 = create_symptom_entry("crs", {"crs_obstruction": 2, "crs_discharge": 0, "crs_facial_pain": 1, "crs_smell": 1, "crs_sleep": 1, "crs_vas": 5, "crs_temp": 1}, day2, composite_score=6)
        entry3 = create_symptom_entry("crs", {"crs_obstruction": 3, "crs_discharge": 1, "crs_facial_pain": 2, "crs_smell": 1, "crs_sleep": 2, "crs_vas": 6, "crs_temp": 2}, day3, composite_score=12)

        result = run_triage(entry3, [entry1, entry2, entry3], now)
        assert result["triage_level"] == LEVEL_YELLOW, f"Scenario 6 failed: expected YELLOW, got {result['triage_level']}"
        return True

    def test_scenario_7_vas4_stable_uncontrolled(self):
        """
        Scenario 7: VAS 4, stable
        Expected: YELLOW
        Rationale: VAS >3.5 with stable = uncontrolled disease per EPOS
        """
        now = datetime.now(timezone.utc)
        day1 = now - timedelta(days=3)

        entry1 = create_symptom_entry(
            "crs",
            {
                "crs_obstruction": 2,
                "crs_discharge": 1,
                "crs_facial_pain": 1,
                "crs_smell": 0,
                "crs_sleep": 1,
                "crs_vas": 4,
                "crs_temp": 0,
            },
            day1,
            composite_score=5,
        )

        result = run_triage(entry1, [entry1], now)
        assert result["triage_level"] == LEVEL_YELLOW, f"Scenario 7 failed: expected YELLOW, got {result['triage_level']}"
        return True

    def test_scenario_8_new_anosmia(self):
        """
        Scenario 8: New complete anosmia
        Expected: YELLOW
        Rationale: Complete anosmia (crs_smell=3) triggers YELLOW for workup
        """
        now = datetime.now(timezone.utc)
        day1 = now - timedelta(days=1)

        entry1 = create_symptom_entry(
            "crs",
            {
                "crs_obstruction": 1,
                "crs_discharge": 0,
                "crs_facial_pain": 0,
                "crs_smell": 3,  # Complete anosmia
                "crs_sleep": 0,
                "crs_vas": 3,
                "crs_temp": 0,
            },
            day1,
            composite_score=4,
        )

        result = run_triage(entry1, [entry1], now)
        assert result["triage_level"] == LEVEL_YELLOW, f"Scenario 8 failed: expected YELLOW, got {result['triage_level']}"
        return True


class TestTonsillopharyngitis:
    """Acute tonsillopharyngitis scenarios (IDSA/McIsaac)."""

    def test_scenario_9_mcisaac1_low_risk(self):
        """
        Scenario 9: McIsaac 1 (age 30, no fever, no exudate, no LAD, cough present)
        Expected: GREEN
        Rationale: McIsaac ≤1 = low probability, improving trend
        """
        now = datetime.now(timezone.utc)
        day1 = now

        entry1 = create_symptom_entry(
            "tonsillopharyngitis",
            {
                "tp_throat_pain": 1,
                "tp_dysphagia": 0,
                "tp_temp": 0,  # No fever
                "tp_exudate": 0,  # No exudate
                "tp_lymph": 0,  # No LAD
                "tp_cough": 1,  # Cough present (diminishes score)
                "tp_age": "15-44y",
                "trismus": 0,
                "uvular_deviation": 0,
                "drooling": 0,
                "neck_swelling": 0,
            },
            day1,
            composite_score=1,
        )

        result = run_triage(entry1, [entry1], now)
        assert result["triage_level"] == LEVEL_GREEN, f"Scenario 9 failed: expected GREEN, got {result['triage_level']}"
        return True

    def test_scenario_10_mcisaac4_moderate(self):
        """
        Scenario 10: McIsaac 4 (age 12, fever 38.5, exudate, LAD, no cough)
        Expected: YELLOW
        Rationale: McIsaac 4-5 without temp=3 → YELLOW
        """
        now = datetime.now(timezone.utc)
        day1 = now

        entry1 = create_symptom_entry(
            "tonsillopharyngitis",
            {
                "tp_throat_pain": 2,
                "tp_dysphagia": 1,
                "tp_temp": 2,  # 38-39°C
                "tp_exudate": 1,  # Exudate
                "tp_lymph": 1,  # LAD
                "tp_cough": 0,  # No cough (+1)
                "tp_age": "6-14y",  # Age <15 (+1)
                "trismus": 0,
                "uvular_deviation": 0,
                "drooling": 0,
                "neck_swelling": 0,
            },
            day1,
            composite_score=5,
        )

        result = run_triage(entry1, [entry1], now)
        assert result["triage_level"] == LEVEL_YELLOW, f"Scenario 10 failed: expected YELLOW, got {result['triage_level']}"
        return True

    def test_scenario_11_mcisaac4_high_fever(self):
        """
        Scenario 11: McIsaac 4 + temp >39°C
        Expected: RED
        Rationale: McIsaac≥4 + temp=3 (>39) → RED
        """
        now = datetime.now(timezone.utc)
        day1 = now

        entry1 = create_symptom_entry(
            "tonsillopharyngitis",
            {
                "tp_throat_pain": 3,
                "tp_dysphagia": 2,
                "tp_temp": 3,  # >39°C
                "tp_exudate": 1,
                "tp_lymph": 1,
                "tp_cough": 0,
                "tp_age": "6-14y",
                "trismus": 0,
                "uvular_deviation": 0,
                "drooling": 0,
                "neck_swelling": 0,
            },
            day1,
            composite_score=10,
        )

        result = run_triage(entry1, [entry1], now)
        assert result["triage_level"] == LEVEL_RED, f"Scenario 11 failed: expected RED, got {result['triage_level']}"
        return True

    def test_scenario_12_peritonsillar_abscess(self):
        """
        Scenario 12: Severe dysphagia + trismus
        Expected: RED
        Rationale: tp_dysphagia=3 + trismus=1 = peritonsillar abscess
        """
        now = datetime.now(timezone.utc)
        day1 = now

        entry1 = create_symptom_entry(
            "tonsillopharyngitis",
            {
                "tp_throat_pain": 3,
                "tp_dysphagia": 3,  # Severe
                "tp_temp": 2,
                "tp_exudate": 1,
                "tp_lymph": 1,
                "tp_cough": 0,
                "tp_age": "15-44y",
                "trismus": 1,  # Trismus present
                "uvular_deviation": 0,
                "drooling": 0,
                "neck_swelling": 0,
            },
            day1,
            composite_score=11,
        )

        result = run_triage(entry1, [entry1], now)
        assert result["triage_level"] == LEVEL_RED, f"Scenario 12 failed: expected RED, got {result['triage_level']}"
        return True


class TestAOM:
    """Acute Otitis Media scenarios (AAP 2013)."""

    def test_scenario_13_age3_unilateral_mild_watchful_waiting(self):
        """
        Scenario 13: Age 3y, unilateral, mild pain, no fever
        Expected: GREEN
        Rationale: Age≥2, unilateral, pain≤1, temp≤1 → watchful waiting
        """
        now = datetime.now(timezone.utc)
        day1 = now

        entry1 = create_symptom_entry(
            "aom",
            {
                "aom_ear_pain": 1,  # Mild
                "aom_hearing": 0,
                "aom_discharge": 0,
                "aom_temp": 0,  # No fever
                "aom_bilateral": 0,  # Unilateral
                "aom_malaise": 0,
                "aom_age": "2-5y",
                "postauricular_swelling": 0,
                "protruding_pinna": 0,
            },
            day1,
            composite_score=1,
        )

        result = run_triage(entry1, [entry1], now)
        assert result["triage_level"] == LEVEL_GREEN, f"Scenario 13 failed: expected GREEN, got {result['triage_level']}"
        return True

    def test_scenario_14_age4mo_fever(self):
        """
        Scenario 14: Age 4mo, fever
        Expected: RED
        Rationale: Age <6mo + any fever = RED (high risk)
        """
        now = datetime.now(timezone.utc)
        day1 = now

        entry1 = create_symptom_entry(
            "aom",
            {
                "aom_ear_pain": 1,
                "aom_hearing": 0,
                "aom_discharge": 0,
                "aom_temp": 1,  # Any fever
                "aom_bilateral": 0,
                "aom_malaise": 1,
                "aom_age": "<6mo",
                "postauricular_swelling": 0,
                "protruding_pinna": 0,
            },
            day1,
            composite_score=3,
        )

        result = run_triage(entry1, [entry1], now)
        assert result["triage_level"] == LEVEL_RED, f"Scenario 14 failed: expected RED, got {result['triage_level']}"
        return True

    def test_scenario_15_age18mo_bilateral_moderate(self):
        """
        Scenario 15: Age 18mo, bilateral, moderate pain
        Expected: YELLOW
        Rationale: Age 6-23mo + bilateral = YELLOW per AAP
        """
        now = datetime.now(timezone.utc)
        day1 = now

        entry1 = create_symptom_entry(
            "aom",
            {
                "aom_ear_pain": 2,  # Moderate
                "aom_hearing": 0,
                "aom_discharge": 0,
                "aom_temp": 1,
                "aom_bilateral": 1,  # Bilateral
                "aom_malaise": 1,
                "aom_age": "6-23mo",
                "postauricular_swelling": 0,
                "protruding_pinna": 0,
            },
            day1,
            composite_score=5,
        )

        result = run_triage(entry1, [entry1], now)
        assert result["triage_level"] == LEVEL_YELLOW, f"Scenario 15 failed: expected YELLOW, got {result['triage_level']}"
        return True

    def test_scenario_16_severe_pain_high_fever(self):
        """
        Scenario 16: Severe ear pain (3) + temp >39°C
        Expected: RED
        Rationale: aom_ear_pain=3 OR aom_temp=3 → RED
        """
        now = datetime.now(timezone.utc)
        day1 = now

        entry1 = create_symptom_entry(
            "aom",
            {
                "aom_ear_pain": 3,  # Severe
                "aom_hearing": 1,
                "aom_discharge": 0,
                "aom_temp": 3,  # >39°C
                "aom_bilateral": 0,
                "aom_malaise": 2,
                "aom_age": "6-14y",
                "postauricular_swelling": 0,
                "protruding_pinna": 0,
            },
            day1,
            composite_score=9,
        )

        result = run_triage(entry1, [entry1], now)
        assert result["triage_level"] == LEVEL_RED, f"Scenario 16 failed: expected RED, got {result['triage_level']}"
        return True


class TestCOM:
    """Chronic Otitis Media scenarios (AAO-HNS OME)."""

    def test_scenario_17_dry_ear_stable(self):
        """
        Scenario 17: Dry ear, stable hearing
        Expected: GREEN
        Rationale: com_discharge=0 + stable trend = GREEN
        """
        now = datetime.now(timezone.utc)
        day1 = now

        entry1 = create_symptom_entry(
            "com",
            {
                "com_hearing": 0,
                "com_fullness": 0,
                "com_discharge": 0,  # Dry ear
                "com_tinnitus": 0,
                "com_vertigo": 0,
                "com_pain": 0,
                "effusion_duration": 0,
                "facial_asymmetry": 0,
            },
            day1,
            composite_score=0,
        )

        result = run_triage(entry1, [entry1], now)
        assert result["triage_level"] == LEVEL_GREEN, f"Scenario 17 failed: expected GREEN, got {result['triage_level']}"
        return True

    def test_scenario_18_vertigo_grade2(self):
        """
        Scenario 18: Vertigo grade 2
        Expected: RED
        Rationale: com_vertigo≥2 = labyrinthine fistula risk → RED
        """
        now = datetime.now(timezone.utc)
        day1 = now

        entry1 = create_symptom_entry(
            "com",
            {
                "com_hearing": 1,
                "com_fullness": 1,
                "com_discharge": 0,
                "com_tinnitus": 2,
                "com_vertigo": 2,  # Moderate vertigo
                "com_pain": 0,
                "effusion_duration": 100,
                "facial_asymmetry": 0,
            },
            day1,
            composite_score=6,
        )

        result = run_triage(entry1, [entry1], now)
        assert result["triage_level"] == LEVEL_RED, f"Scenario 18 failed: expected RED, got {result['triage_level']}"
        return True

    def test_scenario_19_fetid_discharge(self):
        """
        Scenario 19: Fetid discharge
        Expected: RED
        Rationale: com_discharge=3 (purulent/fetid) = cholesteatoma risk → RED
        """
        now = datetime.now(timezone.utc)
        day1 = now

        entry1 = create_symptom_entry(
            "com",
            {
                "com_hearing": 2,
                "com_fullness": 1,
                "com_discharge": 3,  # Fetid/purulent
                "com_tinnitus": 1,
                "com_vertigo": 0,
                "com_pain": 2,
                "effusion_duration": 150,
                "facial_asymmetry": 0,
            },
            day1,
            composite_score=9,
        )

        result = run_triage(entry1, [entry1], now)
        assert result["triage_level"] == LEVEL_RED, f"Scenario 19 failed: expected RED, got {result['triage_level']}"
        return True

    def test_scenario_20_hearing_loss_effusion_3mo(self):
        """
        Scenario 20: Hearing loss 2 + effusion >3 months
        Expected: YELLOW
        Rationale: com_hearing≥2 + effusion_duration≥84 days → YELLOW per AAO-HNS
        """
        now = datetime.now(timezone.utc)
        day1 = now

        entry1 = create_symptom_entry(
            "com",
            {
                "com_hearing": 2,  # Moderate hearing loss
                "com_fullness": 2,
                "com_discharge": 0,
                "com_tinnitus": 1,
                "com_vertigo": 0,
                "com_pain": 0,
                "effusion_duration": 100,  # >3 months (84 days)
                "facial_asymmetry": 0,
            },
            day1,
            composite_score=5,
        )

        result = run_triage(entry1, [entry1], now)
        assert result["triage_level"] == LEVEL_YELLOW, f"Scenario 20 failed: expected YELLOW, got {result['triage_level']}"
        return True


class TestUniversalRedFlags:
    """Test universal red flags across all nosologies."""

    def test_periorbital_edema_on_any_nosology(self):
        """
        Test: Periorbital edema on any nosology
        Expected: RED (universal red flag)
        Rationale: Periorbital edema = possible orbital abscess → RED on ANY nosology
        """
        now = datetime.now(timezone.utc)
        day1 = now

        # Test on ARS
        entry_ars = create_symptom_entry(
            "ars",
            {
                "ars_obstruction": 1,
                "ars_facial_pain": 1,
                "ars_discharge": 0,
                "ars_smell": 0,
                "ars_temp": 1,
                "ars_headache": 0,
                "ars_malaise": 0,
                "periorbital_edema": 1,  # RED FLAG
            },
            day1,
            composite_score=3,
        )

        result = run_triage(entry_ars, [entry_ars], now)
        assert result["triage_level"] == LEVEL_RED, f"Periorbital edema test failed: expected RED, got {result['triage_level']}"
        assert "periorbital_edema" in result["red_flags"], f"Red flag not detected in {result['red_flags']}"
        return True


# =============================================================================
# TEST RUNNER
# =============================================================================

def run_all_tests():
    """Execute all test scenarios and produce summary report."""
    tests = [
        # ARS (4 scenarios)
        ("Scenario 1", "ARS: Day 3, mild, improving", TestARS().test_scenario_1_day3_mild_improving),
        ("Scenario 2", "ARS: Day 12, moderate, stable", TestARS().test_scenario_2_day12_moderate_stable),
        ("Scenario 3", "ARS: Day 7, high fever + severe pain", TestARS().test_scenario_3_day7_high_fever_severe_pain),
        ("Scenario 4", "ARS: Day 8, double sickening", TestARS().test_scenario_4_day8_double_sickening),
        # CRS (4 scenarios)
        ("Scenario 5", "CRS: VAS 2, stable, controlled", TestCRS().test_scenario_5_vas2_stable_controlled),
        ("Scenario 6", "CRS: VAS 6, worsening, fever", TestCRS().test_scenario_6_vas6_worsening_fever),
        ("Scenario 7", "CRS: VAS 4, stable, uncontrolled", TestCRS().test_scenario_7_vas4_stable_uncontrolled),
        ("Scenario 8", "CRS: New complete anosmia", TestCRS().test_scenario_8_new_anosmia),
        # Tonsillopharyngitis (4 scenarios)
        ("Scenario 9", "TP: McIsaac 1, low risk", TestTonsillopharyngitis().test_scenario_9_mcisaac1_low_risk),
        ("Scenario 10", "TP: McIsaac 4, moderate", TestTonsillopharyngitis().test_scenario_10_mcisaac4_moderate),
        ("Scenario 11", "TP: McIsaac 4 + high fever", TestTonsillopharyngitis().test_scenario_11_mcisaac4_high_fever),
        ("Scenario 12", "TP: Peritonsillar abscess", TestTonsillopharyngitis().test_scenario_12_peritonsillar_abscess),
        # AOM (4 scenarios)
        ("Scenario 13", "AOM: Age 3y, unilateral, mild", TestAOM().test_scenario_13_age3_unilateral_mild_watchful_waiting),
        ("Scenario 14", "AOM: Age 4mo + fever", TestAOM().test_scenario_14_age4mo_fever),
        ("Scenario 15", "AOM: Age 18mo, bilateral, moderate", TestAOM().test_scenario_15_age18mo_bilateral_moderate),
        ("Scenario 16", "AOM: Severe pain + high fever", TestAOM().test_scenario_16_severe_pain_high_fever),
        # COM (4 scenarios)
        ("Scenario 17", "COM: Dry ear, stable", TestCOM().test_scenario_17_dry_ear_stable),
        ("Scenario 18", "COM: Vertigo grade 2", TestCOM().test_scenario_18_vertigo_grade2),
        ("Scenario 19", "COM: Fetid discharge", TestCOM().test_scenario_19_fetid_discharge),
        ("Scenario 20", "COM: Hearing loss + effusion 3mo", TestCOM().test_scenario_20_hearing_loss_effusion_3mo),
        # Universal red flags
        ("Red Flag", "Universal: Periorbital edema", TestUniversalRedFlags().test_periorbital_edema_on_any_nosology),
    ]

    print("\n" + "=" * 100)
    print("CLINICAL VERIFICATION TEST SUMMARY")
    print("=" * 100)
    print(f"{'Scenario':<12} | {'Description':<40} | {'Result':<10}")
    print("-" * 100)

    passed = 0
    failed = 0

    for scenario_id, description, test_func in tests:
        try:
            test_func()
            print(f"{scenario_id:<12} | {description:<40} | {'PASS':<10}")
            passed += 1
        except AssertionError as e:
            print(f"{scenario_id:<12} | {description:<40} | {'FAIL':<10}")
            print(f"  Error: {e}")
            failed += 1
        except Exception as e:
            print(f"{scenario_id:<12} | {description:<40} | {'ERROR':<10}")
            print(f"  Exception: {e}")
            failed += 1

    print("-" * 100)
    print(f"\nTOTAL: {passed} passed, {failed} failed out of {len(tests)} scenarios")
    print("=" * 100 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
