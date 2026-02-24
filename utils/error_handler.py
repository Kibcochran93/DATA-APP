"""
Error handling utilities for the SEATS application.
"""
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class SEATSError(Exception):
    """Base exception class for SEATS application."""
    pass

class SecurityError(SEATSError):
    """Exception raised for security-related errors."""
    pass

def handle_error(error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
    """Handle application errors."""
    logger.error(f"Error occurred: {str(error)}", extra=context or {})
    raise SEATSError(str(error))

def log_error(error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
    """Log error with context."""
    logger.error(f"Error: {str(error)}", extra=context or {}) 