"""
PDF report generator for ЛОРдок.
Generates a structured symptom summary with charts for the treating physician.
Uses ReportLab for PDF generation and matplotlib for symptom trend charts.
"""

import io
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.fonts import addMapping
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image,
    HRFlowable, PageBreak,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cyrillic-capable fonts
#
# ReportLab's built-in Helvetica has no Cyrillic glyphs, so Russian text
# renders as hollow squares. We register DejaVu Sans (regular + bold) as
# our primary font — it is bundled with matplotlib and therefore always
# available in any environment where this module loads.
# ---------------------------------------------------------------------------

FONT_REGULAR = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"
_FONTS_REGISTERED = False


def _register_cyrillic_fonts() -> bool:
    """Register DejaVu Sans with ReportLab if not already registered."""
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return True

    # Prefer system-installed DejaVu (Debian/Ubuntu default), then fall
    # back to the copy bundled inside matplotlib — guaranteed to exist
    # because we import matplotlib at module load.
    regular_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    bold_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    ]
    try:
        mpl_ttf_dir = Path(matplotlib.__file__).parent / "mpl-data" / "fonts" / "ttf"
        regular_candidates.append(str(mpl_ttf_dir / "DejaVuSans.ttf"))
        bold_candidates.append(str(mpl_ttf_dir / "DejaVuSans-Bold.ttf"))
    except Exception:
        pass

    regular_path = next((p for p in regular_candidates if Path(p).exists()), None)
    bold_path = next((p for p in bold_candidates if Path(p).exists()), None)

    if regular_path is None:
        logger.warning(
            "DejaVu Sans TTF not found in any expected location, "
            "Cyrillic text in PDF reports will render as squares."
        )
        return False

    pdfmetrics.registerFont(TTFont(FONT_REGULAR, regular_path))
    if bold_path is not None:
        pdfmetrics.registerFont(TTFont(FONT_BOLD, bold_path))
        # Map the font family so Paragraph's <b> and ParagraphStyle
        # fontName resolution work as expected.
        addMapping(FONT_REGULAR, 0, 0, FONT_REGULAR)
        addMapping(FONT_REGULAR, 1, 0, FONT_BOLD)
    else:
        # Regular-only fallback: bold falls back to regular, but at
        # least every glyph renders.
        addMapping(FONT_REGULAR, 0, 0, FONT_REGULAR)
        addMapping(FONT_REGULAR, 1, 0, FONT_REGULAR)

    _FONTS_REGISTERED = True
    logger.info(
        "Registered Cyrillic fonts for PDF reports: regular=%s bold=%s",
        regular_path, bold_path or "(missing, using regular for bold)",
    )
    return True


# Register at import time so the first report request doesn't pay the
# cost and any registration failures are visible in startup logs.
_register_cyrillic_fonts()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NOSOLOGY_LABELS = {
    "ars": "Острый риносинусит",
    "crs": "Хронический риносинусит",
    "tonsillopharyngitis": "Острый тонзиллофарингит",
    "aom": "Острый средний отит",
    "com": "Хронический средний отит",
    "adenoid_hypertrophy": "Гипертрофия аденоидов",
    "undiagnosed_nose": "Без диагноза: нос",
    "undiagnosed_throat": "Без диагноза: горло",
    "undiagnosed_ear": "Без диагноза: ухо",
    "undiagnosed_multiple": "Без диагноза: несколько областей",
    "non_ent": "Не ЛОР-проблема (дневник без анализа «красных флагов»)",
}

TRIAGE_LABELS = {
    "green": ("Наблюдение", colors.HexColor("#27AE60")),
    "yellow": ("Запись к врачу", colors.HexColor("#F39C12")),
    "orange": ("Срочная консультация", colors.HexColor("#E67E22")),
    "red": ("Экстренная помощь", colors.HexColor("#E74C3C")),
}

AGE_LABELS = {
    "<6mo": "до 6 мес.",
    "6-23mo": "6–23 мес.",
    "2-5y": "2–5 лет",
    "6-14y": "6–14 лет",
    "15-44y": "15–44 года",
    ">=45y": "45 лет и старше",
}

