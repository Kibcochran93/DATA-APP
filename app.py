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
from typing import TYPE_CHECKING, Optional

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Third-party imports
try:
    import streamlit as st
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go
except ImportError as e:
    raise ImportError(f"Required dependencies not installed: {str(e)}")

# Optional Redis import - not required for Windows executable
REDIS_AVAILABLE = False
redis = None
try:
    import redis as redis_module
    redis = redis_module
    REDIS_AVAILABLE = True
except ImportError:
    pass  # Redis not available, will use fallback

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
        if 'redis_available' not in st.session_state:
            st.session_state.redis_available = REDIS_AVAILABLE
            
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


def check_auth() -> bool:
    """
    Check if user is authenticated.
    
    Returns:
        bool: True if user is authenticated, False otherwise
        
    Raises:
        AuthenticationError: If authentication check fails
    """
    if st.session_state.token is None:
        return False
    
    if st.session_state.auth is None:
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


def check_redis_connection(max_retries: int = 3, retry_interval: int = 2) -> bool:
    """
    Check if Redis is available and connected.
    
    This is optional - the application will work without Redis.
    Redis is used for caching and session management in Docker deployments.
    
    Args:
        max_retries: Maximum number of connection attempts
        retry_interval: Seconds between retries
        
    Returns:
        bool: True if Redis is connected, False otherwise
    """
    if not REDIS_AVAILABLE:
        logger.info("Redis module not installed - running without Redis support")
        return False
    
    # Check if Redis is enabled via environment
    redis_enabled = os.getenv('REDIS_ENABLED', 'false').lower() == 'true'
    if not redis_enabled:
        logger.info("Redis disabled via REDIS_ENABLED environment variable")
        return False
    
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    for i in range(max_retries):
        try:
            r = redis.from_url(redis_url)
            r.ping()
            logger.info(f"Successfully connected to Redis at {redis_url}")
            return True
        except redis.ConnectionError:
            if i < max_retries - 1:
                logger.warning(f"Redis connection attempt {i+1} failed. Retrying in {retry_interval} seconds...")
                time.sleep(retry_interval)
            else:
                logger.warning("Could not connect to Redis - continuing without Redis support")
                return False
        except Exception as e:
            logger.warning(f"Redis error: {str(e)} - continuing without Redis support")
            return False
    
    return False


def render_data_upload() -> None:
    """Render the data upload page."""
    st.header("Data Upload")
    
    uploaded_file = file_uploader(
        label="Upload your data file",
        allowed_types=["csv", "xlsx", "xls", "json"],
        key="main_file_upload"
    )
    
    if uploaded_file is not None:
        df = handle_file_upload(uploaded_file)
        if df is not None:
            st.success(f"Successfully loaded {len(df)} rows and {len(df.columns)} columns")
            
            # Show data preview
            st.subheader("Data Preview")
            st.dataframe(df.head(10))
            
            # Option to proceed to wizard
            if st.button("Proceed to Validation Wizard", type="primary"):
                st.session_state.df = df
                st.query_params["page"] = "Wizard"
                st.rerun()


def render_data_analysis() -> None:
    """Render the data analysis page."""
    st.header("Data Analysis")
    
    df = st.session_state.get("df")
    
    if df is None or (hasattr(df, 'empty') and df.empty):
        st.info("No data loaded. Please upload a file first.")
        if st.button("Go to Upload"):
            st.query_params["page"] = "Data Upload"
            st.rerun()
        return
    
    # Display validation results if available
    validation_results = st.session_state.get("validation_results")
    if validation_results:
        render_validation_summary(validation_results)
    
    # Data editor
    st.subheader("Data Editor")
    edited_df = render_data_editor(df, key="analysis_editor")
    
    if edited_df is not None and not edited_df.equals(df):
        if st.button("Save Changes"):
            st.session_state.df = edited_df
            st.success("Changes saved!")
    
    # Export options
    st.subheader("Export")
    render_export_options(df, st.session_state.get("user", {}).get("role", "user"))


def render_settings_page() -> None:
    """Render the settings page."""
    st.header("Settings")
    handle_settings()


def render_wizard_page() -> None:
    """Render the validation wizard page."""
    run_wizard()


def main() -> None:
    """Main application entry point."""
    try:
        # Initialize session state
        initialize_session_state()
        
        # Optional Redis check (non-blocking)
        if 'redis_checked' not in st.session_state:
            st.session_state.redis_connected = check_redis_connection()
            st.session_state.redis_checked = True
        
        # Check for test mode (bypass authentication for development)
        test_mode = os.getenv('TEST_MODE', 'false').lower() == 'true'
        
        # Check authentication
        if not test_mode and not check_auth():
            # Handle login
            credentials = render_login()
            if credentials:
                try:
                    if st.session_state.auth:
                        token = st.session_state.auth.authenticate(
                            credentials['username'], 
                            credentials['password']
                        )
                        st.session_state.token = token
                        st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {str(e)}")
            return
        
        # Set test user if in test mode
        if test_mode and st.session_state.user is None:
            st.session_state.user = {'username': 'test_user', 'role': 'admin'}
            st.session_state.token = 'test_token'
        
        # Main application logic
        st.title("SEATS Data Validation")
        
        # Get current page from query params or default to Data Upload
        current_page = st.query_params.get("page", "Data Upload")
        
        # Define available pages
        pages = ["Data Upload", "Wizard", "Data Analysis", "Settings", "Register"]
        
        # Sidebar navigation
        page = st.sidebar.selectbox(
            "Navigation",
            pages,
            index=pages.index(current_page) if current_page in pages else 0
        )
        
        # Show Redis status in sidebar (for debugging)
        if os.getenv('DEBUG', 'false').lower() == 'true':
            with st.sidebar.expander("System Status"):
                st.write(f"Redis Available: {REDIS_AVAILABLE}")
                st.write(f"Redis Connected: {st.session_state.get('redis_connected', False)}")
        
        # Update active page in query params if changed
        if page != current_page:
            st.query_params["page"] = page
        
        # Route to appropriate page
        if page == "Data Upload":
            render_data_upload()
        elif page == "Wizard":
            render_wizard_page()
        elif page == "Data Analysis":
            render_data_analysis()
        elif page == "Settings":
            render_settings_page()
        elif page == "Register":
            render_register()
            
    except Exception as e:
        log_exception(e, logger, context={"action": "main"})
        st.error("An error occurred. Please try again.")
        if os.getenv('DEBUG', 'false').lower() == 'true':
            st.exception(e)


if __name__ == "__main__":
    main()
