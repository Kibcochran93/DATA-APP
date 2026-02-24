"""
Security configuration for the SEATS application.

This module provides security-related configuration including:
- File validation settings
- Data protection configuration
- Authentication settings
- Monitoring configuration
"""

from typing import Dict, Any, Set
import os
from pathlib import Path
from cryptography.fernet import Fernet

# Base directory - use relative path for Windows executable compatibility
# Falls back to /app for Docker compatibility
if os.path.exists('/app'):
    BASE_DIR = Path('/app')
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

# Data directory
DATA_DIR = BASE_DIR / 'data'
LOGS_DIR = BASE_DIR / 'logs'
KEYS_DIR = BASE_DIR / 'keys'

# Ensure directories exist
for directory in [DATA_DIR, LOGS_DIR, KEYS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)


def get_encryption_key() -> bytes:
    """
    Get or generate encryption key.
    
    Returns:
        Encryption key as bytes
    """
    key_file = Path(os.getenv('ENCRYPTION_KEY_FILE', str(KEYS_DIR / 'encryption.key')))
    
    if key_file.exists():
        with open(key_file, 'rb') as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        key_file.parent.mkdir(parents=True, exist_ok=True)
        with open(key_file, 'wb') as f:
            f.write(key)
        return key


# Error messages for consistent error handling
ERROR_MESSAGES: Dict[str, str] = {
    # Authentication errors
    'invalid_credentials': 'Invalid username or password',
    'username_exists': 'Username already exists',
    'user_not_found': 'User not found',
    'token_expired': 'Token has expired',
    'token_invalid': 'Invalid token',
    'unauthorized': 'Unauthorized access',
    
    # Validation errors
    'file_too_large': 'File size exceeds maximum allowed size',
    'invalid_extension': 'File extension not allowed',
    'invalid_format': 'Invalid file format',
    'missing_required_field': 'Required field is missing',
    
    # Security errors
    'encryption_failed': 'Data encryption failed',
    'decryption_failed': 'Data decryption failed',
    'pii_detected': 'PII data detected',
    
    # System errors
    'database_error': 'Database operation failed',
    'file_access_error': 'File access denied',
    'configuration_error': 'Configuration error',
}


# File configuration
FILE_CONFIG: Dict[str, Any] = {
    'max_size': int(os.getenv('MAX_FILE_SIZE', 10 * 1024 * 1024)),  # 10MB
    'allowed_extensions': {'.csv', '.xlsx', '.xls', '.json'},
    'chunk_size': int(os.getenv('CHUNK_SIZE', 1024 * 1024)),  # 1MB
    'upload_timeout': int(os.getenv('UPLOAD_TIMEOUT', 30)),
}


# Data configuration
DATA_CONFIG: Dict[str, Any] = {
    'encryption_key': get_encryption_key(),
    'data_dir': str(DATA_DIR),
    'temp_dir': str(DATA_DIR / 'temp'),
    'exports_dir': str(DATA_DIR / 'exports'),
    'backup_dir': str(DATA_DIR / 'backup'),
}


# PII patterns for detection
PII_PATTERNS: Dict[str, str] = {
    'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    'phone': r'^\+?1?\d{9,15}$',
    'ssn': r'^\d{3}-\d{2}-\d{4}$',
    'credit_card': r'^\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}$',
    'uk_postcode': r'^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$',
    'student_id': r'^[A-Z]{2}\d{6,8}$',
}


# Masking functions for PII
def mask_email(email: str) -> str:
    """Mask email address."""
    if '@' in email:
        local, domain = email.split('@', 1)
        return f"{local[:3]}***@{domain}"
    return '***'


def mask_phone(phone: str) -> str:
    """Mask phone number."""
    return f"***-***-{phone[-4:]}" if len(phone) >= 4 else '***'


def mask_ssn(ssn: str) -> str:
    """Mask SSN."""
    return f"***-**-{ssn[-4:]}" if len(ssn) >= 4 else '***'


def mask_credit_card(card: str) -> str:
    """Mask credit card number."""
    return f"****-****-****-{card[-4:]}" if len(card) >= 4 else '***'


# Protection configuration
PROTECTION_CONFIG: Dict[str, Any] = {
    'encryption_enabled': True,
    'masking_enabled': True,
    'audit_logging': True,
    'log_dir': str(LOGS_DIR),
    'pii_patterns': PII_PATTERNS,
    'masking': {
        'email': mask_email,
        'phone': mask_phone,
        'ssn': mask_ssn,
        'credit_card': mask_credit_card,
    }
}


