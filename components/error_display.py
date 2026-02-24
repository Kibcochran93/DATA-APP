import streamlit as st
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from utils.debug_logger import setup_logger
from helpers.logger import log_exception
import json
from datetime import datetime
from utils.exceptions import (
    ValidationError,
    DataError,
    SecurityError,
    AuthenticationError,
    AuthorizationError
)

logger = setup_logger(__name__, "error_display.log")

class ValidationDisplayError(Exception):
    """Base exception for validation display errors."""
    pass

def get_error_statistics(validation_results: Dict[str, Any]) -> Dict[str, int]:
    """
    Calculate error statistics from validation results.
    
    Args:
        validation_results: Dictionary containing validation results
        
    Returns:
        Dictionary of error counts by type
    """
    stats = {
        "schema_errors": 0,
        "format_errors": 0,
        "referential_errors": 0,
        "security_errors": 0,
        "data_errors": 0,
        "total_errors": 0
    }
    
    try:
        if validation_results.get("schema_errors"):
            stats["schema_errors"] = len(validation_results["schema_errors"])
            
        if validation_results.get("format_errors"):
            stats["format_errors"] = sum(
                len(errors) for errors in validation_results["format_errors"].values()
            )
            
        if validation_results.get("referential_errors"):
            stats["referential_errors"] = len(validation_results["referential_errors"])
            
        if validation_results.get("security_errors"):
            stats["security_errors"] = len(validation_results["security_errors"])
            
        if validation_results.get("data_errors"):
            stats["data_errors"] = len(validation_results["data_errors"])
            
        stats["total_errors"] = sum(stats.values())
        return stats
        
    except Exception as e:
        log_exception(logger, e, "get_error_statistics")
        raise ValidationDisplayError(f"Error calculating statistics: {str(e)}")

def get_user_friendly_message(error: Exception) -> str:
    """
    Convert technical error messages to user-friendly messages.
    
    Args:
        error: The exception to convert
        
    Returns:
        User-friendly error message
    """
    if isinstance(error, ValidationError):
        return f"Data validation error: {str(error)}"
    elif isinstance(error, SecurityError):
        return "Security error: Please contact your administrator"
    elif isinstance(error, DataError):
        return f"Data processing error: {str(error)}"
    elif isinstance(error, AuthenticationError):
        return "Authentication error: Please check your credentials"
    else:
        return "An unexpected error occurred. Please try again or contact support."

def display_validation_errors(
    validation_results: Dict[str, Any],
    df: pd.DataFrame
) -> None:
    """
    Display validation errors in a user-friendly format.
    
    Args:
        validation_results: Dictionary containing validation results
        df: DataFrame containing the data
    """
    try:
        # Get error statistics
        stats = get_error_statistics(validation_results)
        
        # Display error summary
        st.error(f"Found {stats['total_errors']} issues that need attention")
        
        # Create tabs for different error types
        tabs = st.tabs([
            "All Issues",
            "Schema Issues",
            "Format Issues",
            "Data Issues",
            "Security Issues"
        ])
        
        # All Issues tab
        with tabs[0]:
            if stats['total_errors'] > 0:
                st.markdown("### Summary of Issues")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Schema Issues", stats['schema_errors'])
                with col2:
                    st.metric("Format Issues", stats['format_errors'])
                with col3:
                    st.metric("Data Issues", stats['data_errors'])
                
                # Show detailed error list
                st.markdown("### Detailed Issues")
                for error_type, errors in validation_results.items():
                    if errors:
                        st.markdown(f"#### {error_type.replace('_', ' ').title()}")
                        for error in errors:
                            st.error(get_user_friendly_message(error))
            else:
                st.success("No issues found!")
        
        # Schema Issues tab
        with tabs[1]:
            if stats['schema_errors'] > 0:
                st.markdown("### Schema Validation Issues")
                for error in validation_results.get("schema_errors", []):
                    st.error(get_user_friendly_message(error))
            else:
                st.info("No schema issues found")
        
        # Format Issues tab
        with tabs[2]:
            if stats['format_errors'] > 0:
                st.markdown("### Format Validation Issues")
                for field, errors in validation_results.get("format_errors", {}).items():
                    st.markdown(f"#### {field}")
                    for error in errors:
                        st.error(get_user_friendly_message(error))
            else:
                st.info("No format issues found")
        
        # Data Issues tab
        with tabs[3]:
            if stats['data_errors'] > 0:
                st.markdown("### Data Processing Issues")
                for error in validation_results.get("data_errors", []):
                    st.error(get_user_friendly_message(error))
            else:
                st.info("No data issues found")
        
        # Security Issues tab
        with tabs[4]:
            if stats['security_errors'] > 0:
                st.markdown("### Security Issues")
                for error in validation_results.get("security_errors", []):
                    st.error(get_user_friendly_message(error))
            else:
                st.info("No security issues found")
        
        # Add action buttons
        st.markdown("### Actions")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Export Issues"):
                export_validation_report(validation_results)
        with col2:
            if st.button("Request Help"):
                st.info("Please contact your administrator for assistance")
                
    except Exception as e:
        log_exception(logger, e, "display_validation_errors")
        raise ValidationDisplayError(f"Error displaying validation results: {str(e)}")

def export_validation_report(validation_results: Dict[str, Any]) -> None:
    """
    Export validation results to a file.
    
    Args:
        validation_results: Dictionary containing validation results
    """
    try:
        # Create report data
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_issues": get_error_statistics(validation_results)["total_errors"],
            "issues": validation_results
        }
        
        # Convert to JSON
        report_json = json.dumps(report, indent=2)
        
        # Create download button
        st.download_button(
            label="Download Report",
            data=report_json,
            file_name=f"validation_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
        
    except Exception as e:
        log_exception(logger, e, "export_validation_report")
        st.error("Failed to export validation report") 