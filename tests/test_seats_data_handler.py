"""
Tests for SEATS Data Handler.

Tests the SEATS-specific functionality including:
- Leading zeros preservation
- Multi-value field parsing
- Cross-file validation
- DELETE field processing
"""

import pytest
import pandas as pd
import numpy as np
from io import StringIO
import tempfile
import os

from utils.seats_data_handler import (
    SEATSDataHandler,
    get_seats_handler,
    MultiValueField,
    CrossFileValidationResult,
    LEADING_ZERO_FIELDS,
    FORWARD_SLASH_MULTI_VALUE_FIELDS,
    PIPE_MULTI_VALUE_FIELDS,
    load_timetable_spec,
    load_spec_by_type,
)


@pytest.fixture
def handler():
    """Create a SEATS data handler instance."""
    return SEATSDataHandler()


@pytest.fixture
def csv_with_leading_zeros():
    """Create CSV data with leading zeros."""
    return StringIO("""STUDENT_ID,NAME,BADGE_NUMBER,SCHOOL_ID
001234,John Doe,00456789,0001
002345,Jane Smith,00567890,0002
003456,Bob Jones,00678901,0003
""")


@pytest.fixture
def student_df():
    """Create sample student DataFrame."""
    return pd.DataFrame({
        'STUDENT_ID': ['001', '002', '003'],
        'NAME': ['John', 'Jane', 'Bob'],
        'SCHOOL_ID': ['S001', 'S002', 'S001'],
        'SCHOOL_NAME': ['Engineering', 'Business', 'Engineering'],
        'COURSE_ID': ['C001', 'C002', 'C001'],
        'COURSE_NAME': ['Computer Science', 'MBA', 'Computer Science'],
        'MODULE_ID': ['M001', 'M002', 'M001'],
        'MODULE_NAME': ['Programming 101', 'Finance', 'Programming 101'],
    })


@pytest.fixture
def timetable_df():
    """Create sample timetable DataFrame."""
    return pd.DataFrame({
        'EVENT_ID': ['E001', 'E002', 'E003'],
        'STUDENT_ID': ['001', '002', '003'],
        'SCHOOL_ID': ['S001', 'S002', 'S001'],
        'SCHOOL_NAME': ['Engineering', 'Business', 'Engineering'],
        'COURSE_ID': ['C001', 'C002', 'C001'],
        'COURSE_NAME': ['Computer Science', 'MBA', 'Computer Science'],
        'MODULE_ID': ['M001', 'M002', 'M001'],
        'MODULE_NAME': ['Programming 101', 'Finance', 'Programming 101'],
    })


class TestLeadingZerosPreservation:
    """Tests for leading zeros preservation."""
    
    def test_read_csv_preserves_leading_zeros(self, handler, csv_with_leading_zeros):
        """Test that CSV reading preserves leading zeros."""
        df = handler.read_csv_preserve_leading_zeros(csv_with_leading_zeros)
        
        # Check leading zeros are preserved
        assert df['STUDENT_ID'].iloc[0] == '001234'
        assert df['BADGE_NUMBER'].iloc[0] == '00456789'
        assert df['SCHOOL_ID'].iloc[0] == '0001'
    
    def test_read_csv_auto_detects_id_columns(self, handler):
        """Test that ID columns are auto-detected."""
        csv_data = StringIO("""STUDENT_ID,regular_col,MODULE_ID
001,text,002
003,more,004
""")
        df = handler.read_csv_preserve_leading_zeros(csv_data)
        
        # ID columns should be strings
        assert df['STUDENT_ID'].dtype == object
        assert df['MODULE_ID'].dtype == object
        # Values preserved
        assert df['STUDENT_ID'].iloc[0] == '001'
        assert df['MODULE_ID'].iloc[0] == '002'
    
    def test_leading_zero_fields_set(self):
        """Test that LEADING_ZERO_FIELDS contains expected fields."""
        assert 'STUDENT_ID' in LEADING_ZERO_FIELDS
        assert 'BADGE_NUMBER' in LEADING_ZERO_FIELDS
        assert 'EVENT_ID' in LEADING_ZERO_FIELDS
        assert 'MODULE_ID' in LEADING_ZERO_FIELDS


