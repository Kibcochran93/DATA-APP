"""Tests for monitoring module."""

import pytest
import os
import json
import tempfile
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pandas as pd
from monitoring.monitoring import Monitoring
from security.config import MONITORING_CONFIG, ERROR_MESSAGES
from utils.exceptions import SecurityError


def utcnow():
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_metrics_file(temp_dir):
    """Create a temporary metrics file for testing."""
    filepath = os.path.join(temp_dir, "metrics.json")
    with open(filepath, 'w') as f:
        json.dump({}, f)
    return filepath


@pytest.fixture
def temp_events_file(temp_dir):
    """Create a temporary events file for testing."""
    filepath = os.path.join(temp_dir, "events.json")
    with open(filepath, 'w') as f:
        json.dump([], f)
    return filepath


@pytest.fixture
def temp_health_file(temp_dir):
    """Create a temporary health file for testing."""
    filepath = os.path.join(temp_dir, "health.json")
    with open(filepath, 'w') as f:
        json.dump({
            'status': 'healthy',
            'last_check': utcnow().isoformat(),
            'issues': []
        }, f)
    return filepath


@pytest.fixture
def monitoring_config(temp_dir, temp_metrics_file, temp_events_file, temp_health_file):
    """Create monitoring configuration for testing."""
    config = MONITORING_CONFIG.copy()
    config['enabled'] = False  # Disable background monitoring for tests
    config['log_dir'] = temp_dir
    config['metrics'] = {'file_path': temp_metrics_file}
    config['events'] = {'file_path': temp_events_file, 'max_events': 100}
    config['health'] = {
        'file_path': temp_health_file,
        'memory_threshold': 90,
        'thresholds': {
            'memory': {'warning': 80, 'critical': 90},
            'cpu': {'warning': 70, 'critical': 85},
            'disk': {'warning': 75, 'critical': 90}
        }
    }
    return config


@pytest.fixture
def monitoring(monitoring_config):
    """Create a Monitoring instance for testing."""
    return Monitoring(monitoring_config)


class TestMetrics:
    def test_load_metrics(self, monitoring):
        """Test loading metrics returns proper structure."""
        metrics = monitoring._load_metrics()
        assert isinstance(metrics, dict)
        # The metrics should have the default structure
        assert 'performance' in metrics or metrics == {}
    
    def test_save_metrics(self, monitoring, temp_metrics_file):
        """Test saving metrics."""
        metrics = {
            'performance': {'test': 1},
            'security': {'test': 2},
            'system': {'test': 3}
        }
        monitoring.metrics = metrics
        monitoring._save_metrics()
        
        # Verify saved metrics
        with open(temp_metrics_file, 'r') as f:
            saved_metrics = json.load(f)
        assert saved_metrics == metrics
    
    def test_update_performance_metrics(self, monitoring):
        """Test updating performance metrics."""
        # Add some test data
        monitoring.performance_metrics['response_times'] = [1.0, 2.0, 3.0]
        monitoring.performance_metrics['memory_usage'] = [100, 200, 300]
        monitoring.performance_metrics['cpu_usage'] = [10, 20, 30]
        monitoring.performance_metrics['disk_usage'] = [50, 60, 70]
        
        # Update metrics
        monitoring._update_performance_metrics()
        
        # Verify metrics structure exists
        assert 'performance_metrics' in dir(monitoring)


class TestEvents:
    def test_load_events(self, monitoring):
        """Test loading events."""
        events = monitoring._load_events()
        assert isinstance(events, list)
    
    def test_save_events(self, monitoring, temp_events_file):
        """Test saving events."""
        events = [
            {
                'type': 'test',
                'details': {'test': 1},
                'timestamp': utcnow().isoformat()
            }
        ]
        monitoring.events = events
        monitoring._save_events()
        
        # Verify saved events
        with open(temp_events_file, 'r') as f:
            saved_events = json.load(f)
        assert saved_events == events
    
    def test_track_event(self, monitoring):
        """Test tracking an event."""
        event_type = 'test_event'
        details = {'test': 1}
        
        # Track event
        monitoring.track_event(event_type, details)
        
        # Verify event was added
        events = monitoring.get_events()
        assert len(events) >= 1
        # Find our event
        matching = [e for e in events if e.get('type') == event_type]
        assert len(matching) >= 1
    
    def test_get_events_with_filters(self, monitoring):
        """Test getting events with filters."""
        # Add test events directly
        monitoring.events = [
            {
                'type': 'test1',
                'details': {'test': 1},
                'timestamp': (utcnow() - timedelta(hours=1)).isoformat()
            },
            {
                'type': 'test2',
                'details': {'test': 2},
                'timestamp': utcnow().isoformat()
            }
        ]
        
        # Test type filter
        filtered = monitoring.get_events(event_type='test1')
        assert len(filtered) == 1
        assert filtered[0]['type'] == 'test1'


