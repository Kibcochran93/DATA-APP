from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING
import pandas as pd
import numpy as np
from datetime import datetime
import re
import logging
import hashlib
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os
import warnings
import json

# Runtime imports for exceptions and logging
from utils.exceptions import SecurityError, ValidationError
from utils.debug_logger import setup_logger, log_exception

# Setup logger
logger = logging.getLogger(__name__)

# Suppress specific warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=DeprecationWarning)
    warnings.simplefilter("ignore", category=FutureWarning)

class DataProtection:
    """Handles data protection including encryption, masking, and secure storage."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize data protection with configuration.
        
        Args:
            config: Dictionary containing protection configuration
            
        Raises:
            SecurityError: If initialization fails
        """
        try:
            from utils.exceptions import SecurityError
            from utils.debug_logger import setup_logger, log_exception
            
            self.config = config
            self.encryption_key = self._generate_key()
            self.fernet = Fernet(self.encryption_key)
            self.pii_patterns = config.get('pii_patterns', {})
            self.masking_config = config.get('masking', {})
            
            # Validate configuration
            self._validate_config()
            
        except Exception as e:
            log_exception(e, logger, action= "DataProtection.__init__")
            raise SecurityError(f"Failed to initialize data protection: {str(e)}")
    
    def _validate_config(self) -> None:
        """
        Validate the protection configuration.
        
        Raises:
            SecurityError: If configuration is invalid
        """
        try:
            # Validate required fields
            required_fields = ['pii_patterns', 'masking']
            for field in required_fields:
                if field not in self.config:
                    raise SecurityError(f"Missing required configuration field: {field}")
            
            # Validate PII patterns
            if not isinstance(self.pii_patterns, dict):
                raise SecurityError("pii_patterns must be a dictionary")
            
            # Validate masking configuration
            if not isinstance(self.masking_config, dict):
                raise SecurityError("masking configuration must be a dictionary")
            
        except Exception as e:
            log_exception(e, logger, action= "DataProtection._validate_config")
            raise SecurityError(f"Configuration validation failed: {str(e)}")
    
    def _generate_key(self) -> bytes:
        """
        Generate encryption key.
        
        Returns:
            Encryption key bytes
            
        Raises:
            SecurityError: If key generation fails
        """
        try:
            # Use PBKDF2 to generate key
            salt = b'seats_salt'  # Should be stored securely
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000
            )
            key = base64.urlsafe_b64encode(kdf.derive(b'seats_key'))  # Should be stored securely
            return key
            
        except Exception as e:
            log_exception(e, logger, action= "DataProtection._generate_key")
            raise SecurityError(f"Key generation failed: {str(e)}")
    
    def encrypt_data(self, data: Any) -> bytes:
        """
        Encrypt data.
        
        Args:
            data: Data to encrypt
            
        Returns:
            Encrypted data as bytes
            
        Raises:
            SecurityError: If encryption fails
        """
        try:
            if isinstance(data, pd.DataFrame):
                return self._encrypt_dataframe(data)
            if isinstance(data, dict):
                return self._encrypt_dict(data)
            if isinstance(data, list):
                return self._encrypt_list(data)
            if isinstance(data, str):
                return self._encrypt_string(data)
            return self.fernet.encrypt(str(data).encode())
        except Exception as e:
            log_exception(e, logger, action= "DataProtection.encrypt_data")
            raise SecurityError(f"Encryption failed: {str(e)}")
    
    def decrypt_data(self, encrypted_data: bytes) -> Any:
        """
        Decrypt data.
        
        Args:
            encrypted_data: Encrypted data to decrypt
            
        Returns:
            Decrypted data
            
        Raises:
            SecurityError: If decryption fails
        """
        try:
            return self.fernet.decrypt(encrypted_data)
        except Exception as e:
            log_exception(e, logger, action= "DataProtection.decrypt_data")
            raise SecurityError(f"Decryption failed: {str(e)}")
    
    def mask_pii(self, data: Union[pd.DataFrame, Dict, List]) -> Union[pd.DataFrame, Dict, List]:
        """
        Mask PII data.
        
        Args:
            data: Data to mask
            
        Returns:
            Masked data
            
        Raises:
            SecurityError: If masking fails
        """
        try:
            if isinstance(data, pd.DataFrame):
                return self._mask_dataframe(data)
            elif isinstance(data, dict):
                return self._mask_dict(data)
            elif isinstance(data, list):
                return self._mask_list(data)
            else:
                raise SecurityError(f"Unsupported data type: {type(data)}")
                
        except Exception as e:
            log_exception(e, logger, action= "DataProtection.mask_pii")
            raise SecurityError(f"PII masking failed: {str(e)}")
    
    def _encrypt_dataframe(self, df: pd.DataFrame) -> bytes:
        """Encrypt DataFrame."""
        try:
            # Convert DataFrame to JSON
            json_data = df.to_json(orient='records')
            # Encrypt JSON data
            return self.fernet.encrypt(json_data.encode())
        except Exception as e:
            log_exception(e, logger, action= "DataProtection._encrypt_dataframe")
            raise SecurityError(f"DataFrame encryption failed: {str(e)}")
    
    def _encrypt_dict(self, d: Dict[str, Any]) -> bytes:
        """Encrypt dictionary."""
        try:
            # Convert dictionary to JSON
            json_data = pd.Series(d).to_json()
            # Encrypt JSON data
            return self.fernet.encrypt(json_data.encode())
        except Exception as e:
            log_exception(e, logger, action= "DataProtection._encrypt_dict")
            raise SecurityError(f"Dictionary encryption failed: {str(e)}")
    
    def _encrypt_list(self, l: List[Any]) -> bytes:
        """Encrypt list."""
        try:
            # Convert list to JSON
            json_data = pd.Series(l).to_json()
            # Encrypt JSON data
            return self.fernet.encrypt(json_data.encode())
        except Exception as e:
            log_exception(e, logger, action= "DataProtection._encrypt_list")
            raise SecurityError(f"List encryption failed: {str(e)}")
    
    def _encrypt_string(self, s: str) -> bytes:
        """Encrypt string."""
        try:
            return self.fernet.encrypt(s.encode())
        except Exception as e:
            log_exception(e, logger, action= "DataProtection._encrypt_string")
            raise SecurityError(f"String encryption failed: {str(e)}")
    
    def _mask_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Mask PII in DataFrame."""
        try:
            # Create a copy
            df_masked = df.copy()
            
            # Mask each column based on patterns
            for col in df_masked.columns:
                if df_masked[col].dtype == 'object':
                    df_masked[col] = df_masked[col].apply(self._mask_value)
            
            return df_masked
            
        except Exception as e:
            log_exception(e, logger, action= "DataProtection._mask_dataframe")
            raise SecurityError(f"DataFrame masking failed: {str(e)}")
    
    def _mask_value(self, value: str) -> str:
        """
        Mask a single value.
        
        Args:
            value: Value to mask
            
        Returns:
            Masked value
        """
        try:
            if not isinstance(value, str):
                return value
                
            # Check each PII pattern
            for pattern, mask in self.pii_patterns.items():
                if re.search(pattern, value, re.I):
                    return mask
                    
            return value
            
        except Exception as e:
            log_exception(e, logger, action= "DataProtection._mask_value")
            return value  # Return original value on error
    
    def _mask_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mask PII in dictionary."""
        try:
            return {k: self._mask_value(v) if isinstance(v, str) else v 
                   for k, v in data.items()}
                   
        except Exception as e:
            log_exception(e, logger, action= "DataProtection._mask_dict")
            raise SecurityError(f"Dictionary masking failed: {str(e)}")
    
    def _mask_list(self, data: List[Any]) -> List[Any]:
        """Mask PII in list."""
        try:
            return [self._mask_value(item) if isinstance(item, str) else item 
                   for item in data]
                   
        except Exception as e:
            log_exception(e, logger, action= "DataProtection._mask_list")
            raise SecurityError(f"List masking failed: {str(e)}")
    
    def secure_store(self, data: Any, path: str) -> None:
        """
        Securely store data.
        
        Args:
            data: Data to store
            path: Path to store data
            
        Raises:
            SecurityError: If storage fails
        """
        try:
            # Encrypt data
            encrypted_data = self.encrypt_data(data)
            
            # Generate hash for integrity check
            data_hash = hashlib.sha256(encrypted_data).hexdigest()
            
            # Store encrypted data and hash
            with open(path, 'wb') as f:
                f.write(encrypted_data)
            
            with open(f"{path}.hash", 'w') as f:
                f.write(data_hash)
                
        except Exception as e:
            log_exception(e, logger, action= "DataProtection.secure_store")
            raise SecurityError(f"Secure storage failed: {str(e)}")
    
    def secure_load(self, path: str) -> Any:
        """
        Securely load data.
        
        Args:
            path: Path to load data from
            
        Returns:
            Loaded data
            
        Raises:
            SecurityError: If loading fails
        """
        try:
            # Load encrypted data
            with open(path, 'rb') as f:
                encrypted_data = f.read()
            
            # Verify integrity
            with open(f"{path}.hash", 'r') as f:
                stored_hash = f.read().strip()
            
            current_hash = hashlib.sha256(encrypted_data).hexdigest()
            if current_hash != stored_hash:
                raise SecurityError("Data integrity check failed")
            
            # Decrypt data
            return self.decrypt_data(encrypted_data)
            
        except Exception as e:
            log_exception(e, logger, action= "DataProtection.secure_load")
            raise SecurityError(f"Secure loading failed: {str(e)}") 