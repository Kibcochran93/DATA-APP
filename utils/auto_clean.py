"""
One-click "Auto-clean to «type»".

Takes a raw, possibly jumbled CSV/Excel DataFrame and the SEAtS dataset type the
customer selected, and does its best to produce an importable file of that type:

  1. heal known header quirks
  2. auto-map source columns to SEAtS fields (user mapping > SIS/alias match)
  3. force the frame to the exact spec shape (spec columns, spec order)
  4. coerce values to the spec (enum codes, dates, encoding, defaults, fixers)
  5. re-assert the spec shape
  6. re-validate and build a cell-precise residual report

Per the product decision, this ALWAYS returns a fully spec-shaped DataFrame (best
effort). Where a mandatory value genuinely can't be produced, the cell is left
blank and listed in `residual_issues` with severity "error" so the customer can
finish the last mile. `summary["importable"]` is True only when no blocking
issue remains.

Pure logic — no Streamlit — so it is unit-tested and reusable from the UI, a CLI,
or a batch job.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from utils.integrity_checks import heal_headers, run_all as run_integrity_checks

# Error types from seats_validator that make a file un-importable as-is.
_BLOCKING_ERROR_TYPES = {"missing_mandatory"}

# validator row indices are 0-based positional; spreadsheets show header as row 1.
_ROW_OFFSET = 2


@dataclass
class AutoCleanResult:
    dataset_type: str
    cleaned_df: pd.DataFrame
    residual_issues: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    spec: Dict[str, Any] = field(default_factory=dict)

    @property
    def importable(self) -> bool:
        return bool(self.summary.get("importable", False))


def _resolve_spec(dataset_type: str, spec: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if spec:
        return spec
    from utils.seats_data_handler import load_spec_by_type
    return load_spec_by_type(dataset_type)


def _norm(value: str) -> str:
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def _build_alias_index(spec_fields: List[str]) -> Dict[str, str]:
    """normalized source-alias -> SEAtS field, across ALL SIS systems + exact names.

    Detection can misfire on jumbled/partial files (e.g. a lone SPRIDEN_ID detects
    as GENERIC), so we match aliases from every system rather than only the
    detected one.
    """
    from utils.sis_mapper import SISMapper

    spec_fields_upper = {f.upper() for f in spec_fields}
    index: Dict[str, str] = {}
    try:
        column_mappings = SISMapper().column_mappings  # {FIELD: {system: [aliases]}}
    except Exception:
        column_mappings = {}
    for seats_field, systems in column_mappings.items():
        if seats_field.upper() not in spec_fields_upper:
            continue
        index.setdefault(_norm(seats_field), seats_field)
        if isinstance(systems, dict):
            for aliases in systems.values():
                for alias in (aliases or []):
                    index.setdefault(_norm(alias), seats_field)
    # Exact spec names always win for their own key.
    for field_name in spec_fields:
        index.setdefault(_norm(field_name), field_name)
    return index


def _auto_map_columns(df: pd.DataFrame, spec: Dict[str, Any], min_confidence: float,
                      actions: List[str]) -> pd.DataFrame:
    """Rename source columns to SEAtS fields: cross-system alias match, then fuzzy."""
    from utils.seats_data_handler import get_ordered_fields
    from utils.sis_mapper import suggest_mappings

    spec_fields = get_ordered_fields(spec)
    spec_fields_upper = {f.upper() for f in spec_fields}
    alias_index = _build_alias_index(spec_fields)

    taken = {c.upper() for c in df.columns}
    rename: Dict[str, str] = {}

    # 1. Deterministic alias match (across all SIS systems).
    for col in df.columns:
        target = alias_index.get(_norm(col))
        if not target or target.upper() in taken or col.upper() == target.upper():
            continue
        rename[col] = target
        taken.add(target.upper())

    # 2. Fuzzy fallback for anything still unmapped.
    try:
        for m in sorted(suggest_mappings(df), key=lambda x: -x.confidence):
            if m.confidence < min_confidence:
                continue
            if m.target_column.upper() not in spec_fields_upper:
                continue
            if m.source_column not in df.columns or m.source_column in rename:
                continue
            if m.target_column.upper() in taken or m.source_column.upper() == m.target_column.upper():
                continue
            rename[m.source_column] = m.target_column
            taken.add(m.target_column.upper())
    except Exception:
        pass

    if rename:
        df = df.rename(columns=rename)
        preview = ", ".join(f"{s}->{t}" for s, t in list(rename.items())[:6])
        actions.append(f"Auto-mapped {len(rename)} column(s) to SEAtS fields "
                       f"({preview}{'…' if len(rename) > 6 else ''}).")
    return df


def _force_spec_shape(df: pd.DataFrame, spec: Dict[str, Any], actions: List[str],
                      log: bool) -> pd.DataFrame:
    from utils.seats_data_handler import fix_column_names_and_order, get_ordered_fields

    df, report = fix_column_names_and_order(
        df, spec,
        rename_variations=True, remove_duplicates=True,
        remove_out_of_spec=True, insert_missing=True,
    )
    if log:
        if report.get("renamed"):
            actions.append(f"Renamed {len(report['renamed'])} column variation(s) to spec names.")
        if report.get("removed_duplicates"):
            actions.append(f"Removed {len(report['removed_duplicates'])} duplicate column(s).")
        if report.get("removed_out_of_spec"):
            actions.append(f"Dropped {len(report['removed_out_of_spec'])} column(s) not in the "
                           f"{spec.get('dataset_type', 'selected')} spec.")
        if report.get("inserted"):
            actions.append(f"Inserted {len(report['inserted'])} missing spec column(s) (blank).")
    # Defensive: guarantee exactly the spec columns, in spec order.
    ordered = [f for f in get_ordered_fields(spec)]
    for f in ordered:
        if f not in df.columns:
            df[f] = ""
    return df[ordered]


def _coerce_values(df: pd.DataFrame, spec: Dict[str, Any], actions: List[str]) -> pd.DataFrame:
    from utils.data_quality import analyze_data_quality, fix_data_quality
    from utils.seats_data_handler import get_seats_handler

    try:
        report = analyze_data_quality(df, spec)
        df, counts = fix_data_quality(df, report, spec)
        total = sum(int(v) for v in (counts or {}).values())
        if total:
            actions.append(f"Fixed {total} data-quality value issue(s) "
                           f"(encoding, enum codes, dates, separators).")
    except Exception:
        pass

    try:
        df, changes = get_seats_handler().apply_auto_fixes(df, spec)
        if changes:
            rows = sum(int(c.get("rows_changed", 0)) for c in changes)
            if rows:
                actions.append(f"Applied spec fixers/defaults to {rows} value(s).")
    except Exception:
        pass
    return df


def _build_residual_report(df: pd.DataFrame, dataset_type: str,
                           spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    from utils.seats_validator import validate_dataset

    issues: List[Dict[str, Any]] = []

    result = validate_dataset(df, dataset_type, spec=spec)
    for e in result.errors:
        severity = "error" if e.error_type in _BLOCKING_ERROR_TYPES else "warning"
        issues.append({
            "row": (e.row_index + _ROW_OFFSET) if isinstance(e.row_index, int) else e.row_index,
            "column": e.column,
            "severity": severity,
            "type": e.error_type,
            "message": e.message,
        })
    for schema_issue in result.schema_issues:
        issues.append({"row": None, "column": None, "severity": "error",
                       "type": "schema", "message": schema_issue})

    for i in run_integrity_checks(df, dataset_type):
        issues.append({
            "row": i.get("row"), "column": i.get("field"),
            "severity": i.get("type", "warning"), "type": "integrity",
            "message": i.get("message", ""),
        })
    return issues


def auto_clean(df: pd.DataFrame, dataset_type: str,
               spec: Optional[Dict[str, Any]] = None,
               user_mapping: Optional[Dict[str, str]] = None,
               min_confidence: float = 0.7) -> AutoCleanResult:
    """Best-effort transform of `df` into an importable file of `dataset_type`.

    Args:
        df: raw uploaded data.
        dataset_type: SEAtS dataset type (Student / Timetable / Staff / custom).
        spec: optional spec dict (e.g. from utils.template_spec); loaded by type if omitted.
        user_mapping: optional confirmed {source_column: seats_field} to apply first.
        min_confidence: minimum SIS/alias match confidence to auto-apply (0-1).
    """
    spec = _resolve_spec(dataset_type, spec)
    actions: List[str] = []
    work = df.copy() if df is not None else pd.DataFrame()

    if not work.empty:
        work.columns = heal_headers(list(work.columns))

        if user_mapping:
            rename = {s: t for s, t in user_mapping.items() if s in work.columns and t}
            if rename:
                work = work.rename(columns=rename)
                actions.append(f"Applied {len(rename)} confirmed column mapping(s).")

        work = _auto_map_columns(work, spec, min_confidence, actions)
        work = _force_spec_shape(work, spec, actions, log=True)
        work = _coerce_values(work, spec, actions)
        work = _force_spec_shape(work, spec, actions, log=False)
    else:
        work = _force_spec_shape(work, spec, actions, log=False)

    residual = _build_residual_report(work, dataset_type, spec)

    mandatory = [m for m in spec.get("mandatory_fields", []) if m in work.columns]
    blank_cells = 0
    for col in mandatory:
        s = work[col].astype("string")
        blank_cells += int((s.isna() | (s.str.strip() == "")).sum())

    errors = [i for i in residual if i["severity"] == "error"]
    warnings = [i for i in residual if i["severity"] != "error"]
    summary = {
        "rows": int(len(work)),
        "columns": int(len(work.columns)),
        "mandatory_blank_cells": blank_cells,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "importable": len(errors) == 0,
    }
    return AutoCleanResult(
        dataset_type=dataset_type, cleaned_df=work, residual_issues=residual,
        actions=actions, summary=summary, spec=spec,
    )


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """UTF-8 CSV with BOM (Excel-friendly), matching the v2.1 export."""
    return ("﻿" + df.to_csv(index=False)).encode("utf-8")


def issues_to_dataframe(residual_issues: List[Dict[str, Any]]) -> pd.DataFrame:
    cols = ["row", "column", "severity", "type", "message"]
    if not residual_issues:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(residual_issues)[cols]
