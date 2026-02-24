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
