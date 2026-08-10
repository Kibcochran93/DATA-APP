"""Tests for utils.auto_clean (the one-click best-effort transform)."""
import pandas as pd
import pytest

from utils.auto_clean import auto_clean, to_csv_bytes, issues_to_dataframe
from utils.seats_data_handler import get_ordered_fields, load_spec_by_type

STUDENT_SPEC = load_spec_by_type("Student")
STUDENT_FIELDS = get_ordered_fields(STUDENT_SPEC)
STUDENT_MANDATORY = STUDENT_SPEC["mandatory_fields"]


def _full_student_row():
    return {m: v for m, v in {
        "STUDENT_ID": "S1", "STUDENT_FORENAME": "Ada", "STUDENT_LAST_NAME": "Lovelace",
        "COURSE_ID": "C1", "COURSE_NAME": "Computing", "MODULE_ID": "M1",
        "MODULE_NAME": "Engines", "SCHOOL_ID": "SC1", "SCHOOL_NAME": "Eng",
        "STUDENT_LOGIN_ID": "alovelace",
    }.items()}


# --- structural guarantees -------------------------------------------------

def test_output_is_exactly_spec_shaped():
    raw = pd.DataFrame([{"STUDENT_ID": "S1", "SOME_JUNK": "x", "STUDENT_FORENAME": "A"}])
    result = auto_clean(raw, "Student")
    # Exactly the spec columns, in spec order — regardless of the input.
    assert list(result.cleaned_df.columns) == STUDENT_FIELDS
    assert "SOME_JUNK" not in result.cleaned_df.columns


def test_missing_spec_columns_are_inserted_blank():
    raw = pd.DataFrame([{"STUDENT_ID": "S1"}])
    result = auto_clean(raw, "Student")
    assert set(STUDENT_FIELDS).issubset(set(result.cleaned_df.columns))
    # A column that wasn't supplied is present and blank.
    assert result.cleaned_df["STUDENT_LOGIN_ID"].iloc[0] == ""


def test_always_produces_output_even_when_not_importable():
    raw = pd.DataFrame([{"STUDENT_ID": "S1"}])  # missing most mandatory values
    result = auto_clean(raw, "Student")
    assert not result.cleaned_df.empty                 # best-effort file still produced
    assert list(result.cleaned_df.columns) == STUDENT_FIELDS
    assert result.importable is False
    # Blocking issues are surfaced as severity "error" for the customer to finish.
    assert result.summary["error_count"] > 0
    assert any(i["severity"] == "error" and i["type"] == "missing_mandatory"
               for i in result.residual_issues)


def test_missing_mandatory_value_reports_specific_field():
    raw = pd.DataFrame([dict(_full_student_row(), STUDENT_LOGIN_ID="")])
    result = auto_clean(raw, "Student")
    login_errs = [i for i in result.residual_issues
                  if i["column"] == "STUDENT_LOGIN_ID" and i["severity"] == "error"]
    assert login_errs


def test_fully_valid_input_is_importable():
    raw = pd.DataFrame([_full_student_row()])
    result = auto_clean(raw, "Student")
    missing = [i for i in result.residual_issues if i["type"] == "missing_mandatory"]
    assert not missing, f"unexpected missing_mandatory: {missing}"
    assert result.importable is True
    assert result.summary["mandatory_blank_cells"] == 0


# --- mapping ---------------------------------------------------------------

def test_sis_alias_column_is_auto_mapped():
    # SPRIDEN_ID is a Banner alias for STUDENT_ID in the SIS mapping.
    row = _full_student_row()
    row.pop("STUDENT_ID")
    row["SPRIDEN_ID"] = "S1"
    result = auto_clean(pd.DataFrame([row]), "Student")
    assert result.cleaned_df["STUDENT_ID"].iloc[0] == "S1"


def test_user_mapping_is_applied_first():
    row = _full_student_row()
    row.pop("STUDENT_ID")
    row["PID"] = "S9"
    result = auto_clean(pd.DataFrame([row]), "Student", user_mapping={"PID": "STUDENT_ID"})
    assert result.cleaned_df["STUDENT_ID"].iloc[0] == "S9"


# --- helpers & summary -----------------------------------------------------

def test_summary_has_expected_keys():
    result = auto_clean(pd.DataFrame([_full_student_row()]), "Student")
    for key in ("rows", "columns", "mandatory_blank_cells", "error_count",
                "warning_count", "importable"):
        assert key in result.summary
    assert result.summary["columns"] == len(STUDENT_FIELDS)


def test_to_csv_bytes_has_utf8_bom():
    df = pd.DataFrame([{"A": "1", "B": "2"}])
    data = to_csv_bytes(df)
    assert data.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
    assert b"A,B" in data


def test_issues_to_dataframe_empty_and_nonempty():
    assert list(issues_to_dataframe([]).columns) == ["row", "column", "severity", "type", "message"]
    df = issues_to_dataframe([{"row": 2, "column": "X", "severity": "error",
                               "type": "missing_mandatory", "message": "m"}])
    assert len(df) == 1 and df["column"].iloc[0] == "X"


def test_canvas_lms_export_maps_to_student():
    # A Canvas (LMS) roster/enrollment export — different vocabulary from an SIS.
    raw = pd.DataFrame([{
        "sis_user_id": "U100", "first_name": "Grace", "last_name": "Hopper",
        "sis_login_id": "ghopper", "email": "g@uni.edu",
        "course_id": "CS101", "long_name": "Intro CS",
    }])
    result = auto_clean(raw, "Student")
    cd = result.cleaned_df

    def val(col):
        return str(cd[col].iloc[0]).strip().lower()

    assert val("STUDENT_ID") == "u100"
    assert val("STUDENT_FORENAME") == "grace"
    assert val("STUDENT_LAST_NAME") == "hopper"
    assert val("STUDENT_LOGIN_ID") == "ghopper"
    assert val("COURSE_ID") == "cs101"
    assert val("COURSE_NAME") == "intro cs"
    # Best-effort: MODULE/SCHOOL aren't derivable from Canvas -> flagged, not guessed.
    assert result.importable is False
    assert any(i["column"] == "MODULE_NAME" and i["severity"] == "error"
               for i in result.residual_issues)


def test_timetable_type_runs_and_shapes():
    tt_fields = get_ordered_fields(load_spec_by_type("StudentTimetable"))
    raw = pd.DataFrame([{"EVENT_ID": "E1", "DAY": "2026-01-05", "JUNK": "x"}])
    result = auto_clean(raw, "StudentTimetable")
    assert list(result.cleaned_df.columns) == tt_fields
    assert "JUNK" not in result.cleaned_df.columns
