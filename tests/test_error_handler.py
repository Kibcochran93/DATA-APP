import pytest
import logging
import json
from datetime import datetime
from pathlib import Path
from utils.exceptions import (
    ValidationError,
    SecurityError,
    DataError,
    AuthenticationError,
    AuthorizationError
)
from utils.debug_logger import setup_logger, log_exception

@pytest.fixture
def logger():
    """Create a test logger."""
    return setup_logger()

@pytest.fixture
def error_file(tmp_path):
    """Create a temporary error tracking file."""
    return tmp_path / "error_tracking.json"

class TestExceptions:
    def test_validation_error(self):
        """Test ValidationError creation."""
        error = ValidationError(
            message="Validation failed",
            details={"field": "test"}
        )
        
        assert str(error) == "Validation failed"
        assert error.error_code == "VALIDATION_ERROR"
        assert error.details == {"field": "test"}
    
    def test_security_error(self):
        """Test SecurityError creation."""
        error = SecurityError(
            message="Security breach",
            details={"type": "test"}
        )
        
        assert str(error) == "Security breach"
        assert error.error_code == "SECURITY_ERROR"
        assert error.details == {"type": "test"}
    
    def test_data_error(self):
        """Test DataError creation."""
        error = DataError(
            message="Data processing failed",
            details={"operation": "test"}
        )
        
        assert str(error) == "Data processing failed"
        assert error.error_code == "DATA_ERROR"
        assert error.details == {"operation": "test"}
    
    def test_authentication_error(self):
        """Test AuthenticationError creation."""
        error = AuthenticationError(
            message="Authentication failed",
            details={"user": "test"}
        )
        
        assert str(error) == "Authentication failed"
        assert error.error_code == "AUTHENTICATION_ERROR"
        assert error.details == {"user": "test"}
    
    def test_authorization_error(self):
        """Test AuthorizationError creation."""
        error = AuthorizationError(
            message="Authorization failed",
            details={"permission": "test"}
        )
        
        assert str(error) == "Authorization failed"
        assert error.error_code == "AUTHORIZATION_ERROR"
        assert error.details == {"permission": "test"}

class TestErrorLogging:
    def test_log_exception(self, logger, caplog):
        """Test error logging."""
        error = ValidationError("Test error")
        log_exception(error, logger)
        
        assert len(caplog.records) > 0
        assert "Test error" in caplog.text
        assert "VALIDATION_ERROR" in caplog.text
    
    def test_log_exception_with_context(self, logger, caplog):
        """Test error logging with context."""
        error = ValidationError("Test error")
        context = {"user": "test", "action": "validate"}
        log_exception(error, logger, context=context)
        
        assert len(caplog.records) > 0
        assert "Test error" in caplog.text
        assert "user" in caplog.text
        assert "action" in caplog.text
    
    def test_log_exception_different_level(self, logger, caplog):
        """Test error logging with different levels."""
        error = ValidationError("Test error")
        log_exception(error, logger, level=logging.WARNING)
        
        assert len(caplog.records) > 0
        assert caplog.records[0].levelno == logging.WARNING

class TestErrorTracking:
    def test_track_error(self, logger, error_file):
        """Test error tracking."""
        error = ValidationError("Test error")
        track_error(error, logger, error_file)
        
        assert error_file.exists()
        with open(error_file) as f:
            errors = json.load(f)
        
        assert len(errors) == 1
        assert errors[0]["type"] == "ValidationError"
        assert errors[0]["message"] == "Test error"
        assert errors[0]["error_code"] == "VALIDATION_ERROR"
    
    def test_track_error_unexpected(self, logger, error_file):
        """Test tracking unexpected errors."""
        error = ValueError("Unexpected error")
        track_error(error, logger, error_file)
        
        assert error_file.exists()
        with open(error_file) as f:
            errors = json.load(f)
        
        assert len(errors) == 1
        assert errors[0]["type"] == "ValueError"
        assert errors[0]["message"] == "Unexpected error"
        assert "traceback" in errors[0]
    
    def test_track_error_multiple(self, logger, error_file):
        """Test tracking multiple errors."""
        errors = [
            ValidationError("Error 1"),
            SecurityError("Error 2"),
            DataError("Error 3")
        ]
        
        for error in errors:
            track_error(error, logger, error_file)
        
        assert error_file.exists()
        with open(error_file) as f:
            tracked_errors = json.load(f)
        
        assert len(tracked_errors) == 3
        assert tracked_errors[0]["message"] == "Error 1"
        assert tracked_errors[1]["message"] == "Error 2"
        assert tracked_errors[2]["message"] == "Error 3"
    
    def test_track_error_file_error(self, logger, error_file):
        """Test error handling when tracking fails."""
        # Make file unwritable
        error_file.parent.mkdir(parents=True, exist_ok=True)
        error_file.touch()
        error_file.chmod(0o444)
        
        error = ValidationError("Test error")
        track_error(error, logger, error_file)
        
        # Should not raise exception, but log error
        assert len(logger.handlers) > 0 