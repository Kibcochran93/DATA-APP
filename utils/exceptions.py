from typing import Dict, Any, Optional
from datetime import datetime
import traceback
import json

class BaseError(Exception):
    """Base exception class for all application errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str = "UNKNOWN_ERROR",
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        """
        Initialize error with message and context.
        
        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional error details
            original_error: Original exception if this is a wrapper
        """
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.original_error = original_error
        self.timestamp = datetime.utcnow()
        
        # Add stack trace
        self.stack_trace = traceback.format_exc()
        
        # Build full message
        full_message = f"{error_code}: {message}"
        if details:
            full_message += f"\nDetails: {json.dumps(details, indent=2)}"
        if original_error:
            full_message += f"\nOriginal Error: {str(original_error)}"
            
        super().__init__(full_message)
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary format."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "stack_trace": self.stack_trace
        }

class ValidationError(BaseError):
    """Exception for validation errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str = "VALIDATION_ERROR",
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message, error_code, details, original_error)

class DataError(BaseError):
    """Exception for data-related errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str = "DATA_ERROR",
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message, error_code, details, original_error)

class SecurityError(BaseError):
    """Exception for security-related errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str = "SECURITY_ERROR",
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message, error_code, details, original_error)

class AuthenticationError(SecurityError):
    """Exception for authentication errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str = "AUTHENTICATION_ERROR",
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message, error_code, details, original_error)

class AuthorizationError(SecurityError):
    """Exception for authorization errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str = "AUTHORIZATION_ERROR",
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message, error_code, details, original_error) 