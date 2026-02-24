import pytest
import pandas as pd
import numpy as np
from io import BytesIO
from unittest.mock import MagicMock
from security.config import InputValidator, FILE_CONFIG, ERROR_MESSAGES

@pytest.fixture
def validator():
    """Create a validator instance for testing."""
    return InputValidator()

@pytest.fixture
def sample_csv():
    """Create a sample CSV file-like object for testing."""
    data = "col1,col2,col3\n1,2,3\n4,5,6"
    file_obj = BytesIO(data.encode())
    file_obj.name = "test.csv"
    file_obj.size = len(data)
    return file_obj

@pytest.fixture
def sample_dataframe():
    """Create a sample DataFrame for testing."""
    return pd.DataFrame({
        'col1': [1, 2, 3],
        'col2': ['a', 'b', 'c'],
        'col3': [1.1, 2.2, 3.3]
    })

class TestFileValidation:
    def test_valid_file(self, validator, sample_csv):
        """Test validation of a valid file."""
        assert validator.validate_file(sample_csv) is True
    
    def test_file_too_large(self, validator):
        """Test validation of a file that's too large."""
        large_file = MagicMock()
        large_file.name = "large.csv"
        large_file.size = FILE_CONFIG['max_size'] + 1
        
        with pytest.raises(ValueError) as exc_info:
            validator.validate_file(large_file)
        assert ERROR_MESSAGES['file_too_large'] in str(exc_info.value)
    
    def test_invalid_file_extension(self, validator):
        """Test validation of a file with invalid extension."""
        invalid_file = MagicMock()
        invalid_file.name = "test.txt"
        invalid_file.size = 100
        
        with pytest.raises(ValueError) as exc_info:
            validator.validate_file(invalid_file)
        assert ERROR_MESSAGES['invalid_extension'] in str(exc_info.value)
    
    def test_none_file(self, validator):
        """Test validation with None file."""
        with pytest.raises(ValueError) as exc_info:
            validator.validate_file(None)
        assert "No file provided" in str(exc_info.value)

class TestDataFrameValidation:
    def test_valid_dataframe(self, validator, sample_dataframe):
        """Test validation of a valid DataFrame."""
        result = validator.validate_dataframe(sample_dataframe)
        assert result['is_valid'] is True
        assert result['row_count'] == 3
        assert result['column_count'] == 3
    
    def test_empty_dataframe(self, validator):
        """Test validation of an empty DataFrame."""
        empty_df = pd.DataFrame()
        result = validator.validate_dataframe(empty_df)
        assert result['is_valid'] is False
        assert "empty" in result['issues'][0].lower()
    
    def test_none_dataframe(self, validator):
        """Test validation with None DataFrame."""
        result = validator.validate_dataframe(None)
        assert result['is_valid'] is False
        assert result['row_count'] == 0
        assert result['column_count'] == 0

class TestInputSanitization:
    def test_sanitize_dataframe(self, validator, sample_dataframe):
        """Test sanitization of DataFrame."""
        result = validator.sanitize_input(sample_dataframe)
        assert result is not None
        # Sanitization should return a DataFrame
        assert isinstance(result, pd.DataFrame)
    
    def test_sanitize_empty_dataframe(self, validator):
        """Test sanitization of empty DataFrame."""
        empty_df = pd.DataFrame()
        result = validator.sanitize_input(empty_df)
        assert isinstance(result, pd.DataFrame)
