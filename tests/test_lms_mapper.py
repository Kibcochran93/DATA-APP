"""Tests for utils.lms_mapper (LMS -> SEATS mapping vocabulary + detection)."""
import pandas as pd

from utils.lms_mapper import (
    LMSType,
    load_lms_mapping,
    get_lms_column_mappings,
    detect_lms_type,
)


def test_mapping_file_loads_with_canvas():
    cfg = load_lms_mapping()
    assert cfg, "lms_to_seats_mapping.json should load"
    assert "Canvas" in cfg.get("supported_systems", [])


def test_canvas_aliases_present_for_core_fields():
    mappings = get_lms_column_mappings()
    assert "sis_user_id" in mappings["STUDENT_ID"]["canvas"]
    assert "login_id" in mappings["STUDENT_LOGIN_ID"]["canvas"]
    assert "long_name" in mappings["COURSE_NAME"]["canvas"]


def test_detect_canvas_from_indicator_columns():
    df = pd.DataFrame(columns=["sis_user_id", "sis_login_id", "sortable_name", "section"])
    assert detect_lms_type(df) == LMSType.CANVAS


def test_detect_unknown_when_no_indicators():
    df = pd.DataFrame(columns=["foo", "bar", "baz"])
    assert detect_lms_type(df) == LMSType.UNKNOWN