# Keyboard button labels for each scale_type — mirrors inline.py keyboards.
# Used to convert raw numeric values back to the text the patient chose.
SCALE_VALUE_LABELS: dict[str, dict[int, str]] = {
    "severity_0_3": {-1: "Сложно оценить", 0: "Нет", 1: "Слабо", 2: "Умеренно", 3: "Сильно"},
    "discharge": {0: "Нет", 1: "Прозрачные", 2: "Жёлтые", 3: "Зелёные/гнойные"},
    "binary": {0: "Нет", 1: "Да"},
    "temp": {0: "< 37.5°C", 1: "37.5–38°C", 2: "38–39°C", 3: "> 39°C"},
    "vas_0_10": {i: str(i) for i in range(11)},
    "duration": {0: "1–2 дня", 1: "3–5 дней", 2: "5–10 дней", 3: "Более 10 дней"},
    "ome_duration": {0: "Менее 1 месяца", 1: "1–3 месяца", 2: "3–6 месяцев", 3: "Более 6 месяцев"},
    "antipyretic_response": {
        0: "Хорошо снижает",
        1: "Снижает ненадолго",
        2: "Почти не снижает",
        3: "Не принимал(а)",
    },
    "analgesic_response": {
        0: "Хорошо помогает",
        1: "Помогает частично",
        2: "Почти не помогает",
        3: "Не принимал(а)",
    },
    "fever_duration": {
        0: "1–2 дня",
        1: "3–4 дня",
        2: "5–7 дней",
        3: "Более 7 дней",
    },
}

# Red flag answers are binary yes/no.
RED_FLAG_VALUE_LABELS: dict[int, str] = {0: "Нет", 1: "Да"}

# Brand colours (from landing page design system)
COLOR_DARK_BLUE = colors.HexColor("#1F3864")
COLOR_MED_BLUE = colors.HexColor("#2E75B6")
COLOR_LIGHT_BLUE = colors.HexColor("#D6E4F0")
COLOR_BG = colors.HexColor("#F8FAFC")

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def _build_styles():
    """Build ReportLab paragraph styles for the report.

    Every style pins `fontName` to our registered Cyrillic font so that
    Russian characters render correctly. If registration failed (no
    DejaVu found at runtime), we gracefully fall back to Helvetica —
    the text will still render, just without Cyrillic glyphs, matching
    the failure mode users would see before this fix.
    """
    styles = getSampleStyleSheet()
    font_name = FONT_REGULAR if _FONTS_REGISTERED else "Helvetica"
    font_bold = FONT_BOLD if _FONTS_REGISTERED else "Helvetica-Bold"

    styles.add(ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName=font_bold,
        fontSize=18,
        textColor=COLOR_DARK_BLUE,
        spaceAfter=6 * mm,
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontName=font_bold,
        fontSize=13,
        textColor=COLOR_DARK_BLUE,
        spaceBefore=6 * mm,
        spaceAfter=3 * mm,
    ))
    styles.add(ParagraphStyle(
        "BodyRu",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10,
        leading=14,
    ))
    styles.add(ParagraphStyle(
        "Disclaimer",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=8,
        textColor=colors.gray,
        alignment=TA_CENTER,
        spaceBefore=8 * mm,
    ))
    styles.add(ParagraphStyle(
        "SmallRight",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=8,
        textColor=colors.gray,
        alignment=TA_RIGHT,
    ))
    return styles


# ---------------------------------------------------------------------------
# Chart generation (matplotlib → PNG bytes)
# ---------------------------------------------------------------------------

