import pytest
import pandas as pd
import json
import os
import tempfile
from datetime import datetime, timedelta
from utils.data_exporter import DataExporter
from utils.exceptions import SecurityError, ValidationError

@pytest.fixture
def temp_export_dir():
    """Create a temporary export directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

@pytest.fixture
def exporter(temp_export_dir):
    """Create a DataExporter instance for testing."""
    config = {
        'supported_formats': ['csv', 'excel', 'json'],
        'max_file_size': 1024 * 1024,  # 1MB
        'export_dir': temp_export_dir,
        'retention_days': 30,
        'compression': {
            'enabled': True,
            'level': 6
        },
        'formats': {
            'csv': {
                'encoding': 'utf-8',
                'sep': ',',
                'index': False
            },
            'excel': {
                'engine': 'openpyxl',
                'sheet_name': 'Sheet1',
                'index': False
            },
            'json': {
                'indent': 2
            }
        }
    }
    return DataExporter(config)

@pytest.fixture
def sample_dataframe():
    """Create a sample DataFrame for testing."""
    return pd.DataFrame({
        'col1': [1, 2, 3],
        'col2': ['a', 'b', 'c']
    })

@pytest.fixture
def sample_dict():
    """Create a sample dictionary for testing."""
    return {
        'key1': 'value1',
        'key2': [1, 2, 3]
    }

@pytest.fixture
def sample_list():
    """Create a sample list for testing."""
    return [
        {'id': 1, 'name': 'item1'},
        {'id': 2, 'name': 'item2'}
    ]

class TestExportFormats:
    def test_export_csv(self, exporter, sample_dataframe):
        """Test CSV export."""
        result = exporter.export_data(sample_dataframe, 'csv')
        assert result['format'] == 'csv'
        assert result['filename'].endswith('.csv')
        assert os.path.exists(result['path'])
        
        # Verify content
        df = pd.read_csv(result['path'])
        pd.testing.assert_frame_equal(df, sample_dataframe)
    
    def test_export_excel(self, exporter, sample_dataframe):
        """Test Excel export."""
        result = exporter.export_data(sample_dataframe, 'excel')
        assert result['format'] == 'excel'
        assert result['filename'].endswith('.xlsx')
        assert os.path.exists(result['path'])
        
        # Verify content
        df = pd.read_excel(result['path'])
        pd.testing.assert_frame_equal(df, sample_dataframe)
    
    def test_export_json(self, exporter, sample_dict):
        """Test JSON export."""
        result = exporter.export_data(sample_dict, 'json')
        assert result['format'] == 'json'
        assert result['filename'].endswith('.json')
        assert os.path.exists(result['path'])
        
        # Verify content
        with open(result['path'], 'r') as f:
            data = json.load(f)
        assert data == sample_dict

class TestDataTypes:
    def test_export_dataframe(self, exporter, sample_dataframe):
        """Test exporting DataFrame."""
        result = exporter.export_data(sample_dataframe, 'csv')
        assert result['format'] == 'csv'
        assert os.path.exists(result['path'])
    
    def test_export_dict(self, exporter, sample_dict):
        """Test exporting dictionary."""
        result = exporter.export_data(sample_dict, 'json')
        assert result['format'] == 'json'
        assert os.path.exists(result['path'])
    
    def test_export_list(self, exporter, sample_list):
        """Test exporting list."""
        result = exporter.export_data(sample_list, 'json')
        assert result['format'] == 'json'
        assert os.path.exists(result['path'])

class TestErrorHandling:
    def test_unsupported_format(self, exporter, sample_dataframe):
        """Test exporting with unsupported format."""
        with pytest.raises(ValidationError) as exc_info:
            exporter.export_data(sample_dataframe, 'invalid')
        assert "Unsupported format" in str(exc_info.value)
    
    def test_file_too_large(self, exporter):
        """Test exporting file that's too large."""
        # Create large DataFrame
        large_df = pd.DataFrame({
            'col1': ['x' * 1024 * 1024] * 2  # 2MB of data
        })
        
        with pytest.raises(SecurityError) as exc_info:
            exporter.export_data(large_df, 'csv')
        assert "Export file too large" in str(exc_info.value)
    
    def test_invalid_data(self, exporter):
        """Test exporting invalid data."""
        with pytest.raises(SecurityError) as exc_info:
            exporter.export_data(object(), 'json')
        assert "Export failed" in str(exc_info.value)

class TestExportHistory:
    def test_get_export_history(self, exporter, sample_dataframe):
        """Test getting export history."""
        # Create some exports
        exporter.export_data(sample_dataframe, 'csv')
        exporter.export_data(sample_dataframe, 'excel')
        
        history = exporter.get_export_history()
        assert len(history) == 2
        assert all('filename' in record for record in history)
        assert all('size' in record for record in history)
        assert all('created' in record for record in history)
        assert all('path' in record for record in history)
    
    def test_cleanup_exports(self, exporter, sample_dataframe):
        """Test cleaning up old exports."""
        # Create some exports
        exporter.export_data(sample_dataframe, 'csv')
        exporter.export_data(sample_dataframe, 'excel')
        
        # Clean up exports older than 0 days
        exporter.cleanup_exports(max_age_days=0)
        
        # Verify all exports are cleaned up
        history = exporter.get_export_history()
        assert len(history) == 0 