"""Triage data models — shared across engine and rule modules."""

from dataclasses import dataclass, field
from enum import Enum


class TriageLevel(Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


@dataclass
class TriageResult:
    level: TriageLevel
    message_ru: str
    rationale_en: str
    red_flags_triggered: list[str] = field(default_factory=list)
    guideline_ref: str = ""
    safety_net_ru: str = ""
