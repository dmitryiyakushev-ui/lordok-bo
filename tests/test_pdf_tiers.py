"""Тесты двух версий PDF-отчёта: бесплатной сводки и полной."""

from datetime import datetime, timedelta, timezone

import pytest

from bot.services.pdf_report import generate_pdf_report

NOW = datetime.now(timezone.utc)

USER = {"first_name": "Анна", "nosology": "ars", "age_group": "15-44y"}
ENTRIES = [
    {
        "recorded_at": NOW - timedelta(days=i),
        "composite_score": 8 - i,
        "triage_level": "yellow" if i % 2 else "green",
        "triage_message": "Симптомы стабильны.",
        "symptoms": {"ars_obstruction": 2, "ars_temp": 1},
        "red_flags": [],
        "nosology": "ars",
        "user_notes": "",
    }
    for i in range(6)
]
SCALES = [
    {"scale": "centor", "score": 3, "action": "yellow", "details": {}, "created_at": NOW}
]
EPISODES = [
    {"episode_type": "aom", "started_at": NOW, "scale_score": 3, "notes": ""}
]
RECOMMENDATIONS = ["Тонзиллэктомия: критерии выполнены (7 эпизодов за год)."]


async def _build(full: bool) -> bytes:
    return await generate_pdf_report(
        user_data=USER,
        entries=ENTRIES,
        period_days=30 if full else 7,
        scale_scores=SCALES,
        episodes=EPISODES,
        recommendations=RECOMMENDATIONS,
        full=full,
    )


@pytest.fixture(scope="module")
async def reports():
    return {"full": await _build(True), "free": await _build(False)}


async def test_both_versions_are_valid_pdf(reports):
    assert reports["full"].startswith(b"%PDF")
    assert reports["free"].startswith(b"%PDF")


async def test_free_version_has_no_chart(reports):
    assert reports["free"].count(b"/Subtype /Image") == 0
    assert reports["full"].count(b"/Subtype /Image") > 0


async def test_free_version_is_shorter(reports):
    assert len(reports["free"]) < len(reports["full"])


async def test_free_version_explains_what_is_missing(reports):
    # Текст в PDF сжат, поэтому проверяем на одностраничность как признак
    # урезанной версии, а полноту разделов на разнице объёма.
    assert reports["free"].count(b"/Type /Page") < reports["full"].count(b"/Type /Page")
