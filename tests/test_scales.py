"""Tests for clinical scoring scales (Centor, FeverPAIN)."""

import pytest
from bot.services.scales import (
    CentorInput,
    FeverPainInput,
    centor_score,
    centor_action,
    feverpain_score,
    feverpain_action,
    build_centor_input,
    build_feverpain_input,
    compute_tp_scales,
)


# ═══════════════════════════════════════════════════════════════════════
# Centor / McIsaac
# ═══════════════════════════════════════════════════════════════════════

class TestCentorScore:
    def test_all_negative_adult(self):
        """Adult with no criteria → score 0."""
        inp = CentorInput(
            fever_over_38=False, no_cough=False,
            tender_anterior_lymph=False, tonsillar_exudate=False,
            age_group="15-44y",
        )
        assert centor_score(inp) == 0

    def test_all_positive_child(self):
        """Child with all 4 criteria → 4 + 1 (age) = 5."""
        inp = CentorInput(
            fever_over_38=True, no_cough=True,
            tender_anterior_lymph=True, tonsillar_exudate=True,
            age_group="6-14y",
        )
        assert centor_score(inp) == 5

    def test_all_positive_elderly(self):
        """≥45y with all 4 criteria → 4 - 1 (age) = 3."""
        inp = CentorInput(
            fever_over_38=True, no_cough=True,
            tender_anterior_lymph=True, tonsillar_exudate=True,
            age_group=">=45y",
        )
        assert centor_score(inp) == 3

    def test_partial_adult(self):
        """Adult with 2 criteria → score 2."""
        inp = CentorInput(
            fever_over_38=True, no_cough=True,
            tender_anterior_lymph=False, tonsillar_exudate=False,
            age_group="15-44y",
        )
        assert centor_score(inp) == 2

    def test_negative_score_possible(self):
        """≥45y with 0 criteria → -1."""
        inp = CentorInput(
            fever_over_38=False, no_cough=False,
            tender_anterior_lymph=False, tonsillar_exudate=False,
            age_group=">=45y",
        )
        assert centor_score(inp) == -1


class TestCentorAction:
    def test_low_scores(self):
        assert centor_action(-1) == "green_no_ab"
        assert centor_action(0) == "green_no_ab"
        assert centor_action(1) == "green_no_ab"

    def test_moderate_score(self):
        assert centor_action(2) == "yellow_test"

    def test_high_scores(self):
        assert centor_action(3) == "yellow_test_or_ab"
        assert centor_action(4) == "yellow_test_or_ab"
        assert centor_action(5) == "yellow_test_or_ab"


# ═══════════════════════════════════════════════════════════════════════
# FeverPAIN
# ═══════════════════════════════════════════════════════════════════════

class TestFeverPainScore:
    def test_all_negative(self):
        inp = FeverPainInput(
            fever_24h=False, purulent_tonsils=False,
            attended_rapidly=False, inflamed_tonsils=False,
            no_cough_no_coryza=False,
        )
        assert feverpain_score(inp) == 0

    def test_all_positive(self):
        inp = FeverPainInput(
            fever_24h=True, purulent_tonsils=True,
            attended_rapidly=True, inflamed_tonsils=True,
            no_cough_no_coryza=True,
        )
        assert feverpain_score(inp) == 5

    def test_partial(self):
        inp = FeverPainInput(
            fever_24h=True, purulent_tonsils=False,
            attended_rapidly=True, inflamed_tonsils=False,
            no_cough_no_coryza=True,
        )
        assert feverpain_score(inp) == 3


class TestFeverPainAction:
    def test_low(self):
        assert feverpain_action(0) == "green_no_ab"
        assert feverpain_action(1) == "green_no_ab"

    def test_moderate(self):
        assert feverpain_action(2) == "yellow_delayed_or_test"
        assert feverpain_action(3) == "yellow_delayed_or_test"

    def test_high(self):
        assert feverpain_action(4) == "yellow_or_red_ab"
        assert feverpain_action(5) == "yellow_or_red_ab"