def _generate_trend_chart(
    entries: list[dict], nosology: str, period_days: int = 7
) -> bytes:
    """
    Generate a symptom trend PNG chart from diary entries.

    Parameters
    ----------
    entries : list of dicts with keys: recorded_at (datetime),
              composite_score (int), triage_level (str)
    nosology : str
    period_days : int
        Period covered by the report; used to pin sensible x-axis limits
        so a single data point doesn't produce a half-year axis.

    Returns
    -------
    PNG image as bytes
    """
    if not entries:
        return b""

    # Sort chronologically
    entries_sorted = sorted(entries, key=lambda e: e["recorded_at"])

    dates = [e["recorded_at"] for e in entries_sorted]
    scores = [e["composite_score"] for e in entries_sorted]
    levels = [e["triage_level"] for e in entries_sorted]

    triage_colors = {
        "green": "#27AE60",
        "yellow": "#F39C12",
        "orange": "#E67E22",
        "red": "#E74C3C",
    }
    dot_colors = [triage_colors.get(lv, "#999999") for lv in levels]

    fig: Figure
    fig, ax = plt.subplots(figsize=(7, 2.8), dpi=150)

    # Line
    ax.plot(dates, scores, color="#2E75B6", linewidth=1.5, zorder=2)

    # Colored dots per triage level
    for d, s, c in zip(dates, scores, dot_colors):
        ax.scatter(d, s, color=c, s=36, zorder=3, edgecolors="white", linewidths=0.5)

    ax.set_ylabel("Суммарный балл", fontsize=9)
    ax.set_xlabel("")

    # Pin the x-axis to the report window ending at "now". AutoDateLocator
    # with a single point produces meaningless ticks like 01.07/01.01,
    # so we explicitly anchor the range.
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=max(1, period_days))
    # Strip tzinfo for matplotlib (which mixes naïve and aware poorly).
    ax.set_xlim(
        mdates.date2num(start.replace(tzinfo=None)),
        mdates.date2num(now.replace(tzinfo=None)),
    )

    # Choose a tick density that fits the range without crowding.
    if period_days <= 7:
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    elif period_days <= 14:
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    else:
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    fig.autofmt_xdate(rotation=30, ha="right")

    ax.grid(axis="y", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_title("Динамика симптомов", fontsize=11, color="#1F3864", loc="left")

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# PDF assembly
# ---------------------------------------------------------------------------

async def generate_pdf_report(
    user_data: dict,
    entries: list[dict],
    period_days: int = 7,
    scale_scores: list[dict] | None = None,
    episodes: list[dict] | None = None,
    recommendations: list[str] | None = None,
    full: bool = True,
) -> bytes:
    """
    Generate a PDF symptom report.

    Parameters
    ----------
    user_data : dict
        Keys: first_name, nosology, age_group
    entries : list of dict
        Each entry: recorded_at, symptoms (dict), composite_score (int),
                    triage_level (str), triage_message (str), red_flags (list)
        Should already be filtered to the requested period.
    period_days : int
        Report period in days (7, 14, or 30).
    scale_scores : list of dict, optional
        Each: scale (str), score (int), action (str), details (dict),
              created_at (datetime).
    episodes : list of dict, optional
        Each: episode_type (str), started_at (datetime), scale_score (int|None),
              notes (str).
    recommendations : list of str, optional
        Clinical criteria-based recommendations for the physician.
    full : bool
        Полный отчёт или бесплатная сводка. В сокращённой версии
        остаются даты, баллы, оценки триажа и красные флаги, то есть
        всё, что относится к безопасности. Убираются график динамики,
        детализация по симптомам, шкалы, эпизоды и блок рекомендаций.

    Returns
    -------
    bytes — PDF file content
    """
    styles = _build_styles()
    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title="ЛОРдок: отчёт для врача",
        author="ЛОРдок",
    )

    story: list = []
    now = datetime.now(timezone.utc)

    # ── Header ──────────────────────────────────────────────
    story.append(Paragraph("ЛОРдок: отчёт для врача", styles["ReportTitle"]))

    nosology_label = NOSOLOGY_LABELS.get(user_data.get("nosology", ""), "—")
    age_label = AGE_LABELS.get(user_data.get("age_group", ""), "—")
    first_name = user_data.get("first_name", "Пациент")

    meta_data = [
        ["Пациент:", first_name],
        ["Диагноз:", nosology_label],
        ["Возрастная группа:", age_label],
        ["Период отчёта:", f"Последние {period_days} дней"],
        ["Дата формирования:", now.strftime("%d.%m.%Y %H:%M UTC")],
    ]

    font_name = FONT_REGULAR if _FONTS_REGISTERED else "Helvetica"
    font_bold = FONT_BOLD if _FONTS_REGISTERED else "Helvetica-Bold"

    meta_table = Table(meta_data, colWidths=[45 * mm, 120 * mm])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), COLOR_DARK_BLUE),
        ("FONTNAME", (0, 0), (0, -1), font_bold),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_MED_BLUE))

    # ── Trend chart ─────────────────────────────────────────
    if entries and full:
        story.append(Paragraph("Динамика симптомов", styles["SectionHeader"]))
        chart_png = _generate_trend_chart(
            entries, user_data.get("nosology", ""), period_days=period_days
        )
        if chart_png:
            chart_img = Image(io.BytesIO(chart_png), width=170 * mm, height=65 * mm)
            story.append(chart_img)
        story.append(Spacer(1, 3 * mm))

    # ── Daily log table ─────────────────────────────────────
    story.append(Paragraph("Ежедневные записи", styles["SectionHeader"]))

    if not entries:
        story.append(Paragraph(
            "За выбранный период записей не найдено.",
            styles["BodyRu"],
        ))
    else:
        entries_sorted = sorted(entries, key=lambda e: e["recorded_at"])

        # Table header
        header = ["Дата", "Балл", "Триаж", "Красные флаги"]
        table_data = [header]

        for entry in entries_sorted:
            dt_str = entry["recorded_at"].strftime("%d.%m.%Y")
            score = str(entry.get("composite_score", "—"))
            triage_lv = entry.get("triage_level", "green")
            triage_label, _ = TRIAGE_LABELS.get(triage_lv, ("—", colors.gray))

            rf = entry.get("red_flags", [])
            rf_str = ", ".join(rf) if rf else "—"

            table_data.append([dt_str, score, triage_label, rf_str])

        col_widths = [28 * mm, 18 * mm, 40 * mm, 80 * mm]
        t = Table(table_data, colWidths=col_widths, repeatRows=1)

        # Colour rows by triage level
        style_commands = [
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTNAME", (0, 0), (-1, 0), font_bold),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_LIGHT_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_DARK_BLUE),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]

        for row_idx, entry in enumerate(entries_sorted, start=1):
            triage_lv = entry.get("triage_level", "green")
            _, triage_color = TRIAGE_LABELS.get(triage_lv, ("—", colors.gray))
            # Tint the triage column cell
            style_commands.append(
                ("TEXTCOLOR", (2, row_idx), (2, row_idx), triage_color)
            )

        t.setStyle(TableStyle(style_commands))
        story.append(t)

    # ── Detailed symptom entries ──────────────────────────────
    if entries and full:
        story.append(Paragraph("Детализация записей", styles["SectionHeader"]))

        entries_sorted_detail = sorted(entries, key=lambda e: e["recorded_at"])
        for idx, entry in enumerate(entries_sorted_detail, 1):
            dt_str = entry["recorded_at"].strftime("%d.%m.%Y %H:%M")
            triage_lv = entry.get("triage_level", "green")
            triage_label, triage_color = TRIAGE_LABELS.get(
                triage_lv, ("—", colors.gray)
            )

            # Entry sub-header
            story.append(Paragraph(
                f'<b>Запись {idx}</b>: {dt_str} '
                f'(<font color="{triage_color.hexval()}">{triage_label}</font>)',
                styles["BodyRu"],
            ))
            story.append(Spacer(1, 1.5 * mm))

            # Symptom key-value pairs — show button text, not raw numbers
            symptoms = entry.get("symptoms", {})
            if symptoms:
                # Import param labels lazily to avoid circular imports
                from bot.triage.params import get_params, get_red_flags

                nosology = entry.get("nosology", "")
                params_list = get_params(nosology)
                red_flags_list = get_red_flags(nosology)

                # Build lookups: param_id → label_ru, param_id → scale_type,
                # param_id → value_map (for reverse-mapping stored values),
                # param_id → is_pain (for "Не болит" label on zero value)
                label_map: dict[str, str] = {}
                scale_map: dict[str, str] = {}
                value_map_reverse: dict[str, dict[int, int]] = {}
                pain_params: set[str] = set()

                for p in params_list:
                    pid = p["id"]
                    label_map[pid] = p.get("label_ru", pid)
                    scale_map[pid] = p.get("scale_type", "binary")
                    if p.get("is_pain"):
                        pain_params.add(pid)
                    vmap = p.get("value_map")
                    if vmap:
                        # Reverse: mapped_value → original_bucket
                        value_map_reverse[pid] = {v: k for k, v in vmap.items()}

                rf_ids: set[str] = set()
                for rf in red_flags_list:
                    rid = rf["id"]
                    rf_ids.add(rid)
                    label_map[rid] = rf.get("question_ru", rf.get("label_ru", rid))

                symptom_rows = [["Симптом", "Ответ"]]
                for key, val in symptoms.items():
                    label = label_map.get(key, key)
                    # Truncate long labels for table fit
                    if len(label) > 60:
                        label = label[:57] + "..."

                    # Convert numeric value to button text
                    if key in rf_ids:
                        # Red flag — binary yes/no
                        display_val = RED_FLAG_VALUE_LABELS.get(val, str(val))
                    elif key in scale_map:
                        scale_type = scale_map[key]
                        lookup_val = val
                        # If value_map was applied, reverse to original bucket
                        if key in value_map_reverse and val in value_map_reverse[key]:
                            lookup_val = value_map_reverse[key][val]
                        labels = SCALE_VALUE_LABELS.get(scale_type, {})
                        display_val = labels.get(lookup_val, str(val))
                        # Pain params: show "Не болит" instead of "Нет" for 0
                        if key in pain_params and lookup_val == 0:
                            display_val = "Не болит"
                    elif isinstance(val, str):
                        # String values like age group — show as-is
                        display_val = val
                    else:
                        display_val = str(val)

                    symptom_rows.append([label, display_val])

                if len(symptom_rows) > 1:
                    sym_table = Table(
                        symptom_rows,
                        colWidths=[120 * mm, 40 * mm],
                        repeatRows=1,
                    )
                    sym_table.setStyle(TableStyle([
                        ("FONTNAME", (0, 0), (-1, -1), font_name),
                        ("FONTNAME", (0, 0), (-1, 0), font_bold),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("BACKGROUND", (0, 0), (-1, 0), COLOR_LIGHT_BLUE),
                        ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_DARK_BLUE),
                        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ]))
                    story.append(sym_table)

            # User notes
            user_notes = entry.get("user_notes", "")
            if user_notes:
                story.append(Spacer(1, 1 * mm))
                story.append(Paragraph(
                    f'<b>Комментарий пациента:</b> {user_notes}',
                    styles["BodyRu"],
                ))

            # Red flags for this entry
            rf = entry.get("red_flags", [])
            if rf:
                story.append(Spacer(1, 1 * mm))
                rf_str = ", ".join(rf)
                story.append(Paragraph(
                    f'<b>Тревожные признаки:</b> {rf_str}',
                    styles["BodyRu"],
                ))

            story.append(Spacer(1, 3 * mm))

    # ── Latest triage result ────────────────────────────────
    if entries:
        latest = max(entries, key=lambda e: e["recorded_at"])
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("Последний результат триажа", styles["SectionHeader"]))

        triage_lv = latest.get("triage_level", "green")
        triage_label, triage_color = TRIAGE_LABELS.get(triage_lv, ("—", colors.gray))
        msg = latest.get("triage_message", "")

        result_text = (
            f'<font color="{triage_color.hexval()}">'
            f'<b>{triage_label}</b></font><br/>{msg}'
        )
        story.append(Paragraph(result_text, styles["BodyRu"]))

    # ── Scale scores (Centor, FeverPAIN, etc.) ──────────────
    if scale_scores and full:
        story.append(Paragraph("Валидированные шкалы", styles["SectionHeader"]))

        SCALE_LABELS = {
            "centor": "Centor / McIsaac",
            "feverpain": "FeverPAIN",
        }
        ACTION_LABELS = {
            "no_abx": "Антибиотики не показаны",
            "delayed_abx": "Отложенная тактика",
            "consider_abx": "Рассмотреть антибиотики",
            "abx_recommended": "Антибиотики рекомендованы",
        }

        scale_header = ["Дата", "Шкала", "Баллы", "Рекомендация"]
        scale_data = [scale_header]
        for sc in sorted(scale_scores, key=lambda s: s["created_at"]):
            dt_str = sc["created_at"].strftime("%d.%m.%Y")
            scale_name = SCALE_LABELS.get(sc["scale"], sc["scale"])
            score_val = str(sc["score"])
            action_text = ACTION_LABELS.get(sc.get("action", ""), sc.get("action", "—"))
            scale_data.append([dt_str, scale_name, score_val, action_text])

        sc_widths = [28 * mm, 40 * mm, 20 * mm, 78 * mm]
        sc_table = Table(scale_data, colWidths=sc_widths, repeatRows=1)
        sc_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTNAME", (0, 0), (-1, 0), font_bold),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_LIGHT_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_DARK_BLUE),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(sc_table)

    # ── Episodes ───────────────────────────────────────────
    if episodes and full:
        story.append(Paragraph("Зарегистрированные эпизоды", styles["SectionHeader"]))

        EPISODE_TYPE_LABELS = {
            "tonsillopharyngitis": "Тонзиллофарингит",
            "aom": "Острый средний отит",
            "crs_flare": "Обострение ХРС",
        }

        ep_header = ["Дата начала", "Тип", "Балл шкалы", "Заметки"]
        ep_data = [ep_header]
        for ep in sorted(episodes, key=lambda e: e["started_at"], reverse=True):
            dt_str = ep["started_at"].strftime("%d.%m.%Y")
            ep_type = EPISODE_TYPE_LABELS.get(ep["episode_type"], ep["episode_type"])
            score_str = str(ep["scale_score"]) if ep.get("scale_score") is not None else "—"
            notes = ep.get("notes", "") or "—"
            if len(notes) > 50:
                notes = notes[:47] + "..."
            ep_data.append([dt_str, ep_type, score_str, notes])

        ep_widths = [28 * mm, 45 * mm, 25 * mm, 68 * mm]
        ep_table = Table(ep_data, colWidths=ep_widths, repeatRows=1)
        ep_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTNAME", (0, 0), (-1, 0), font_bold),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_LIGHT_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_DARK_BLUE),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(ep_table)

    # ── Recommendations ────────────────────────────────────
    if recommendations and full:
        story.append(Paragraph("Рекомендации врачу", styles["SectionHeader"]))
        story.append(Paragraph(
            "На основе кумулятивных данных пациента и международных "
            "клинических критериев:",
            styles["BodyRu"],
        ))
        story.append(Spacer(1, 2 * mm))
        for rec in recommendations:
            story.append(Paragraph(
                f'• {rec}',
                styles["BodyRu"],
            ))
            story.append(Spacer(1, 1.5 * mm))

    # ── Что осталось за пределами бесплатной версии ─────────
    if not full:
        story.append(Spacer(1, 6 * mm))
        story.append(HRFlowable(width="100%", thickness=0.3, color=COLOR_MED_BLUE))
        story.append(Paragraph(
            "Это сводка за 7 дней. В полной версии отчёта есть график "
            "динамики симптомов, детализация по каждому симптому, "
            "валидированные шкалы, учёт эпизодов и блок рекомендаций "
            "для врача.",
            styles["Disclaimer"],
        ))

    # ── Disclaimer ──────────────────────────────────────────
    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width="100%", thickness=0.3, color=colors.lightgrey))
    story.append(Paragraph(
        "ЛОРдок это информационный сервис для мониторинга симптомов. "
        "Не является медицинским изделием. "
        "Не предназначен для постановки диагноза или назначения лечения. "
        "При ухудшении состояния всегда обращайтесь к врачу.",
        styles["Disclaimer"],
    ))
    story.append(Paragraph(
        f"Сгенерировано: {now.strftime('%d.%m.%Y %H:%M')} · lordok.ru",
        styles["SmallRight"],
    ))

    # ── Build ───────────────────────────────────────────────
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Chart-only service (for /history in premium mode)
# ---------------------------------------------------------------------------

async def generate_trend_chart_png(entries: list[dict], nosology: str) -> Optional[bytes]:
    """Return trend chart as PNG bytes, or None if no data."""
    if not entries:
        return None
    return _generate_trend_chart(entries, nosology)
