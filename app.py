# Standard library imports
# Note: This project uses files from:
#   - security/: Authentication, monitoring, and data protection
#   - utils/: Error handling, data cleaning, and validation 
#   - tests/: Unit and integration tests
import os
import sys
import warnings
import time
from pathlib import Path
from typing import TYPE_CHECKING

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Third-party imports
try:
    import streamlit as st
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go
    import redis
except ImportError as e:
    raise ImportError(f"Required dependencies not installed: {str(e)}")

# Local imports
from utils.import_validator import validate_project_imports
from utils.error_handler import SecurityError
from utils.exceptions import (
    ValidationError,
    DataError,
    AuthenticationError,
    AuthorizationError
)
from core import get_data_cleaner
from config.config import SESSION_KEYS
from wizard_controller import run_wizard
from security.config import (
    InputValidator,
    FILE_CONFIG,
    DATA_CONFIG,
    PROTECTION_CONFIG,
    AUTH_CONFIG,
    MONITORING_CONFIG
)
from protection.data_protection import DataProtection
from autho.auth import Authentication
from monitoring.monitoring import Monitoring
from ui_components import (
    render_header,
    render_validation_summary,
    render_data_editor,
    render_autofix_options,
    render_export_options,
    render_export_history,
    render_login,
    render_register,
    render_user_management,
    render_monitoring_dashboard,
    file_uploader,
    export_dataframe
)
from controller.upload_controller import handle_file_upload
from controller.monitoring_controller import handle_monitoring
from controller.export_controller import handle_export
from controller.settings_controller import handle_settings
from utils.debug_logger import setup_logger, log_exception
from utils.session_manager import store_dataframe, store_validation_results, clear_session_state

# Validate all imports and dependencies
validate_project_imports()

# Suppress specific warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=DeprecationWarning)
    warnings.simplefilter("ignore", category=FutureWarning)

# Initialize logger
logger = setup_logger()

# Add global exception handler
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception

def initialize_session_state() -> None:
    """
    Initialize session state variables.
    
    Raises:
        ValidationError: If initialization fails
    """
    try:
        # Initialize basic session state keys first
        if 'df' not in st.session_state:
            st.session_state.df = None
        if 'validation_results' not in st.session_state:
            st.session_state.validation_results = None
        if 'user' not in st.session_state:
            st.session_state.user = None
        if 'token' not in st.session_state:
            st.session_state.token = None
            
        # Initialize all session state keys from config
        for key in SESSION_KEYS.values():
            if key not in st.session_state:
                st.session_state[key] = None
                
        # Initialize services after basic state
        if 'protection' not in st.session_state:
            st.session_state.protection = DataProtection(PROTECTION_CONFIG)
        if 'monitoring' not in st.session_state:
            st.session_state.monitoring = Monitoring(MONITORING_CONFIG)
            
        # Initialize auth last since it depends on other services
        if 'auth' not in st.session_state:
            try:
                st.session_state.auth = Authentication(AUTH_CONFIG)
            except Exception as e:
                logger.error(f"Failed to initialize auth: {str(e)}")
                st.session_state.auth = None
                
    except Exception as e:
        error = ValidationError(
            "Failed to initialize session state",
            error_code="SESSION_INIT_ERROR",
            details={"error": str(e)},
            original_error=e
        )
        log_exception(error, logger, {"action": "initialize_session_state"})
        raise error

def check_auth():
    """
    Check if user is authenticated.
    
    Returns:
        bool: True if user is authenticated, False otherwise
        
    Raises:
        AuthenticationError: If authentication check fails
    """
    if st.session_state.token is None:
        return False
    
    try:
        user_info = st.session_state.auth.verify_token(st.session_state.token)
        st.session_state.user = user_info
        return True
    except SecurityError as e:
        st.session_state.token = None
        st.session_state.user = None
        error = AuthenticationError(
            "Authentication check failed",
            error_code="AUTH_CHECK_ERROR",
            details={"error": str(e)},
            original_error=e
        )
        log_exception(error, logger, {"action": "check_auth"})
        return False

def wait_for_redis(max_retries=5, retry_interval=5):
    """Wait for Redis to be available."""
    redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
    for i in range(max_retries):
        try:
            r = redis.from_url(redis_url)
            r.ping()
            return True
        except redis.ConnectionError:
            if i < max_retries - 1:
                logger.warning(f"Redis connection attempt {i+1} failed. Retrying in {retry_interval} seconds...")
                time.sleep(retry_interval)
            else:
                logger.error("Failed to connect to Redis after maximum retries")
                return False

def main() -> None:
    """Main application entry point."""
    try:
        # Initialize session state
        initialize_session_state()
        
        # Check authentication
        if not check_auth():
            render_login()
            return
        
        # Main application logic
        st.title("Seats Data Analysis")
        
        # Get current page from query params or default to Data Upload
        current_page = st.query_params.get("page", "Data Upload")
        
        # Sidebar navigation
        page = st.sidebar.selectbox(
            "Navigation",
            ["Data Upload", "Data Analysis", "Settings", "Register"],
            index=["Data Upload", "Data Analysis", "Settings", "Register"].index(current_page) if current_page in ["Data Upload", "Data Analysis", "Settings", "Register"] else 0
        )
        
        # Update active page in query params if changed
        if page != current_page:
            st.query_params["page"] = page
        
        if page == "Data Upload":
            render_data_upload()
        elif page == "Data Analysis":
            render_data_analysis()
        elif page == "Settings":
            render_settings()
        elif page == "Register":
            render_register()
            
    except Exception as e:
        log_exception(e, logger, context={"action": "main"})
        st.error("An error occurred. Please try again.")
        st.rerun()

if __name__ == "__main__":
    main()