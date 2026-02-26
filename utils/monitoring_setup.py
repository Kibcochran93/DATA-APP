def get_monitoring():
    """Get the monitoring instance using lazy import to avoid circular dependencies."""
    from monitoring.monitoring import Monitoring
    from security.config import MONITORING_CONFIG
    return Monitoring(MONITORING_CONFIG)

# Initialize monitoring instance lazily
_monitoring_instance = None

def get_monitoring_instance():
    """Get or create the monitoring instance."""
    global _monitoring_instance
    if _monitoring_instance is None:
        _monitoring_instance = get_monitoring()
    return _monitoring_instance 