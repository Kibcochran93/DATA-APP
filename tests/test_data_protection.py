import pytest
import pandas as pd
import numpy as np
from datetime import datetime
import os
import tempfile
from protection.data_protection import DataProtection
from security.config import PROTECTION_CONFIG, ERROR_MESSAGES
from utils.exceptions import SecurityError

@pytest.fixture
def protection():
    """Create a DataProtection instance for testing."""
    return DataProtection(PROTECTION_CONFIG)

@pytest.fixture
def sample_dataframe():
    """Create a sample DataFrame with PII for testing."""
    return pd.DataFrame({
        'email': ['john.doe@example.com', 'jane.smith@example.com'],
        'phone': ['+1234567890', '+1987654321'],
        'ssn': ['123-45-6789', '987-65-4321'],
        'credit_card': ['1234-5678-9012-3456', '9876-5432-1098-7654']
    })

@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing file operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

class TestEncryption:
    def test_encrypt_decrypt_string(self, protection):
        """Test encryption and decryption of string data."""
        original = "test data"
        encrypted = protection.encrypt_data(original)
        decrypted = protection.decrypt_data(encrypted)
        assert decrypted.decode() == original
    
    def test_encrypt_decrypt_dataframe(self, protection, sample_dataframe):
        """Test encryption and decryption of DataFrame."""
        encrypted = protection.encrypt_data(sample_dataframe)
        decrypted = protection.decrypt_data(encrypted)
        decrypted_df = pd.read_json(decrypted)
        pd.testing.assert_frame_equal(decrypted_df, sample_dataframe)
    
    def test_encrypt_decrypt_dict(self, protection):
        """Test encryption and decryption of dictionary."""
        original = {'key1': 'value1', 'key2': 'value2'}
        encrypted = protection.encrypt_data(original)
        decrypted = protection.decrypt_data(encrypted)
        decrypted_dict = pd.read_json(decrypted, typ='series').to_dict()
        assert decrypted_dict == original
    
    def test_encrypt_decrypt_list(self, protection):
        """Test encryption and decryption of list."""
        original = ['item1', 'item2', 'item3']
        encrypted = protection.encrypt_data(original)
        decrypted = protection.decrypt_data(encrypted)
        decrypted_list = pd.read_json(decrypted, typ='series').tolist()
        assert decrypted_list == original

class TestMasking:
    def test_mask_email(self, protection):
        """Test masking of email addresses."""
        original = "john.doe@example.com"
        masked = protection._mask_string(original)
        assert masked == "j***@example.com"
    
    def test_mask_phone(self, protection):
        """Test masking of phone numbers."""
        original = "+1234567890"
        masked = protection._mask_string(original)
        assert masked == "+1******7890"
    
    def test_mask_ssn(self, protection):
        """Test masking of SSN."""
        original = "123-45-6789"
        masked = protection._mask_string(original)
        assert masked == "***-**-6789"
    
    def test_mask_credit_card(self, protection):
        """Test masking of credit card numbers."""
        original = "1234-5678-9012-3456"
        masked = protection._mask_string(original)
        assert masked == "****-****-****-3456"
    
    def test_mask_dataframe(self, protection, sample_dataframe):
        """Test masking of DataFrame with PII."""
        masked_df = protection.mask_pii(sample_dataframe)
        assert masked_df['email'].iloc[0] == "j***@example.com"
        assert masked_df['phone'].iloc[0] == "+1******7890"
        assert masked_df['ssn'].iloc[0] == "***-**-6789"
        assert masked_df['credit_card'].iloc[0] == "****-****-****-3456"

class TestSecureStorage:
    def test_secure_store_load_string(self, protection, temp_dir):
        """Test secure storage and loading of string data."""
        original = "test data"
        path = os.path.join(temp_dir, "test.txt")
        
        # Store data
        protection.secure_store(original, path)
        
        # Load data
        loaded = protection.secure_load(path)
        assert loaded.decode() == original
    
    def test_secure_store_load_dataframe(self, protection, temp_dir, sample_dataframe):
        """Test secure storage and loading of DataFrame."""
        path = os.path.join(temp_dir, "test.csv")
        
        # Store data
        protection.secure_store(sample_dataframe, path)
        
        # Load data
        loaded = protection.secure_load(path)
        loaded_df = pd.read_json(loaded)
        pd.testing.assert_frame_equal(loaded_df, sample_dataframe)
    
    def test_integrity_check(self, protection, temp_dir):
        """Test data integrity check."""
        original = "test data"
        path = os.path.join(temp_dir, "test.txt")
        
        # Store data
        protection.secure_store(original, path)
        
        # Tamper with data
        with open(path, 'wb') as f:
            f.write(b'tampered data')
        
        # Attempt to load data
        with pytest.raises(SecurityError) as exc_info:
            protection.secure_load(path)
        assert str(exc_info.value) == ERROR_MESSAGES['integrity_check_failed']

class TestErrorHandling:
    def test_encryption_error(self, protection):
        """Test error handling during encryption."""
        with pytest.raises(SecurityError) as exc_info:
            protection.encrypt_data(object())
        assert "Encryption failed" in str(exc_info.value)
    
    def test_decryption_error(self, protection):
        """Test error handling during decryption."""
        with pytest.raises(SecurityError) as exc_info:
            protection.decrypt_data(b'invalid data')
        assert "Decryption failed" in str(exc_info.value)
    
    def test_masking_error(self, protection):
        """Test error handling during masking."""
        with pytest.raises(SecurityError) as exc_info:
            protection.mask_pii(object())
        assert "Masking failed" in str(exc_info.value)
    
    def test_storage_error(self, protection):
        """Test error handling during storage."""
        with pytest.raises(SecurityError) as exc_info:
            protection.secure_store("test", "/invalid/path/test.txt")
        assert "Secure storage failed" in str(exc_info.value)
    
    def test_loading_error(self, protection):
        """Test error handling during loading."""
        with pytest.raises(SecurityError) as exc_info:
            protection.secure_load("/invalid/path/test.txt")
        assert "Secure loading failed" in str(exc_info.value) 