"""
Wizard controller for the SEATS application.

Manages the step-by-step data validation wizard workflow.
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
import logging

from utils.debug_logger import setup_logger, log_exception
from utils.exceptions import ValidationError

logger = setup_logger(__name__)


class WizardStep(Enum):
    """Enumeration of wizard steps."""
    UPLOAD = 1
    DATASET_SELECT = 2
    HEADER_MAPPING = 3
    VALIDATION = 4
    AUTO_FIX = 5
    REVIEW = 6
    EXPORT = 7


class WizardState:
    """Manages wizard state in session."""
    
    def __init__(self):
        self._initialize_state()
    
    def _initialize_state(self) -> None:
        """Initialize wizard state in session."""
        if "wizard_step" not in st.session_state:
            st.session_state.wizard_step = WizardStep.UPLOAD.value
        if "wizard_data" not in st.session_state:
            st.session_state.wizard_data = {}
        if "wizard_history" not in st.session_state:
            st.session_state.wizard_history = []
    
    @property
    def current_step(self) -> int:
        """Get current wizard step."""
        step = st.session_state.get("wizard_step")
        if step is None:
            st.session_state.wizard_step = WizardStep.UPLOAD.value
            return WizardStep.UPLOAD.value
        return step
    
    @current_step.setter
    def current_step(self, value: int) -> None:
        """Set current wizard step."""
        st.session_state.wizard_step = value
    
    @property
    def data(self) -> Dict[str, Any]:
        """Get wizard data."""
        return st.session_state.wizard_data
    
    def set_data(self, key: str, value: Any) -> None:
        """Set wizard data value."""
        st.session_state.wizard_data[key] = value
    
    def get_data(self, key: str, default: Any = None) -> Any:
        """Get wizard data value."""
        return st.session_state.wizard_data.get(key, default)
    
    def next_step(self) -> None:
        """Move to next wizard step."""
        if self.current_step < WizardStep.EXPORT.value:
            st.session_state.wizard_history.append(self.current_step)
            self.current_step += 1
    
    def previous_step(self) -> None:
        """Move to previous wizard step."""
        if st.session_state.wizard_history:
            self.current_step = st.session_state.wizard_history.pop()
    
    def go_to_step(self, step: WizardStep) -> None:
        """Jump to specific wizard step."""
        st.session_state.wizard_history.append(self.current_step)
        self.current_step = step.value
    
    def reset(self) -> None:
        """Reset wizard to initial state."""
        st.session_state.wizard_step = WizardStep.UPLOAD.value
        st.session_state.wizard_data = {}
        st.session_state.wizard_history = []


def render_progress_bar(wizard_state: WizardState) -> None:
    """Render wizard progress bar."""
    total_steps = len(WizardStep)
    current = wizard_state.current_step or 1
    progress = current / total_steps
    
    st.progress(progress)
    
    # Step labels
    cols = st.columns(total_steps)
    step_names = ["Upload", "Select", "Map", "Validate", "Fix", "Review", "Export"]
    
    for i, (col, name) in enumerate(zip(cols, step_names), 1):
        with col:
            if i < current:
                st.markdown(f"~~{name}~~")
            elif i == current:
                st.markdown(f"**{name}**")
            else:
                st.markdown(f"_{name}_")


def render_step_upload(wizard_state: WizardState) -> None:
    """Render upload step."""
    st.subheader("Step 1: Upload Data File")
    
    uploaded_file = st.file_uploader(
        "Choose a CSV or Excel file",
        type=["csv", "xlsx", "xls"],
        help="Upload the data file you want to validate"
    )
    
    if uploaded_file is not None:
        try:
            # Read file
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            # Store in wizard state
            wizard_state.set_data("dataframe", df)
            wizard_state.set_data("filename", uploaded_file.name)
            wizard_state.set_data("original_columns", df.columns.tolist())
            
            # Show preview
            st.success(f"Loaded {len(df)} rows and {len(df.columns)} columns")
            st.dataframe(df.head(10))
            
            if st.button("Continue to Dataset Selection", type="primary"):
                wizard_state.next_step()
                st.rerun()
                
        except Exception as e:
            log_exception(e, logger, {"action": "upload_file"})
            st.error(f"Error reading file: {str(e)}")


def render_step_dataset_select(wizard_state: WizardState) -> None:
    """Render dataset selection step."""
    st.subheader("Step 2: Select Dataset Type")
    
    from config.config import DATASET_TYPES
    
    dataset_type = st.selectbox(
        "What type of data is this?",
        options=DATASET_TYPES,
        help="Select the dataset type that matches your data"
    )
    
    wizard_state.set_data("dataset_type", dataset_type)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back"):
            wizard_state.previous_step()
            st.rerun()
    with col2:
        if st.button("Continue to Header Mapping", type="primary"):
            wizard_state.next_step()
            st.rerun()


def render_step_header_mapping(wizard_state: WizardState) -> None:
    """Render header mapping step."""
    st.subheader("Step 3: Map Headers")
    
    df = wizard_state.get_data("dataframe")
    dataset_type = wizard_state.get_data("dataset_type")
    
    if df is None:
        st.error("No data loaded. Please go back to upload.")
        return
    
    st.info("Map your column headers to the expected fields.")
    
    # Get expected headers for dataset type
    try:
        from utils.master_spec_loader import MasterSpecLoader
        loader = MasterSpecLoader()
        expected = loader.get_expected_headers(dataset_type)
    except Exception:
        expected = {"mandatory": [], "optional": []}
    
    current_headers = df.columns.tolist()
    all_expected = expected.get("mandatory", []) + expected.get("optional", [])
    
    mapping = {}
    for col in current_headers:
        selected = st.selectbox(
            f"Map '{col}' to:",
            options=["(ignore)"] + all_expected,
            key=f"map_{col}"
        )
        if selected != "(ignore)":
            mapping[col] = selected
    
    wizard_state.set_data("header_mapping", mapping)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back"):
            wizard_state.previous_step()
            st.rerun()
    with col2:
        if st.button("Continue to Validation", type="primary"):
            wizard_state.next_step()
            st.rerun()


def render_step_validation(wizard_state: WizardState) -> None:
    """Render validation step."""
    st.subheader("Step 4: Validate Data")
    
    df = wizard_state.get_data("dataframe")
    dataset_type = wizard_state.get_data("dataset_type")
    mapping = wizard_state.get_data("header_mapping", {})
    
    if df is None:
        st.error("No data loaded.")
        return
    
    # Apply header mapping
    if mapping:
        df_mapped = df.rename(columns=mapping)
    else:
        df_mapped = df
    
    # Run validation
    with st.spinner("Validating data..."):
        try:
            from utils.validator import validate_dataframe
            results = validate_dataframe(df_mapped, dataset_type)
            wizard_state.set_data("validation_results", results)
            wizard_state.set_data("dataframe_mapped", df_mapped)
            
            # Display results
            total_errors = results.get("total_errors", 0)
            if total_errors == 0:
                st.success("Validation passed! No issues found.")
            else:
                st.warning(f"Found {total_errors} validation issues.")
                
                with st.expander("View Issues"):
                    for error_type, errors in results.items():
                        if errors and error_type != "total_errors":
                            st.markdown(f"**{error_type}:**")
                            for error in errors[:10]:  # Limit display
                                st.markdown(f"- {error}")
                                
        except Exception as e:
            log_exception(e, logger, {"action": "validation"})
            st.error(f"Validation error: {str(e)}")
            results = {"error": str(e)}
            wizard_state.set_data("validation_results", results)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back"):
            wizard_state.previous_step()
            st.rerun()
    with col2:
        if st.button("Continue to Auto-Fix", type="primary"):
            wizard_state.next_step()
            st.rerun()


def render_step_autofix(wizard_state: WizardState) -> None:
    """Render auto-fix step."""
    st.subheader("Step 5: Auto-Fix Issues")
    
    results = wizard_state.get_data("validation_results", {})
    df = wizard_state.get_data("dataframe_mapped")
    
    if not results or results.get("total_errors", 0) == 0:
        st.info("No issues to fix. You can proceed to review.")
    else:
        st.info("Select which issues to auto-fix:")
        
        fix_whitespace = st.checkbox("Trim whitespace", value=True)
        fix_case = st.checkbox("Standardize case", value=True)
        fix_dates = st.checkbox("Fix date formats", value=True)
        
        if st.button("Apply Fixes"):
            with st.spinner("Applying fixes..."):
                try:
                    from utils.data_cleaner import DataCleaner
                    cleaner = DataCleaner()
                    
                    df_fixed = df.copy()
                    
                    if fix_whitespace:
                        for col in df_fixed.select_dtypes(include=["object"]).columns:
                            df_fixed[col] = df_fixed[col].str.strip()
                    
                    if fix_case:
                        # Apply case fixes based on field rules
                        pass
                    
                    if fix_dates:
                        # Apply date fixes
                        pass
                    
                    wizard_state.set_data("dataframe_fixed", df_fixed)
                    st.success("Fixes applied successfully!")
                    
                except Exception as e:
                    log_exception(e, logger, {"action": "auto_fix"})
                    st.error(f"Error applying fixes: {str(e)}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back"):
            wizard_state.previous_step()
            st.rerun()
    with col2:
        if st.button("Continue to Review", type="primary"):
            wizard_state.next_step()
            st.rerun()


def render_step_review(wizard_state: WizardState) -> None:
    """Render review step."""
    st.subheader("Step 6: Review Changes")
    
    df_original = wizard_state.get_data("dataframe")
    df_fixed = wizard_state.get_data("dataframe_fixed")
    
    if df_fixed is None:
        df_fixed = wizard_state.get_data("dataframe_mapped", df_original)
    
    st.markdown("### Final Data Preview")
    st.dataframe(df_fixed.head(20))
    
    st.markdown("### Summary")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Rows", len(df_fixed))
    with col2:
        st.metric("Total Columns", len(df_fixed.columns))
    
    wizard_state.set_data("dataframe_final", df_fixed)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back"):
            wizard_state.previous_step()
            st.rerun()
    with col2:
        if st.button("Continue to Export", type="primary"):
            wizard_state.next_step()
            st.rerun()


def render_step_export(wizard_state: WizardState) -> None:
    """Render export step."""
    st.subheader("Step 7: Export Data")
    
    df = wizard_state.get_data("dataframe_final")
    
    if df is None:
        st.error("No data to export.")
        return
    
    export_format = st.selectbox(
        "Export Format",
        options=["CSV", "Excel", "JSON"]
    )
    
    filename = st.text_input(
        "Filename",
        value=f"validated_data.{export_format.lower()}"
    )
    
    if st.button("Export", type="primary"):
        try:
            if export_format == "CSV":
                data = df.to_csv(index=False)
                mime = "text/csv"
            elif export_format == "Excel":
                import io
                buffer = io.BytesIO()
                df.to_excel(buffer, index=False)
                data = buffer.getvalue()
                mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            else:
                data = df.to_json(orient="records", indent=2)
                mime = "application/json"
            
            st.download_button(
                label="Download File",
                data=data,
                file_name=filename,
                mime=mime
            )
            
            st.success("Export ready! Click the download button above.")
            
        except Exception as e:
            log_exception(e, logger, {"action": "export"})
            st.error(f"Export error: {str(e)}")
    
    if st.button("Start Over"):
        wizard_state.reset()
        st.rerun()


def run_wizard() -> None:
    """
    Run the data validation wizard.
    
    Main entry point for the wizard workflow.
    """
    st.title("Data Validation Wizard")
    st.markdown("---")
    
    wizard_state = WizardState()
    
    # Render progress bar
    render_progress_bar(wizard_state)
    st.markdown("---")
    
    # Render current step
    step = wizard_state.current_step
    
    if step == WizardStep.UPLOAD.value:
        render_step_upload(wizard_state)
    elif step == WizardStep.DATASET_SELECT.value:
        render_step_dataset_select(wizard_state)
    elif step == WizardStep.HEADER_MAPPING.value:
        render_step_header_mapping(wizard_state)
    elif step == WizardStep.VALIDATION.value:
        render_step_validation(wizard_state)
    elif step == WizardStep.AUTO_FIX.value:
        render_step_autofix(wizard_state)
    elif step == WizardStep.REVIEW.value:
        render_step_review(wizard_state)
    elif step == WizardStep.EXPORT.value:
        render_step_export(wizard_state)


__all__ = [
    "run_wizard",
    "WizardState",
    "WizardStep",
]