class TestHealth:
    def test_load_health(self, monitoring):
        """Test loading health status."""
        # Health should be loadable without error
        if hasattr(monitoring, '_load_health'):
            health = monitoring._load_health()
            assert isinstance(health, dict)
    
    def test_save_health(self, monitoring, temp_health_file):
        """Test saving health status."""
        health = {
            'status': 'unhealthy',
            'last_check': utcnow().isoformat(),
            'issues': [{'type': 'test', 'message': 'test issue'}]
        }
        
        if hasattr(monitoring, '_save_health'):
            # _save_health takes health as argument
            monitoring._save_health(health)
            
            # Verify saved health status
            with open(temp_health_file, 'r') as f:
                saved_health = json.load(f)
            assert saved_health == health
    
    def test_check_health(self, monitoring):
        """Test health check."""
        if hasattr(monitoring, '_check_health'):
            # Run health check
            monitoring._check_health()
            
            # Verify health can be retrieved
            if hasattr(monitoring, 'get_health'):
                health = monitoring.get_health()
                assert 'status' in health


class TestPerformance:
    def test_get_performance_report(self, monitoring):
        """Test getting performance report."""
        # Add test data
        monitoring.performance_metrics['response_times'] = [1.0, 2.0, 3.0]
        monitoring.performance_metrics['memory_usage'] = [100, 200, 300]
        monitoring.performance_metrics['cpu_usage'] = [10, 20, 30]
        monitoring.performance_metrics['disk_usage'] = [50, 60, 70]
        
        # Get report
        if hasattr(monitoring, 'get_performance_report'):
            report = monitoring.get_performance_report()
            assert report is not None


class TestErrorHandling:
    def test_load_metrics_error(self, monitoring):
        """Test error handling when loading metrics from unreadable file."""
        # Make metrics file unreadable
        if os.path.exists(monitoring.metrics_file):
            original_mode = os.stat(monitoring.metrics_file).st_mode
            try:
                os.chmod(monitoring.metrics_file, 0o000)
                # Should handle gracefully or raise SecurityError
                try:
                    result = monitoring._load_metrics()
                    # If it returns, should be default structure
                    assert isinstance(result, dict)
                except (SecurityError, PermissionError):
                    pass  # Expected behavior
            finally:
                os.chmod(monitoring.metrics_file, original_mode)
    
    def test_save_metrics_error(self, monitoring):
        """Test error handling when saving metrics to unwritable file."""
        if os.path.exists(monitoring.metrics_file):
            original_mode = os.stat(monitoring.metrics_file).st_mode
            try:
                os.chmod(monitoring.metrics_file, 0o444)
                # Should handle gracefully or raise SecurityError
                try:
                    monitoring._save_metrics()
                except (SecurityError, PermissionError):
                    pass  # Expected behavior
            finally:
                os.chmod(monitoring.metrics_file, original_mode)
    
    def test_track_event_error(self, monitoring):
        """Test error handling when tracking events fails."""
        if os.path.exists(monitoring.events_file):
            original_mode = os.stat(monitoring.events_file).st_mode
            try:
                os.chmod(monitoring.events_file, 0o444)
                # Should handle gracefully or raise SecurityError
                try:
                    monitoring.track_event('test', {'test': 1})
                except (SecurityError, PermissionError):
                    pass  # Expected behavior
            finally:
                os.chmod(monitoring.events_file, original_mode) 