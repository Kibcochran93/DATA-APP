import pytest
import pandas as pd
import zipfile
import io
from utils.export_packager import ExportPackager

@pytest.fixture
def packager():
    """Create ExportPackager instance for testing."""
    return ExportPackager()

@pytest.fixture
def sample_dataframe():
    """Create sample DataFrame for testing."""
    return pd.DataFrame({
        'col1': [1, 2, 3],
        'col2': ['a', 'b', 'c']
    })

@pytest.fixture
def validation_results():
    """Create sample validation results."""
    return {
        "is_valid": True,
        "issues": ["Test issue"],
        "row_count": 3
    }

def test_create_export_package(packager, sample_dataframe, validation_results):
    """Test basic export package creation."""
    # Create package
    zip_content, zip_filename = packager.create_export_package(
        df=sample_dataframe,
        dataset_type="Test",
        validation_results=validation_results
    )
    
    # Verify ZIP content
    assert zip_content is not None
    assert len(zip_content) > 0
    assert zip_filename.endswith('.zip')
    
    with zipfile.ZipFile(io.BytesIO(zip_content)) as zip_file:
        # Check files exist
        assert len(zip_file.namelist()) >= 1
        # Should contain a CSV file
        csv_files = [name for name in zip_file.namelist() if name.endswith('.csv')]
        assert len(csv_files) >= 1

def test_create_export_package_with_spec_version(packager, sample_dataframe, validation_results):
    """Test export package with spec version."""
    zip_content, zip_filename = packager.create_export_package(
        df=sample_dataframe,
        dataset_type="Test",
        validation_results=validation_results,
        spec_version="2.0"
    )
    
    assert zip_content is not None
    assert zip_filename.endswith('.zip')

def test_create_export_package_empty_dataframe(packager, validation_results):
    """Test export package with empty DataFrame."""
    empty_df = pd.DataFrame()
    
    zip_content, zip_filename = packager.create_export_package(
        df=empty_df,
        dataset_type="Empty",
        validation_results=validation_results
    )
    
    assert zip_content is not None

def test_packager_initialization():
    """Test packager initializes correctly."""
    packager = ExportPackager()
    assert packager is not None
    assert hasattr(packager, 'create_export_package')
