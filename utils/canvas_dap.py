"""
Canvas DAP (Data Access Platform / Canvas Data 2) ingest.

Canvas DAP exports the LMS as separate NORMALISED tables (users, pseudonyms,
enrollments, courses, course_sections, accounts, ...). Unlike a single gradebook
CSV, producing a SEAtS roster requires JOINING those tables. This module does
that join and emits a flat frame with SEAtS-canonical column names, which is then
fed to utils.auto_clean for shaping / validation / the residual report.

Column resolution is tolerant: it is case-insensitive and strips DAP's
`value.` / `key.` / `meta.` prefixes, so it accepts either a flattened CSV
(`name`, `user_id`) or the DAP nested-then-flattened form (`value.name`,
`key.id`). Verify the table/column names against a real DAP extract — the schema
encoded here follows the documented Canvas Data 2 model.

Primary entry points:
    build_roster(tables, dataset_type) -> (roster_df, notes)
    ingest_dap(tables, dataset_type)   -> AutoCleanResult   (build_roster + auto_clean)
where `tables` is {table_name: DataFrame} (keys may include a `canvas.` prefix or
a `.csv`/`.jsonl` suffix).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# enrollment.type values that count as students / staff.
_STUDENT_ENROLLMENTS = {"studentenrollment"}
_STAFF_ENROLLMENTS = {"teacherenrollment", "taenrollment", "designerenrollment"}


def _strip_prefix(name: str) -> str:
    n = str(name).strip().lower()
    for pref in ("value.", "key.", "meta."):
        if n.startswith(pref):
            return n[len(pref):]
    return n


def _colmap(df: pd.DataFrame) -> Dict[str, str]:
    """normalized column name -> actual column name."""
    out: Dict[str, str] = {}
    for c in df.columns:
        out.setdefault(_strip_prefix(c), c)
    return out


def _get(row: Dict[str, Any], colmap: Dict[str, str], *candidates: str) -> str:
    for cand in candidates:
        actual = colmap.get(cand)
        if actual is not None:
            value = row.get(actual, "")
            if value is None or (isinstance(value, float) and pd.isna(value)):
                return ""
            return str(value).strip()
    return ""


def _normalize_tables(tables: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    out: Dict[str, pd.DataFrame] = {}
    for name, df in (tables or {}).items():
        key = str(name).strip().lower().replace("\\", "/").rsplit("/", 1)[-1]
        for ext in (".csv", ".jsonl", ".json", ".parquet", ".tsv"):
            if key.endswith(ext):
                key = key[: -len(ext)]
        if key.startswith("canvas."):
            key = key[len("canvas."):]
        if df is not None:
            out[key] = df
    return out


def _split_name(sortable_name: str, name: str) -> Tuple[str, str]:
    """Return (forename, last_name). Prefer 'Last, First' sortable_name."""
    sortable_name = (sortable_name or "").strip()
    name = (name or "").strip()
    if "," in sortable_name:
        last, _, first = sortable_name.partition(",")
        return first.strip(), last.strip()
    if name:
        parts = name.split()
        if len(parts) == 1:
            return "", parts[0]
        return " ".join(parts[:-1]), parts[-1]
    return "", ""


def _index_by(df: Optional[pd.DataFrame], id_field: str) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
    """Map str(id) -> row dict, keyed on the given normalized id field."""
    if df is None or df.empty:
        return {}, {}
    colmap = _colmap(df)
    id_col = colmap.get(id_field)
    if id_col is None:
        return {}, colmap
    index: Dict[str, Dict[str, Any]] = {}
    for row in df.to_dict("records"):
        key = str(row.get(id_col, "")).strip()
        if key and key not in index:
            index[key] = row
    return index, colmap


def _best_pseudonym_by_user(pseudonyms: Optional[pd.DataFrame]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
    """One pseudonym per user_id: active first, then those carrying a sis_user_id."""
    if pseudonyms is None or pseudonyms.empty:
        return {}, {}
    colmap = _colmap(pseudonyms)
    uid = colmap.get("user_id")
    if uid is None:
        return {}, colmap
    ws = colmap.get("workflow_state")
    sis = colmap.get("sis_user_id")

    def rank(row: Dict[str, Any]) -> tuple:
        active = 1 if (ws and str(row.get(ws, "")).strip().lower() == "active") else 0
        has_sis = 1 if (sis and str(row.get(sis, "")).strip() not in ("", "nan")) else 0
        return (active, has_sis)

    best: Dict[str, Dict[str, Any]] = {}
    best_rank: Dict[str, tuple] = {}
    for row in pseudonyms.to_dict("records"):
        key = str(row.get(uid, "")).strip()
        if not key:
            continue
        r = rank(row)
        if key not in best or r > best_rank[key]:
            best[key] = row
            best_rank[key] = r
    return best, colmap


def _email_by_user(comm_channels: Optional[pd.DataFrame]) -> Dict[str, str]:
    if comm_channels is None or comm_channels.empty:
        return {}
    colmap = _colmap(comm_channels)
    uid = colmap.get("user_id")
    path = colmap.get("path")
    path_type = colmap.get("path_type")
    if uid is None or path is None:
        return {}
    out: Dict[str, str] = {}
    for row in comm_channels.to_dict("records"):
        if path_type and str(row.get(path_type, "")).strip().lower() != "email":
            continue
        key = str(row.get(uid, "")).strip()
        value = str(row.get(path, "")).strip()
        if key and value and key not in out:
            out[key] = value
    return out


def build_roster(tables: Dict[str, pd.DataFrame],
                 dataset_type: str = "Student") -> Tuple[pd.DataFrame, List[str]]:
    """Join Canvas DAP tables into a flat SEAtS-shaped roster (one row per enrollment).

    Returns (roster_df with SEAtS-canonical columns, notes about what was used/missing).
    Raises ValueError if the minimum tables (enrollments, users) are absent.
    """
    notes: List[str] = []
    T = _normalize_tables(tables)

    enrollments = T.get("enrollments")
    users = T.get("users")
    if enrollments is None or users is None:
        raise ValueError("Canvas DAP roster needs at least 'enrollments' and 'users' tables.")

    is_staff = "staff" in dataset_type.lower()
    wanted_types = _STAFF_ENROLLMENTS if is_staff else _STUDENT_ENROLLMENTS

    users_by_id, users_cols = _index_by(users, "id")
    pseudo_by_user, pseudo_cols = _best_pseudonym_by_user(T.get("pseudonyms"))
    courses_by_id, courses_cols = _index_by(T.get("courses"), "id")
    sections_by_id, sections_cols = _index_by(T.get("course_sections"), "id")
    accounts_by_id, accounts_cols = _index_by(T.get("accounts"), "id")
    email_by_user = _email_by_user(T.get("communication_channels"))

    for label, present in [("pseudonyms", pseudo_by_user), ("courses", courses_by_id),
                           ("course_sections", sections_by_id), ("accounts", accounts_by_id)]:
        if not present:
            notes.append(f"'{label}' table not provided — related fields left blank (see residual report).")

    enr_cols = _colmap(enrollments)
    e_type = enr_cols.get("type")
    e_ws = enr_cols.get("workflow_state")
    e_user = enr_cols.get("user_id")
    e_course = enr_cols.get("course_id")
    e_section = enr_cols.get("course_section_id")
    if e_user is None:
        raise ValueError("enrollments table has no user_id column.")

    rows: List[Dict[str, str]] = []
    skipped_inactive = 0
    for enr in enrollments.to_dict("records"):
        if e_type and str(enr.get(e_type, "")).strip().lower() not in wanted_types:
            continue
        if e_ws and str(enr.get(e_ws, "")).strip().lower() not in ("active", ""):
            skipped_inactive += 1
            continue

        user_id = str(enr.get(e_user, "")).strip()
        user = users_by_id.get(user_id, {})
        pseudo = pseudo_by_user.get(user_id, {})
        course = courses_by_id.get(str(enr.get(e_course, "")).strip(), {}) if e_course else {}
        section = sections_by_id.get(str(enr.get(e_section, "")).strip(), {}) if e_section else {}
        acct_id = _get(course, courses_cols, "account_id")
        account = accounts_by_id.get(acct_id, {}) if acct_id else {}

        sis_user_id = _get(pseudo, pseudo_cols, "sis_user_id")
        login_id = _get(pseudo, pseudo_cols, "unique_id")
        forename, last_name = _split_name(
            _get(user, users_cols, "sortable_name"),
            _get(user, users_cols, "name"),
        )
        email = email_by_user.get(user_id, "") or _get(user, users_cols, "email")
        course_id = _get(course, courses_cols, "sis_source_id") or _get(course, courses_cols, "id")
        course_name = _get(course, courses_cols, "name")
        school_id = _get(account, accounts_cols, "sis_source_id") or _get(account, accounts_cols, "id")
        school_name = _get(account, accounts_cols, "name")
        section_name = _get(section, sections_cols, "name")

        person_id = sis_user_id or user_id

        if is_staff:
            rows.append({
                "STAFF_NUMBER": person_id,
                "FORENAME": forename,
                "LAST_NAME": last_name,
                "UNIVERSITY_EMAIL": email,
                "LOGIN_ID": login_id,
            })
        else:
            rows.append({
                "STUDENT_ID": person_id,
                "STUDENT_FORENAME": forename,
                "STUDENT_LAST_NAME": last_name,
                "STUDENT_LOGIN_ID": login_id,
                "STUDENT_EMAIL": email,
                "UNIVERSITY_EMAIL": email,
                "COURSE_ID": course_id,
                "COURSE_NAME": course_name,
                "SCHOOL_ID": school_id,
                "SCHOOL_NAME": school_name,
                "MODULE_GROUP": section_name,  # Canvas section ~ teaching group, not a SEAtS MODULE
            })

    if skipped_inactive:
        notes.append(f"Skipped {skipped_inactive} non-active enrollment(s).")
    notes.append(f"Built {len(rows)} {'staff' if is_staff else 'student'} row(s) from "
                 f"{len(enrollments)} enrollment(s).")
    roster = pd.DataFrame(rows).fillna("")
    return roster, notes


def ingest_dap(tables: Dict[str, pd.DataFrame], dataset_type: str = "Student",
               spec: Optional[Dict[str, Any]] = None):
    """Full path: join DAP tables -> roster -> auto_clean -> AutoCleanResult.

    The returned result's `actions` is prefixed with the DAP join notes.
    """
    from utils.auto_clean import auto_clean

    roster, notes = build_roster(tables, dataset_type)
    result = auto_clean(roster, dataset_type, spec=spec)
    result.actions = [f"[DAP] {n}" for n in notes] + result.actions
    return result
