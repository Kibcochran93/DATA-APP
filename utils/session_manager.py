"""
Session state management utilities for the SEATS application.
"""
import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional
from utils.debug_logger import setup_logger, log_exception
from utils.exceptions import ValidationError

# Initialize logger
logger = setup_logger(__name__)

def store_dataframe(df: pd.DataFrame, key: str) -> None:
    """
    Safely store a DataFrame in session state.
    
    Args:
        df: DataFrame to store
        key: Session state key to use
    """
    if df is not None:
        st.session_state[key] = df.copy()
    else:
        st.session_state[key] = None

def store_validation_results(results: dict, key: str = "validation_results") -> None:
    """
    Safely store validation results in session state.
    
    Args:
        results: Validation results dictionary
        key: Session state key to use
    """
    if results is not None:
        st.session_state[key] = results.copy()
    else:
        st.session_state[key] = None

def clear_session_state() -> None:
    """
    Clear session state variables while preserving authentication.
    
    This should be called when switching between major operations
    or when resetting the application state.
    """
    # Store auth-related state
    auth = st.session_state.get('auth')
    user = st.session_state.get('user')
    token = st.session_state.get('token')
    monitoring = st.session_state.get('monitoring')
    
    # Clear all session state
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    
    # Restore auth-related state
    if auth:
        st.session_state.auth = auth
    if user:
        st.session_state.user = user
    if token:
        st.session_state.token = token
    if monitoring:
        st.session_state.monitoring = monitoring 