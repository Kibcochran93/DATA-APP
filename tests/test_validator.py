import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from utils.validator import (
    validate_dataset,
    validate_schema,
    validate_formats,
    validate_referential_integrity,
    convert_to_type,
    auto_fix_fields
)

@pytest.fixture
def sample_student_data():
    """Create sample student data for testing."""
    return pd.DataFrame({
        'STUDENT_ID': ['S1234567', 'S7654321', 'S1111111'],
        'FIRST_NAME': ['John', 'Jane', 'Bob'],
        'LAST_NAME': ['Doe', 'Smith', 'Johnson'],
        'EMAIL': ['john.doe@uni.edu', 'jane.smith@uni.edu', 'bob.johnson@uni.edu'],
        'ENROLLMENT_DATE': ['2023-01-01', '2023-01-02', '2023-01-03']
    })

@pytest.fixture
def student_spec():
    """Create sample student specification for testing."""
    return {
        "required_fields": ["STUDENT_ID", "FIRST_NAME", "LAST_NAME", "EMAIL"],
        "optional_fields": ["ENROLLMENT_DATE"],
        "format_rules": {
            "STUDENT_ID": {
                "pattern": r"^S\d{7}$",
                "type": "str"
            },
            "EMAIL": {
                "pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
                "type": "str"
            },
            "ENROLLMENT_DATE": {
                "pattern": r"^\d{4}-\d{2}-\d{2}$",
                "type": "date"
            }
        },
        "referential_constraints": []
    }

def test_validate_schema(sample_student_data, student_spec):
    """Test schema validation."""
    results = {"schema_errors": [], "warnings": []}
    validate_schema(sample_student_data, student_spec, results)
    assert not results["schema_errors"]
    assert not results["warnings"]

def test_validate_schema_missing_required(sample_student_data, student_spec):
    """Test schema validation with missing required field."""
    df = sample_student_data.drop(columns=['EMAIL'])
    results = {"schema_errors": [], "warnings": []}
    validate_schema(df, student_spec, results)
    assert "Missing required fields: EMAIL" in results["schema_errors"][0]

def test_validate_formats(sample_student_data, student_spec):
    """Test format validation."""
    results = {"format_errors": {}}
    validate_formats(sample_student_data, student_spec, results)
    assert not results["format_errors"]

def test_validate_formats_invalid_email(sample_student_data, student_spec):
    """Test format validation with invalid email."""
    df = sample_student_data.copy()
    df.loc[0, 'EMAIL'] = 'invalid-email'
    results = {"format_errors": {}}
    validate_formats(df, student_spec, results)
    assert 'EMAIL' in results["format_errors"]

def test_convert_to_type():
    """Test type conversion."""
    # Test integer conversion
    data = pd.Series(['1', '2', '3'])
    result = convert_to_type(data, 'int')
    assert result.dtype == 'Int64'
    
    # Test date conversion - pd.to_datetime returns Timestamp objects
    data = pd.Series(['2023-01-01', '2023-01-02'])
    result = convert_to_type(data, 'date')
    assert pd.api.types.is_datetime64_any_dtype(result)
    
    # Test boolean conversion
    data = pd.Series(['true', 'false', 'yes', 'no'])
    result = convert_to_type(data, 'bool')
    # Result should have True/False values
    assert result.iloc[0] == True
    assert result.iloc[1] == False

def test_validate_dataset_complete(sample_student_data, student_spec):
    """Test complete dataset validation."""
    results = validate_dataset(sample_student_data, student_spec)
    assert results["is_valid"]
    assert not results["schema_errors"]
    assert not results["format_errors"]
    assert not results["referential_errors"]

def test_validate_dataset_invalid(sample_student_data, student_spec):
    """Test dataset validation with invalid data."""
    df = sample_student_data.copy()
    df.loc[0, 'STUDENT_ID'] = 'invalid'
    df.loc[1, 'EMAIL'] = 'invalid-email'
    results = validate_dataset(df, student_spec)
    assert not results["is_valid"]
    assert 'STUDENT_ID' in results["format_errors"]
    assert 'EMAIL' in results["format_errors"]

def test_validate_referential_integrity(sample_student_data, student_spec):
    """Test referential integrity validation."""
    results = {"referential_errors": []}
    validate_referential_integrity(sample_student_data, student_spec, results)
    assert not results["referential_errors"]

def test_auto_fix_with_rollback():
    """Test auto-fix functionality with rollback verification."""
    # Create test data
    df = pd.DataFrame({
        "STUDENT_ID": [" 001", " 002 ", "003"],
        "DATE": ["2024-01-01", "bad-date", "2024-01-03"],
        "GENDER": ["m", "x", "f"]
    })
    
    # Create format rules (flat structure as expected by auto_fix_fields)
    format_rules = {
        "STUDENT_ID": {
            "type": "str",
            "pattern": r"^\d{3}$"
        },
        "DATE": {
            "type": "date",
            "format": "%Y-%m-%d"
        },
        "GENDER": {
            "type": "enum",
            "values": ["M", "F"]
        }
    }
    
    # Store original DataFrame
    original_df = df.copy()
    
    # Apply auto-fix with format_errors including the fields we want to fix
    fixed_df = auto_fix_fields(
        df,
        validation_results={"format_errors": {"STUDENT_ID": ["error"], "DATE": ["error"], "GENDER": ["error"]}},
        format_rules=format_rules,
        log_changes=True
    )
    
    # Verify whitespace stripped from STUDENT_ID
    assert fixed_df["STUDENT_ID"].tolist() == ["001", "002", "003"]
    
    # Verify GENDER converted to uppercase
    assert fixed_df["GENDER"].tolist() == ["M", "X", "F"]
    
    # Verify original data not modified
    assert df.equals(original_df) 