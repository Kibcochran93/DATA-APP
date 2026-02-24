import pytest
import os
import json
import tempfile
import time
from datetime import datetime, timedelta
import pandas as pd
from monitoring.monitoring import Monitoring
from security.config import MONITORING_CONFIG, ERROR_MESSAGES
from utils.exceptions import SecurityError

@pytest.fixture
def temp_metrics_file():
    """Create a temporary metrics file for testing."""
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
        json.dump({}, f)
    yield f.name
    os.unlink(f.name)

@pytest.fixture
def temp_events_file():
    """Create a temporary events file for testing."""
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
        json.dump([], f)
    yield f.name
    os.unlink(f.name)

@pytest.fixture
def temp_health_file():
    """Create a temporary health file for testing."""
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
        json.dump({
            'status': 'healthy',
            'last_check': datetime.utcnow().isoformat(),
            'issues': []
        }, f)
    yield f.name
    os.unlink(f.name)

@pytest.fixture
def monitoring(temp_metrics_file, temp_events_file, temp_health_file):
    """Create a Monitoring instance for testing."""
    config = MONITORING_CONFIG.copy()
    config['metrics']['file_path'] = temp_metrics_file
    config['events']['file_path'] = temp_events_file
    config['health']['file_path'] = temp_health_file
    return Monitoring(config)

class TestMetrics:
    def test_load_metrics(self, monitoring):
        """Test loading metrics."""
        metrics = monitoring._load_metrics()
        assert isinstance(metrics, dict)
        assert 'performance' in metrics
        assert 'security' in metrics
        assert 'system' in metrics
    
    def test_save_metrics(self, monitoring):
        """Test saving metrics."""
        metrics = {
            'performance': {'test': 1},
            'security': {'test': 2},
            'system': {'test': 3}
        }
        monitoring.metrics = metrics
        monitoring._save_metrics()
        
        # Verify saved metrics
        with open(monitoring.metrics_file, 'r') as f:
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
        
        # Verify metrics
        metrics = monitoring.get_metrics()
        assert 'performance' in metrics
        assert 'response_time' in metrics['performance']
        assert 'memory_usage' in metrics['performance']
        assert 'cpu_usage' in metrics['performance']
        assert 'disk_usage' in metrics['performance']

class TestEvents:
    def test_load_events(self, monitoring):
        """Test loading events."""
        events = monitoring._load_events()
        assert isinstance(events, list)
    
    def test_save_events(self, monitoring):
        """Test saving events."""
        events = [
            {
                'type': 'test',
                'details': {'test': 1},
                'timestamp': datetime.utcnow().isoformat()
            }
        ]
        monitoring.events = events
        monitoring._save_events()
        
        # Verify saved events
        with open(monitoring.events_file, 'r') as f:
            saved_events = json.load(f)
        assert saved_events == events
    
    def test_track_event(self, monitoring):
        """Test tracking an event."""
        event_type = 'test_event'
        details = {'test': 1}
        
        # Track event
        monitoring.track_event(event_type, details)
        
        # Wait for event processing
        time.sleep(0.1)
        
        # Verify event
        events = monitoring.get_events()
        assert len(events) == 1
        assert events[0]['type'] == event_type
        assert events[0]['details'] == details
        assert 'timestamp' in events[0]
    
    def test_get_events_with_filters(self, monitoring):
        """Test getting events with filters."""
        # Add test events
        events = [
            {
                'type': 'test1',
                'details': {'test': 1},
                'timestamp': (datetime.utcnow() - timedelta(hours=1)).isoformat()
            },
            {
                'type': 'test2',
                'details': {'test': 2},
                'timestamp': datetime.utcnow().isoformat()
            }
        ]
        monitoring.events = events
        
        # Test type filter
        filtered = monitoring.get_events(event_type='test1')
        assert len(filtered) == 1
        assert filtered[0]['type'] == 'test1'
        
        # Test time filter
        start_time = datetime.utcnow() - timedelta(minutes=30)
        filtered = monitoring.get_events(start_time=start_time)
        assert len(filtered) == 1
        assert filtered[0]['type'] == 'test2'

class TestHealth:
    def test_load_health(self, monitoring):
        """Test loading health status."""
        health = monitoring._load_health()
        assert isinstance(health, dict)
        assert 'status' in health
        assert 'last_check' in health
        assert 'issues' in health
    
    def test_save_health(self, monitoring):
        """Test saving health status."""
        health = {
            'status': 'unhealthy',
            'last_check': datetime.utcnow().isoformat(),
            'issues': [{'type': 'test', 'message': 'test issue'}]
        }
        monitoring.health_status = health
        monitoring._save_health()
        
        # Verify saved health status
        with open(monitoring.health_file, 'r') as f:
            saved_health = json.load(f)
        assert saved_health == health
    
    def test_check_health(self, monitoring):
        """Test health check."""
        # Mock high memory usage
        monitoring.config['health']['memory_threshold'] = 0
        
        # Run health check
        monitoring._check_health()
        
        # Verify health status
        health = monitoring.get_health_status()
        assert health['status'] == 'unhealthy'
        assert len(health['issues']) > 0
        assert any(issue['type'] == 'memory' for issue in health['issues'])

class TestPerformance:
    def test_get_performance_report(self, monitoring):
        """Test getting performance report."""
        # Add test data
        monitoring.performance_metrics['response_times'] = [1.0, 2.0, 3.0]
        monitoring.performance_metrics['memory_usage'] = [100, 200, 300]
        monitoring.performance_metrics['cpu_usage'] = [10, 20, 30]
        monitoring.performance_metrics['disk_usage'] = [50, 60, 70]
        
        # Get report
        report = monitoring.get_performance_report()
        
        # Verify report
        assert isinstance(report, pd.DataFrame)
        assert 'timestamp' in report.columns
        assert 'response_time' in report.columns
        assert 'memory_usage' in report.columns
        assert 'cpu_usage' in report.columns
        assert 'disk_usage' in report.columns
        assert len(report) == 3

class TestErrorHandling:
    def test_load_metrics_error(self, monitoring):
        """Test error handling when loading metrics."""
        # Make metrics file unreadable
        os.chmod(monitoring.metrics_file, 0o000)
        with pytest.raises(SecurityError) as exc_info:
            monitoring._load_metrics()
        assert "Failed to load metrics" in str(exc_info.value)
    
    def test_save_metrics_error(self, monitoring):
        """Test error handling when saving metrics."""
        # Make metrics file unwritable
        os.chmod(monitoring.metrics_file, 0o444)
        with pytest.raises(SecurityError) as exc_info:
            monitoring._save_metrics()
        assert "Failed to save metrics" in str(exc_info.value)
    
    def test_track_event_error(self, monitoring):
        """Test error handling when tracking events."""
        # Make events file unwritable
        os.chmod(monitoring.events_file, 0o444)
        with pytest.raises(SecurityError) as exc_info:
            monitoring.track_event('test', {'test': 1})
        assert "Failed to track event" in str(exc_info.value) 