"""Tests for utils.data_profile (profile-before-export analysis cards)."""
import pandas as pd

from utils.data_profile import profile_dataframe, unique_values, unique_entities


def _card(cards, label):
    return next((c for c in cards if c["label"] == label), None)


def test_unique_values_dedupes_and_sorts_numeric():
    df = pd.DataFrame({"COURSE_ID": ["10", "2", "10", "", "2"]})
    assert unique_values(df, "COURSE_ID") == ["2", "10"]


def test_unique_entities_formats_id_and_name():
    df = pd.DataFrame([
        {"SCHOOL_ID": "1", "SCHOOL_NAME": "Business"},
        {"SCHOOL_ID": "1", "SCHOOL_NAME": "Business"},
        {"SCHOOL_ID": "2", "SCHOOL_NAME": "Arts"},
    ])
    entities = unique_entities(df, "SCHOOL_ID", ["SCHOOL_NAME"])
    assert "1 — Business" in entities and "2 — Arts" in entities
    assert len(entities) == 2


def test_student_profile_cards():
    df = pd.DataFrame([
        {"STUDENT_ID": "S1", "COURSE_ID": "C1", "MODULE_ID": "M1",
         "SCHOOL_ID": "1", "SCHOOL_NAME": "Biz", "STUDENT_LOGIN_ID": "s1"},
        {"STUDENT_ID": "S2", "COURSE_ID": "C1", "MODULE_ID": "M2",
         "SCHOOL_ID": "1", "SCHOOL_NAME": "Biz", "STUDENT_LOGIN_ID": "s2"},
    ])
    cards = profile_dataframe(df, "Student")
    assert _card(cards, "Unique students")["count"] == 2
    assert _card(cards, "Unique course values")["count"] == 1
    assert _card(cards, "Unique schools")["count"] == 1
    conflicts = _card(cards, "Students with conflicting Login IDs")
    assert conflicts["count"] == 0 and conflicts["state"] == "good"


def test_student_profile_flags_login_conflicts():
    df = pd.DataFrame([
        {"STUDENT_ID": "S1", "STUDENT_LOGIN_ID": "a"},
        {"STUDENT_ID": "S1", "STUDENT_LOGIN_ID": "b"},
    ])
    cards = profile_dataframe(df, "Student")
    conflicts = _card(cards, "Students with conflicting Login IDs")
    assert conflicts["count"] == 1 and conflicts["state"] == "warning"
    assert conflicts["values"][0]["student"] == "S1"


def test_timetable_profile_cards():
    df = pd.DataFrame([
        {"EVENT_ID": "E1", "STUDENT_ID": "S1", "COURSE_ID": "C1",
         "MODULE_ID": "M1", "SCHOOL_ID": "1", "SCHOOL_NAME": "Biz"},
        {"EVENT_ID": "E1", "STUDENT_ID": "S2", "COURSE_ID": "C1",
         "MODULE_ID": "M1", "SCHOOL_ID": "1", "SCHOOL_NAME": "Biz"},
    ])
    cards = profile_dataframe(df, "Timetable")
    assert _card(cards, "Unique events")["count"] == 1
    assert _card(cards, "Unique students")["count"] == 2
    # Student-only cards should not appear for timetable.
    assert _card(cards, "Students with conflicting Login IDs") is None


def test_empty_dataframe_returns_no_cards():
    assert profile_dataframe(pd.DataFrame(), "Student") == []
