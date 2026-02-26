"""
Tests for monitoring setup and singleton behavior.
"""

import pytest
from unittest.mock import patch, MagicMock
import importlib


def test_monitoring_singleton():
    """Test that get_monitoring_instance() returns the same instance."""
    # Need to reimport and reset the singleton for clean test
    import utils.monitoring_setup as ms
    importlib.reload(ms)  # Reset the module state
    
    # Mock the Monitoring class and config to avoid file system issues
    with patch.object(ms, 'get_monitoring') as mock_get:
        mock_instance = MagicMock()
        mock_get.return_value = mock_instance
        
        m1 = ms.get_monitoring_instance()
        m2 = ms.get_monitoring_instance()
        
        assert m1 is m2, "get_monitoring_instance should return the same instance (singleton pattern)"
        # Should only call get_monitoring once due to singleton caching
        assert mock_get.call_count == 1


def test_monitoring_initialization():
    """Test that monitoring instance is properly initialized."""
    # Mock the Monitoring class at its source location
    with patch('monitoring.monitoring.Monitoring') as MockMonitoring:
        mock_instance = MagicMock()
        mock_instance.log = MagicMock()
        mock_instance.track = MagicMock()
        MockMonitoring.return_value = mock_instance
        
        # Reimport to get fresh instance with mocked class
        import utils.monitoring_setup as ms
        importlib.reload(ms)
        
        monitoring = ms.get_monitoring()
        
        assert hasattr(monitoring, 'log'), "Monitoring instance should have log method"
        assert hasattr(monitoring, 'track'), "Monitoring instance should have track method" 