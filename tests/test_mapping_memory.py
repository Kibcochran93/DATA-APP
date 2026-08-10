"""Tests for utils.mapping_memory (persisted header-mapping memory)."""
import pytest

from utils.mapping_memory import (
    mapping_signature,
    save_mapping,
    get_saved_mapping,
    remembered_mapping,
)


def test_signature_is_order_independent():
    a = mapping_signature("Student", ["Person ID", "First Name", "Surname"])
    b = mapping_signature("Student", ["Surname", "First Name", "Person ID"])
    assert a == b


def test_signature_differs_by_dataset_type():
    assert mapping_signature("Student", ["A", "B"]) != mapping_signature("Timetable", ["A", "B"])


def test_save_and_get_roundtrip(tmp_path):
    store = tmp_path / "mappings.json"
    sig = mapping_signature("Student", ["Person ID", "First Name"])
    save_mapping(sig, {"STUDENT_ID": "Person ID", "STUDENT_FORENAME": "First Name"}, path=store)
    assert get_saved_mapping(sig, path=store) == {
        "STUDENT_ID": "Person ID",
        "STUDENT_FORENAME": "First Name",
    }


def test_get_missing_returns_none(tmp_path):
    assert get_saved_mapping("nope::x", path=tmp_path / "mappings.json") is None


def test_remembered_mapping_resolves_against_current_headings(tmp_path):
    store = tmp_path / "mappings.json"
    headings = ["Person ID", "First Name", "Surname"]
    sig = mapping_signature("Student", headings)
    save_mapping(sig, {"STUDENT_ID": "Person ID", "STUDENT_FORENAME": "First Name"}, path=store)

    # Re-upload with different capitalisation/spacing -> still resolves.
    resolved = remembered_mapping(
        "Student",
        ["person  id", "FIRST NAME", "Surname"],
        ["STUDENT_ID", "STUDENT_FORENAME", "STUDENT_LAST_NAME"],
        path=store,
    )
    assert resolved["STUDENT_ID"] == "person  id"
    assert resolved["STUDENT_FORENAME"] == "FIRST NAME"
    assert resolved["STUDENT_LAST_NAME"] == ""  # never mapped


def test_remembered_mapping_empty_when_nothing_saved(tmp_path):
    resolved = remembered_mapping(
        "Student", ["A", "B"], ["STUDENT_ID"], path=tmp_path / "mappings.json"
    )
    assert resolved == {}
