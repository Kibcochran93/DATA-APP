"""
Cross-row data-integrity checks for SEAtS imports.

These complement utils.seats_validator (schema + per-cell rules) with checks that
span multiple rows — the kind of dirty-SIS-export problem that passes cell-level
validation but breaks a SEAtS import. Ported from the standalone SEAtS Data
Validator v2.1 browser tool:

  #4  Within-file Name <-> ID 1:many conflicts (School/Course/Module/...)
  #4  Students with more than one distinct login id
  #5  Timetable event-consistency (per EVENT_ID first-row consistency,
      duplicate student-per-event, site/building all-or-nothing)
  #6  BADGENUMBER blank-header auto-heal

Every check returns a list of plain issue dicts:
    {"row": <1-based spreadsheet row or None>, "field": <column>,
     "type": "error"|"warning", "message": <str>}
so callers (the wizard, tests, CLI) can display them uniformly.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import pandas as pd

# pandas names blank header cells "Unnamed: N" on read; treat those as blank.
_PANDAS_BLANK = re.compile(r"^unnamed:\s*\d+$", re.I)

# Header row is row 1, so the first data row is row 2 (matches the v2.1 tool and
# what a user sees in Excel).
FIRST_DATA_ROW = 2

# (label, id-field candidates, name-field candidates)
NAME_ID_PAIRS = [
    ("School", ["SCHOOL_ID"], ["SCHOOL_NAME"]),
    ("Course", ["COURSE_ID"], ["COURSE_NAME"]),
    ("Module", ["MODULE_ID"], ["MODULE_NAME"]),
    ("Programme", ["PROGRAMME_ID"], ["PROGRAMME_NAME"]),
    ("Faculty", ["FACULTY_ID"], ["FACULITY_NAME", "FACULTY_NAME"]),
    ("Room", ["ROOM_ID"], ["ROOM_NAME"]),
    ("Site", ["SITE_ID", "SITE_CODE"], ["SITE_NAME"]),
    ("Building", ["BUILDING_ID"], ["BUILDING_NAME"]),
]

# Fields that must be identical across every row sharing an EVENT_ID.
EVENT_CONSISTENT_FIELDS = [
    "DAY", "START_TIME", "END_TIME", "ROOM_ID", "ROOM_NAME",
    "COURSE_ID", "COURSE_NAME", "MODULE_ID", "MODULE_NAME",
    "SCHOOL_ID", "SCHOOL_NAME",
]

SITE_FIELDS = ["SITE_CODE", "SITE_NAME"]
BUILDING_FIELDS = ["BUILDING_ID", "BUILDING_NAME"]


def _colmap(df: pd.DataFrame) -> Dict[str, str]:
    """Upper-cased column name -> actual column name."""
    return {str(c).strip().upper(): c for c in df.columns}


def _first_present(colmap: Dict[str, str], candidates: List[str]) -> Optional[str]:
    for cand in candidates:
        if cand.upper() in colmap:
            return colmap[cand.upper()]
    return None


def _cell(row, col: Optional[str]) -> str:
    if not col:
        return ""
    value = row.get(col, "")
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def find_name_id_conflicts(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Flag any NAME that is linked to more than one ID (per entity type)."""
    issues: List[Dict[str, Any]] = []
    if df is None or df.empty:
        return issues
    colmap = _colmap(df)
    records = list(df.to_dict("records"))

    for label, id_cands, name_cands in NAME_ID_PAIRS:
        id_field = _first_present(colmap, id_cands)
        name_field = _first_present(colmap, name_cands)
        if not id_field or not name_field:
            continue

        by_name: Dict[str, Dict[str, int]] = {}
        for pos, row in enumerate(records):
            ident = _cell(row, id_field)
            name = _cell(row, name_field)
            if not ident or not name:
                continue
            key = name.lower()
            ids = by_name.setdefault(key, {})
            if ident not in ids:
                ids[ident] = pos + FIRST_DATA_ROW

        for key, ids in by_name.items():
            if len(ids) < 2:
                continue
            ordered = sorted(ids.items(), key=lambda kv: kv[1])
            display_name = next(
                _cell(r, name_field) for r in records if _cell(r, name_field).lower() == key
            )
            listed = ", ".join(f"{ident} (row {row})" for ident, row in ordered)
            issues.append({
                "row": ordered[1][1],
                "field": id_field,
                "type": "warning",
                "message": f'{label} name "{display_name}" is linked to multiple '
                           f"{label} IDs: {listed}",
            })
    return issues


