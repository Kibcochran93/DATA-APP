"""
Settings controller for the SEATS application.

Handles application settings and user management.
"""

import streamlit as st
from typing import Optional, Dict, Any
import logging

from utils.debug_logger import setup_logger, log_exception
from ui_components import render_user_management

logger = setup_logger(__name__)


def handle_settings() -> None:
    """
    Handle settings page display.
    
    Admin users see user management.
    Regular users see personal settings.
    """
    user = st.session_state.get("user")
    
    if user is None:
        st.warning("Please log in to access settings.")
        return
    
    user_role = user.get("role", "user")
    
    if user_role == "admin":
        render_admin_settings()
    else:
        render_user_settings()


def render_admin_settings() -> None:
    """Render admin settings page."""
    st.markdown("### Admin Settings")
    
    tabs = st.tabs(["User Management", "System Settings", "Security"])
    
    with tabs[0]:
        render_user_management()
    
    with tabs[1]:
        render_system_settings()
    
    with tabs[2]:
        render_security_settings()


def render_user_settings() -> None:
    """Render user settings page."""
    st.markdown("### User Settings")
    
    user = st.session_state.get("user", {})
    
    st.markdown("#### Profile")
    st.text(f"Username: {user.get('username', 'Unknown')}")
    st.text(f"Role: {user.get('role', 'user')}")
    
    st.markdown("#### Change Password")
    
    with st.form("change_password_form"):
        current_password = st.text_input("Current Password", type="password")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm New Password", type="password")
        
        if st.form_submit_button("Update Password"):
            if not all([current_password, new_password, confirm_password]):
                st.error("Please fill in all fields.")
            elif new_password != confirm_password:
                st.error("New passwords do not match.")
            elif len(new_password) < 8:
                st.error("Password must be at least 8 characters.")
            else:
                try:
                    auth = st.session_state.get("auth")
                    if auth:
                        auth.change_password(
                            user.get("username"),
                            current_password,
                            new_password
                        )
                        st.success("Password updated successfully.")
                except Exception as e:
                    st.error(f"Failed to update password: {str(e)}")


def render_system_settings() -> None:
    """Render system settings section."""
    st.markdown("#### System Configuration")
    
    from config.config import get_config
    config = get_config()
    
    st.json(config)
    
    st.markdown("#### Update Settings")
    st.info("System settings can be modified through environment variables or the .env file.")


def render_security_settings() -> None:
    """Render security settings section."""
    st.markdown("#### Security Configuration")
    
    st.markdown("**Current Settings:**")
    st.text("- JWT Token Expiry: 3600 seconds")
    st.text("- Max File Size: 10 MB")
    st.text("- Allowed Extensions: .csv, .xlsx, .xls, .json")
    
    st.markdown("#### Security Events")
    
    monitoring = st.session_state.get("monitoring")
    if monitoring:
        events = monitoring.get_events(event_type="security")
        if events:
            for event in events[-10:]:
                st.text(f"{event.get('timestamp', '')} - {event.get('details', {})}")
        else:
            st.info("No security events recorded.")


def render_settings_page() -> None:
    """Render the settings page."""
    st.markdown("### Settings")
    handle_settings()


__all__ = [
    "handle_settings",
    "render_admin_settings",
    "render_user_settings",
    "render_settings_page"
]
