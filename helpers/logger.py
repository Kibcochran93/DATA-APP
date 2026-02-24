"""
Logging helper utilities for the SEATS application.

Provides convenience functions for logging throughout the application.
"""

import logging
import sys
from typing import Optional, Dict, Any, Union
from datetime import datetime
from pathlib import Path


def setup_logger(
    name: str = "seats",
    log_file: Optional[str] = None,
    level: int = logging.INFO
) -> logging.Logger:
    """
    Set up and configure a logger.
    
    Args:
        name: Logger name
        log_file: Optional log file path
        level: Logging level
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    
    return logger


def log_exception(
    logger_or_exception: Union[logging.Logger, Exception],
    exception_or_logger: Union[Exception, logging.Logger] = None,
    context: Optional[Union[str, Dict[str, Any]]] = None,
    extra: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an exception with context.
    
    Supports two calling conventions for backward compatibility:
    1. log_exception(logger, exception, context_string)  - Old style
    2. log_exception(exception, logger, context_dict)    - New style
    
    Args:
        logger_or_exception: Either a logger or exception
        exception_or_logger: Either an exception or logger
        context: Context string or dictionary
        extra: Additional information (new style only)
    """
    # Detect calling convention
    if isinstance(logger_or_exception, logging.Logger):
        # Old style: log_exception(logger, exception, context_string)
        logger = logger_or_exception
        exception = exception_or_logger
        if isinstance(context, str):
            context_dict = {"context": context}
        else:
            context_dict = context or {}
    elif isinstance(logger_or_exception, Exception):
        # New style: log_exception(exception, logger, context_dict)
        exception = logger_or_exception
        logger = exception_or_logger if isinstance(exception_or_logger, logging.Logger) else setup_logger()
        context_dict = context if isinstance(context, dict) else {}
    else:
        # Fallback
        logger = setup_logger()
        exception = logger_or_exception if isinstance(logger_or_exception, Exception) else Exception(str(logger_or_exception))
        context_dict = {}
    
    # Add extra info if provided
    if extra:
        context_dict.update(extra)
    
    # Build message
    message_parts = [f"Exception: {type(exception).__name__}: {str(exception)}"]
    
    if context_dict:
        # Redact sensitive information
        safe_context = {
            k: "***REDACTED***" if any(s in k.lower() for s in ['password', 'secret', 'key', 'token']) else v
            for k, v in context_dict.items()
        }
        message_parts.append(f"Context: {safe_context}")
    
    message_parts.append(f"Timestamp: {datetime.utcnow().isoformat()}")
    
    logger.exception(" | ".join(message_parts))


def log_info(
    logger: logging.Logger,
    message: str,
    context: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an info message with optional context.
    
    Args:
        logger: Logger instance
        message: Log message
        context: Optional context description
        extra: Optional extra information
    """
    if context:
        message = f"[{context}] {message}"
    
    if extra:
        message = f"{message} | {extra}"
    
    logger.info(message)


def log_warning(
    logger: logging.Logger,
    message: str,
    context: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log a warning message with optional context.
    
    Args:
        logger: Logger instance
        message: Log message
        context: Optional context description
        extra: Optional extra information
    """
    if context:
        message = f"[{context}] {message}"
    
    if extra:
        message = f"{message} | {extra}"
    
    logger.warning(message)


def log_error(
    logger: logging.Logger,
    message: str,
    context: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an error message with optional context.
    
    Args:
        logger: Logger instance
        message: Log message
        context: Optional context description
        extra: Optional extra information
    """
    if context:
        message = f"[{context}] {message}"
    
    if extra:
        message = f"{message} | {extra}"
    
    logger.error(message)


def log_debug(
    logger: logging.Logger,
    message: str,
    context: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log a debug message with optional context.
    
    Args:
        logger: Logger instance
        message: Log message
        context: Optional context description
        extra: Optional extra information
    """
    if context:
        message = f"[{context}] {message}"
    
    if extra:
        message = f"{message} | {extra}"
    
    logger.debug(message)


def log_security_event(
    logger: logging.Logger,
    event_type: str,
    details: Optional[Dict[str, Any]] = None,
    user: Optional[str] = None
) -> None:
    """
    Log a security-related event.
    
    Args:
        logger: Logger instance
        event_type: Type of security event
        details: Event details
        user: Associated user
    """
    message_parts = [f"SECURITY EVENT: {event_type}"]
    
    if user:
        message_parts.append(f"User: {user}")
    
    if details:
        # Redact sensitive information
        safe_details = {
            k: "***REDACTED***" if "password" in k.lower() or "secret" in k.lower() else v
            for k, v in details.items()
        }
        message_parts.append(f"Details: {safe_details}")
    
    message_parts.append(f"Timestamp: {datetime.utcnow().isoformat()}")
    
    logger.warning(" | ".join(message_parts))


__all__ = [
    "setup_logger",
    "log_exception",
    "log_info",
    "log_warning",
    "log_error",
    "log_debug",
    "log_security_event"
]
