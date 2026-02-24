"""
Security package for the SEATS application.

Provides security-related functionality including:
- Authentication and authorization
- Security configuration
- Input validation
"""

from security.config import (
    SecurityConfig,
    InputValidator,
    FILE_CONFIG,
    DATA_CONFIG,
    PROTECTION_CONFIG,
    AUTH_CONFIG,
    MONITORING_CONFIG,
    ERROR_MESSAGES,
    PII_PATTERNS,
    get_encryption_key,
    BASE_DIR,
    DATA_DIR,
    LOGS_DIR,
)

# Import auth functions from autho package
try:
    from autho.auth import authenticate_user, authorize_access
except ImportError:
    # Fallback if autho package not available
    authenticate_user = None
    authorize_access = None

__all__ = [
    'SecurityConfig',
    'InputValidator',
    'FILE_CONFIG',
    'DATA_CONFIG',
    'PROTECTION_CONFIG',
    'AUTH_CONFIG',
    'MONITORING_CONFIG',
    'ERROR_MESSAGES',
    'PII_PATTERNS',
    'get_encryption_key',
    'authenticate_user',
    'authorize_access',
    'BASE_DIR',
    'DATA_DIR',
    'LOGS_DIR',
]
