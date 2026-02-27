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
        if "wizard_step" not in st.session_state or st.session_state.wizard_step is None:
            st.session_state.wizard_step = WizardStep.UPLOAD.value
        if "wizard_data" not in st.session_state or st.session_state.wizard_data is None:
            st.session_state.wizard_data = {}
        if "wizard_history" not in st.session_state or st.session_state.wizard_history is None:
            st.session_state.wizard_history = []
    
    def _ensure_data_dict(self) -> None:
        """Ensure wizard_data is a dictionary."""
        if st.session_state.get("wizard_data") is None:
            st.session_state.wizard_data = {}
    
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
        self._ensure_data_dict()
        return st.session_state.wizard_data
    
    def set_data(self, key: str, value: Any) -> None:
        """Set wizard data value."""
        self._ensure_data_dict()
        st.session_state.wizard_data[key] = value
    
    def get_data(self, key: str, default: Any = None) -> Any:
        """Get wizard data value."""
        self._ensure_data_dict()
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
    """Render wizard progress bar with reset option."""
    total_steps = len(WizardStep)
    current = wizard_state.current_step or 1
    progress = current / total_steps
    
    # Progress bar and reset button in same row
    col_progress, col_reset = st.columns([5, 1])
    
    with col_progress:
        st.progress(progress)
    
    with col_reset:
        if current > 1:  # Only show reset if not on first step
            if st.button("🔄 Reset", help="Start wizard from the beginning"):
                wizard_state.reset()
                # Also clear pre-loaded data reference
                if "df" in st.session_state:
                    st.session_state.df = None
                st.rerun()
    
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
    
    st.info("Map your column headers to the expected SEATS fields.")
    
    # Get expected headers from SEATS spec
    try:
        from utils.seats_data_handler import load_spec_by_type
        spec = load_spec_by_type(dataset_type)
        
        mandatory_fields = spec.get('mandatory_fields', [])
        all_fields = list(spec.get('fields', {}).keys())
        optional_fields = [f for f in all_fields if f not in mandatory_fields]
        
        expected = {
            "mandatory": mandatory_fields,
            "optional": optional_fields
        }
        
        # Show spec info
        st.markdown(f"**Dataset:** {spec.get('dataset_type', dataset_type)} v{spec.get('version', '?')}")
        st.markdown(f"**Required fields:** {len(mandatory_fields)} | **Optional fields:** {len(optional_fields)}")
        
    except ValueError:
        # Fallback if spec not found
        try:
            from utils.master_spec_loader import MasterSpecLoader
            loader = MasterSpecLoader()
            expected = loader.get_expected_headers(dataset_type)
        except Exception:
            expected = {"mandatory": [], "optional": []}
    
    current_headers = df.columns.tolist()
    all_expected = expected.get("mandatory", []) + expected.get("optional", [])
    
    # Show current columns vs expected
    st.markdown("### Column Mapping")
    
    # Auto-suggest mappings
    file_cols_set = set(current_headers)
    auto_suggestions = _suggest_column_mappings(file_cols_set, expected.get("mandatory", []))
    
    if auto_suggestions:
        st.warning("⚠️ Some columns may need renaming. Suggested mappings:")
        for file_col, spec_col in auto_suggestions.items():
            st.markdown(f"- `{file_col}` → **{spec_col}**")
    
    # Check for already matching columns
    matching = [col for col in current_headers if col in all_expected]
    missing_mandatory = [f for f in expected.get("mandatory", []) if f not in current_headers]
    
    if matching:
        st.success(f"✓ {len(matching)} columns already match spec names")
    
    if missing_mandatory:
        st.error(f"✗ {len(missing_mandatory)} mandatory columns missing: {', '.join(missing_mandatory[:5])}{'...' if len(missing_mandatory) > 5 else ''}")
    
    # Column mapping interface
    st.markdown("---")
    st.markdown("**Map each column to a SEATS field (or ignore):**")
    
    mapping = {}
    
    # Group columns: exact matches, suggested mappings, others
    cols_with_suggestions = list(auto_suggestions.keys())
    cols_exact_match = [c for c in current_headers if c in all_expected]
    cols_other = [c for c in current_headers if c not in cols_exact_match and c not in cols_with_suggestions]
    
    # Show suggested mappings first
    if cols_with_suggestions:
        st.markdown("**Columns needing attention:**")
        for col in cols_with_suggestions:
            suggested = auto_suggestions.get(col, "(ignore)")
            default_idx = all_expected.index(suggested) + 1 if suggested in all_expected else 0
            selected = st.selectbox(
                f"'{col}' →",
                options=["(ignore)"] + all_expected,
                index=default_idx,
                key=f"map_{col}"
            )
            if selected != "(ignore)":
                mapping[col] = selected
    
    # Show other columns in expander
    with st.expander(f"Other columns ({len(cols_exact_match) + len(cols_other)})"):
        for col in cols_exact_match + cols_other:
            default_idx = all_expected.index(col) + 1 if col in all_expected else 0
            selected = st.selectbox(
                f"'{col}' →",
                options=["(ignore)"] + all_expected,
                index=default_idx,
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
    """Render validation step with row-level error flagging for all dataset types."""
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
    
    # Run validation using SEATS Master Spec with row-level error detection
    with st.spinner(f"Validating {dataset_type} data against SEATS Master Spec..."):
        try:
            from utils.seats_validator import validate_dataset
            from components.validation_error_panel import render_validation_panel, export_errors_to_csv
            
            # Run validation against Master Spec
            validation_result = validate_dataset(df_mapped, dataset_type)
            
            # Store validation result for later steps
            wizard_state.set_data("validation_result", validation_result)
            wizard_state.set_data("dataframe_mapped", df_mapped)
            
            # Convert to legacy format for compatibility with other steps
            validation_results = {
                "is_valid": validation_result.to_summary()["total_errors"] == 0,
                "errors": [e.to_dict() for e in validation_result.errors],
                "warnings": validation_result.warnings,
                "schema_issues": validation_result.schema_issues,
                "total_errors": validation_result.to_summary()["total_errors"],
                "total_warnings": len(validation_result.warnings),
                "rows_affected": validation_result.to_summary()["rows_affected"],
            }
            wizard_state.set_data("validation_results", validation_results)
            
            # Render the validation error panel with cell highlighting
            render_validation_panel(
                df=df_mapped,
                validation_result=validation_result,
                key_prefix=f"wizard_{dataset_type.lower().replace(' ', '_')}"
            )
            
            # Export option
            st.markdown("---")
            export_errors_to_csv(validation_result, f"{dataset_type.lower().replace(' ', '_')}_validation_errors.csv")
            
        except ImportError as e:
            # Fallback to existing validation if new validator not available
            log_exception(e, logger, {"action": "import_validator"})
            _render_legacy_validation(wizard_state, df_mapped, dataset_type)
            
        except Exception as e:
            log_exception(e, logger, {"action": "validation"})
            st.error(f"Validation error: {str(e)}")
            validation_results = {"error": str(e), "total_errors": 1}
            wizard_state.set_data("validation_results", validation_results)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back"):
            wizard_state.previous_step()
            st.rerun()
    with col2:
        if st.button("Continue to Auto-Fix", type="primary"):
            wizard_state.next_step()
            st.rerun()


def _render_legacy_validation(wizard_state: WizardState, df_mapped: pd.DataFrame, dataset_type: str) -> None:
    """Fallback validation using existing seats_data_handler."""
    try:
        from utils.seats_data_handler import get_seats_handler, load_spec_by_type
        
        handler = get_seats_handler()
        
        try:
            spec = load_spec_by_type(dataset_type)
            results = handler.validate_against_spec(df_mapped, spec)
            
            validation_results = {
                "is_valid": results.get("is_valid", False),
                "errors": results.get("errors", []),
                "warnings": results.get("warnings", []),
                "total_errors": len(results.get("errors", [])),
                "total_warnings": len(results.get("warnings", [])),
            }
            
        except ValueError:
            from utils.validator import validate_dataframe
            results = validate_dataframe(df_mapped, dataset_type)
            validation_results = results
        
        wizard_state.set_data("validation_results", validation_results)
        wizard_state.set_data("dataframe_mapped", df_mapped)
        
        # Display results
        total_errors = validation_results.get("total_errors", 0)
        total_warnings = validation_results.get("total_warnings", 0)
        
        if total_errors == 0:
            st.success("Validation passed! No critical issues found.")
        else:
            st.error(f"Found {total_errors} validation errors.")
        
        if total_warnings > 0:
            st.warning(f"Found {total_warnings} warnings.")
        
        # Display errors
        errors = validation_results.get("errors", [])
        if errors:
            with st.expander(f"View Issues ({len(errors)})"):
                for error in errors[:20]:
                    if isinstance(error, dict):
                        st.markdown(f"- **{error.get('field', 'Unknown')}**: {error.get('message', str(error))}")
                    else:
                        st.markdown(f"- {error}")
        
        # Display warnings
        warnings = validation_results.get("warnings", [])
        if warnings:
            with st.expander(f"View Warnings ({len(warnings)})"):
                for warning in warnings[:20]:
                    if isinstance(warning, dict):
                        st.markdown(f"- **{warning.get('field', 'Unknown')}**: {warning.get('message', str(warning))}")
                    else:
                        st.markdown(f"- {warning}")
                        
    except Exception as e:
        log_exception(e, logger, {"action": "legacy_validation"})
        st.error(f"Validation error: {str(e)}")


def _suggest_column_mappings(file_cols: set, missing_cols: list) -> dict:
    """Suggest column mappings based on common naming patterns."""
    suggestions = {}
    
    # Common naming variations for all dataset types
    mapping_patterns = {
        # Timetable mappings
        'COURSE_ID': ['PROGRAM_ID', 'PROGRAMME_ID', 'PROG_ID', 'COURSE_CODE'],
        'COURSE_NAME': ['PROGRAM_NAME', 'PROGRAMME_NAME', 'PROG_NAME'],
        'MODULE_ID': ['CLASS_ID', 'SUBJECT_ID', 'UNIT_ID', 'MODULE_CODE'],
        'MODULE_NAME': ['CLASS_NAME', 'SUBJECT_NAME', 'UNIT_NAME'],
        'SCHOOL_ID': ['DEPARTMENT_ID', 'DEPT_ID', 'FACULTY_ID', 'SCHOOL_CODE'],
        'SCHOOL_NAME': ['DEPARTMENT_NAME', 'DEPT_NAME', 'FACULTY_NAME'],
        'EVENT_ID': ['EVENTID', 'TIMETABLE_ID', 'SCHEDULE_ID', 'LECTURE_ID', 'SESSION_ID'],
        
        # Student mappings
        'STUDENT_ID': ['STUDENTID', 'STU_ID', 'STUDENT_NUMBER', 'STUDENT_CODE', 'ID'],
        'STUDENT_FORENAME': ['FORENAME', 'FIRST_NAME', 'FIRSTNAME', 'GIVEN_NAME'],
        'STUDENT_LAST_NAME': ['LAST_NAME', 'LASTNAME', 'SURNAME', 'FAMILY_NAME'],
        'STUDENT_EMAIL': ['EMAIL', 'PERSONAL_EMAIL', 'STU_EMAIL'],
        'UNIVERSITY_EMAIL': ['UNI_EMAIL', 'INSTITUTIONAL_EMAIL', 'COLLEGE_EMAIL'],
        'STUDENT_LOGIN_ID': ['LOGIN_ID', 'USERNAME', 'USER_ID', 'SSO_ID'],
        'STUDENT_TELEPHONE': ['TELEPHONE', 'PHONE', 'MOBILE', 'CONTACT_NUMBER'],
        'DATE_OF_BIRTH': ['DOB', 'BIRTHDATE', 'BIRTH_DATE'],
        'VISAREQUIRED': ['VISA_REQUIRED', 'IS_TIER4', 'TIER4', 'INTERNATIONAL'],
        'BADGE_NUMBER': ['BADGE_ID', 'CARD_NUMBER', 'CARD_ID'],
        'CTY_NATIONALITY': ['NATIONALITY', 'COUNTRY_NATIONALITY'],
        'CTY_DOMICILE': ['DOMICILE', 'HOME_COUNTRY', 'COUNTRY_DOMICILE'],
        'CTY_BIRTH': ['COUNTRY_OF_BIRTH', 'BIRTH_COUNTRY'],
        'STUDENT_MOA': ['MODE_OF_ATTENDANCE', 'ATTENDANCE_MODE', 'MOA'],
        'STUDENT_STATUS': ['STATUS', 'ENROLMENT_STATUS', 'ENROLLMENT_STATUS'],
        'ADMIN_AREA': ['EDUCATION_LEVEL', 'LEVEL', 'STUDY_LEVEL'],
        'FEE_CATEGORY': ['FEE_STATUS', 'FEE_TYPE'],
        
        # Staff mappings
        'STAFF_NUMBER': ['STAFF_ID', 'STAFFID', 'EMPLOYEE_ID', 'EMP_ID', 'STAFF_CODE'],
        'FORENAME': ['FIRST_NAME', 'FIRSTNAME', 'GIVEN_NAME'],
        'LAST_NAME': ['LASTNAME', 'SURNAME', 'FAMILY_NAME'],
        'STAFF_TYPE': ['STAFFTYPE', 'ROLE', 'JOB_TYPE', 'POSITION'],
        'LOGIN_ID': ['USERNAME', 'USER_ID', 'SSO_ID', 'STAFF_LOGIN'],
        'EMAIL': ['PERSONAL_EMAIL', 'STAFF_EMAIL'],
        'TELEPHONE': ['PHONE', 'MOBILE', 'CONTACT_NUMBER'],
        'EXTERNAL_KEY': ['EXTERNAL_ID', 'EXT_KEY', 'ACCESS_PROFILE_KEY'],
    }
    
    # Track which file columns have been used to avoid duplicate mappings
    used_file_cols = set()
    
    for missing_col in missing_cols:
        if missing_col in mapping_patterns:
            for pattern in mapping_patterns[missing_col]:
                # Check case-insensitive
                for file_col in file_cols:
                    if file_col.upper() == pattern.upper() and file_col not in used_file_cols:
                        suggestions[file_col] = missing_col
                        used_file_cols.add(file_col)
                        break
                if missing_col in [v for v in suggestions.values()]:
                    break
    
    return suggestions


def render_step_autofix(wizard_state: WizardState) -> None:
    """Render auto-fix step."""
    st.subheader("Step 5: Auto-Fix Issues")
    
    results = wizard_state.get_data("validation_results", {})
    df = wizard_state.get_data("dataframe_mapped")
    dataset_type = wizard_state.get_data("dataset_type")
    
    if df is None:
        st.error("No data loaded. Please go back to upload.")
        return
    
    # Load spec to check for missing columns
    try:
        from utils.seats_data_handler import (
            load_spec_by_type,
            get_missing_columns,
            get_ordered_fields
        )
        spec = load_spec_by_type(dataset_type)
        missing_cols = get_missing_columns(df, spec)
        mandatory_fields = spec.get('mandatory_fields', [])
        missing_mandatory = [col for col in missing_cols if col in mandatory_fields]
        missing_optional = [col for col in missing_cols if col not in mandatory_fields]
    except Exception as e:
        log_exception(e, logger, {"action": "load_spec_for_autofix"})
        spec = None
        missing_cols = []
        missing_mandatory = []
        missing_optional = []
    
    has_validation_errors = results and results.get("total_errors", 0) > 0
    has_missing_columns = len(missing_cols) > 0
    
    if not has_validation_errors and not has_missing_columns:
        st.success("No issues to fix. You can proceed to review.")
    else:
        st.info("Select which issues to auto-fix:")
        
        # Section 1: Missing Columns
        if has_missing_columns:
            st.markdown("#### Missing Columns")
            
            if missing_mandatory:
                st.warning(f"**{len(missing_mandatory)} mandatory column(s) missing:** {', '.join(missing_mandatory)}")
            
            if missing_optional:
                st.caption(f"{len(missing_optional)} optional column(s) missing: {', '.join(missing_optional[:5])}{'...' if len(missing_optional) > 5 else ''}")
            
            fix_missing_cols = st.checkbox(
                f"Insert {len(missing_cols)} missing column(s) in correct spec order",
                value=len(missing_mandatory) > 0,
                help="Adds empty columns for all missing fields in the position defined by the SEATS spec"
            )
            
            if fix_missing_cols:
                # Show which columns will be added
                with st.expander("Columns to be inserted", expanded=False):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Mandatory:**")
                        for col in missing_mandatory:
                            st.write(f"- {col}")
                        if not missing_mandatory:
                            st.write("None")
                    with col2:
                        st.markdown("**Optional:**")
                        for col in missing_optional[:10]:
                            st.write(f"- {col}")
                        if len(missing_optional) > 10:
                            st.write(f"... and {len(missing_optional) - 10} more")
                        if not missing_optional:
                            st.write("None")
        else:
            fix_missing_cols = False
        
        st.markdown("---")
        
        # Section 2: Data Fixes
        st.markdown("#### Data Fixes")
        fix_whitespace = st.checkbox("Trim whitespace", value=True)
        fix_case = st.checkbox("Standardize case (uppercase for enum fields)", value=True)
        fix_dates = st.checkbox("Fix date formats", value=True)
        
        if st.button("Apply Fixes", type="primary"):
            with st.spinner("Applying fixes..."):
                try:
                    df_fixed = df.copy()
                    fixes_applied = []
                    
                    # Fix 1: Insert missing columns
                    if fix_missing_cols and spec:
                        from utils.seats_data_handler import insert_missing_columns
                        df_fixed = insert_missing_columns(df_fixed, spec)
                        fixes_applied.append(f"Inserted {len(missing_cols)} missing columns")
                    
                    # Fix 2: Trim whitespace
                    if fix_whitespace:
                        for col in df_fixed.select_dtypes(include=["object"]).columns:
                            df_fixed[col] = df_fixed[col].astype(str).str.strip()
                            # Replace 'nan' strings with empty
                            df_fixed[col] = df_fixed[col].replace('nan', '')
                        fixes_applied.append("Trimmed whitespace")
                    
                    # Fix 3: Standardize case for enum fields
                    if fix_case and spec:
                        fields_spec = spec.get('fields', {})
                        for field_name, field_def in fields_spec.items():
                            if field_def.get('type') == 'enum':
                                # Find matching column (case-insensitive)
                                matching_col = None
                                for col in df_fixed.columns:
                                    if col.upper() == field_name.upper():
                                        matching_col = col
                                        break
                                
                                if matching_col and matching_col in df_fixed.columns:
                                    df_fixed[matching_col] = df_fixed[matching_col].astype(str).str.upper()
                                    df_fixed[matching_col] = df_fixed[matching_col].replace('NAN', '')
                        fixes_applied.append("Standardized case for enum fields")
                    
                    # Fix 4: Date formats
                    if fix_dates and spec:
                        fields_spec = spec.get('fields', {})
                        for field_name, field_def in fields_spec.items():
                            if field_def.get('type') == 'date':
                                # Find matching column
                                matching_col = None
                                for col in df_fixed.columns:
                                    if col.upper() == field_name.upper():
                                        matching_col = col
                                        break
                                
                                if matching_col and matching_col in df_fixed.columns:
                                    try:
                                        # Try to parse and reformat dates
                                        date_col = pd.to_datetime(
                                            df_fixed[matching_col],
                                            errors='coerce',
                                            dayfirst=True
                                        )
                                        # Format as YYYY-MM-DD
                                        df_fixed[matching_col] = date_col.dt.strftime('%Y-%m-%d')
                                        df_fixed[matching_col] = df_fixed[matching_col].fillna('')
                                    except Exception:
                                        pass  # Skip if date parsing fails
                        fixes_applied.append("Standardized date formats")
                    
                    wizard_state.set_data("dataframe_fixed", df_fixed)
                    
                    # Show summary
                    st.success(f"Fixes applied successfully!")
                    for fix in fixes_applied:
                        st.write(f"- {fix}")
                    
                    # Show preview of fixed data
                    st.markdown("#### Preview of Fixed Data")
                    st.dataframe(df_fixed.head(10))
                    
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
    """Render export step with validation warning."""
    st.subheader("Step 7: Export Data")
    
    df = wizard_state.get_data("dataframe_final")
    validation_results = wizard_state.get_data("validation_results", {})
    
    if df is None:
        st.error("No data to export.")
        return
    
    # Check for validation errors
    total_errors = validation_results.get("total_errors", 0)
    has_errors = total_errors > 0
    
    # Show warning if there are validation errors
    if has_errors:
        st.warning(f"⚠️ This data has {total_errors} validation error(s) that were not fixed.")
        
        # Use session state to track if user acknowledged the warning
        warning_key = "export_warning_acknowledged"
        if warning_key not in st.session_state:
            st.session_state[warning_key] = False
        
        if not st.session_state[warning_key]:
            st.error("Please acknowledge the warning before exporting.")
            if st.button("I understand, proceed with export anyway", type="secondary"):
                st.session_state[warning_key] = True
                st.rerun()
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Back to Review"):
                    wizard_state.previous_step()
                    st.rerun()
            with col2:
                if st.button("Back to Auto-Fix"):
                    wizard_state.current_step = WizardStep.AUTO_FIX.value
                    st.rerun()
            return
    
    # Export options
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
            
            # Reset warning acknowledgment for next time
            if "export_warning_acknowledged" in st.session_state:
                del st.session_state["export_warning_acknowledged"]
            
        except Exception as e:
            log_exception(e, logger, {"action": "export"})
            st.error(f"Export error: {str(e)}")
    
    st.markdown("---")
    if st.button("Start Over"):
        # Reset warning acknowledgment
        if "export_warning_acknowledged" in st.session_state:
            del st.session_state["export_warning_acknowledged"]
        wizard_state.reset()
        st.rerun()


def run_wizard() -> None:
    """
    Run the data validation wizard.
    
    Main entry point for the wizard workflow.
    Handles multiple entry scenarios:
    - Fresh start (no data) -> Step 1
    - Pre-loaded from Data Upload -> Skip to Step 2
    - Return mid-wizard -> Resume at last step
    - Session lost mid-wizard -> Reset to Step 1
    """
    st.title("Data Validation Wizard")
    st.markdown("---")
    
    wizard_state = WizardState()
    
    # Check if data was pre-loaded from Data Upload page
    pre_loaded_df = st.session_state.get("df")
    wizard_df = wizard_state.get_data("dataframe")
    
    # SAFEGUARD: If we're past step 1 but have no data, reset to step 1
    # This handles browser refresh / session loss scenarios
    if wizard_state.current_step > WizardStep.UPLOAD.value and wizard_df is None and pre_loaded_df is None:
        st.warning("Session data was lost. Please upload your data again.")
        wizard_state.reset()
        st.rerun()
    
    # If we have pre-loaded data but wizard doesn't have it yet, transfer it
    if pre_loaded_df is not None and wizard_df is None:
        wizard_state.set_data("dataframe", pre_loaded_df)
        wizard_state.set_data("filename", "Uploaded from Data Upload page")
        wizard_state.set_data("original_columns", pre_loaded_df.columns.tolist())
        # Skip to dataset selection step
        if wizard_state.current_step == WizardStep.UPLOAD.value:
            wizard_state.current_step = WizardStep.DATASET_SELECT.value
            st.rerun()
    
    # Sync wizard data back to session state for Data Analysis page
    final_df = wizard_state.get_data("dataframe_final")
    if final_df is not None:
        st.session_state.df = final_df
    elif wizard_state.get_data("dataframe_fixed") is not None:
        st.session_state.df = wizard_state.get_data("dataframe_fixed")
    elif wizard_state.get_data("dataframe_mapped") is not None:
        st.session_state.df = wizard_state.get_data("dataframe_mapped")
    elif wizard_df is not None:
        st.session_state.df = wizard_df
    
    # Sync validation results
    validation_results = wizard_state.get_data("validation_results")
    if validation_results:
        st.session_state.validation_results = validation_results
    
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
