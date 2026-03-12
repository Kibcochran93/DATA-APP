"""
Validation Error Panel Component

Displays validation errors with:
- Summary panel with clickable row numbers
- Inline cell highlighting in dataframe
- Auto-scroll to errors toggle
- Error details with explanations
"""

import streamlit as st
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass


@dataclass
class CellStyle:
    """Style configuration for cell highlighting."""
    background_color: str = "#fff3cd"  # Warning yellow
    border: str = "2px solid #ffc107"
    color: str = "#856404"


class ValidationErrorPanel:
    """
    Component for displaying validation errors with interactive features.
    """
    
    # Default warning style (yellow)
    WARNING_STYLE = CellStyle(
        background_color="#fff3cd",
        border="2px solid #ffc107",
        color="#856404"
    )
    
    def __init__(self, key_prefix: str = "validation"):
        """
        Initialize the error panel.
        
        Args:
            key_prefix: Prefix for Streamlit session state keys
        """
        self.key_prefix = key_prefix
        self._init_session_state()
    
    def _init_session_state(self):
        """Initialize session state variables."""
        if f"{self.key_prefix}_auto_scroll" not in st.session_state:
            st.session_state[f"{self.key_prefix}_auto_scroll"] = True
        if f"{self.key_prefix}_selected_row" not in st.session_state:
            st.session_state[f"{self.key_prefix}_selected_row"] = None
        if f"{self.key_prefix}_filter_errors_only" not in st.session_state:
            st.session_state[f"{self.key_prefix}_filter_errors_only"] = False
    
    def render(
        self,
        df: pd.DataFrame,
        validation_result: Any,
        show_dataframe: bool = True
    ) -> pd.DataFrame:
        """
        Render the complete validation error panel.
        
        Args:
            df: The dataframe being validated
            validation_result: ValidationResult object from validator
            show_dataframe: Whether to show the highlighted dataframe
            
        Returns:
            The (potentially filtered) dataframe
        """
        # Render controls
        self._render_controls(validation_result)
        
        # Render summary panel
        self._render_summary_panel(validation_result)
        
        # Render schema issues if any
        if validation_result.schema_issues:
            self._render_schema_issues(validation_result.schema_issues)
        
        # Render error details
        self._render_error_details(validation_result)
        
        # Render highlighted dataframe
        if show_dataframe:
            return self._render_highlighted_dataframe(df, validation_result)
        
        return df
    
    def _render_controls(self, validation_result: Any):
        """Render control toggles."""
        col1, col2, col3 = st.columns([2, 2, 2])
        
        with col1:
            st.session_state[f"{self.key_prefix}_auto_scroll"] = st.toggle(
                "Auto-scroll to errors",
                value=st.session_state.get(f"{self.key_prefix}_auto_scroll", True),
                key=f"{self.key_prefix}_auto_scroll_toggle"
            )
        
        with col2:
            st.session_state[f"{self.key_prefix}_filter_errors_only"] = st.toggle(
                "Show only rows with errors",
                value=st.session_state.get(f"{self.key_prefix}_filter_errors_only", False),
                key=f"{self.key_prefix}_filter_toggle"
            )
        
        with col3:
            error_rows = validation_result.get_error_rows()
            if error_rows:
                st.metric("Rows with errors", len(error_rows))
    
    def _render_summary_panel(self, validation_result: Any):
        """Render error summary statistics."""
        summary = validation_result.to_summary()
        
        if summary["total_errors"] == 0 and not validation_result.schema_issues:
            st.success("No validation errors found!")
            return
        
        # Summary metrics
        st.markdown("### Validation Summary")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Errors",
                summary["total_errors"],
                delta=None,
                delta_color="inverse"
            )
        
        with col2:
            st.metric(
                "Rows Affected",
                summary["rows_affected"]
            )
        
        with col3:
            st.metric(
                "Schema Issues",
                len(validation_result.schema_issues)
            )
        
        with col4:
            st.metric(
                "Columns Affected",
                len(summary.get("columns_affected", {}))
            )
        
        # Error type breakdown
        if summary.get("error_types"):
            with st.expander("Error Types Breakdown", expanded=False):
                for error_type, count in summary["error_types"].items():
                    st.write(f"- **{error_type.replace('_', ' ').title()}**: {count}")
        
        # Columns affected
        if summary.get("columns_affected"):
            with st.expander("Columns Affected", expanded=False):
                for col, count in sorted(
                    summary["columns_affected"].items(),
                    key=lambda x: x[1],
                    reverse=True
                ):
                    st.write(f"- **{col}**: {count} errors")
    
    def _render_schema_issues(self, schema_issues: List[str]):
        """Render schema-level issues.
        
        Per SEATS Data Interface Spec:
        - All missing columns are errors (all spec columns are required)
        - Column order issues are errors (blocks export)
        - Duplicates and name mismatches are errors
        """
        st.markdown("### Schema Issues")
        
        for issue in schema_issues:
            if "Missing required column" in issue:
                st.error(f"**Missing Column:** {issue}")
            elif "Missing mandatory" in issue:
                # Legacy format compatibility
                st.error(f"**Missing Column:** {issue}")
            elif "Duplicate" in issue:
                st.error(f"**Duplicate Column:** {issue}")
            elif "out of required order" in issue.lower():
                st.error(f"**Column Order:** {issue}")
            elif "mismatch" in issue.lower():
                st.error(f"**Column Name:** {issue}")
            elif "whitespace" in issue.lower():
                st.warning(f"**Column Naming:** {issue}")
            else:
                st.error(issue)
    
    def _render_error_details(self, validation_result: Any):
        """Render detailed error list with row navigation."""
        errors = validation_result.errors
        
        if not errors:
            return
        
        st.markdown("### Error Details")
        
        # Group errors by row
        errors_by_row: Dict[int, List] = {}
        for error in errors:
            if error.row_index not in errors_by_row:
                errors_by_row[error.row_index] = []
            errors_by_row[error.row_index].append(error)
        
        # Create tabs for different views
        tab1, tab2 = st.tabs(["By Row", "By Column"])
        
        with tab1:
            self._render_errors_by_row(errors_by_row)
        
        with tab2:
            self._render_errors_by_column(validation_result)
    
    def _render_errors_by_row(self, errors_by_row: Dict[int, List]):
        """Render errors grouped by row."""
        # Pagination for large error sets
        rows_per_page = 10
        error_rows = sorted(errors_by_row.keys())
        total_pages = max(1, (len(error_rows) + rows_per_page - 1) // rows_per_page)
        
        if len(error_rows) > rows_per_page:
            page = st.selectbox(
                "Page",
                range(1, total_pages + 1),
                key=f"{self.key_prefix}_error_page"
            )
            start_idx = (page - 1) * rows_per_page
            end_idx = start_idx + rows_per_page
            display_rows = error_rows[start_idx:end_idx]
        else:
            display_rows = error_rows
        
        for row_idx in display_rows:
            row_errors = errors_by_row[row_idx]
            
            with st.expander(
                f"Row {row_idx + 1} - {len(row_errors)} error(s)",
                expanded=st.session_state.get(f"{self.key_prefix}_auto_scroll", True)
            ):
                for error in row_errors:
                    self._render_single_error(error)
    
    def _render_errors_by_column(self, validation_result: Any):
        """Render errors grouped by column."""
        errors_by_col: Dict[str, List] = {}
        for error in validation_result.errors:
            if error.column not in errors_by_col:
                errors_by_col[error.column] = []
            errors_by_col[error.column].append(error)
        
        for col in sorted(errors_by_col.keys()):
            col_errors = errors_by_col[col]
            
            with st.expander(
                f"{col} - {len(col_errors)} error(s)",
                expanded=False
            ):
                # Show sample errors (first 5)
                for error in col_errors[:5]:
                    self._render_single_error(error)
                
                if len(col_errors) > 5:
                    st.info(f"... and {len(col_errors) - 5} more errors in this column")
    
    def _render_single_error(self, error: Any):
        """Render a single error with details using native Streamlit components."""
        error_dict = error.to_dict()
        
        with st.container(border=True):
            col_name = error_dict.get('column', 'Unknown')
            message = error_dict.get('message', '')
            current_val = error_dict.get('current_value', 'EMPTY')
            expected = error_dict.get('expected_format', '')
            suggestion = error_dict.get('suggestion', '')
            
            st.markdown(f"**Column:** {col_name}")
            st.markdown(f"**Issue:** {message}")
            st.markdown(f"**Current Value:** `{current_val}`")
            if expected:
                st.markdown(f"**Expected:** {expected}")
            if suggestion:
                st.markdown(f"**Suggestion:** {suggestion}")
    
    # Maximum cells for styled rendering (Pandas default is 262144)
    # Set slightly below to account for any overhead
    MAX_STYLED_CELLS = 250000
    # Number of rows to show when using partial styling
    PARTIAL_STYLE_ROWS = 1000
    
    def _render_highlighted_dataframe(
        self,
        df: pd.DataFrame,
        validation_result: Any
    ) -> pd.DataFrame:
        """Render dataframe with highlighted error cells."""
        st.markdown("### Data Preview")
        
        # Get error cells
        error_cells = validation_result.get_error_cells()
        error_rows = validation_result.get_error_rows()
        
        # Filter to error rows only if toggle is on
        if st.session_state.get(f"{self.key_prefix}_filter_errors_only", False):
            if error_rows:
                display_df = df.loc[error_rows].copy()
            else:
                display_df = df.copy()
        else:
            display_df = df.copy()
        
        # Auto-scroll: show first error rows at top
        if st.session_state.get(f"{self.key_prefix}_auto_scroll", True) and error_rows:
            # Reorder to put error rows first
            non_error_rows = [i for i in display_df.index if i not in error_rows]
            error_rows_in_display = [i for i in error_rows if i in display_df.index]
            new_order = error_rows_in_display + non_error_rows
            display_df = display_df.loc[new_order]
        
        # Calculate total cells for styling decision
        total_cells = display_df.shape[0] * display_df.shape[1]
        
        # Check if dataframe is too large for full styling
        if total_cells > self.MAX_STYLED_CELLS:
            self._render_large_dataframe(display_df, error_cells, error_rows, df)
        else:
            self._render_styled_dataframe(display_df, error_cells, error_rows, df)
        
        return display_df
    
    def _render_styled_dataframe(
        self,
        display_df: pd.DataFrame,
        error_cells: list,
        error_rows: list,
        original_df: pd.DataFrame
    ) -> None:
        """Render dataframe with full error cell highlighting."""
        # Convert error_cells to set for faster lookup
        error_cells_set = set(error_cells)
        
        # Create style function
        def highlight_errors(row):
            styles = [''] * len(row)
            row_idx = row.name
            
            for i, col in enumerate(row.index):
                if (row_idx, col) in error_cells_set:
                    styles[i] = (
                        'background-color: #fff3cd; '
                        'border: 2px solid #ffc107; '
                        'color: #856404;'
                    )
            
            return styles
        
        # Apply styling
        styled_df = display_df.style.apply(highlight_errors, axis=1)
        
        # Display with Streamlit
        st.dataframe(
            styled_df,
            width='stretch',
            height=400
        )
        
        # Row count info
        if st.session_state.get(f"{self.key_prefix}_filter_errors_only", False):
            st.caption(f"Showing {len(display_df)} rows with errors out of {len(original_df)} total rows")
        else:
            st.caption(f"Showing {len(display_df)} rows ({len(error_rows)} with errors)")
    
    def _render_large_dataframe(
        self,
        display_df: pd.DataFrame,
        error_cells: list,
        error_rows: list,
        original_df: pd.DataFrame
    ) -> None:
        """Render large dataframe with optional partial styling."""
        total_cells = display_df.shape[0] * display_df.shape[1]
        
        # Info message about styling being disabled
        st.info(
            f"Cell highlighting is disabled for performance "
            f"({total_cells:,} cells exceeds {self.MAX_STYLED_CELLS:,} limit). "
            f"Error details are still available in the panels above."
        )
        
        # Toggle for partial styling
        show_partial = st.toggle(
            f"Show first {self.PARTIAL_STYLE_ROWS} rows with highlighting",
            value=False,
            key=f"{self.key_prefix}_partial_style_toggle"
        )
        
        if show_partial:
            # Show first N rows with styling
            partial_df = display_df.head(self.PARTIAL_STYLE_ROWS).copy()
            error_cells_set = set(error_cells)
            
            def highlight_errors(row):
                styles = [''] * len(row)
                row_idx = row.name
                
                for i, col in enumerate(row.index):
                    if (row_idx, col) in error_cells_set:
                        styles[i] = (
                            'background-color: #fff3cd; '
                            'border: 2px solid #ffc107; '
                            'color: #856404;'
                        )
                
                return styles
            
            styled_df = partial_df.style.apply(highlight_errors, axis=1)
            
            st.dataframe(
                styled_df,
                width='stretch',
                height=400
            )
            
            st.caption(
                f"Showing first {len(partial_df)} rows with highlighting "
                f"(of {len(display_df)} total, {len(error_rows)} with errors)"
            )
        else:
            # Show full dataframe without styling
            st.dataframe(
                display_df,
                width='stretch',
                height=400
            )
            
            # Row count info
            if st.session_state.get(f"{self.key_prefix}_filter_errors_only", False):
                st.caption(f"Showing {len(display_df)} rows with errors out of {len(original_df)} total rows")
            else:
                st.caption(f"Showing {len(display_df)} rows ({len(error_rows)} with errors)")


def render_validation_panel(
    df: pd.DataFrame,
    validation_result: Any,
    key_prefix: str = "validation"
) -> pd.DataFrame:
    """
    Convenience function to render validation error panel.
    
    Args:
        df: DataFrame to display
        validation_result: ValidationResult from validator
        key_prefix: Prefix for session state keys
        
    Returns:
        Displayed (potentially filtered) dataframe
    """
    panel = ValidationErrorPanel(key_prefix=key_prefix)
    return panel.render(df, validation_result)


def create_error_summary_table(validation_result: Any) -> pd.DataFrame:
    """
    Create a summary table of ALL validation issues for export.
    Includes schema issues (missing columns, wrong order, etc.) and row-level errors.
    
    Args:
        validation_result: ValidationResult object
        
    Returns:
        DataFrame with error details
    """
    rows = []
    
    # Schema issues first (file-level errors)
    for issue in validation_result.schema_issues:
        rows.append({
            "Row Number": "N/A",
            "Column": "SCHEMA",
            "Error Type": "Schema Error",
            "Message": issue,
            "Current Value": "",
            "Expected Format": "",
            "Suggestion": ""
        })
    
    # Warnings
    for warning in validation_result.warnings:
        rows.append({
            "Row Number": "N/A",
            "Column": "FILE",
            "Error Type": "Warning",
            "Message": warning,
            "Current Value": "",
            "Expected Format": "",
            "Suggestion": ""
        })
    
    # Row-level errors
    for error in validation_result.errors:
        rows.append({
            "Row Number": error.row_index + 1,
            "Column": error.column,
            "Error Type": error.error_type.replace("_", " ").title(),
            "Message": error.message,
            "Current Value": str(error.current_value) if error.current_value else "EMPTY",
            "Expected Format": error.expected_format or "",
            "Suggestion": error.suggestion or ""
        })
    
    if not rows:
        return pd.DataFrame()
    
    return pd.DataFrame(rows)


def export_errors_to_csv(validation_result: Any, filename: str = "validation_errors.csv"):
    """
    Export full validation report (schema issues + row errors + warnings) to CSV.
    
    Args:
        validation_result: ValidationResult object
        filename: Output filename
    """
    error_df = create_error_summary_table(validation_result)
    
    if error_df.empty:
        st.info("No errors to export")
        return
    
    csv = error_df.to_csv(index=False)
    
    # Summary counts for the button label
    schema_count = len(validation_result.schema_issues)
    row_count = len(validation_result.errors)
    warn_count = len(validation_result.warnings)
    total = schema_count + row_count + warn_count
    
    st.download_button(
        label=f"Download Error Report ({total} issues)",
        data=csv,
        file_name=filename,
        mime="text/csv"
    )
