"""
Error handling utilities for the SEATS application.

Provides centralized error handling, tracking, and logging.
"""

import logging
import traceback
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from functools import wraps

from utils.exceptions import (
    BaseError,
    ValidationError,
    DataError,
    SecurityError,
    AuthenticationError,
    AuthorizationError
)
from utils.debug_logger import setup_logger, log_exception

logger = setup_logger(__name__)


def handle_error(
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    reraise: bool = False
) -> Dict[str, Any]:
    """
    Central error handling function.
    
    Args:
        error: Exception to handle
        context: Additional context information
        reraise: Whether to re-raise the exception
        
    Returns:
        Dictionary containing error information
        
    Raises:
        Exception: If reraise is True
    """
    error_info = {
        "error_type": type(error).__name__,
        "message": str(error),
        "timestamp": datetime.utcnow().isoformat(),
        "context": context or {}
    }
    
    # Add error code if available
    if hasattr(error, "error_code"):
        error_info["error_code"] = error.error_code
    
    # Add details if available
    if hasattr(error, "details"):
        error_info["details"] = error.details
    
    # Add stack trace
    error_info["stack_trace"] = traceback.format_exc()
    
    # Log the error
    log_exception(error, logger, context)
    
    # Track the error
    track_error(error_info)
    
    if reraise:
        raise error
    
    return error_info


def track_error(error_info: Dict[str, Any]) -> None:
    """
    Track error for monitoring and analysis.
    
    Args:
        error_info: Error information dictionary
    """
    try:
        # Import here to avoid circular imports
        import streamlit as st
        
        monitoring = st.session_state.get("monitoring")
        if monitoring and hasattr(monitoring, "track_event"):
            monitoring.track_event(
                event_type="error",
                details=error_info,
                severity="error"
            )
    except Exception:
        # Fail silently if tracking fails
        pass


def setup_error_logging(log_file: Optional[str] = None) -> logging.Logger:
    """
    Set up error logging configuration.
    
    Args:
        log_file: Optional log file path
        
    Returns:
        Configured logger
    """
    return setup_logger("error_handler", log_file or "logs/errors.log")


def error_handler(
    default_return: Any = None,
    log_errors: bool = True,
    reraise_types: Optional[tuple] = None
) -> Callable:
    """
    Decorator for handling errors in functions.
    
    Args:
        default_return: Value to return on error
        log_errors: Whether to log errors
        reraise_types: Exception types to re-raise
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if reraise_types and isinstance(e, reraise_types):
                    raise
                
                if log_errors:
                    handle_error(
                        e,
                        context={
                            "function": func.__name__,
                            "args": str(args)[:100],
                            "kwargs": str(kwargs)[:100]
                        }
                    )
                
                return default_return
        
        return wrapper
    return decorator


def get_user_friendly_message(error: Exception) -> str:
    """
    Convert technical error to user-friendly message.
    
    Args:
        error: Exception instance
        
    Returns:
        User-friendly error message
    """
    if isinstance(error, ValidationError):
        return f"Data validation failed: {str(error)}"
    
    elif isinstance(error, AuthenticationError):
        return "Authentication failed. Please check your credentials."
    
    elif isinstance(error, AuthorizationError):
        return "You do not have permission to perform this action."
    
    elif isinstance(error, SecurityError):
        return "A security error occurred. Please contact support."
    
    elif isinstance(error, DataError):
        return f"Data processing error: {str(error)}"
    
    else:
        return "An unexpected error occurred. Please try again."


# Re-export SecurityError for backward compatibility
__all__ = [
    "handle_error",
    "track_error",
    "setup_error_logging",
    "error_handler",
    "get_user_friendly_message",
    "SecurityError",
    "ValidationError",
    "DataError",
    "AuthenticationError",
    "AuthorizationError",
    "BaseError"
]
