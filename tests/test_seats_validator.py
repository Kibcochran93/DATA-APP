"""
Tests for utils.seats_validator — the spec-driven validator used at runtime by
the wizard. Exercised against the real SEAtS Interface Spec v8.2 JSON files in
data/master/ so the tests track the authoritative spec.

(This replaces the old tests/test_validator.py, which covered the removed legacy
utils/validator.py.)
"""
import json
from pathlib import Path

import pandas as pd
import pytest

from utils.seats_validator import (
    ValidationError,
    ValidationResult,
    SEATSValidator,
    validate_dataset,
    validate_student,
    validate_timetable,
)

SPEC_DIR = Path(__file__).resolve().parent.parent / "data" / "master"


def _load_spec(filename):
    return json.loads((SPEC_DIR / filename).read_text(encoding="utf-8"))


STUDENT_SPEC = _load_spec("student_data_spec.json")
TIMETABLE_SPEC = _load_spec("student_timetable_spec.json")


def _ordered_fields(spec):
    """All spec field names in spec (position) order."""
    fields = spec["fields"]
    return sorted(fields.keys(), key=lambda k: fields[k].get("position", 9999))


def _full_row(spec, values=None):
    """A row dict with every spec column present (blank), overlaid with `values`."""
    row = {field: "" for field in _ordered_fields(spec)}
    if values:
        row.update(values)
    return row


def _student_df(values=None):
    filled = {
        "STUDENT_ID": "S001",
        "STUDENT_FORENAME": "Ada",
        "STUDENT_LAST_NAME": "Lovelace",
        "VISAREQUIRED": "N",
        "COURSE_ID": "C1",
        "MODULE_ID": "M1",
        "SCHOOL_ID": "SCH1",
        "STUDENT_LOGIN_ID": "alovelace",
    }
    if values:
        filled.update(values)
    return pd.DataFrame([_full_row(STUDENT_SPEC, filled)], columns=_ordered_fields(STUDENT_SPEC))


def _timetable_df(values=None):
    filled = {
        "EVENT_ID": "E1",
        "DAY": "2026-01-05",
        "START_TIME": "09:00",
        "END_TIME": "10:00",
        "ROOM_ID": "R1",
        "ROOM_NAME": "Room 1",
        "COURSE_ID": "C1",
        "COURSE_NAME": "Course 1",
        "MODULE_ID": "M1",
        "MODULE_NAME": "Module 1",
        "SCHOOL_ID": "SCH1",
        "SCHOOL_NAME": "School 1",
        "STUDENT_ID": "S001",
    }
    if values:
        filled.update(values)
    return pd.DataFrame([_full_row(TIMETABLE_SPEC, filled)], columns=_ordered_fields(TIMETABLE_SPEC))


# --- basics ---------------------------------------------------------------

def test_validate_dataset_returns_validation_result():
    result = validate_dataset(_student_df(), "Student", spec=STUDENT_SPEC)
    assert isinstance(result, ValidationResult)
    assert result.dataset_type == "Student"


def test_to_summary_shape():
    result = validate_dataset(_student_df(), "Student", spec=STUDENT_SPEC)
    summary = result.to_summary()
    for key in ("dataset_type", "total_errors", "rows_affected", "error_types", "columns_affected"):
        assert key in summary
    assert summary["total_errors"] == len(result.errors)


# --- schema-level checks --------------------------------------------------

def test_all_spec_columns_present_has_no_schema_issues():
    result = validate_dataset(_student_df(), "Student", spec=STUDENT_SPEC)
    assert result.schema_issues == []


def test_missing_mandatory_column_is_flagged():
    df = _student_df().drop(columns=["STUDENT_ID"])
    result = validate_dataset(df, "Student", spec=STUDENT_SPEC)
    assert any("STUDENT_ID" in issue for issue in result.schema_issues)


def test_near_match_typo_column_is_suggested():
    # Hyphen variant normalizes to the spec name -> near-match suggestion.
    df = _student_df().rename(columns={"STUDENT_ID": "STUDENT-ID"})
    result = validate_dataset(df, "Student", spec=STUDENT_SPEC)
    assert any("STUDENT_ID" in issue and "STUDENT-ID" in issue for issue in result.schema_issues)


def test_duplicate_column_is_flagged():
    fields = _ordered_fields(STUDENT_SPEC)
    df = _student_df()
    # Append a duplicate STUDENT_ID column (pandas .1 suffix style).
    df["STUDENT_ID.1"] = df["STUDENT_ID"]
    result = validate_dataset(df, "Student", spec=STUDENT_SPEC)
    assert any("Duplicate column" in issue and "STUDENT_ID" in issue for issue in result.schema_issues)


# --- row-level checks -----------------------------------------------------

def test_empty_mandatory_value_produces_missing_mandatory_error():
    df = _student_df({"STUDENT_ID": ""})
    result = validate_dataset(df, "Student", spec=STUDENT_SPEC)
    errs = [e for e in result.errors if e.error_type == "missing_mandatory" and e.column == "STUDENT_ID"]
    assert errs, "expected a missing_mandatory error on STUDENT_ID"


def test_timetable_end_before_start_flags_time_sequence():
    df = _timetable_df({"START_TIME": "10:00", "END_TIME": "09:00"})
    result = validate_timetable(df, spec=TIMETABLE_SPEC)
    seq = [e for e in result.errors if e.error_type == "time_sequence"]
    assert seq and seq[0].column == "END_TIME"


def test_timetable_valid_time_sequence_has_no_time_error():
    df = _timetable_df({"START_TIME": "09:00", "END_TIME": "10:00"})
    result = validate_timetable(df, spec=TIMETABLE_SPEC)
    assert not [e for e in result.errors if e.error_type == "time_sequence"]


def test_virtual_lesson_is_exempt_from_room_and_time_mandatory():
    # LESSON_TYPE V (virtual) => ROOM_ID/ROOM_NAME/START_TIME/END_TIME may be blank.
    df = _timetable_df({
        "LESSON_TYPE": "V",
        "ROOM_ID": "", "ROOM_NAME": "",
        "START_TIME": "", "END_TIME": "",
    })
    result = validate_timetable(df, spec=TIMETABLE_SPEC)
    exempt = {"ROOM_ID", "ROOM_NAME", "START_TIME", "END_TIME"}
    offending = [e for e in result.errors
                 if e.error_type == "missing_mandatory" and e.column in exempt]
    assert not offending, f"virtual lesson should be exempt, got: {[e.column for e in offending]}"


# --- convenience aliases --------------------------------------------------

def test_validate_student_alias_matches_validate_dataset():
    df = _student_df({"STUDENT_ID": ""})
    a = validate_student(df, spec=STUDENT_SPEC)
    b = validate_dataset(df, "Student", spec=STUDENT_SPEC)
    assert len(a.errors) == len(b.errors)


def test_validator_class_direct_use():
    validator = SEATSValidator(dataset_type="Student", spec=STUDENT_SPEC)
    result = validator.validate(_student_df())
    assert isinstance(result, ValidationResult)
    assert result.schema_issues == []