# ═══════════════════════════════════════════════════════════════════════
# Mapping from symptoms dict
# ═══════════════════════════════════════════════════════════════════════

class TestBuildCentorInput:
    def test_typical_mapping(self):
        symptoms = {
            "tp_temp": 2,       # ≥38 → fever_over_38=True
            "tp_cough": 0,      # no cough → no_cough=True
            "tp_lymph": 1,      # yes
            "tp_exudate": 0,    # no
        }
        inp = build_centor_input(symptoms, "15-44y")
        assert inp.fever_over_38 is True
        assert inp.no_cough is True
        assert inp.tender_anterior_lymph is True
        assert inp.tonsillar_exudate is False

    def test_low_temp_no_fever(self):
        symptoms = {"tp_temp": 1, "tp_cough": 1, "tp_lymph": 0, "tp_exudate": 0}
        inp = build_centor_input(symptoms, "15-44y")
        assert inp.fever_over_38 is False
        assert inp.no_cough is False


class TestBuildFeverPainInput:
    def test_typical_mapping(self):
        symptoms = {
            "tp_temp": 3,       # >39 → fever_24h=True
            "tp_exudate": 1,    # purulent
            "tp_dysphagia": 2,  # ≥2 → inflamed_tonsils=True
            "tp_cough": 0,      # no cough
        }
        inp = build_feverpain_input(symptoms, symptom_duration=2)
        assert inp.fever_24h is True
        assert inp.purulent_tonsils is True
        assert inp.attended_rapidly is True  # 2 <= 3
        assert inp.inflamed_tonsils is True
        assert inp.no_cough_no_coryza is True

    def test_late_presentation(self):
        symptoms = {"tp_temp": 2, "tp_exudate": 0, "tp_dysphagia": 1, "tp_cough": 1}
        inp = build_feverpain_input(symptoms, symptom_duration=5)
        assert inp.attended_rapidly is False  # 5 > 3
        assert inp.inflamed_tonsils is False  # 1 < 2


# ═══════════════════════════════════════════════════════════════════════
# compute_tp_scales integration
# ═══════════════════════════════════════════════════════════════════════

class TestComputeTPScales:
    def test_returns_all_keys(self):
        symptoms = {
            "tp_temp": 2, "tp_cough": 0, "tp_lymph": 1,
            "tp_exudate": 1, "tp_dysphagia": 2,
        }
        result = compute_tp_scales(symptoms, "15-44y", 2)
        assert "centor_score" in result
        assert "centor_action" in result
        assert "centor_message" in result
        assert "feverpain_score" in result
        assert "feverpain_action" in result
        assert "feverpain_message" in result

    def test_classic_strep_adult(self):
        """Classic strep presentation: fever, exudate, lymph, no cough → Centor 4."""
        symptoms = {
            "tp_temp": 3, "tp_cough": 0, "tp_lymph": 1,
            "tp_exudate": 1, "tp_dysphagia": 2,
        }
        result = compute_tp_scales(symptoms, "15-44y", 1)
        assert result["centor_score"] == 4
        assert result["centor_action"] == "yellow_test_or_ab"
        assert result["feverpain_score"] == 5  # all 5 criteria met
        assert result["feverpain_action"] == "yellow_or_red_ab"

    def test_viral_pattern(self):
        """Viral pattern: no fever, cough present, no exudate → Centor 0.
        FeverPAIN = 1 (only 'attended_rapidly' since duration=3 ≤ 3)."""
        symptoms = {
            "tp_temp": 0, "tp_cough": 1, "tp_lymph": 0,
            "tp_exudate": 0, "tp_dysphagia": 0,
        }
        result = compute_tp_scales(symptoms, "15-44y", 3)
        assert result["centor_score"] == 0
        assert result["centor_action"] == "green_no_ab"
        assert result["feverpain_score"] == 1  # attended_rapidly=True
        assert result["feverpain_action"] == "green_no_ab"
