"""
Chart generation utilities for ЛОРдок.
Thin wrapper around pdf_report chart functions for use in handlers.
"""

from bot.services.pdf_report import generate_trend_chart_png

__all__ = ["generate_trend_chart_png"]
