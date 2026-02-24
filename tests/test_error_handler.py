import pytest
import os
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
        
        assert error.message == "Validation failed"
        assert error.error_code == "VALIDATION_ERROR"
        assert error.details == {"field": "test"}
    
    def test_security_error(self):
        """Test SecurityError creation."""
        error = SecurityError(
            message="Security breach",
            details={"type": "test"}
        )
        
        assert error.message == "Security breach"
        assert error.error_code == "SECURITY_ERROR"
        assert error.details == {"type": "test"}
    
    def test_data_error(self):
        """Test DataError creation."""
        error = DataError(
            message="Data processing failed",
            details={"operation": "test"}
        )
        
        assert error.message == "Data processing failed"
        assert error.error_code == "DATA_ERROR"
        assert error.details == {"operation": "test"}
    
    def test_authentication_error(self):
        """Test AuthenticationError creation."""
        error = AuthenticationError(
            message="Authentication failed",
            details={"user": "test"}
        )
        
        assert error.message == "Authentication failed"
        assert error.error_code == "AUTHENTICATION_ERROR"
        assert error.details == {"user": "test"}
    
    def test_authorization_error(self):
        """Test AuthorizationError creation."""
        error = AuthorizationError(
            message="Authorization failed",
            details={"permission": "test"}
        )
        
        assert error.message == "Authorization failed"
        assert error.error_code == "AUTHORIZATION_ERROR"
        assert error.details == {"permission": "test"}
    
    def test_error_to_dict(self):
        """Test error to_dict method."""
        error = ValidationError(
            message="Test error",
            error_code="TEST_ERROR",
            details={"test": "value"}
        )
        
        error_dict = error.to_dict()
        assert error_dict["error_code"] == "TEST_ERROR"
        assert error_dict["message"] == "Test error"
        assert error_dict["details"] == {"test": "value"}
        assert "timestamp" in error_dict
        assert "stack_trace" in error_dict

class TestErrorLogging:
    def test_log_exception(self, logger, caplog):
        """Test error logging."""
        error = ValidationError("Test error")
        with caplog.at_level(logging.ERROR):
            log_exception(error, logger)
        
        # Logger should have been called
        assert len(caplog.records) > 0
        assert caplog.records[0].levelno == logging.ERROR
    
    def test_log_exception_with_context(self, logger, caplog):
        """Test error logging with context."""
        error = ValidationError("Test error")
        context = {"user": "test", "action": "validate"}
        with caplog.at_level(logging.ERROR):
            log_exception(error, logger, context=context)
        
        # Logger should have been called
        assert len(caplog.records) > 0
    
    def test_log_exception_different_level(self, logger, caplog):
        """Test error logging records at ERROR level."""
        error = ValidationError("Test error")
        with caplog.at_level(logging.ERROR):
            log_exception(error, logger)
        
        assert len(caplog.records) > 0
        # log_exception uses ERROR level by default
        assert caplog.records[0].levelno == logging.ERROR

class TestErrorTracking:
    def test_track_error_with_dict(self):
        """Test error tracking accepts dict."""
        from utils.error_handler import track_error
        
        error_info = {
            "type": "ValidationError",
            "message": "Test error",
            "error_code": "VALIDATION_ERROR"
        }
        
        # Should not raise - tracking may fail silently without streamlit
        track_error(error_info)
    
    def test_track_error_empty_dict(self):
        """Test error tracking with empty dict."""
        from utils.error_handler import track_error
        
        # Should not raise
        track_error({})
    
    def test_track_error_with_details(self):
        """Test error tracking with detailed info."""
        from utils.error_handler import track_error
        
        error_info = {
            "type": "SecurityError",
            "message": "Security breach",
            "error_code": "SECURITY_ERROR",
            "details": {"ip": "127.0.0.1"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Should not raise
        track_error(error_info)