class TestMultiValueFieldParsing:
    """Tests for multi-value field parsing."""
    
    def test_parse_forward_slash_separated(self, handler):
        """Test parsing forward-slash separated values."""
        result = handler.parse_multi_value_field("Room A / Room B / Room C", "ROOM_NAME")
        
        assert len(result.values) == 3
        assert result.values == ['Room A', 'Room B', 'Room C']
        assert result.separator == '/'
    
    def test_parse_pipe_separated(self, handler):
        """Test parsing pipe-separated values (badges)."""
        result = handler.parse_multi_value_field("BADGE001|BADGE002", "BADGE_NUMBER")
        
        assert len(result.values) == 2
        assert result.values == ['BADGE001', 'BADGE002']
        assert result.separator == '|'
    
    def test_parse_single_value(self, handler):
        """Test parsing single value."""
        result = handler.parse_multi_value_field("Single Room", "ROOM_NAME")
        
        assert len(result.values) == 1
        assert result.values == ['Single Room']
    
    def test_parse_empty_value(self, handler):
        """Test parsing empty value."""
        result = handler.parse_multi_value_field("", "ROOM_NAME")
        assert len(result.values) == 0
        
        result = handler.parse_multi_value_field(None, "ROOM_NAME")
        assert len(result.values) == 0
        
        result = handler.parse_multi_value_field(np.nan, "ROOM_NAME")
        assert len(result.values) == 0
    
    def test_expand_multi_value_rows(self, handler):
        """Test expanding multi-value rows."""
        df = pd.DataFrame({
            'EVENT_ID': ['E001', 'E002'],
            'ROOM_NAME': ['Room A', 'Room B / Room C'],
            'TUTOR': ['Prof X', 'Prof Y'],
        })
        
        expanded = handler.expand_multi_value_rows(df, 'ROOM_NAME')
        
        # Should have 3 rows now (1 + 2)
        assert len(expanded) == 3
        assert 'Room B' in expanded['ROOM_NAME'].values
        assert 'Room C' in expanded['ROOM_NAME'].values
    
    def test_multi_value_field_sets(self):
        """Test that field sets contain expected values."""
        assert 'ROOM_ID' in FORWARD_SLASH_MULTI_VALUE_FIELDS
        assert 'ROOM_NAME' in FORWARD_SLASH_MULTI_VALUE_FIELDS
        assert 'TUTOR_ID' in FORWARD_SLASH_MULTI_VALUE_FIELDS
        assert 'BADGE_NUMBER' in PIPE_MULTI_VALUE_FIELDS


class TestCrossFileValidation:
    """Tests for cross-file validation."""
    
    def test_matching_files_pass(self, handler, student_df, timetable_df):
        """Test that matching files pass validation."""
        result = handler.validate_cross_file_consistency(student_df, timetable_df)
        
        assert result.is_valid
        assert len(result.mismatches) == 0
    
    def test_mismatched_names_detected(self, handler, student_df):
        """Test that mismatched names are detected."""
        # Create timetable with different name for same ID
        timetable_df = pd.DataFrame({
            'SCHOOL_ID': ['S001', 'S002'],
            'SCHOOL_NAME': ['DIFFERENT NAME', 'Business'],  # Mismatch!
            'COURSE_ID': ['C001', 'C002'],
            'COURSE_NAME': ['Computer Science', 'MBA'],
            'MODULE_ID': ['M001', 'M002'],
            'MODULE_NAME': ['Programming 101', 'Finance'],
        })
        
        result = handler.validate_cross_file_consistency(student_df, timetable_df)
        
        assert not result.is_valid
        assert len(result.mismatches) > 0
    
    def test_missing_ids_detected(self, handler, student_df):
        """Test that missing IDs are detected."""
        # Create timetable missing some IDs
        timetable_df = pd.DataFrame({
            'SCHOOL_ID': ['S001'],  # Missing S002
            'SCHOOL_NAME': ['Engineering'],
            'COURSE_ID': ['C001'],
            'COURSE_NAME': ['Computer Science'],
            'MODULE_ID': ['M001'],
            'MODULE_NAME': ['Programming 101'],
        })
        
        result = handler.validate_cross_file_consistency(student_df, timetable_df)
        
        assert len(result.missing_in_timetable) > 0


