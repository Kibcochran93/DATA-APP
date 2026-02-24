"""
UI Components for the SEATS application.

Contains all Streamlit UI rendering functions.
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple, Callable
from datetime import datetime
import io
import logging

from utils.debug_logger import setup_logger, log_exception
from utils.exceptions import ValidationError, SecurityError

logger = setup_logger(__name__)


# =============================================================================
# Header and Navigation Components
# =============================================================================

def render_header() -> None:
    """Render the application header."""
    st.markdown(
        """
        <style>
        .main-header {
            font-size: 2rem;
            font-weight: bold;
            color: #1f77b4;
            padding-bottom: 1rem;
            border-bottom: 2px solid #1f77b4;
            margin-bottom: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    st.markdown('<div class="main-header">SEATS Data Validator</div>', unsafe_allow_html=True)


def section_header(title: str, icon: str = "") -> None:
    """
    Render a section header.
    
    Args:
        title: Section title
        icon: Optional emoji icon
    """
    if icon:
        st.markdown(f"### {icon} {title}")
    else:
        st.markdown(f"### {title}")


# =============================================================================
# Validation Components
# =============================================================================

def render_validation_summary(results: Dict[str, Any]) -> None:
    """
    Render validation results summary.
    
    Args:
        results: Dictionary containing validation results
    """
    if not results:
        st.info("No validation results available.")
        return
    
    total_errors = results.get("total_errors", 0)
    
    if total_errors == 0:
        st.success("All validation checks passed!")
        return
    
    st.warning(f"Found {total_errors} validation issues")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        schema_errors = len(results.get("schema_errors", []))
        st.metric("Schema Issues", schema_errors)
    
    with col2:
        format_errors = sum(len(v) for v in results.get("format_errors", {}).values())
        st.metric("Format Issues", format_errors)
    
    with col3:
        ref_errors = len(results.get("referential_errors", []))
        st.metric("Reference Issues", ref_errors)
    
    with col4:
        data_errors = len(results.get("data_errors", []))
        st.metric("Data Issues", data_errors)
    
    # Detailed errors
    with st.expander("View Details", expanded=False):
        for error_type, errors in results.items():
            if errors and error_type not in ["total_errors", "is_valid"]:
                st.markdown(f"**{error_type.replace('_', ' ').title()}:**")
                if isinstance(errors, dict):
                    for field, field_errors in errors.items():
                        st.markdown(f"- {field}:")
                        for error in field_errors[:5]:
                            st.markdown(f"  - {error}")
                elif isinstance(errors, list):
                    for error in errors[:10]:
                        st.markdown(f"- {error}")


def render_field_validation_summary(
    field: str,
    errors: List[str],
    row_count: int
) -> None:
    """
    Render validation summary for a specific field.
    
    Args:
        field: Field name
        errors: List of error messages
        row_count: Total row count
    """
    error_count = len(errors)
    error_rate = (error_count / row_count * 100) if row_count > 0 else 0
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.markdown(f"**{field}**")
    with col2:
        st.markdown(f"{error_count} errors")
    with col3:
        st.markdown(f"{error_rate:.1f}%")
    
    if errors:
        with st.expander(f"Show errors for {field}"):
            for error in errors[:10]:
                st.markdown(f"- {error}")
            if len(errors) > 10:
                st.markdown(f"_...and {len(errors) - 10} more_")


# =============================================================================
# Header Mapping Components
# =============================================================================

def render_header_mapping(
    raw_headers: List[str],
    normalized_headers: List[str],
    dataset_type: str,
    expected_options: List[str]
) -> List[str]:
    """
    Render header mapping interface.
    
    Args:
        raw_headers: Original column headers
        normalized_headers: Normalized column headers
        dataset_type: Dataset type
        expected_options: Expected header options
        
    Returns:
        List of mapped headers
    """
    st.markdown("#### Map Column Headers")
    st.info("Map your file columns to the expected fields.")
    
    options = ["(ignore)"] + expected_options
    mapped_headers = []
    
    for i, (raw, normalized) in enumerate(zip(raw_headers, normalized_headers)):
        col1, col2, col3 = st.columns([2, 1, 2])
        
        with col1:
            st.text(raw)
        
        with col2:
            st.text("→")
        
        with col3:
            # Try to find best match
            default_idx = 0
            if normalized in options:
                default_idx = options.index(normalized)
            
            selected = st.selectbox(
                f"Map {raw}",
                options=options,
                index=default_idx,
                key=f"header_map_{dataset_type}_{i}",
                label_visibility="collapsed"
            )
            mapped_headers.append(selected)
    
    return mapped_headers


def render_mapping_summary(
    mapped: int,
    ignored: int,
    missing: List[str]
) -> None:
    """
    Render header mapping summary.
    
    Args:
        mapped: Number of mapped columns
        ignored: Number of ignored columns
        missing: List of missing required columns
    """
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Mapped", mapped)
    with col2:
        st.metric("Ignored", ignored)
    with col3:
        st.metric("Missing", len(missing))
    
    if missing:
        st.warning(f"Missing required fields: {', '.join(missing)}")


# =============================================================================
# Data Editor Components
# =============================================================================

def render_data_editor(
    df: pd.DataFrame,
    key: str = "data_editor",
    disabled_columns: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Render an editable data table.
    
    Args:
        df: DataFrame to edit
        key: Unique key for the editor
        disabled_columns: Columns that cannot be edited
        
    Returns:
        Edited DataFrame
    """
    if df is None or df.empty:
        st.info("No data to display.")
        return df
    
    column_config = {}
    if disabled_columns:
        for col in disabled_columns:
            if col in df.columns:
                column_config[col] = st.column_config.Column(disabled=True)
    
    edited_df = st.data_editor(
        df,
        key=key,
        column_config=column_config,
        use_container_width=True,
        num_rows="dynamic"
    )
    
    return edited_df


def render_row_format_hint(field: str, format_rule: Dict[str, Any]) -> None:
    """
    Render format hint for a field.
    
    Args:
        field: Field name
        format_rule: Format rule dictionary
    """
    rule_type = format_rule.get("type", "unknown")
    description = format_rule.get("description", "")
    pattern = format_rule.get("pattern", "")
    values = format_rule.get("values", [])
    
    hint_parts = [f"**{field}** ({rule_type})"]
    
    if description:
        hint_parts.append(f": {description}")
    
    if pattern:
        hint_parts.append(f" | Pattern: `{pattern}`")
    
    if values:
        hint_parts.append(f" | Values: {', '.join(values[:5])}")
        if len(values) > 5:
            hint_parts.append(f" (+{len(values) - 5} more)")
    
    st.markdown("".join(hint_parts))


# =============================================================================
# Auto-Fix Components
# =============================================================================

def render_autofix_options(
    validation_results: Dict[str, Any],
    format_rules: Dict[str, Any]
) -> Dict[str, bool]:
    """
    Render auto-fix options interface.
    
    Args:
        validation_results: Validation results
        format_rules: Format rules for fields
        
    Returns:
        Dictionary of selected fix options
    """
    st.markdown("#### Auto-Fix Options")
    
    options = {}
    
    options["trim_whitespace"] = st.checkbox(
        "Trim whitespace from text fields",
        value=True,
        help="Remove leading and trailing spaces"
    )
    
    options["standardize_case"] = st.checkbox(
        "Standardize text case",
        value=True,
        help="Apply uppercase/lowercase rules"
    )
    
    options["fix_dates"] = st.checkbox(
        "Fix date formats",
        value=True,
        help="Convert dates to standard format"
    )
    
    options["remove_duplicates"] = st.checkbox(
        "Remove duplicate rows",
        value=False,
        help="Remove exact duplicate rows"
    )
    
    options["fill_defaults"] = st.checkbox(
        "Fill default values",
        value=False,
        help="Fill missing values with defaults where available"
    )
    
    return options


# =============================================================================
# Export Components
# =============================================================================

def render_export_options(df: pd.DataFrame, user_role: str) -> None:
    """
    Render export options interface.
    
    Args:
        df: DataFrame to export
        user_role: Current user role
    """
    if df is None or df.empty:
        st.info("No data available to export.")
        return
    
    st.markdown("#### Export Options")
    
    col1, col2 = st.columns(2)
    
    with col1:
        export_format = st.selectbox(
            "Format",
            options=["CSV", "Excel", "JSON"],
            key="export_format"
        )
    
    with col2:
        include_validation = st.checkbox(
            "Include validation report",
            value=True,
            key="include_validation"
        )
    
    filename = st.text_input(
        "Filename",
        value=f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        key="export_filename"
    )
    
    if st.button("Generate Export", type="primary"):
        try:
            data, mime, ext = export_dataframe(df, export_format)
            
            st.download_button(
                label=f"Download {export_format}",
                data=data,
                file_name=f"{filename}.{ext}",
                mime=mime
            )
            
        except Exception as e:
            log_exception(e, logger, {"action": "export"})
            st.error(f"Export failed: {str(e)}")


def render_export_history(user_role: str) -> None:
    """
    Render export history.
    
    Args:
        user_role: Current user role
    """
    st.markdown("#### Export History")
    
    # Get export history from session state
    history = st.session_state.get("export_history", [])
    
    if not history:
        st.info("No export history available.")
        return
    
    for item in history[-10:]:  # Show last 10
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.text(item.get("filename", "Unknown"))
        with col2:
            st.text(item.get("format", ""))
        with col3:
            st.text(item.get("timestamp", ""))


def export_dataframe(
    df: pd.DataFrame,
    format_type: str
) -> Tuple[bytes, str, str]:
    """
    Export DataFrame to specified format.
    
    Args:
        df: DataFrame to export
        format_type: Export format (CSV, Excel, JSON)
        
    Returns:
        Tuple of (data bytes, mime type, file extension)
    """
    if format_type.upper() == "CSV":
        data = df.to_csv(index=False).encode("utf-8")
        return data, "text/csv", "csv"
    
    elif format_type.upper() == "EXCEL":
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False, engine="openpyxl")
        data = buffer.getvalue()
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return data, mime, "xlsx"
    
    elif format_type.upper() == "JSON":
        data = df.to_json(orient="records", indent=2).encode("utf-8")
        return data, "application/json", "json"
    
    else:
        raise ValueError(f"Unsupported export format: {format_type}")


# =============================================================================
# Authentication Components
# =============================================================================

def render_login() -> Optional[Dict[str, str]]:
    """
    Render login form.
    
    Returns:
        User credentials if submitted, None otherwise
    """
    st.markdown("### Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login", type="primary")
        
        if submit:
            if username and password:
                return {"username": username, "password": password}
            else:
                st.error("Please enter both username and password.")
    
    return None


def render_register() -> Optional[Dict[str, str]]:
    """
    Render registration form.
    
    Returns:
        Registration data if submitted, None otherwise
    """
    st.markdown("### Register")
    
    with st.form("register_form"):
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submit = st.form_submit_button("Register", type="primary")
        
        if submit:
            if not all([username, email, password, confirm_password]):
                st.error("Please fill in all fields.")
            elif password != confirm_password:
                st.error("Passwords do not match.")
            elif len(password) < 8:
                st.error("Password must be at least 8 characters.")
            else:
                return {
                    "username": username,
                    "email": email,
                    "password": password
                }
    
    return None


def render_user_management() -> None:
    """Render user management interface (admin only)."""
    st.markdown("### User Management")
    
    # Get users from auth system
    auth = st.session_state.get("auth")
    if auth is None:
        st.error("Authentication not initialized.")
        return
    
    users = auth.users if hasattr(auth, "users") else {}
    
    if not users:
        st.info("No users registered.")
        return
    
    # Display users table
    user_data = []
    for username, info in users.items():
        user_data.append({
            "Username": username,
            "Role": info.get("role", "user"),
            "Created": info.get("created_at", "Unknown")
        })
    
    st.dataframe(pd.DataFrame(user_data), use_container_width=True)


# =============================================================================
# Monitoring Components
# =============================================================================

def render_monitoring_dashboard() -> None:
    """Render monitoring dashboard (admin only)."""
    st.markdown("### System Monitoring")
    
    monitoring = st.session_state.get("monitoring")
    if monitoring is None:
        st.warning("Monitoring not initialized.")
        return
    
    # Get metrics
    try:
        metrics = monitoring.get_metrics() if hasattr(monitoring, "get_metrics") else {}
    except Exception:
        metrics = {}
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Memory Usage",
            f"{metrics.get('memory_usage', 0):.1f}%"
        )
    
    with col2:
        st.metric(
            "CPU Usage",
            f"{metrics.get('cpu_usage', 0):.1f}%"
        )
    
    with col3:
        st.metric(
            "Active Sessions",
            metrics.get("active_sessions", 0)
        )
    
    with col4:
        st.metric(
            "Requests/min",
            metrics.get("requests_per_minute", 0)
        )
    
    # Recent events
    st.markdown("#### Recent Events")
    try:
        events = monitoring.get_events() if hasattr(monitoring, "get_events") else []
        if events:
            for event in events[-10:]:
                st.text(f"{event.get('timestamp', '')} - {event.get('type', '')} - {event.get('message', '')}")
        else:
            st.info("No recent events.")
    except Exception:
        st.info("Unable to load events.")


# =============================================================================
# File Upload Components
# =============================================================================

def file_uploader(
    label: str = "Upload File",
    allowed_types: Optional[List[str]] = None,
    key: str = "file_upload"
) -> Optional[Any]:
    """
    Render file upload component with validation.
    
    Args:
        label: Upload label
        allowed_types: List of allowed file extensions
        key: Unique key for the uploader
        
    Returns:
        Uploaded file object or None
    """
    if allowed_types is None:
        allowed_types = ["csv", "xlsx", "xls"]
    
    uploaded_file = st.file_uploader(
        label,
        type=allowed_types,
        key=key,
        help=f"Supported formats: {', '.join(allowed_types)}"
    )
    
    if uploaded_file is not None:
        # Validate file size
        from config.config import FILE_CONFIG
        max_size = FILE_CONFIG.get("max_size", 10485760)
        
        if uploaded_file.size > max_size:
            st.error(f"File too large. Maximum size: {max_size / 1024 / 1024:.1f} MB")
            return None
        
        st.success(f"File uploaded: {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
    
    return uploaded_file


__all__ = [
    # Header/Navigation
    "render_header",
    "section_header",
    
    # Validation
    "render_validation_summary",
    "render_field_validation_summary",
    
    # Header Mapping
    "render_header_mapping",
    "render_mapping_summary",
    
    # Data Editor
    "render_data_editor",
    "render_row_format_hint",
    
    # Auto-Fix
    "render_autofix_options",
    
    # Export
    "render_export_options",
    "render_export_history",
    "export_dataframe",
    
    # Auth
    "render_login",
    "render_register",
    "render_user_management",
    
    # Monitoring
    "render_monitoring_dashboard",
    
    # File Upload
    "file_uploader",
]
