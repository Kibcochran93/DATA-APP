"""Tests for utils.canvas_dap (Canvas DAP table join -> SEAtS roster)."""
import pandas as pd
import pytest

from utils.canvas_dap import build_roster, ingest_dap


def _tables():
    users = pd.DataFrame([
        {"id": 1, "name": "Grace Hopper", "sortable_name": "Hopper, Grace", "workflow_state": "active"},
        {"id": 2, "name": "Alan Turing", "sortable_name": "Turing, Alan", "workflow_state": "active"},
        {"id": 9, "name": "Ada Prof", "sortable_name": "Prof, Ada", "workflow_state": "active"},
    ])
    pseudonyms = pd.DataFrame([
        {"id": 10, "user_id": 1, "unique_id": "ghopper", "sis_user_id": "S1001", "workflow_state": "active"},
        {"id": 11, "user_id": 2, "unique_id": "aturing", "sis_user_id": "S1002", "workflow_state": "active"},
        {"id": 19, "user_id": 9, "unique_id": "aprof", "sis_user_id": "T900", "workflow_state": "active"},
    ])
    enrollments = pd.DataFrame([
        {"id": 100, "user_id": 1, "course_id": 500, "course_section_id": 700, "type": "StudentEnrollment", "workflow_state": "active"},
        {"id": 101, "user_id": 2, "course_id": 500, "course_section_id": 700, "type": "StudentEnrollment", "workflow_state": "active"},
        {"id": 102, "user_id": 9, "course_id": 500, "course_section_id": 700, "type": "TeacherEnrollment", "workflow_state": "active"},
        {"id": 103, "user_id": 1, "course_id": 500, "course_section_id": 701, "type": "StudentEnrollment", "workflow_state": "deleted"},
    ])
    courses = pd.DataFrame([
        {"id": 500, "name": "Intro CS", "account_id": 800, "sis_source_id": "CRS-500"},
    ])
    course_sections = pd.DataFrame([
        {"id": 700, "course_id": 500, "name": "Section A"},
        {"id": 701, "course_id": 500, "name": "Section B"},
    ])
    accounts = pd.DataFrame([
        {"id": 800, "name": "School of Computing", "sis_source_id": "ACC-800"},
    ])
    return {
        "users": users, "pseudonyms": pseudonyms, "enrollments": enrollments,
        "courses": courses, "course_sections": course_sections, "accounts": accounts,
    }


def test_build_student_roster_joins_and_filters():
    roster, notes = build_roster(_tables(), "Student")
    # Only active StudentEnrollments -> 2 rows (deleted one skipped, teacher excluded).
    assert len(roster) == 2
    grace = roster[roster["STUDENT_LOGIN_ID"] == "ghopper"].iloc[0]
    assert grace["STUDENT_ID"] == "S1001"          # sis_user_id preferred over internal id
    assert grace["STUDENT_FORENAME"] == "Grace"    # split from "Hopper, Grace"
    assert grace["STUDENT_LAST_NAME"] == "Hopper"
    assert grace["COURSE_ID"] == "CRS-500"
    assert grace["COURSE_NAME"] == "Intro CS"
    assert grace["SCHOOL_NAME"] == "School of Computing"
    assert grace["MODULE_GROUP"] == "Section A"
    assert any("Skipped 1 non-active" in n for n in notes)


def test_build_staff_roster_uses_teacher_enrollments():
    roster, _ = build_roster(_tables(), "Staff")
    assert len(roster) == 1
    staff = roster.iloc[0]
    assert staff["STAFF_NUMBER"] == "T900"
    assert staff["FORENAME"] == "Ada" and staff["LAST_NAME"] == "Prof"
    assert staff["LOGIN_ID"] == "aprof"


def test_tolerant_to_dap_value_prefix_and_case():
    tables = _tables()
    tables["users"] = tables["users"].rename(columns={
        "id": "key.id", "name": "VALUE.Name", "sortable_name": "value.Sortable_Name",
    })
    roster, _ = build_roster(tables, "Student")
    assert (roster["STUDENT_FORENAME"] == "Grace").any()


def test_missing_optional_tables_leave_blanks_and_note():
    tables = _tables()
    del tables["pseudonyms"]
    del tables["courses"]
    roster, notes = build_roster(tables, "Student")
    assert (roster["STUDENT_LOGIN_ID"] == "").all()      # no pseudonyms -> no login
    assert (roster["COURSE_NAME"] == "").all()           # no courses
    # STUDENT_ID falls back to the internal user id when there's no sis_user_id.
    assert set(roster["STUDENT_ID"]) == {"1", "2"}
    assert any("pseudonyms" in n for n in notes)


def test_requires_enrollments_and_users():
    with pytest.raises(ValueError):
        build_roster({"users": _tables()["users"]}, "Student")


def test_ingest_dap_end_to_end_is_spec_shaped_with_residual():
    from utils.seats_data_handler import get_ordered_fields, load_spec_by_type
    result = ingest_dap(_tables(), "Student")
    assert list(result.cleaned_df.columns) == get_ordered_fields(load_spec_by_type("Student"))
    assert result.cleaned_df["STUDENT_ID"].tolist()  # populated
    # MODULE isn't derivable from Canvas -> mandatory blank -> flagged, not guessed.
    assert result.importable is False
    assert any(i["column"] == "MODULE_NAME" and i["severity"] == "error"
               for i in result.residual_issues)
    assert any(a.startswith("[DAP]") for a in result.actions)