# Authentication configuration
AUTH_CONFIG: Dict[str, Any] = {
    'jwt': {
        'secret_key': os.getenv('JWT_SECRET', os.getenv('SECRET_KEY', 'change-this-secret-key-in-production')),
        'token_expiry': int(os.getenv('TOKEN_EXPIRY', '3600')),
        'algorithm': 'HS256',
    },
    'users': {
        'file_path': str(DATA_DIR / 'users.json'),
    },
    'encryption': {
        'key': get_encryption_key(),
    },
    'password': {
        'min_length': 8,
        'require_uppercase': True,
        'require_lowercase': True,
        'require_digit': True,
    }
}


# Monitoring configuration
MONITORING_CONFIG: Dict[str, Any] = {
    'enabled': os.getenv('MONITORING_ENABLED', 'true').lower() == 'true',
    'log_dir': str(LOGS_DIR),
    'metrics_port': int(os.getenv('METRICS_PORT', '9090')),
    'alert_threshold': int(os.getenv('ALERT_THRESHOLD', '1000')),
    'metrics': {
        'file_path': str(DATA_DIR / 'metrics.json'),
        'retention_days': 30,
    },
    'events': {
        'file_path': str(DATA_DIR / 'events.json'),
        'max_events': 10000,
    },
    'health': {
        'file_path': str(DATA_DIR / 'health.json'),
        'check_interval': 60,
        'thresholds': {
            'memory': {'warning': 80, 'critical': 90},
            'cpu': {'warning': 70, 'critical': 85},
            'disk': {'warning': 75, 'critical': 90},
        }
    },
    'performance': {
        'check_interval': 5,
        'max_samples': 1000,
        'memory_threshold': int(os.getenv('MEMORY_THRESHOLD', '80')),
        'cpu_threshold': int(os.getenv('CPU_THRESHOLD', '70')),
        'disk_threshold': int(os.getenv('DISK_THRESHOLD', '75')),
    }
}


class SecurityConfig:
    """Security configuration class."""
    
    def __init__(self):
        """Initialize security configuration."""
        self.secret_key = AUTH_CONFIG['jwt']['secret_key']
        self.token_expiry = AUTH_CONFIG['jwt']['token_expiry']
        self.allowed_origins = os.getenv('ALLOWED_ORIGINS', '*').split(',')
    
    def get_config(self) -> Dict[str, Any]:
        """Get security configuration dictionary."""
        return {
            'secret_key': self.secret_key,
            'token_expiry': self.token_expiry,
            'allowed_origins': self.allowed_origins,
        }


class InputValidator:
    """Input validation class for file uploads and data."""
    
    def __init__(self):
        """Initialize input validator."""
        self.max_file_size = FILE_CONFIG['max_size']
        self.allowed_extensions = FILE_CONFIG['allowed_extensions']
    
    def validate_file(self, uploaded_file) -> bool:
        """
        Validate uploaded file.
        
        Args:
            uploaded_file: Streamlit uploaded file object
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If validation fails
        """
        if uploaded_file is None:
            raise ValueError("No file provided")
        
        # Check file size
        if hasattr(uploaded_file, 'size'):
            if uploaded_file.size > self.max_file_size:
                raise ValueError(ERROR_MESSAGES['file_too_large'])
        
        # Check extension
        if hasattr(uploaded_file, 'name'):
            ext = Path(uploaded_file.name).suffix.lower()
            if ext not in self.allowed_extensions:
                raise ValueError(ERROR_MESSAGES['invalid_extension'])
        
        return True
    
    def validate_dataframe(self, df) -> Dict[str, Any]:
        """
        Validate a DataFrame.
        
        Args:
            df: pandas DataFrame
            
        Returns:
            Validation result dictionary
        """
        result = {
            'is_valid': True,
            'issues': [],
            'row_count': len(df) if df is not None else 0,
            'column_count': len(df.columns) if df is not None else 0,
        }
        
        if df is None or df.empty:
            result['is_valid'] = False
            result['issues'].append("DataFrame is empty")
        
        return result
    
    def sanitize_input(self, df):
        """
        Sanitize DataFrame input.
        
        Args:
            df: pandas DataFrame
            
        Returns:
            Sanitized DataFrame
        """
        if df is None:
            return df
        
        # Strip whitespace from string columns
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
        
        return df


__all__ = [
    'FILE_CONFIG',
    'DATA_CONFIG',
    'PROTECTION_CONFIG',
    'AUTH_CONFIG',
    'MONITORING_CONFIG',
    'ERROR_MESSAGES',
    'PII_PATTERNS',
    'SecurityConfig',
    'InputValidator',
    'get_encryption_key',
    'BASE_DIR',
    'DATA_DIR',
    'LOGS_DIR',
]
