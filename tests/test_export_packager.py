import pytest
import pandas as pd
import zipfile
import io
import os
import tempfile
from datetime import datetime
from utils.export_packager import ExportPackager

@pytest.fixture
def temp_dir():
    """Create temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

@pytest.fixture
def packager(temp_dir):
    """Create ExportPackager instance for testing."""
    return ExportPackager(temp_dir)

@pytest.fixture
def sample_dataframe():
    """Create sample DataFrame for testing."""
    return pd.DataFrame({
        'col1': [1, 2, 3],
        'col2': ['a', 'b', 'c']
    })

def test_create_export_package(packager, sample_dataframe):
    """Test basic export package creation."""
    # Create package
    zip_content, zip_filename = packager.create_export_package(
        df=sample_dataframe,
        dataset_type="Test",
        validation_results={"issues": ["Test issue"]}
    )
    
    # Verify ZIP content
    with zipfile.ZipFile(io.BytesIO(zip_content)) as zip_file:
        # Check files exist
        assert len(zip_file.namelist()) == 2
        assert any(name.endswith('.csv') for name in zip_file.namelist())
        assert any(name.endswith('.txt') for name in zip_file.namelist())
        
        # Verify CSV content
        csv_content = zip_file.read(next(name for name in zip_file.namelist() if name.endswith('.csv')))
        df = pd.read_csv(io.BytesIO(csv_content))
        pd.testing.assert_frame_equal(df, sample_dataframe)
        
        # Verify README content
        readme_content = zip_file.read(next(name for name in zip_file.namelist() if name.endswith('.txt')))
        assert b"Test issue" in readme_content

def test_filename_conflict_resolution(packager, sample_dataframe):
    """Test handling of filename conflicts."""
    # Create first package
    zip_content1, _ = packager.create_export_package(
        df=sample_dataframe,
        dataset_type="Test"
    )
    
    # Create second package with same dataset type
    zip_content2, _ = packager.create_export_package(
        df=sample_dataframe,
        dataset_type="Test"
    )
    
    # Verify different filenames
    with zipfile.ZipFile(io.BytesIO(zip_content1)) as zip1, \
         zipfile.ZipFile(io.BytesIO(zip_content2)) as zip2:
        files1 = zip1.namelist()
        files2 = zip2.namelist()
        assert files1 != files2

def test_temp_dir_cleanup(packager, temp_dir):
    """Test temporary directory cleanup."""
    # Create some files in temp dir
    test_file = os.path.join(temp_dir, "test.txt")
    with open(test_file, "w") as f:
        f.write("test")
    
    # Delete packager to trigger cleanup
    del packager
    
    # Verify temp dir is cleaned up
    assert not os.path.exists(temp_dir)

def test_content_hash_generation(packager):
    """Test content hash generation."""
    # Test with different content
    content1 = b"test1"
    content2 = b"test2"
    
    hash1 = packager._calculate_content_hash(content1)
    hash2 = packager._calculate_content_hash(content2)
    
    assert hash1 != hash2
    assert len(hash1) == 64  # SHA-256 hash length

def test_unique_filename_generation(packager):
    """Test unique filename generation."""
    base_name = "test"
    content_hash = "a" * 64
    
    filename = packager._generate_unique_filename(base_name, content_hash)
    
    # Verify format
    assert filename.startswith(base_name)
    assert "_" in filename
    assert content_hash[:8] in filename
    assert any(c.isdigit() for c in filename)  # Should contain timestamp 