class TestDeleteFieldProcessing:
    """Tests for DELETE field processing."""
    
    def test_process_delete_field(self, handler):
        """Test DELETE field processing."""
        df = pd.DataFrame({
            'EVENT_ID': ['E001', 'E002', 'E003', 'E004'],
            'DELETE': ['N', 'Y', 'N', 'Y'],
            'DATA': ['keep1', 'delete1', 'keep2', 'delete2'],
        })
        
        keep, delete = handler.process_delete_field(df)
        
        assert len(keep) == 2
        assert len(delete) == 2
        assert 'keep1' in keep['DATA'].values
        assert 'delete1' in delete['DATA'].values
    
    def test_no_delete_column(self, handler):
        """Test handling when no DELETE column exists."""
        df = pd.DataFrame({
            'EVENT_ID': ['E001', 'E002'],
            'DATA': ['data1', 'data2'],
        })
        
        keep, delete = handler.process_delete_field(df)
        
        assert len(keep) == 2
        assert len(delete) == 0
    
    def test_delete_case_sensitive(self, handler):
        """Test that DELETE values are case-sensitive."""
        df = pd.DataFrame({
            'EVENT_ID': ['E001', 'E002', 'E003'],
            'DELETE': ['Y', 'y', 'N'],  # lowercase 'y' should NOT be treated as delete
        })
        
        keep, delete = handler.process_delete_field(df)
        
        # Only uppercase 'Y' should be deleted
        assert len(delete) == 1
        assert delete['EVENT_ID'].iloc[0] == 'E001'


class TestMultiValueFieldClass:
    """Tests for MultiValueField dataclass."""
    
    def test_parse_basic(self):
        """Test basic parsing."""
        result = MultiValueField.parse("A / B / C", "/")
        
        assert result.original == "A / B / C"
        assert result.values == ['A', 'B', 'C']
        assert result.separator == '/'
    
    def test_to_list(self):
        """Test to_list method."""
        result = MultiValueField.parse("X|Y", "|")
        assert result.to_list() == ['X', 'Y']
    
    def test_str_representation(self):
        """Test string representation."""
        result = MultiValueField.parse("Original Value", "/")
        assert str(result) == "Original Value"


class TestSingleton:
    """Test singleton pattern."""
    
    def test_get_seats_handler_returns_same_instance(self):
        """Test that get_seats_handler returns the same instance."""
        handler1 = get_seats_handler()
        handler2 = get_seats_handler()
        
        assert handler1 is handler2


class TestSpecLoading:
    """Tests for spec loading and validation."""
    
    def test_load_spec_student(self, handler):
        """Test loading the student spec."""
        from pathlib import Path
        spec_path = Path(__file__).parent.parent / 'data' / 'master' / 'student_data_spec.json'
        
        if spec_path.exists():
            spec = handler.load_spec(spec_path)
            
            assert spec['dataset_type'] == 'Student'
            assert 'fields' in spec
            assert 'mandatory_fields' in spec
            assert 'STUDENT_ID' in spec['mandatory_fields']
    
    def test_validate_against_spec(self, handler):
        """Test validation against spec."""
        # Create a simple spec
        spec = {
            'dataset_type': 'Test',
            'version': '1.0',
            'mandatory_fields': ['ID', 'NAME'],
            'fields': {
                'ID': {
                    'type': 'str',
                    'mandatory': True
                },
                'NAME': {
                    'type': 'str',
                    'mandatory': True
                },
                'STATUS': {
                    'type': 'enum',
                    'mandatory': False,
                    'values': ['A', 'I', '']
                }
            }
        }
        
        # Valid data
        df_valid = pd.DataFrame({
            'ID': ['001', '002'],
            'NAME': ['John', 'Jane'],
            'STATUS': ['A', 'I']
        })
        
        result = handler.validate_against_spec(df_valid, spec)
        assert result['is_valid']
        assert len(result['errors']) == 0
        
        # Invalid data - missing mandatory field
        df_missing = pd.DataFrame({
            'ID': ['001', '002'],
            # NAME is missing
        })
        
        result = handler.validate_against_spec(df_missing, spec)
        assert not result['is_valid']
        assert any(e['type'] == 'missing_mandatory_field' for e in result['errors'])
    
    def test_validate_enum_values(self, handler):
        """Test enum value validation."""
        spec = {
            'dataset_type': 'Test',
            'version': '1.0',
            'mandatory_fields': [],
            'fields': {
                'GENDER': {
                    'type': 'enum',
                    'values': ['M', 'F', 'O', '']
                }
            }
        }
        
        df = pd.DataFrame({
            'GENDER': ['M', 'F', 'X', 'INVALID']  # X and INVALID are not valid
        })
        
        result = handler.validate_against_spec(df, spec)
        
        # Should have enum validation error
        enum_errors = [e for e in result['errors'] if e['type'] == 'invalid_enum_value']
        assert len(enum_errors) > 0
        assert enum_errors[0]['invalid_count'] == 2
    
    def test_apply_auto_fixes(self, handler):
        """Test auto-fix application."""
        spec = {
            'dataset_type': 'Test',
            'version': '1.0',
            'mandatory_fields': [],
            'fields': {
                'VISAREQUIRED': {
                    'type': 'enum',
                    'fixer': 'uppercase',
                    'values': ['Y', 'N']
                },
                'EMAIL': {
                    'type': 'str',
                    'fixer': 'strip'
                },
                'STATUS': {
                    'type': 'enum',
                    'default': 'A',
                    'values': ['A', 'I', '']
                }
            }
        }
        
        df = pd.DataFrame({
            'VISAREQUIRED': ['y', 'n', 'Y'],
            'EMAIL': ['  test@example.com  ', 'user@test.com', '  space@space.com'],
            'STATUS': ['A', '', np.nan]
        })
        
        fixed_df, changes = handler.apply_auto_fixes(df, spec)
        
        # Check uppercase was applied
        assert fixed_df['VISAREQUIRED'].iloc[0] == 'Y'
        assert fixed_df['VISAREQUIRED'].iloc[1] == 'N'
        
        # Check strip was applied
        assert fixed_df['EMAIL'].iloc[0] == 'test@example.com'
        
        # Check default was applied
        assert fixed_df['STATUS'].iloc[1] == 'A'
        
        # Check changes were logged
        assert len(changes) > 0


