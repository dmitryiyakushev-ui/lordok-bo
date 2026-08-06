"""
Episode tracking service — registers discrete clinical episodes and
evaluates cumulative criteria (e.g. tonsillectomy indications).

Evidence base:
  - Guntinas-Lichius O et al. (2023): German S2k guideline on
    recurrent acute tonsillitis. Tonsillectomy criteria:
    ≥7 episodes/1 year, ≥5/year for 2 consecutive years,
    ≥3/year for 3 consecutive years.
  - AAO-HNS Tonsillectomy CPG (2019): Paradise criteria aligned.
  - AAP/AAO-HNS AOM CPG (Lieberthal AS et al. 2013): recurrent AOM =
    ≥3 episodes in 6 months OR ≥4 in 12 months → consider tubes/adenoidectomy.
  - EPOS 2020 (Fokkens WJ et al.): CRS flare frequency as criterion
    for escalation to FESS or biologics — ≥4 flares/12 months
    requiring systemic GCS or antibiotics.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.episode import EpisodeLog

logger = logging.getLogger(__name__)

# Minimum gap (days) between episodes to count as separate.
# Prevents double-counting if patient logs daily during one episode.
MIN_EPISODE_GAP_DAYS = 14


async def register_episode(
    session: AsyncSession,
    *,
    user_id: int,
    patient_id: int | None,
    episode_type: str,
    scale_score: int | None = None,
    notes: str | None = None,
    started_at: datetime | None = None,
) -> EpisodeLog | None:
    """Register a new episode if the last one ended ≥ MIN_EPISODE_GAP_DAYS ago.

    Returns the new EpisodeLog, or None if too close to the previous episode
    (i.e. this is a continuation, not a new episode).
    """
    now = started_at or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=MIN_EPISODE_GAP_DAYS)

    # Check for recent episode of the same type for this patient
    stmt = (
        select(EpisodeLog)
        .where(
            EpisodeLog.user_id == user_id,
            EpisodeLog.episode_type == episode_type,
            EpisodeLog.started_at >= cutoff,
        )
    )
    if patient_id is not None:
        stmt = stmt.where(EpisodeLog.patient_id == patient_id)

    result = await session.execute(stmt.order_by(EpisodeLog.started_at.desc()).limit(1))
    recent = result.scalar_one_or_none()

    if recent is not None:
        logger.debug(
            "Skipping episode registration for user %d: last %s episode was %s",
            user_id, episode_type, recent.started_at,
        )
        return None

    ep = EpisodeLog(
        user_id=user_id,
        patient_id=patient_id,
        episode_type=episode_type,
        scale_score=scale_score,
        started_at=now,
        notes=notes,
    )
    session.add(ep)
    await session.flush()

    logger.info(
        "Registered %s episode #%d for user %d (patient %s, score=%s)",
        episode_type, ep.id, user_id, patient_id, scale_score,
    )
    return ep


async def count_episodes_per_year(
    session: AsyncSession,
    user_id: int,
    episode_type: str,
    years: int = 3,
    patient_id: int | None = None,
    now: datetime | None = None,
) -> list[int]:
    """Count episodes per year going back N years.

    Returns a list of length `years`, where index 0 is the most recent
    year (last 12 months), index 1 is 12–24 months ago, etc.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    counts = []
    for i in range(years):
        year_end = now - timedelta(days=365 * i)
        year_start = now - timedelta(days=365 * (i + 1))

        stmt = (
            select(func.count(EpisodeLog.id))
            .where(
                EpisodeLog.user_id == user_id,
                EpisodeLog.episode_type == episode_type,
                EpisodeLog.started_at >= year_start,
                EpisodeLog.started_at < year_end,
            )
        )
        if patient_id is not None:
            stmt = stmt.where(EpisodeLog.patient_id == patient_id)

        result = await session.execute(stmt)
        counts.append(result.scalar() or 0)

    return counts


