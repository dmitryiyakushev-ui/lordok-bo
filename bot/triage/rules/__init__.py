"""
Triage rule modules for each nosology.

Each module exports a run_triage() function with signature:
    run_triage(symptoms, composite_score, symptom_duration, trend, previous_entries) -> dict
"""

from . import acute_rhinosinusitis
from . import chronic_rhinosinusitis
from . import acute_tonsillopharyngitis
from . import acute_otitis_media
from . import chronic_otitis_media
from . import adenoid_hypertrophy
from . import undiagnosed
from . import non_ent

__all__ = [
    "acute_rhinosinusitis",
    "chronic_rhinosinusitis",
    "acute_tonsillopharyngitis",
    "acute_otitis_media",
    "chronic_otitis_media",
    "adenoid_hypertrophy",
    "undiagnosed",
    "non_ent",
]
