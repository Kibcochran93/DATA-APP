"""
Upload controller for the SEATS application.

Handles file upload processing and validation.
"""

import streamlit as st
import pandas as pd
from typing import Optional, Any
import logging

from utils.debug_logger import setup_logger, log_exception
from utils.exceptions import ValidationError, SecurityError, DataError
from utils.seats_data_handler import get_seats_handler
from security.config import InputValidator

logger = setup_logger(__name__)


def handle_file_upload(uploaded_file: Any) -> Optional[pd.DataFrame]:
    """
    Handle file upload processing.
    
    Args:
        uploaded_file: Streamlit uploaded file object
        
    Returns:
        Processed DataFrame or None if processing fails
    """
    if uploaded_file is None:
        return None
    
    try:
        # Initialize validator and SEATS handler
        validator = InputValidator()
        seats_handler = get_seats_handler()
        
        # Validate file
        validator.validate_file(uploaded_file)
        
        # Read file based on extension, preserving leading zeros
        filename = uploaded_file.name.lower()
        
        if filename.endswith(".csv"):
            # Use SEATS handler to preserve leading zeros in ID fields
            df = seats_handler.read_csv_preserve_leading_zeros(uploaded_file)
        elif filename.endswith((".xlsx", ".xls")):
            # Use SEATS handler to preserve leading zeros in ID fields
            df = seats_handler.read_excel_preserve_leading_zeros(uploaded_file)
        elif filename.endswith(".json"):
            df = pd.read_json(uploaded_file)
        else:
            raise ValidationError(
                f"Unsupported file type: {filename}",
                error_code="UNSUPPORTED_FILE_TYPE"
            )
        
        # Validate dataframe
        validation_result = validator.validate_dataframe(df)
        
        if not validation_result.get("is_valid", False):
            issues = validation_result.get("issues", [])
            st.warning(f"Validation issues found: {len(issues)}")
            for issue in issues[:5]:
                st.text(f"- {issue}")
        
        # Sanitize input
        df = validator.sanitize_input(df)
        
        # Store in session state
        st.session_state.df = df
        st.session_state.upload_complete = True
        
        # Track event
        monitoring = st.session_state.get("monitoring")
        if monitoring:
            monitoring.track_event(
                "file_upload",
                details={
                    "filename": uploaded_file.name,
                    "rows": len(df),
                    "columns": len(df.columns)
                }
            )
        
        return df
        
    except ValidationError as e:
        log_exception(e, logger, {"action": "file_upload", "file": uploaded_file.name})
        st.error(f"Validation error: {e.message}")
        return None
        
    except SecurityError as e:
        log_exception(e, logger, {"action": "file_upload", "file": uploaded_file.name})
        st.error(f"Security error: {e.message}")
        return None
        
    except Exception as e:
        log_exception(e, logger, {"action": "file_upload", "file": uploaded_file.name})
        st.error(f"Error processing file: {str(e)}")
        return None


def render_upload_page() -> None:
    """Render the file upload page."""
    st.markdown("### Upload Data File")
    
    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["csv", "xlsx", "xls", "json"],
        help="Upload a CSV, Excel, or JSON file"
    )
    
    if uploaded_file is not None:
        df = handle_file_upload(uploaded_file)
        
        if df is not None:
            st.success(f"Successfully loaded {len(df)} rows")
            
            # Show preview
            st.markdown("#### Data Preview")
            st.dataframe(df.head(10))
            
            # Show column info
            with st.expander("Column Information"):
                col_info = pd.DataFrame({
                    "Column": df.columns,
                    "Type": df.dtypes.astype(str),
                    "Non-Null": df.count(),
                    "Null": df.isna().sum()
                })
                st.dataframe(col_info)


__all__ = [
    "handle_file_upload",
    "render_upload_page"
]
