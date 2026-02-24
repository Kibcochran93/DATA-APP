"""
Export controller for the SEATS application.

Handles data export functionality.
"""

import streamlit as st
import pandas as pd
from typing import Optional, Dict, Any
from datetime import datetime
import io
import logging

from utils.debug_logger import setup_logger, log_exception
from utils.exceptions import DataError
from ui_components import render_export_options, render_export_history

logger = setup_logger(__name__)


def handle_export() -> None:
    """
    Handle data export workflow.
    
    Renders export options and processes export requests.
    """
    # Check prerequisites
    df = st.session_state.get("df")
    user = st.session_state.get("user")
    
    if df is None:
        st.info("No data available to export. Please upload a file first.")
        return
    
    if user is None:
        st.warning("Please log in to export data.")
        return
    
    user_role = user.get("role", "user")
    
    # Render export options
    render_export_options(df, user_role)
    
    st.markdown("---")
    
    # Render export history
    render_export_history(user_role)


def export_to_csv(df: pd.DataFrame, filename: str) -> bytes:
    """
    Export DataFrame to CSV.
    
    Args:
        df: DataFrame to export
        filename: Output filename
        
    Returns:
        CSV data as bytes
    """
    return df.to_csv(index=False).encode("utf-8")


def export_to_excel(df: pd.DataFrame, filename: str) -> bytes:
    """
    Export DataFrame to Excel.
    
    Args:
        df: DataFrame to export
        filename: Output filename
        
    Returns:
        Excel data as bytes
    """
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    return buffer.getvalue()


def export_to_json(df: pd.DataFrame, filename: str) -> bytes:
    """
    Export DataFrame to JSON.
    
    Args:
        df: DataFrame to export
        filename: Output filename
        
    Returns:
        JSON data as bytes
    """
    return df.to_json(orient="records", indent=2).encode("utf-8")


def record_export(
    filename: str,
    format_type: str,
    row_count: int,
    user: str
) -> None:
    """
    Record export in history.
    
    Args:
        filename: Export filename
        format_type: Export format
        row_count: Number of rows exported
        user: Username
    """
    if "export_history" not in st.session_state:
        st.session_state.export_history = []
    
    export_record = {
        "filename": filename,
        "format": format_type,
        "rows": row_count,
        "user": user,
        "timestamp": datetime.now().isoformat()
    }
    
    st.session_state.export_history.append(export_record)
    
    # Track event
    monitoring = st.session_state.get("monitoring")
    if monitoring:
        monitoring.track_event("data_export", details=export_record)


def render_export_page() -> None:
    """Render the export page."""
    st.markdown("### Export Data")
    handle_export()


__all__ = [
    "handle_export",
    "export_to_csv",
    "export_to_excel",
    "export_to_json",
    "record_export",
    "render_export_page"
]
