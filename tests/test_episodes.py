"""Tests for episode criteria functions (AOM tubes, CRS surgery, tonsillectomy)."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from bot.services.episodes import (
    aom_tube_criteria_met,
    crs_surgery_criteria_met,
    tonsillectomy_criteria_met,
    count_episodes_in_period,
)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _make_mock_session(count_values: list[int]):
    """Create a mock AsyncSession that returns count_values sequentially.

    Each call to session.execute() returns a mock whose .scalar() returns
    the next value from count_values.
    """
    session = AsyncMock()
    results = []
    for val in count_values:
        mock_result = MagicMock()
        mock_result.scalar.return_value = val
        mock_result.scalar_one_or_none.return_value = None
        results.append(mock_result)

    session.execute = AsyncMock(side_effect=results)
    return session


# ═══════════════════════════════════════════════════════════════════════
# AOM Tube Criteria — AAP 2013
# ≥3 episodes in 6 months OR ≥4 episodes in 12 months
# ═══════════════════════════════════════════════════════════════════════

class TestAOMTubeCriteria:
    @pytest.mark.asyncio
    async def test_no_episodes(self):
        """No episodes → criteria not met."""
        session = _make_mock_session([0, 0])  # 6mo=0, 12mo=0
        met, reason = await aom_tube_criteria_met(session, user_id=1)
        assert met is False
        assert reason == ""

    @pytest.mark.asyncio
    async def test_three_in_six_months(self):
        """3 episodes in 6 months → criteria met (first criterion)."""
        session = _make_mock_session([3, 3])  # 6mo=3, 12mo=3
        met, reason = await aom_tube_criteria_met(session, user_id=1)
        assert met is True
        assert "3" in reason
        assert "6 месяцев" in reason

    @pytest.mark.asyncio
    async def test_four_in_twelve_months(self):
        """2 in 6mo but 4 in 12mo → second criterion fires."""
        session = _make_mock_session([2, 4])  # 6mo=2, 12mo=4
        met, reason = await aom_tube_criteria_met(session, user_id=1)
        assert met is True
        assert "12 месяцев" in reason

    @pytest.mark.asyncio
    async def test_borderline_not_met(self):
        """2 in 6mo, 3 in 12mo → neither criterion met."""
        session = _make_mock_session([2, 3])  # 6mo=2, 12mo=3
        met, reason = await aom_tube_criteria_met(session, user_id=1)
        assert met is False

    @pytest.mark.asyncio
    async def test_exceeds_both(self):
        """5 in 6mo, 7 in 12mo → first criterion fires (checked first)."""
        session = _make_mock_session([5, 7])
        met, reason = await aom_tube_criteria_met(session, user_id=1)
        assert met is True
        assert "6 месяцев" in reason  # first criterion takes priority


# ═══════════════════════════════════════════════════════════════════════
# CRS Surgery Criteria — EPOS 2020
# ≥4 flares in 12 months with systemic GCS/AB
# ═══════════════════════════════════════════════════════════════════════

class TestCRSSurgeryCriteria:
    @pytest.mark.asyncio
    async def test_no_flares(self):
        session = _make_mock_session([0])  # 12mo=0
        met, reason = await crs_surgery_criteria_met(session, user_id=1)
        assert met is False

    @pytest.mark.asyncio
    async def test_three_flares(self):
        """3 flares → not yet enough."""
        session = _make_mock_session([3])
        met, reason = await crs_surgery_criteria_met(session, user_id=1)
        assert met is False

    @pytest.mark.asyncio
    async def test_four_flares(self):
        """4 flares → criteria met."""
        session = _make_mock_session([4])
        met, reason = await crs_surgery_criteria_met(session, user_id=1)
        assert met is True
        assert "4" in reason
        assert "12 месяцев" in reason

    @pytest.mark.asyncio
    async def test_many_flares(self):
        """8 flares → criteria clearly met."""
        session = _make_mock_session([8])
        met, reason = await crs_surgery_criteria_met(session, user_id=1)
        assert met is True


# ═══════════════════════════════════════════════════════════════════════
# Tonsillectomy Criteria — Guntinas-Lichius 2023
# (regression tests for existing functionality)
# ═══════════════════════════════════════════════════════════════════════

class TestTonsillectomyCriteria:
    @pytest.mark.asyncio
    async def test_seven_in_one_year(self):
        """≥7 in last year → met."""
        session = _make_mock_session([7, 0, 0])  # year0=7, year1=0, year2=0
        met, reason = await tonsillectomy_criteria_met(session, user_id=1)
        assert met is True
        assert "7" in reason

    @pytest.mark.asyncio
    async def test_five_per_year_for_two(self):
        """≥5/year for 2 consecutive years → met."""
        session = _make_mock_session([5, 5, 0])
        met, reason = await tonsillectomy_criteria_met(session, user_id=1)
        assert met is True
        assert "два года" in reason

    @pytest.mark.asyncio
    async def test_three_per_year_for_three(self):
        """≥3/year for 3 consecutive years → met."""
        session = _make_mock_session([3, 3, 3])
        met, reason = await tonsillectomy_criteria_met(session, user_id=1)
        assert met is True
        assert "три года" in reason

    @pytest.mark.asyncio
    async def test_not_met(self):
        """4/year for 1 year only → not met."""
        session = _make_mock_session([4, 2, 1])
        met, reason = await tonsillectomy_criteria_met(session, user_id=1)
        assert met is False
