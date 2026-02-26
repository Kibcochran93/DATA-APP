"""
Example integration of timetable validation with UI error panel.

This module demonstrates how to integrate the TimetableValidator
with the ValidationErrorPanel in a Streamlit application.
"""

import streamlit as st
import pandas as pd
from typing import Optional

# Import validators
from utils.timetable_validator import TimetableValidator, validate_timetable, ValidationResult
from components.validation_error_panel import (
    ValidationErrorPanel,
    render_validation_panel,
    export_errors_to_csv,
    create_error_summary_table
)


def run_timetable_validation_workflow(
    df: pd.DataFrame,
    dataset_name: str = "Timetable"
) -> Optional[ValidationResult]:
    """
    Complete validation workflow for timetable data.
    
    Args:
        df: Uploaded timetable dataframe
        dataset_name: Name for display purposes
        
    Returns:
        ValidationResult or None if validation not run
    """
    st.subheader(f"Validating {dataset_name}")
    
    # Show file info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Rows", len(df))
    with col2:
        st.metric("Total Columns", len(df.columns))
    with col3:
        st.metric("Dataset Type", dataset_name)
    
    # Run validation
    with st.spinner("Running validation checks..."):
        result = validate_timetable(df)
    
    # Display results using the error panel
    render_validation_panel(
        df=df,
        validation_result=result,
        key_prefix=f"val_{dataset_name.lower()}"
    )
    
    # Export options
    st.markdown("---")
    st.markdown("### Export Options")
    
    col1, col2 = st.columns(2)
    
    with col1:
        export_errors_to_csv(result, f"{dataset_name.lower()}_errors.csv")
    
    with col2:
        # Export corrected data option
        if st.button("Download Original Data", key=f"download_orig_{dataset_name}"):
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"{dataset_name.lower()}_data.csv",
                mime="text/csv"
            )
    
    return result


def validate_uploaded_file():
    """
    Streamlit page for validating uploaded timetable files.
    """
    st.title("SEATS Timetable Validator")
    st.markdown("Upload a timetable CSV file to validate against SEATS specifications.")
    
    # File upload
    uploaded_file = st.file_uploader(
        "Upload Timetable CSV",
        type=["csv"],
        help="Upload a CSV file containing timetable data"
    )
    
    if uploaded_file is not None:
        try:
            # Read CSV
            df = pd.read_csv(uploaded_file)
            
            # Store in session state
            st.session_state["uploaded_df"] = df
            st.session_state["uploaded_filename"] = uploaded_file.name
            
            # Run validation workflow
            result = run_timetable_validation_workflow(df)
            
            # Store result
            st.session_state["validation_result"] = result
            
        except Exception as e:
            st.error(f"Error reading file: {str(e)}")
            return
    
    elif "uploaded_df" in st.session_state:
        # Use previously uploaded data
        df = st.session_state["uploaded_df"]
        st.info(f"Using previously uploaded file: {st.session_state.get('uploaded_filename', 'Unknown')}")
        
        if st.button("Re-validate"):
            result = run_timetable_validation_workflow(df)
            st.session_state["validation_result"] = result


def integrate_with_wizard(wizard_state: dict, df: pd.DataFrame):
    """
    Integration point for existing wizard workflow.
    
    Call this function in the wizard step where validation occurs.
    
    Args:
        wizard_state: Current wizard session state
        df: DataFrame from current wizard step
    """
    # Determine dataset type from wizard state
    dataset_type = wizard_state.get("dataset_type", "Timetable")
    
    if dataset_type == "Timetable":
        # Run timetable-specific validation
        result = validate_timetable(df)
        
        # Store in wizard state
        wizard_state["validation_result"] = result
        wizard_state["validation_errors"] = result.errors
        wizard_state["has_errors"] = len(result.errors) > 0
        
        # Render error panel
        render_validation_panel(
            df=df,
            validation_result=result,
            key_prefix=f"wizard_{dataset_type.lower()}"
        )
        
        # Return validation status
        return len(result.errors) == 0
    
    # For other dataset types, use existing validation
    return True


# Example usage in existing app.py or wizard
"""
# In your existing validation step:

from validation_integration import integrate_with_wizard

# Inside the wizard validation step:
if st.session_state.get("current_step") == "validation":
    df = st.session_state.get("uploaded_df")
    
    if df is not None:
        is_valid = integrate_with_wizard(st.session_state, df)
        
        if is_valid:
            st.success("Validation passed! You can proceed to the next step.")
            if st.button("Continue"):
                st.session_state["current_step"] = "export"
        else:
            st.warning("Please fix the errors above before proceeding.")
            
            # Option to proceed anyway
            if st.checkbox("I understand there are errors and want to proceed anyway"):
                if st.button("Continue with Warnings"):
                    st.session_state["current_step"] = "export"
"""


if __name__ == "__main__":
    # Standalone test mode
    validate_uploaded_file()
