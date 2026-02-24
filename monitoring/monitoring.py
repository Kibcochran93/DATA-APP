"""
Monitoring module for the SEATS application.

Provides system monitoring, metrics collection, and health checks.
"""

import os
import json
import time
import threading
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import psutil

from utils.debug_logger import setup_logger, log_exception
from utils.exceptions import SecurityError

logger = setup_logger(__name__)


class Monitoring:
    """
    System monitoring and metrics collection.
    
    Tracks performance metrics, security events, and system health.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize monitoring with configuration.
        
        Args:
            config: Monitoring configuration dictionary
        """
        self.config = config
        self.enabled = config.get("enabled", True)
        
        # File paths
        self.log_dir = Path(config.get("log_dir", "logs"))
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.metrics_file = Path(config.get("metrics", {}).get(
            "file_path",
            str(self.log_dir / "metrics.json")
        ))
        
        self.events_file = Path(config.get("events", {}).get(
            "file_path",
            str(self.log_dir / "events.json")
        ))
        
        self.health_file = Path(config.get("health", {}).get(
            "file_path",
            str(self.log_dir / "health.json")
        ))
        
        # Thresholds
        self.thresholds = config.get("health", {}).get("thresholds", {
            "memory": {"warning": 80, "critical": 90},
            "cpu": {"warning": 70, "critical": 85},
            "disk": {"warning": 75, "critical": 90}
        })
        
        # Performance tracking
        self.performance_metrics = {
            "response_times": [],
            "memory_usage": [],
            "cpu_usage": [],
            "disk_usage": []
        }
        
        # Initialize storage
        self.metrics = self._load_metrics()
        self.events = self._load_events()
        
        # Start background monitoring
        self._monitoring_thread = None
        self._stop_monitoring = threading.Event()
        
        if self.enabled:
            self._start_background_monitoring()
    
    def _load_metrics(self) -> Dict[str, Any]:
        """Load metrics from file."""
        try:
            if self.metrics_file.exists():
                with open(self.metrics_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load metrics: {e}")
        
        return {
            "performance": {},
            "security": {},
            "system": {}
        }
    
    def _save_metrics(self) -> None:
        """Save metrics to file."""
        try:
            self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.metrics_file, "w") as f:
                json.dump(self.metrics, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
    
    def _load_events(self) -> List[Dict[str, Any]]:
        """Load events from file."""
        try:
            if self.events_file.exists():
                with open(self.events_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load events: {e}")
        
        return []
    
    def _save_events(self) -> None:
        """Save events to file."""
        try:
            self.events_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Limit events to max count
            max_events = self.config.get("events", {}).get("max_events", 10000)
            if len(self.events) > max_events:
                self.events = self.events[-max_events:]
            
            with open(self.events_file, "w") as f:
                json.dump(self.events, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save events: {e}")
    
    def _start_background_monitoring(self) -> None:
        """Start background monitoring thread."""
        if self._monitoring_thread is not None:
            return
        
        def monitor_loop():
            check_interval = self.config.get("performance", {}).get("check_interval", 30)
            
            while not self._stop_monitoring.is_set():
                try:
                    self._update_performance_metrics()
                    self._check_health()
                except Exception as e:
                    logger.error(f"Monitoring error: {e}")
                
                self._stop_monitoring.wait(check_interval)
        
        self._monitoring_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitoring_thread.start()
    
    def _update_performance_metrics(self) -> None:
        """Update performance metrics."""
        try:
            # Memory usage
            memory = psutil.virtual_memory()
            self.performance_metrics["memory_usage"].append(memory.percent)
            
            # CPU usage
            cpu = psutil.cpu_percent(interval=1)
            self.performance_metrics["cpu_usage"].append(cpu)
            
            # Disk usage
            disk = psutil.disk_usage("/")
            self.performance_metrics["disk_usage"].append(disk.percent)
            
            # Limit stored samples
            max_samples = self.config.get("performance", {}).get("max_samples", 1000)
            for key in self.performance_metrics:
                if len(self.performance_metrics[key]) > max_samples:
                    self.performance_metrics[key] = self.performance_metrics[key][-max_samples:]
            
            # Update aggregated metrics
            self.metrics["performance"] = {
                "memory_usage": memory.percent,
                "cpu_usage": cpu,
                "disk_usage": disk.percent,
                "response_time": self._calculate_avg_response_time(),
                "last_updated": datetime.utcnow().isoformat()
            }
            
            self._save_metrics()
            
        except Exception as e:
            logger.error(f"Failed to update performance metrics: {e}")
    
    def _calculate_avg_response_time(self) -> float:
        """Calculate average response time."""
        times = self.performance_metrics.get("response_times", [])
        if times:
            return sum(times) / len(times)
        return 0.0
    
    def _check_health(self) -> Dict[str, Any]:
        """Check system health against thresholds."""
        health = {
            "status": "healthy",
            "issues": [],
            "last_check": datetime.utcnow().isoformat()
        }
        
        try:
            # Check memory
            memory = psutil.virtual_memory().percent
            mem_thresholds = self.thresholds.get("memory", {})
            if memory >= mem_thresholds.get("critical", 90):
                health["status"] = "critical"
                health["issues"].append(f"Memory usage critical: {memory}%")
            elif memory >= mem_thresholds.get("warning", 80):
                if health["status"] == "healthy":
                    health["status"] = "warning"
                health["issues"].append(f"Memory usage high: {memory}%")
            
            # Check CPU
            cpu = psutil.cpu_percent()
            cpu_thresholds = self.thresholds.get("cpu", {})
            if cpu >= cpu_thresholds.get("critical", 85):
                health["status"] = "critical"
                health["issues"].append(f"CPU usage critical: {cpu}%")
            elif cpu >= cpu_thresholds.get("warning", 70):
                if health["status"] == "healthy":
                    health["status"] = "warning"
                health["issues"].append(f"CPU usage high: {cpu}%")
            
            # Check disk
            disk = psutil.disk_usage("/").percent
            disk_thresholds = self.thresholds.get("disk", {})
            if disk >= disk_thresholds.get("critical", 90):
                health["status"] = "critical"
                health["issues"].append(f"Disk usage critical: {disk}%")
            elif disk >= disk_thresholds.get("warning", 75):
                if health["status"] == "healthy":
                    health["status"] = "warning"
                health["issues"].append(f"Disk usage high: {disk}%")
            
            # Save health status
            self._save_health(health)
            
        except Exception as e:
            health["status"] = "error"
            health["issues"].append(f"Health check failed: {str(e)}")
        
        return health
    
    def _save_health(self, health: Dict[str, Any]) -> None:
        """Save health status to file."""
        try:
            self.health_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.health_file, "w") as f:
                json.dump(health, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save health status: {e}")
    
    def track_event(
        self,
        event_type: str,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "info"
    ) -> None:
        """
        Track an event.
        
        Args:
            event_type: Type of event
            details: Event details
            severity: Event severity (info, warning, error, critical)
        """
        event = {
            "type": event_type,
            "details": details or {},
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.events.append(event)
        self._save_events()
        
        # Log based on severity
        if severity == "critical":
            logger.critical(f"Event: {event_type} - {details}")
        elif severity == "error":
            logger.error(f"Event: {event_type} - {details}")
        elif severity == "warning":
            logger.warning(f"Event: {event_type} - {details}")
        else:
            logger.info(f"Event: {event_type} - {details}")
    
    def track_security_event(
        self,
        event_type: str,
        user: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track a security event.
        
        Args:
            event_type: Type of security event
            user: Associated user
            details: Event details
        """
        security_details = details or {}
        if user:
            security_details["user"] = user
        
        self.track_event(
            event_type=f"security.{event_type}",
            details=security_details,
            severity="warning"
        )
        
        # Update security metrics
        security_metrics = self.metrics.get("security", {})
        event_count = security_metrics.get(event_type, 0)
        security_metrics[event_type] = event_count + 1
        security_metrics["last_event"] = datetime.utcnow().isoformat()
        self.metrics["security"] = security_metrics
        self._save_metrics()
    
    def record_response_time(self, response_time: float) -> None:
        """
        Record a response time measurement.
        
        Args:
            response_time: Response time in seconds
        """
        self.performance_metrics["response_times"].append(response_time)
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics.
        
        Returns:
            Dictionary containing all metrics
        """
        # Get fresh system metrics
        try:
            return {
                "memory_usage": psutil.virtual_memory().percent,
                "cpu_usage": psutil.cpu_percent(),
                "disk_usage": psutil.disk_usage("/").percent,
                "active_sessions": 0,  # Would need session tracking
                "requests_per_minute": 0,  # Would need request tracking
                **self.metrics.get("performance", {})
            }
        except Exception:
            return self.metrics.get("performance", {})
    
    def get_events(
        self,
        event_type: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get events with optional filtering.
        
        Args:
            event_type: Filter by event type
            since: Filter events since datetime
            limit: Maximum events to return
            
        Returns:
            List of events
        """
        events = self.events.copy()
        
        if event_type:
            events = [e for e in events if e.get("type") == event_type]
        
        if since:
            since_iso = since.isoformat()
            events = [e for e in events if e.get("timestamp", "") >= since_iso]
        
        return events[-limit:]
    
    def get_health(self) -> Dict[str, Any]:
        """
        Get current health status.
        
        Returns:
            Health status dictionary
        """
        return self._check_health()
    
    def stop(self) -> None:
        """Stop monitoring."""
        self._stop_monitoring.set()
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)


__all__ = ["Monitoring"]