async def tonsillectomy_criteria_met(
    session: AsyncSession,
    user_id: int,
    patient_id: int | None = None,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """Check if tonsillectomy criteria are met (Guntinas-Lichius 2023).

    Criteria (any one sufficient):
    1. ≥7 episodes in the last 1 year
    2. ≥5 episodes/year for each of the last 2 years
    3. ≥3 episodes/year for each of the last 3 years

    Returns:
        (met: bool, reason: str) — reason is a human-readable explanation.
    """
    counts = await count_episodes_per_year(
        session, user_id, "tonsillitis", years=3,
        patient_id=patient_id, now=now,
    )

    # Criterion 1: ≥7 in last year
    if counts[0] >= 7:
        return True, f"≥7 эпизодов за последний год ({counts[0]})"

    # Criterion 2: ≥5/year for 2 consecutive years
    if len(counts) >= 2 and counts[0] >= 5 and counts[1] >= 5:
        return True, f"≥5 эпизодов/год два года подряд ({counts[0]}, {counts[1]})"

    # Criterion 3: ≥3/year for 3 consecutive years
    if len(counts) >= 3 and all(c >= 3 for c in counts[:3]):
        return True, (
            f"≥3 эпизодов/год три года подряд "
            f"({counts[0]}, {counts[1]}, {counts[2]})"
        )

    return False, ""


async def count_episodes_in_period(
    session: AsyncSession,
    user_id: int,
    episode_type: str,
    days: int,
    patient_id: int | None = None,
    now: datetime | None = None,
) -> int:
    """Count episodes within the last `days` days.

    Useful for criteria that use a 6-month (182 days) window
    rather than a strict calendar-year window.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    cutoff = now - timedelta(days=days)
    stmt = (
        select(func.count(EpisodeLog.id))
        .where(
            EpisodeLog.user_id == user_id,
            EpisodeLog.episode_type == episode_type,
            EpisodeLog.started_at >= cutoff,
            EpisodeLog.started_at <= now,
        )
    )
    if patient_id is not None:
        stmt = stmt.where(EpisodeLog.patient_id == patient_id)

    result = await session.execute(stmt)
    return result.scalar() or 0


async def aom_tube_criteria_met(
    session: AsyncSession,
    user_id: int,
    patient_id: int | None = None,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """Check if ventilation tube / adenoidectomy discussion criteria are met.

    Based on AAP/AAO-HNS 2013 recurrent AOM definition:
    1. ≥3 episodes in 6 months
    2. ≥4 episodes in 12 months

    Returns:
        (met: bool, reason: str)
    """
    if now is None:
        now = datetime.now(timezone.utc)

    count_6m = await count_episodes_in_period(
        session, user_id, "aom", days=182,
        patient_id=patient_id, now=now,
    )
    count_12m = await count_episodes_in_period(
        session, user_id, "aom", days=365,
        patient_id=patient_id, now=now,
    )

    if count_6m >= 3:
        return True, f"≥3 эпизода ОСО за 6 месяцев ({count_6m})"

    if count_12m >= 4:
        return True, f"≥4 эпизода ОСО за 12 месяцев ({count_12m})"

    return False, ""


async def crs_surgery_criteria_met(
    session: AsyncSession,
    user_id: int,
    patient_id: int | None = None,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """Check if FESS / biologics discussion criteria are met.

    Based on EPOS 2020 escalation logic:
    ≥4 flares requiring systemic GCS or antibiotics in 12 months
    → consider endoscopic sinus surgery or biologics.

    Returns:
        (met: bool, reason: str)
    """
    if now is None:
        now = datetime.now(timezone.utc)

    count_12m = await count_episodes_in_period(
        session, user_id, "crs_flare", days=365,
        patient_id=patient_id, now=now,
    )

    if count_12m >= 4:
        return True, f"≥4 обострения ХРС за 12 месяцев ({count_12m})"

    return False, ""


async def get_episode_summary(
    session: AsyncSession,
    user_id: int,
    episode_type: str,
    patient_id: int | None = None,
    now: datetime | None = None,
) -> dict:
    """Get a summary of episodes for display in reports.

    Returns:
        {
            "total": int,
            "last_12m": int,
            "last_24m": int,
            "last_episode": datetime | None,
        }
    """
    if now is None:
        now = datetime.now(timezone.utc)

    counts = await count_episodes_per_year(
        session, user_id, episode_type, years=2,
        patient_id=patient_id, now=now,
    )

    # Total count
    stmt = (
        select(func.count(EpisodeLog.id))
        .where(
            EpisodeLog.user_id == user_id,
            EpisodeLog.episode_type == episode_type,
        )
    )
    if patient_id is not None:
        stmt = stmt.where(EpisodeLog.patient_id == patient_id)
    total_result = await session.execute(stmt)
    total = total_result.scalar() or 0

    # Last episode date
    stmt_last = (
        select(EpisodeLog.started_at)
        .where(
            EpisodeLog.user_id == user_id,
            EpisodeLog.episode_type == episode_type,
        )
        .order_by(EpisodeLog.started_at.desc())
        .limit(1)
    )
    if patient_id is not None:
        stmt_last = stmt_last.where(EpisodeLog.patient_id == patient_id)
    last_result = await session.execute(stmt_last)
    last_episode = last_result.scalar_one_or_none()

    return {
        "total": total,
        "last_12m": counts[0] if counts else 0,
        "last_24m": counts[1] if len(counts) > 1 else 0,
        "last_episode": last_episode,
    }
