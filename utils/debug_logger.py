# Standard library imports
import sys
import logging
import inspect
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import re

# Third-party imports
# None required

# Local imports
# None required

# Configure logging
def setup_logger(name: str = 'seats_debug', log_file: str = 'debug.log') -> logging.Logger:
    """Set up logging configuration.
    
    Args:
        name: Logger name
        log_file: Log file name
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Create logs directory - try /app/logs first (container), fallback to local
    log_dir = Path('/app/logs')
    if not log_dir.parent.exists():
        # Not in container, use local logs directory
        log_dir = Path.cwd() / 'logs'
    
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError):
        # Fallback to temp directory if we can't create logs
        import tempfile
        log_dir = Path(tempfile.gettempdir()) / 'seats_logs'
        log_dir.mkdir(parents=True, exist_ok=True)
    
    # File handler for debug logs
    debug_handler = logging.FileHandler(
        log_dir / log_file,
        encoding='utf-8',
        mode='a'  # Append mode
    )
    debug_handler.setLevel(logging.DEBUG)
    
    # Console handler for debug output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    
    # Create formatters with more detailed information
    debug_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s\n'
        'File: %(pathname)s\n'
        'Line: %(lineno)d\n'
        'Function: %(funcName)s\n'
        'Process ID: %(process)d\n'
        'Thread ID: %(thread)d\n'
        'Stack Trace:\n%(exc_info)s'
    )
    
    # Set formatters
    debug_handler.setFormatter(debug_formatter)
    console_handler.setFormatter(debug_formatter)
    
    # Add handlers
    logger.addHandler(debug_handler)
    logger.addHandler(console_handler)
    
    # Add PII filter
    logger.addFilter(PIIFilter())
    
    return logger

class PIIFilter(logging.Filter):
    """Filter to prevent logging of PII data."""
    
    # Patterns for PII data
    PII_PATTERNS = [
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
        r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # Phone
        r'\b[A-Za-z]+(?:\s+[A-Za-z]+){1,2}\b',  # Names
        r'\b\d{1,3}\s+[A-Za-z]+\s+[A-Za-z]+\b',  # Addresses
        r'\b[A-Z]{2}\d{2}\s?\d{2}\s?\d{2}\s?\d{2}\b',  # UK Postcodes
        r'\b\d{2}/\d{2}/\d{4}\b',  # Dates
        r'\b[A-Z]{2}\d{6}\b',  # Student IDs
        r'\b[A-Z]{2}\d{8}\b'   # Staff IDs
    ]
    
    def filter(self, record):
        """Filter out PII data from log records."""
        if isinstance(record.msg, str):
            # Replace PII data with [REDACTED]
            for pattern in self.PII_PATTERNS:
                record.msg = re.sub(pattern, '[REDACTED]', record.msg)
        return True

def log_exception(
    exception: Exception,
    logger: Optional[logging.Logger] = None,
    context: Optional[Dict[str, Any]] = None,
    action: Optional[str] = None
) -> None:
    """
    Log an exception with context.
    
    Args:
        exception: Exception to log
        logger: Optional logger instance
        context: Additional context information
        action: Optional action that was being performed
    """
    if logger is None:
        logger = setup_logger()
        
    # Get caller information
    frame = inspect.currentframe()
    if frame is not None:
        caller = frame.f_back
        if caller is not None:
            context = context or {}
            context.update({
                'caller_file': caller.f_code.co_filename,
                'caller_line': caller.f_lineno,
                'caller_function': caller.f_code.co_name
            })
    
    # Add action to context if provided
    if action:
        context = context or {}
        context['action'] = action
    
    # Log exception
    logger.exception(
        f"Exception: {str(exception)}",
        extra={
            'context': context,
            'timestamp': datetime.utcnow().isoformat()
        }
    )

def log_debug_info(
    message: str,
    logger: Optional[logging.Logger] = None,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log debug information with context.
    
    Args:
        message: Debug message
        logger: Optional logger instance
        context: Additional context information
    """
    if logger is None:
        logger = setup_logger()
        
    # Get caller information
    frame = inspect.currentframe()
    if frame is not None:
        caller = frame.f_back
        if caller is not None:
            context = context or {}
            context.update({
                'caller_file': caller.f_code.co_filename,
                'caller_line': caller.f_lineno,
                'caller_function': caller.f_code.co_name
            })
    
    # Log debug message
    logger.debug(
        message,
        extra={
            'context': context,
            'timestamp': datetime.utcnow().isoformat()
        }
    )

def log_security_event(
    event_type: str,
    message: str,
    logger: Optional[logging.Logger] = None,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log security-related events.
    
    Args:
        event_type: Type of security event
        message: Event message
        logger: Optional logger instance
        context: Additional context information
    """
    if logger is None:
        logger = setup_logger()
        
    # Log security event
    logger.warning(
        f"Security Event - {event_type}: {message}",
        extra={
            'event_type': event_type,
            'context': context,
            'timestamp': datetime.utcnow().isoformat()
        }
    )

def log_codebase_issues() -> None:
    """
    Log identified issues in the codebase to the debug log.
    """
    debug_logger = setup_logger()
    
    # Log error handling issues
    error_handling_issues = {
        "issue_type": "Error Handling",
        "description": "Inconsistent error handling patterns across files",
        "affected_files": [
            "app.py",
            "master_spec_loader.py",
            "validator.py",
            "components/file_uploader.py"
        ],
        "recommendation": "Standardize error handling and logging patterns"
    }
    log_debug_info(debug_logger, error_handling_issues)
    
    # Log caching issues
    caching_issues = {
        "issue_type": "Caching",
        "description": "Inconsistent cache sizes and potential cache invalidation needs",
        "affected_functions": [
            "get_available_datasets (maxsize=1)",
            "get_spec_description (maxsize=128)",
            "validate_dataset (maxsize=CACHE_CONFIG['maxsize'])"
        ],
        "recommendation": "Standardize cache sizes and implement cache invalidation"
    }
    log_debug_info(debug_logger, caching_issues)
    
    # Log type hint issues
    type_hint_issues = {
        "issue_type": "Type Hints",
        "description": "Missing or inconsistent type hints",
        "affected_files": [
            "utils/spec_loader.py",
            "components/error_display.py",
            "dataset_logic.py"
        ],
        "recommendation": "Add comprehensive type hints and standardize docstrings"
    }
    log_debug_info(debug_logger, type_hint_issues)
    
    # Log security issues
    security_issues = {
        "issue_type": "Security",
        "description": "Potential security vulnerabilities",
        "concerns": [
            "File upload validation could be enhanced",
            "Path traversal protection could be improved",
            "Session state management needs review"
        ],
        "recommendation": "Implement additional security checks and validations"
    }
    log_debug_info(debug_logger, security_issues)
    log_security_event(debug_logger, "Security review needed for file upload and path handling", "warning")
    
    # Log performance issues
    performance_issues = {
        "issue_type": "Performance",
        "description": "Potential performance optimizations",
        "areas": [
            "Large file handling",
            "Cache utilization",
            "Database operations"
        ],
        "recommendation": "Review and optimize performance-critical sections"
    }
    log_debug_info(debug_logger, performance_issues)
    
    # Log system information
    system_info = {
        "python_version": sys.version,
        "platform": sys.platform,
        "working_directory": str(Path.cwd()),
        "python_path": sys.path
    }
    log_debug_info(debug_logger, system_info)

if __name__ == "__main__":
    log_codebase_issues() 