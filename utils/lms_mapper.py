"""
LMS -> SEATS mapping support.

A Learning Management System (Canvas, Blackboard, Moodle, Brightspace) is a data
SOURCE that can feed the SEATS Student spec — distinct from a Student Information
System (SIS). This module loads the LMS column-alias vocabulary
(data/mappings/lms_to_seats_mapping.json) and offers light detection, mirroring
utils.sis_mapper. The heavy lifting (aliasing + coercion) is done by
utils.auto_clean, which reads both the SIS and LMS vocabularies.
"""
from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


class LMSType(Enum):
    CANVAS = "canvas"
    BLACKBOARD = "blackboard"
    MOODLE = "moodle"
    BRIGHTSPACE = "brightspace"
    GENERIC = "generic"
    UNKNOWN = "unknown"


_SEARCH_PATHS = [
    Path("data/mappings/lms_to_seats_mapping.json"),
    Path("./data/mappings/lms_to_seats_mapping.json"),
    Path("/app/data/mappings/lms_to_seats_mapping.json"),
    Path(__file__).resolve().parent.parent / "data" / "mappings" / "lms_to_seats_mapping.json",
]


def load_lms_mapping(mapping_file: Optional[str] = None) -> Dict[str, Any]:
    """Load the LMS mapping config, or {} if not found."""
    paths = [Path(mapping_file)] if mapping_file else _SEARCH_PATHS
    for path in paths:
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
    return {}


def get_lms_column_mappings(mapping_file: Optional[str] = None) -> Dict[str, Any]:
    """{SEATS_FIELD: {lms_system: [aliases], ...}} from the LMS mapping."""
    return load_lms_mapping(mapping_file).get("column_mappings", {})


def detect_lms_type(df: pd.DataFrame, mapping_file: Optional[str] = None) -> LMSType:
    """Best-guess the LMS from column-name indicators (UNKNOWN if none match)."""
    rules = load_lms_mapping(mapping_file).get("auto_detection_rules", {})
    columns_upper = {str(c).upper() for c in df.columns}

    best_type, best_score = LMSType.UNKNOWN, 0
    for lms in (LMSType.CANVAS, LMSType.BLACKBOARD, LMSType.MOODLE, LMSType.BRIGHTSPACE):
        indicators = rules.get(f"{lms.value}_indicators", [])
        if not indicators:
            continue
        score = sum(
            1 for ind in indicators
            if any(ind.upper() in col or col == ind.upper() for col in columns_upper)
        )
        if score > best_score:
            best_type, best_score = lms, score
    return best_type


__all__ = ["LMSType", "load_lms_mapping", "get_lms_column_mappings", "detect_lms_type"]
