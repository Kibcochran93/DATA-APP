import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from io import BytesIO
from security.config import InputValidator, FILE_CONFIG, DATA_CONFIG, ERROR_MESSAGES
from utils.exceptions import SecurityError

@pytest.fixture
def validator():
    """Create a validator instance for testing."""
    config = {**FILE_CONFIG, **DATA_CONFIG}
    return InputValidator(config)

@pytest.fixture
def sample_csv():
    """Create a sample CSV file for testing."""
    data = "col1,col2,col3\n1,2,3\n4,5,6"
    return BytesIO(data.encode())

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
        large_file = BytesIO(b'0' * (FILE_CONFIG['max_file_size'] + 1))
        with pytest.raises(SecurityError) as exc_info:
            validator.validate_file(large_file)
        assert str(exc_info.value) == ERROR_MESSAGES['file_too_large']
    
    def test_invalid_file_type(self, validator):
        """Test validation of a file with invalid type."""
        invalid_file = BytesIO(b'test')
        invalid_file.name = 'test.txt'
        with pytest.raises(SecurityError) as exc_info:
            validator.validate_file(invalid_file)
        assert str(exc_info.value) == ERROR_MESSAGES['invalid_file_type']
    
    def test_invalid_content(self, validator):
        """Test validation of a file with invalid content."""
        invalid_file = BytesIO(b'\x00test')
        invalid_file.name = 'test.csv'
        with pytest.raises(SecurityError) as exc_info:
            validator.validate_file(invalid_file)
        assert str(exc_info.value) == ERROR_MESSAGES['invalid_content']

class TestDataFrameValidation:
    def test_valid_dataframe(self, validator, sample_dataframe):
        """Test validation of a valid DataFrame."""
        assert validator.validate_dataframe(sample_dataframe) is True
    
    def test_dataframe_too_large(self, validator):
        """Test validation of a DataFrame that's too large."""
        large_df = pd.DataFrame(np.random.randn(FILE_CONFIG['max_rows'] + 1, 2))
        with pytest.raises(SecurityError) as exc_info:
            validator.validate_dataframe(large_df)
        assert str(exc_info.value) == ERROR_MESSAGES['dataframe_too_large']
    
    def test_invalid_column_names(self, validator):
        """Test validation of a DataFrame with invalid column names."""
        df = pd.DataFrame({None: [1, 2, 3]})
        with pytest.raises(SecurityError) as exc_info:
            validator.validate_dataframe(df)
        assert str(exc_info.value) == ERROR_MESSAGES['invalid_column_names']
    
    def test_duplicate_column_names(self, validator):
        """Test validation of a DataFrame with duplicate column names."""
        df = pd.DataFrame({'col1': [1, 2], 'col1': [3, 4]})
        with pytest.raises(SecurityError) as exc_info:
            validator.validate_dataframe(df)
        assert str(exc_info.value) == ERROR_MESSAGES['invalid_column_names']

class TestInputSanitization:
    def test_string_sanitization(self, validator):
        """Test sanitization of string input."""
        input_str = "test\x00string"
        expected = "teststring"
        assert validator.sanitize_input(input_str) == expected
    
    def test_dict_sanitization(self, validator):
        """Test sanitization of dictionary input."""
        input_dict = {
            "key1": "value1\x00",
            "key2": ["test\x00", "value2"]
        }
        expected = {
            "key1": "value1",
            "key2": ["test", "value2"]
        }
        assert validator.sanitize_input(input_dict) == expected
    
    def test_dataframe_sanitization(self, validator):
        """Test sanitization of DataFrame input."""
        df = pd.DataFrame({
            'col1': ['test\x00', 'value1'],
            'col2': [1, 2]
        })
        result = validator.sanitize_input(df)
        assert result['col1'].iloc[0] == 'test'
        assert result['col2'].iloc[0] == 1
    
    def test_long_string_truncation(self, validator):
        """Test truncation of long strings."""
        long_str = 'a' * (DATA_CONFIG['max_string_length'] + 1)
        result = validator.sanitize_input(long_str)
        assert len(result) == DATA_CONFIG['max_string_length']

class TestErrorHandling:
    def test_file_validation_error_logging(self, validator, caplog):
        """Test error logging during file validation."""
        invalid_file = BytesIO(b'\x00test')
        invalid_file.name = 'test.csv'
        with pytest.raises(SecurityError):
            validator.validate_file(invalid_file)
        assert "File content check failed" in caplog.text
    
    def test_dataframe_validation_error_logging(self, validator, caplog):
        """Test error logging during DataFrame validation."""
        df = pd.DataFrame({None: [1, 2, 3]})
        with pytest.raises(SecurityError):
            validator.validate_dataframe(df)
        assert "Column name check failed" in caplog.text
    
    def test_sanitization_error_logging(self, validator, caplog):
        """Test error logging during input sanitization."""
        with pytest.raises(SecurityError):
            validator.sanitize_input({'key': object()})
        assert "Input sanitization failed" in caplog.text 