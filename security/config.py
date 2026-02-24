"""
Security configuration for the SEATS application.
"""
from typing import Dict, Any
import os
from pathlib import Path
from cryptography.fernet import Fernet

# Base directory for the application
BASE_DIR = Path('/app')

# Generate a Fernet key if not provided
def get_encryption_key():
    key_file = os.getenv('ENCRYPTION_KEY_FILE', str(BASE_DIR / 'keys/encryption.key'))
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        os.makedirs(os.path.dirname(key_file), exist_ok=True)
        with open(key_file, 'wb') as f:
            f.write(key)
        return key

# File configuration
FILE_CONFIG = {
    'max_size': int(os.getenv('MAX_FILE_SIZE', 10 * 1024 * 1024)),  # 10MB
    'allowed_extensions': {'.csv', '.xlsx'},
    'chunk_size': int(os.getenv('CHUNK_SIZE', 1024 * 1024))  # 1MB
}

# Data configuration
DATA_CONFIG = {
    'encryption_key': get_encryption_key(),
    'data_dir': str(BASE_DIR / 'data'),
    'temp_dir': str(BASE_DIR / 'data/temp')
}

# Protection configuration
PROTECTION_CONFIG = {
    'encryption_enabled': True,
    'masking_enabled': True,
    'audit_logging': True,
    'log_dir': str(BASE_DIR / 'logs'),
    'pii_patterns': {
        'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        'phone': r'^\+?1?\d{9,15}$',
        'ssn': r'^\d{3}-\d{2}-\d{4}$',
        'credit_card': r'^\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}$'
    },
    'masking': {
        'email': lambda x: f"{x[:3]}***@{x.split('@')[1]}",
        'phone': lambda x: f"***-***-{x[-4:]}",
        'ssn': lambda x: f"***-**-{x[-4:]}",
        'credit_card': lambda x: f"****-****-****-{x[-4:]}"
    }
}

# Authentication configuration
AUTH_CONFIG = {
    'jwt': {
        'secret_key': os.getenv('SECRET_KEY', 'default-secret-key'),
        'token_expiry': int(os.getenv('TOKEN_EXPIRY', '3600'))
    },
    'users': {
        'file_path': str(BASE_DIR / 'data/users.json')
    },
    'encryption': {
        'key': get_encryption_key()
    }
}

# Monitoring configuration
MONITORING_CONFIG = {
    'enabled': True,
    'log_dir': str(BASE_DIR / 'logs'),
    'metrics_port': int(os.getenv('METRICS_PORT', '9090')),
    'alert_threshold': int(os.getenv('ALERT_THRESHOLD', '1000')),
    'metrics': {
        'file_path': str(BASE_DIR / 'data/metrics.json'),
        'retention_days': 30
    },
    'events': {
        'file_path': str(BASE_DIR / 'data/events.json'),
        'max_events': 10000
    },
    'health': {
        'file_path': str(BASE_DIR / 'data/health.json'),
        'check_interval': 60,
        'thresholds': {
            'memory': {
                'warning': 80,  # 80% memory usage triggers warning
                'critical': 90  # 90% memory usage triggers critical
            },
            'cpu': {
                'warning': 70,  # 70% CPU usage triggers warning
                'critical': 85  # 85% CPU usage triggers critical
            },
            'disk': {
                'warning': 75,  # 75% disk usage triggers warning
                'critical': 90  # 90% disk usage triggers critical
            }
        }
    },
    'performance': {
        'check_interval': 5,
        'max_samples': 1000,
        'memory_threshold': int(os.getenv('MEMORY_THRESHOLD', '80')),  # 80% memory threshold
        'cpu_threshold': int(os.getenv('CPU_THRESHOLD', '70')),  # 70% CPU threshold
        'disk_threshold': int(os.getenv('DISK_THRESHOLD', '75'))  # 75% disk threshold
    }
}

class SecurityConfig:
    """Security configuration class."""
    
    def __init__(self):
        self.secret_key = os.getenv('SECRET_KEY', 'default-secret-key')
        self.token_expiry = int(os.getenv('TOKEN_EXPIRY', '3600'))
        self.allowed_origins = os.getenv('ALLOWED_ORIGINS', '*').split(',')
        
    def get_config(self) -> Dict[str, Any]:
        """Get security configuration."""
        return {
            'secret_key': self.secret_key,
            'token_expiry': self.token_expiry,
            'allowed_origins': self.allowed_origins
        }

class InputValidator:
    """Input validation class."""
    
    def __init__(self):
        self.max_file_size = FILE_CONFIG['max_size']
        self.allowed_extensions = FILE_CONFIG['allowed_extensions']
        
    def validate_file(self, file_path: str) -> bool:
        """Validate file size and extension."""
        if not file_path:
            return False
            
        file_size = os.path.getsize(file_path)
        file_ext = os.path.splitext(file_path)[1].lower()
        
        return (
            file_size <= self.max_file_size and
            file_ext in self.allowed_extensions
        ) 