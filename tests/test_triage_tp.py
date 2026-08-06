"""Tests for acute tonsillopharyngitis triage rule with Centor/FeverPAIN."""

import pytest
from bot.triage.rules.acute_tonsillopharyngitis import run_triage


class TestTPTriageScenarios:
    """Integration tests: symptoms → triage_level + scale scores."""

    def test_green_viral_pattern(self):
        """No fever, cough present, no exudate → GREEN (Centor 0)."""
        result = run_triage(
            symptoms={
                "tp_temp": 0, "tp_cough": 1, "tp_lymph": 0,
                "tp_exudate": 0, "tp_throat_pain": 1, "tp_dysphagia": 0,
                "tp_age": "15-44y",
                "trismus": 0, "uvular_deviation": 0, "drooling": 0,
                "neck_swelling": 0,
            },
            composite_score=2,
            symptom_duration=2,
            trend="stable",
            previous_entries=[],
        )
        assert result["triage_level"] == "green"
        assert result["centor_score"] == 0
        assert result["centor_action"] == "green_no_ab"
        assert result["feverpain_score"] == 1  # only attended_rapidly=True

    def test_yellow_moderate_centor(self):
        """Centor 2 → YELLOW (testing recommended)."""
        result = run_triage(
            symptoms={
                "tp_temp": 2, "tp_cough": 0, "tp_lymph": 0,
                "tp_exudate": 0, "tp_throat_pain": 2, "tp_dysphagia": 1,
                "tp_age": "15-44y",
                "trismus": 0, "uvular_deviation": 0, "drooling": 0,
                "neck_swelling": 0,
            },
            composite_score=5,
            symptom_duration=2,
            trend="stable",
            previous_entries=[],
        )
        assert result["triage_level"] == "yellow"
        assert result["centor_score"] == 2
        assert "экспресс-тест" in result["triage_message"].lower() or "radt" in result["triage_message"].lower()

    def test_yellow_high_centor_child(self):
        """Child 6-14y with Centor 5 → YELLOW (high probability)."""
        result = run_triage(
            symptoms={
                "tp_temp": 3, "tp_cough": 0, "tp_lymph": 1,
                "tp_exudate": 1, "tp_throat_pain": 3, "tp_dysphagia": 2,
                "tp_age": "6-14y",
                "trismus": 0, "uvular_deviation": 0, "drooling": 0,
                "neck_swelling": 0,
            },
            composite_score=10,
            symptom_duration=1,
            trend="worsening",
            previous_entries=[],
        )
        assert result["triage_level"] == "yellow"
        assert result["centor_score"] == 5
        # FeverPAIN not computed for children
        assert result["feverpain_score"] is None

    def test_red_peritonsillar_abscess(self):
        """Severe dysphagia + trismus → RED (abscess screening)."""
        result = run_triage(
            symptoms={
                "tp_temp": 3, "tp_cough": 0, "tp_lymph": 1,
                "tp_exudate": 1, "tp_throat_pain": 3, "tp_dysphagia": 3,
                "tp_age": "15-44y",
                "trismus": 1, "uvular_deviation": 0, "drooling": 0,
                "neck_swelling": 0,
            },
            composite_score=12,
            symptom_duration=3,
            trend="worsening",
            previous_entries=[],
        )
        assert result["triage_level"] == "red"
        assert "абсцесс" in result["triage_message"].lower()
        # Scales not computed when RED from abscess
        assert result["centor_score"] is None

    def test_green_escalates_on_duration(self):
        """Centor 0–1 but symptoms >7 days → YELLOW."""
        result = run_triage(
            symptoms={
                "tp_temp": 0, "tp_cough": 1, "tp_lymph": 0,
                "tp_exudate": 0, "tp_throat_pain": 1, "tp_dysphagia": 0,
                "tp_age": "15-44y",
                "trismus": 0, "uvular_deviation": 0, "drooling": 0,
                "neck_swelling": 0,
            },
            composite_score=2,
            symptom_duration=8,
            trend="stable",
            previous_entries=[],
        )
        assert result["triage_level"] == "yellow"
        assert "7 дней" in result["triage_message"]

    def test_feverpain_elevates_action(self):
        """FeverPAIN higher risk than Centor → uses higher action."""
        # Centor: fever + no_cough = 2 → yellow_test
        # FeverPAIN: fever + no_cough + rapid + inflamed = 4 → yellow_or_red_ab
        result = run_triage(
            symptoms={
                "tp_temp": 2, "tp_cough": 0, "tp_lymph": 0,
                "tp_exudate": 0, "tp_throat_pain": 2, "tp_dysphagia": 2,
                "tp_age": "15-44y",
                "trismus": 0, "uvular_deviation": 0, "drooling": 0,
                "neck_swelling": 0,
            },
            composite_score=6,
            symptom_duration=1,
            trend="stable",
            previous_entries=[],
        )
        assert result["triage_level"] == "yellow"
        assert result["centor_score"] == 2
        assert result["feverpain_score"] == 4
        # The message should include FeverPAIN info
        assert "FeverPAIN" in result["triage_message"]

    def test_elderly_centor_minus_one(self):
        """≥45y with only fever → Centor 0 (1 criterion - 1 age)."""
        result = run_triage(
            symptoms={
                "tp_temp": 2, "tp_cough": 1, "tp_lymph": 0,
                "tp_exudate": 0, "tp_throat_pain": 1, "tp_dysphagia": 0,
                "tp_age": ">=45y",
                "trismus": 0, "uvular_deviation": 0, "drooling": 0,
                "neck_swelling": 0,
            },
            composite_score=4,
            symptom_duration=2,
            trend="stable",
            previous_entries=[],
        )
        assert result["centor_score"] == 0  # 1 (fever) - 1 (age) = 0
        assert result["centor_action"] == "green_no_ab"
