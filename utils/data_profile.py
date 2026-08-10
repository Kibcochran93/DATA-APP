"""
"Profile the data before export" — quick entity counts so an implementer can
sanity-check an import ("37 unique schools? should be 6") before shipping it to
SEAtS. Ported from the standalone SEAtS Data Validator v2.1 analysis grid.

profile_dataframe() returns a list of card dicts:
    {"label": str, "count": int, "values": list[str],
     "kind": "values" | "conflicts", "state": None | "good" | "warning"}
The wizard renders these as cards with a drill-down; tests assert on them
directly.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd


def _colmap(df: pd.DataFrame) -> Dict[str, str]:
    return {str(c).strip().upper(): c for c in df.columns}


def _has(colmap: Dict[str, str], name: str) -> Optional[str]:
    return colmap.get(name.upper())


def _clean_series(df: pd.DataFrame, col: str) -> List[str]:
    return [s for s in (str(v).strip() for v in df[col].tolist()) if s and s.lower() != "nan"]


def unique_values(df: pd.DataFrame, field: str) -> List[str]:
    """Sorted distinct non-blank values for a column (numeric-aware sort)."""
    col = _colmap(df).get(field.upper())
    if not col:
        return []
    values = set(_clean_series(df, col))
    return sorted(values, key=lambda s: (len(s), s) if not s.isdigit() else (0, int(s)))


def unique_entities(df: pd.DataFrame, id_field: str, name_fields: List[str]) -> List[str]:
    """Distinct "ID — Name" entities keyed on id (falling back to name)."""
    colmap = _colmap(df)
    id_col = colmap.get(id_field.upper())
    name_cols = [colmap[f.upper()] for f in name_fields if f.upper() in colmap]
    if not id_col and not name_cols:
        return []

    entities: Dict[str, str] = {}
    for row in df.to_dict("records"):
        ident = str(row.get(id_col, "")).strip() if id_col else ""
        ident = "" if ident.lower() == "nan" else ident
        name = ""
        for nc in name_cols:
            candidate = str(row.get(nc, "")).strip()
            if candidate and candidate.lower() != "nan":
                name = candidate
                break
        key = ident or name
        if not key or key in entities:
            continue
        entities[key] = f"{ident} — {name}" if (ident and name and ident != name) else key
    return sorted(entities.values(), key=lambda s: (len(s), s))


def _login_conflicts(df: pd.DataFrame) -> List[Dict[str, Any]]:
    colmap = _colmap(df)
    id_col = colmap.get("STUDENT_ID")
    login_col = colmap.get("STUDENT_LOGIN_ID")
    email_cols = [colmap[c] for c in ("STUDENT_EMAIL", "UNIVERSITY_EMAIL") if c in colmap]
    if not id_col or not login_col:
        return []

    grouped: Dict[str, Dict[str, set]] = {}
    for row in df.to_dict("records"):
        student = str(row.get(id_col, "")).strip()
        if not student or student.lower() == "nan":
            continue
        g = grouped.setdefault(student, {"logins": set(), "emails": set()})
        login = str(row.get(login_col, "")).strip()
        if login and login.lower() != "nan":
            g["logins"].add(login)
        for ec in email_cols:
            email = str(row.get(ec, "")).strip()
            if email and email.lower() != "nan":
                g["emails"].add(email)

    return [
        {"student": student, "logins": sorted(g["logins"]), "emails": sorted(g["emails"])}
        for student, g in grouped.items() if len(g["logins"]) > 1
    ]


def profile_dataframe(df: pd.DataFrame, dataset_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Build analysis cards appropriate to the dataset type."""
    cards: List[Dict[str, Any]] = []
    if df is None or df.empty:
        return cards
    colmap = _colmap(df)
    is_timetable = dataset_type is not None and "timetable" in str(dataset_type).lower()
    is_timetable = is_timetable or ("EVENT_ID" in colmap and "STUDENT_ID" in colmap and dataset_type is None)

    def card(label, values, kind="values", state=None):
        cards.append({"label": label, "count": len(values), "values": values,
                      "kind": kind, "state": state})

    if is_timetable:
        if "EVENT_ID" in colmap:
            card("Unique events", unique_values(df, "EVENT_ID"))
        if "STUDENT_ID" in colmap:
            card("Unique students", unique_values(df, "STUDENT_ID"))
        if "COURSE_ID" in colmap:
            card("Unique course values", unique_values(df, "COURSE_ID"))
        if "MODULE_ID" in colmap:
            card("Unique module values", unique_values(df, "MODULE_ID"))
        if "SCHOOL_ID" in colmap or "SCHOOL_NAME" in colmap:
            card("Unique schools", unique_entities(df, "SCHOOL_ID", ["SCHOOL_NAME"]))
        return cards

    # Student (default) profile.
    if "STUDENT_ID" in colmap:
        card("Unique students", unique_values(df, "STUDENT_ID"))
    if "COURSE_ID" in colmap:
        card("Unique course values", unique_values(df, "COURSE_ID"))
    if "MODULE_ID" in colmap:
        card("Unique module values", unique_values(df, "MODULE_ID"))
    if "SCHOOL_ID" in colmap or "SCHOOL_NAME" in colmap:
        card("Unique schools", unique_entities(df, "SCHOOL_ID", ["SCHOOL_NAME"]))
    programmes = unique_entities(df, "PROGRAMME_ID", ["PROGRAMME_NAME"])
    if programmes:
        card("Unique programmes", programmes)
    faculties = unique_entities(df, "FACULTY_ID", ["FACULITY_NAME", "FACULTY_NAME"])
    if faculties:
        card("Unique faculties", faculties)

    conflicts = _login_conflicts(df)
    if "STUDENT_ID" in colmap and "STUDENT_LOGIN_ID" in colmap:
        cards.append({
            "label": "Students with conflicting Login IDs",
            "count": len(conflicts),
            "values": conflicts,
            "kind": "conflicts",
            "state": "warning" if conflicts else "good",
        })
    return cards
