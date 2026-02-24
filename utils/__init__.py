"""
Utility functions and helper modules for the SEATS application.

This package contains various utility modules for:
- Logging and error handling
- Data validation and cleaning
- Header normalization
- Data export functionality
- Specification loading and processing
"""

from utils.exceptions import (
    BaseError,
    ValidationError,
    SecurityError,
    DataError,
    AuthenticationError,
    AuthorizationError
)

__all__ = [
    'BaseError',
    'ValidationError',
    'SecurityError',
    'DataError',
    'AuthenticationError',
    'AuthorizationError'
] 