class TestTimetableSpec:
    """Tests for Student Timetable specification loading and validation."""
    
    def test_load_timetable_spec(self, handler):
        """Test that timetable spec loads correctly."""
        spec = load_timetable_spec()
        
        assert spec is not None
        assert spec['dataset_type'] == 'StudentTimetable'
        assert spec['version'] == '8.2'
    
    def test_timetable_spec_has_32_fields(self, handler):
        """Test that timetable spec has all 32 fields."""
        spec = load_timetable_spec()
        
        assert len(spec['fields']) == 32
    
    def test_timetable_mandatory_fields(self, handler):
        """Test that mandatory fields are correctly specified."""
        spec = load_timetable_spec()
        
        expected_mandatory = [
            'EVENT_ID', 'DAY', 'START_TIME', 'END_TIME',
            'ROOM_ID', 'ROOM_NAME', 'COURSE_ID', 'COURSE_NAME',
            'MODULE_ID', 'MODULE_NAME', 'SCHOOL_ID', 'SCHOOL_NAME',
            'STUDENT_ID'
        ]
        
        assert set(spec['mandatory_fields']) == set(expected_mandatory)
    
    def test_timetable_unique_key(self, handler):
        """Test that unique key is EVENT_ID + DAY."""
        spec = load_timetable_spec()
        
        assert spec['unique_key'] == ['EVENT_ID', 'DAY']
    
    def test_timetable_multi_value_fields(self, handler):
        """Test that multi-value fields are correctly specified."""
        spec = load_timetable_spec()
        
        multi_value_fields = [
            'ROOM_ID', 'ROOM_NAME', 'SITE_CODE', 'SITE_NAME',
            'TUTOR_ID', 'TUTOR', 'BUILDING_ID', 'BUILDING_NAME',
            'GROUP_ID', 'GROUP_NAME'
        ]
        
        for field_name in multi_value_fields:
            field_spec = spec['fields'][field_name]
            assert field_spec.get('multi_value') is True, f"{field_name} should be multi_value"
            assert field_spec.get('separator') == '/', f"{field_name} should use / separator"
    
    def test_timetable_lesson_types(self, handler):
        """Test that lesson types enum has all values."""
        spec = load_timetable_spec()
        
        lesson_type = spec['fields']['LESSON_TYPE']
        
        assert lesson_type['type'] == 'enum'
        assert lesson_type['default'] == 'L'
        assert 'L' in lesson_type['values']  # Lecture
        assert 'S' in lesson_type['values']  # Seminar
        assert 'HYB' in lesson_type['values']  # Hybrid
    
    def test_timetable_delete_field(self, handler):
        """Test that DELETE field is case-sensitive."""
        spec = load_timetable_spec()
        
        delete_field = spec['fields']['DELETE']
        
        assert delete_field['case_sensitive'] is True
        assert set(delete_field['values']) == {'Y', 'N'}
    
    def test_timetable_cross_file_fields(self, handler):
        """Test that cross-file match fields are specified."""
        spec = load_timetable_spec()
        
        cross_file_fields = spec['validation_rules']['cross_file_match_fields']
        
        expected = [
            'SCHOOL_ID', 'SCHOOL_NAME', 'COURSE_ID', 'COURSE_NAME',
            'MODULE_ID', 'MODULE_NAME', 'MODULE_GROUP', 'STUDENT_ID'
        ]
        
        assert set(cross_file_fields) == set(expected)
    
    def test_timetable_location_hierarchy(self, handler):
        """Test that location hierarchy rules are specified."""
        spec = load_timetable_spec()
        
        hierarchy = spec['validation_rules']['location_hierarchy']
        
        assert 'rules' in hierarchy
        assert len(hierarchy['rules']) == 4  # SITE_CODE, SITE_NAME, BUILDING_ID, BUILDING_NAME
    
    def test_validate_timetable_data(self, handler):
        """Test validation against timetable spec."""
        spec = load_timetable_spec()
        
        valid_df = pd.DataFrame({
            'EVENT_ID': ['E001', 'E002'],
            'DAY': ['2024-01-15', '2024-01-16'],
            'START_TIME': ['09:00', '10:00'],
            'END_TIME': ['10:00', '11:00'],
            'ROOM_ID': ['R001', 'R002'],
            'ROOM_NAME': ['Lab 1', 'Lab 2'],
            'COURSE_ID': ['C001', 'C001'],
            'COURSE_NAME': ['Computer Science', 'Computer Science'],
            'MODULE_ID': ['M001', 'M001'],
            'MODULE_NAME': ['Programming', 'Programming'],
            'SCHOOL_ID': ['S001', 'S001'],
            'SCHOOL_NAME': ['Engineering', 'Engineering'],
            'STUDENT_ID': ['STU001', 'STU002'],
            'LESSON_TYPE': ['L', 'S'],
        })
        
        result = handler.validate_against_spec(valid_df, spec)
        
        # Should have no missing mandatory field errors
        missing_mandatory = [e for e in result['errors'] if e.get('type') == 'missing_mandatory_field']
        assert len(missing_mandatory) == 0
    
    def test_validate_timetable_missing_mandatory(self, handler):
        """Test validation catches missing mandatory fields."""
        spec = load_timetable_spec()
        
        # Missing STUDENT_ID
        invalid_df = pd.DataFrame({
            'EVENT_ID': ['E001'],
            'DAY': ['2024-01-15'],
            'START_TIME': ['09:00'],
            'END_TIME': ['10:00'],
            'ROOM_ID': ['R001'],
            'ROOM_NAME': ['Lab 1'],
        })
        
        result = handler.validate_against_spec(invalid_df, spec)
        
        # Should detect missing mandatory fields
        missing_mandatory = [e for e in result['errors'] if e.get('type') == 'missing_mandatory_field']
        missing_fields = [e['field'] for e in missing_mandatory]
        assert 'STUDENT_ID' in missing_fields


class TestLoadSpecByType:
    """Tests for load_spec_by_type function."""
    
    def test_load_student_spec(self):
        """Test loading student spec by type."""
        spec = load_spec_by_type('Student')
        assert spec['dataset_type'] == 'Student'
    
    def test_load_timetable_spec(self):
        """Test loading timetable spec by type."""
        spec = load_spec_by_type('StudentTimetable')
        assert spec['dataset_type'] == 'StudentTimetable'
    
    def test_load_spec_case_insensitive(self):
        """Test that spec loading is case insensitive."""
        spec1 = load_spec_by_type('STUDENT')
        spec2 = load_spec_by_type('student')
        spec3 = load_spec_by_type('Student')
        
        assert spec1['dataset_type'] == spec2['dataset_type'] == spec3['dataset_type']
    
    def test_load_spec_with_spaces(self):
        """Test that spec loading handles spaces."""
        spec = load_spec_by_type('Student Timetable')
        assert spec['dataset_type'] == 'StudentTimetable'
    
    def test_load_spec_invalid_type(self):
        """Test that invalid type raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            load_spec_by_type('InvalidType')
        
        assert 'Unknown dataset type' in str(exc_info.value)
