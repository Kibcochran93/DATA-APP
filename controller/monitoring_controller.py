"""
Monitoring controller for the SEATS application.

Handles system monitoring display and management.
"""

import streamlit as st
from typing import Optional, Dict, Any
import logging

from utils.debug_logger import setup_logger, log_exception
from ui_components import render_monitoring_dashboard

logger = setup_logger(__name__)


def handle_monitoring() -> None:
    """
    Handle monitoring dashboard display.
    
    Only accessible to admin users.
    """
    user = st.session_state.get("user")
    
    if user is None:
        st.warning("Please log in to access monitoring.")
        return
    
    user_role = user.get("role", "user")
    
    if user_role != "admin":
        st.error("Access denied. Admin privileges required.")
        return
    
    render_monitoring_dashboard()


def get_system_status() -> Dict[str, Any]:
    """
    Get current system status.
    
    Returns:
        Dictionary containing system status information
    """
    monitoring = st.session_state.get("monitoring")
    
    if monitoring is None:
        return {
            "status": "unknown",
            "message": "Monitoring not initialized"
        }
    
    try:
        health = monitoring.get_health()
        metrics = monitoring.get_metrics()
        
        return {
            "status": health.get("status", "unknown"),
            "health": health,
            "metrics": metrics
        }
        
    except Exception as e:
        log_exception(e, logger, {"action": "get_system_status"})
        return {
            "status": "error",
            "message": str(e)
        }


def render_monitoring_page() -> None:
    """Render the monitoring page."""
    st.markdown("### System Monitoring")
    handle_monitoring()


__all__ = [
    "handle_monitoring",
    "get_system_status",
    "render_monitoring_page"
]