def find_login_id_conflicts(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Flag students (STUDENT_ID) that have more than one distinct login id."""
    issues: List[Dict[str, Any]] = []
    if df is None or df.empty:
        return issues
    colmap = _colmap(df)
    id_field = _first_present(colmap, ["STUDENT_ID"])
    login_field = _first_present(colmap, ["STUDENT_LOGIN_ID"])
    if not id_field or not login_field:
        return issues

    logins_by_student: Dict[str, Dict[str, int]] = {}
    for pos, row in enumerate(df.to_dict("records")):
        student = _cell(row, id_field)
        login = _cell(row, login_field)
        if not student or not login:
            continue
        seen = logins_by_student.setdefault(student, {})
        seen.setdefault(login, pos + FIRST_DATA_ROW)

    for student, logins in logins_by_student.items():
        if len(logins) < 2:
            continue
        first_row = min(logins.values())
        listed = ", ".join(sorted(logins))
        issues.append({
            "row": first_row,
            "field": login_field,
            "type": "warning",
            "message": f"Student {student} has multiple login IDs: {listed}",
        })
    return issues


def find_event_consistency_issues(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Timetable-only cross-row checks keyed on EVENT_ID."""
    issues: List[Dict[str, Any]] = []
    if df is None or df.empty:
        return issues
    colmap = _colmap(df)
    event_field = _first_present(colmap, ["EVENT_ID"])
    if not event_field:
        return issues
    student_field = _first_present(colmap, ["STUDENT_ID"])

    seen_event_student: Dict[str, int] = {}
    first_event_row: Dict[str, Dict[str, Any]] = {}

    for pos, row in enumerate(df.to_dict("records")):
        row_number = pos + FIRST_DATA_ROW
        event_id = _cell(row, event_field)

        # Site/building all-or-nothing.
        site_cols = [colmap[f.upper()] for f in SITE_FIELDS if f.upper() in colmap]
        building_cols = [colmap[f.upper()] for f in BUILDING_FIELDS if f.upper() in colmap]
        has_site = any(_cell(row, c) for c in site_cols)
        has_building = any(_cell(row, c) for c in building_cols)
        if has_site or has_building:
            for col in site_cols + building_cols:
                if not _cell(row, col):
                    issues.append({
                        "row": row_number, "field": col, "type": "error",
                        "message": "Site and building details must all be populated "
                                   "when either is provided",
                    })

        if not event_id:
            continue

        # Duplicate student within the same event.
        if student_field:
            student_id = _cell(row, student_field)
            if student_id:
                key = f"{event_id}\x00{student_id}"
                if key in seen_event_student:
                    issues.append({
                        "row": row_number, "field": student_field, "type": "warning",
                        "message": f"Student is already listed for this event on row "
                                   f"{seen_event_student[key]}",
                    })
                else:
                    seen_event_student[key] = row_number

        # Consistency of event-level fields vs the first row for this event.
        if event_id not in first_event_row:
            first_event_row[event_id] = {"row": row_number, "data": row}
        else:
            first = first_event_row[event_id]
            for field in EVENT_CONSISTENT_FIELDS:
                col = colmap.get(field.upper())
                if not col:
                    continue
                current = _cell(row, col)
                original = _cell(first["data"], col)
                if current and original and current != original:
                    issues.append({
                        "row": row_number, "field": col, "type": "warning",
                        "message": f"Value differs from the first row for event "
                                   f"{event_id} (row {first['row']})",
                    })
    return issues


def heal_headers(headers: List[str]) -> List[str]:
    """Repair the known SEAtS template quirk where the BADGENUMBER header is blank.

    If the header row contains ``VISAREQUIRED, <blank>, COURSE_ID`` in sequence,
    the blank is the BADGENUMBER column; fill it in. Returns a new list.
    """
    healed = [("" if h is None else str(h)).strip() for h in headers]

    def _is_blank(name: str) -> bool:
        return name == "" or bool(_PANDAS_BLANK.match(name))

    for i, name in enumerate(healed):
        if name.upper() == "VISAREQUIRED" and i + 2 < len(healed):
            if _is_blank(healed[i + 1]) and healed[i + 2].upper() == "COURSE_ID":
                healed[i + 1] = "BADGENUMBER"
    return healed


def run_all(df: pd.DataFrame, dataset_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Run every integrity check appropriate to the dataset and return all issues."""
    issues = find_name_id_conflicts(df)
    issues += find_login_id_conflicts(df)
    if dataset_type is None or "timetable" in str(dataset_type).lower():
        issues += find_event_consistency_issues(df)
    return issues
