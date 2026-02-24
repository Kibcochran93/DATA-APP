"""
Tests for monitoring setup and singleton behavior.
"""

import pytest
from autho import get_monitoring

def test_monitoring_singleton():
    """Test that get_monitoring() returns the same instance."""
    m1 = get_monitoring()
    m2 = get_monitoring()
    assert m1 is m2, "Monitoring should return the same instance (singleton pattern)"

def test_monitoring_initialization():
    """Test that monitoring instance is properly initialized."""
    monitoring = get_monitoring()
    assert hasattr(monitoring, 'log'), "Monitoring instance should have log method"
    assert hasattr(monitoring, 'track'), "Monitoring instance should have track method" 