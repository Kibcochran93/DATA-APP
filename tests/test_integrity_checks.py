"""Tests for utils.integrity_checks (cross-row checks ported from v2.1)."""
import pandas as pd

from utils.integrity_checks import (
    find_name_id_conflicts,
    find_login_id_conflicts,
    find_event_consistency_issues,
    heal_headers,
    run_all,
)


# --- name <-> id conflicts (#4) ------------------------------------------

def test_name_id_conflict_detected():
    df = pd.DataFrame([
        {"SCHOOL_ID": "1", "SCHOOL_NAME": "Business"},
        {"SCHOOL_ID": "7", "SCHOOL_NAME": "Business"},  # same name, different id
    ])
    issues = find_name_id_conflicts(df)
    assert len(issues) == 1
    assert issues[0]["type"] == "warning"
    assert issues[0]["field"] == "SCHOOL_ID"
    assert "Business" in issues[0]["message"]
    assert "1 (row 2)" in issues[0]["message"] and "7 (row 3)" in issues[0]["message"]


def test_name_id_no_conflict_when_consistent():
    df = pd.DataFrame([
        {"COURSE_ID": "C1", "COURSE_NAME": "Maths"},
        {"COURSE_ID": "C1", "COURSE_NAME": "Maths"},
        {"COURSE_ID": "C2", "COURSE_NAME": "Physics"},
    ])
    assert find_name_id_conflicts(df) == []


def test_name_id_ignores_blank_values():
    df = pd.DataFrame([
        {"MODULE_ID": "", "MODULE_NAME": "Intro"},
        {"MODULE_ID": "M2", "MODULE_NAME": "Intro"},
    ])
    assert find_name_id_conflicts(df) == []


def test_faculty_typo_name_column_is_supported():
    # The spec ships FACULITY_NAME (sic); the check accepts either spelling.
    df = pd.DataFrame([
        {"FACULTY_ID": "F1", "FACULITY_NAME": "Arts"},
        {"FACULTY_ID": "F2", "FACULITY_NAME": "Arts"},
    ])
    issues = find_name_id_conflicts(df)
    assert len(issues) == 1 and issues[0]["field"] == "FACULTY_ID"


# --- login id conflicts (#4) ---------------------------------------------

def test_login_id_conflict_detected():
    df = pd.DataFrame([
        {"STUDENT_ID": "S1", "STUDENT_LOGIN_ID": "a.smith"},
        {"STUDENT_ID": "S1", "STUDENT_LOGIN_ID": "asmith2"},
        {"STUDENT_ID": "S2", "STUDENT_LOGIN_ID": "b.jones"},
    ])
    issues = find_login_id_conflicts(df)
    assert len(issues) == 1
    assert "S1" in issues[0]["message"]
    assert "a.smith" in issues[0]["message"] and "asmith2" in issues[0]["message"]


def test_login_id_single_login_ok():
    df = pd.DataFrame([
        {"STUDENT_ID": "S1", "STUDENT_LOGIN_ID": "a.smith"},
        {"STUDENT_ID": "S1", "STUDENT_LOGIN_ID": "a.smith"},
    ])
    assert find_login_id_conflicts(df) == []


# --- timetable event consistency (#5) ------------------------------------

def test_event_field_inconsistency_flagged():
    df = pd.DataFrame([
        {"EVENT_ID": "E1", "STUDENT_ID": "S1", "ROOM_ID": "R1", "START_TIME": "09:00"},
        {"EVENT_ID": "E1", "STUDENT_ID": "S2", "ROOM_ID": "R9", "START_TIME": "09:00"},
    ])
    issues = find_event_consistency_issues(df)
    msgs = [i for i in issues if i["field"] == "ROOM_ID" and "differs" in i["message"]]
    assert msgs and msgs[0]["row"] == 3


def test_duplicate_student_per_event_flagged():
    df = pd.DataFrame([
        {"EVENT_ID": "E1", "STUDENT_ID": "S1"},
        {"EVENT_ID": "E1", "STUDENT_ID": "S1"},  # duplicate
    ])
    issues = find_event_consistency_issues(df)
    dup = [i for i in issues if i["field"] == "STUDENT_ID"]
    assert dup and "already listed" in dup[0]["message"]


def test_site_building_all_or_nothing():
    df = pd.DataFrame([
        {"EVENT_ID": "E1", "SITE_CODE": "SC1", "SITE_NAME": "Main",
         "BUILDING_ID": "B1", "BUILDING_NAME": ""},  # building name missing
    ])
    issues = find_event_consistency_issues(df)
    errs = [i for i in issues if i["type"] == "error" and i["field"] == "BUILDING_NAME"]
    assert errs


def test_site_building_fully_blank_is_ok():
    df = pd.DataFrame([
        {"EVENT_ID": "E1", "SITE_CODE": "", "SITE_NAME": "",
         "BUILDING_ID": "", "BUILDING_NAME": ""},
    ])
    assert find_event_consistency_issues(df) == []


# --- BADGENUMBER blank-header heal (#6) ----------------------------------

def test_heal_headers_injects_badgenumber():
    headers = ["STUDENT_ID", "VISAREQUIRED", "", "COURSE_ID", "MODULE_ID"]
    assert heal_headers(headers) == [
        "STUDENT_ID", "VISAREQUIRED", "BADGENUMBER", "COURSE_ID", "MODULE_ID",
    ]


def test_heal_headers_leaves_normal_headers_untouched():
    headers = ["STUDENT_ID", "VISAREQUIRED", "BADGENUMBER", "COURSE_ID"]
    assert heal_headers(headers) == headers


def test_heal_headers_no_change_when_pattern_absent():
    headers = ["STUDENT_ID", "", "COURSE_ID"]  # no VISAREQUIRED before the blank
    assert heal_headers(headers) == ["STUDENT_ID", "", "COURSE_ID"]


def test_heal_headers_recognizes_pandas_unnamed_placeholder():
    # pandas names a blank header column "Unnamed: N" on read.
    headers = ["STUDENT_ID", "VISAREQUIRED", "Unnamed: 2", "COURSE_ID"]
    assert heal_headers(headers) == [
        "STUDENT_ID", "VISAREQUIRED", "BADGENUMBER", "COURSE_ID",
    ]


# --- aggregator -----------------------------------------------------------

def test_run_all_combines_checks():
    df = pd.DataFrame([
        {"EVENT_ID": "E1", "STUDENT_ID": "S1", "SCHOOL_ID": "1", "SCHOOL_NAME": "Biz"},
        {"EVENT_ID": "E1", "STUDENT_ID": "S1", "SCHOOL_ID": "2", "SCHOOL_NAME": "Biz"},
    ])
    issues = run_all(df, dataset_type="Timetable")
    fields = {i["field"] for i in issues}
    assert "SCHOOL_ID" in fields      # name<->id conflict
    assert "STUDENT_ID" in fields     # duplicate student per event
