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

            # Repair the known SEAtS template quirk (blank BADGENUMBER header) and
            # strip stray header whitespace before anything else touches the data.
            from utils.integrity_checks import heal_headers
            df.columns = heal_headers(list(df.columns))

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
    """Render dataset selection step with hierarchy configuration."""
    st.subheader("Step 2: Select Dataset Type & Configure Hierarchy")
    
    from config.config import DATASET_TYPES
    
    # Tab layout for cleaner organization
    tab1, tab2 = st.tabs(["📁 Dataset Type", "🏛️ Data Hierarchy"])
    
    with tab1:
        st.markdown("#### Select Your Dataset Type")
        
        dataset_type = st.selectbox(
            "What type of data is this?",
            options=DATASET_TYPES,
            help="Select the dataset type that matches your data"
        )
        
        wizard_state.set_data("dataset_type", dataset_type)
        
        # Show dataset info
        dataset_info = {
            "Student": "Student enrollment data including demographics, courses, and modules",
            "StudentTimetable": "Timetable/schedule data linking students to events, rooms, and times",
            "Staff": "Staff/instructor information and assignments"
        }
        
        if dataset_type in dataset_info:
            st.info(f"**{dataset_type}:** {dataset_info[dataset_type]}")
        
        # Show preview of uploaded data
        df = wizard_state.get_data("dataframe")
        if df is not None:
            with st.expander(f"Preview: {wizard_state.get_data('filename', 'data')}", expanded=False):
                st.dataframe(df.head(5))
                st.caption(f"{len(df):,} rows, {len(df.columns)} columns")

        # --- Custom dataset from a SEAtS template (ported from v2.1) ---
        st.markdown("#### Or define the dataset from a SEAtS template")
        st.caption(
            "Drop in a SEAtS template spreadsheet to derive the expected columns "
            "automatically — headers highlighted green are detected as mandatory. "
            "This overrides the built-in spec and unlocks dataset types that have "
            "no bundled JSON spec."
        )
        template_file = st.file_uploader(
            "Upload a SEAtS template (.xlsx or .csv)",
            type=["xlsx", "csv"],
            key="custom_template_upload",
        )
        if template_file is not None:
            try:
                from utils.template_spec import derive_spec_from_template
                custom_spec = derive_spec_from_template(
                    template_file.getvalue(),
                    dataset_type=dataset_type,
                    filename=template_file.name,
                )
                wizard_state.set_data("custom_spec", custom_spec)
                st.success(
                    f"Custom spec active from '{template_file.name}': "
                    f"{len(custom_spec['fields'])} fields, "
                    f"{len(custom_spec['mandatory_fields'])} mandatory."
                )
            except Exception as exc:
                log_exception(exc, logger, {"action": "derive_custom_spec"})
                st.error(f"Could not read that template: {exc}")
        if wizard_state.get_data("custom_spec"):
            if st.button("Clear custom spec"):
                wizard_state.set_data("custom_spec", None)
                st.rerun()

    with tab2:
        try:
            from utils.hierarchy_config import (
                render_hierarchy_quick_select,
                render_hierarchy_mapping,
                render_hierarchy_explanation
            )
            
            # Check if user wants explanation
            show_help = st.checkbox("Show hierarchy explanation", value=True, key="show_hierarchy_help")
            
            if show_help:
                render_hierarchy_explanation()
                st.markdown("---")
            
            # Quick preset selector
            render_hierarchy_quick_select(wizard_state)
            
            st.markdown("---")
            
            # Detailed mapping (collapsed by default if preset was selected)
            with st.expander("⚙️ Advanced: Customize Hierarchy Levels", expanded=False):
                render_hierarchy_mapping(wizard_state, show_explanation=False)
            
        except ImportError as e:
            st.warning("Hierarchy configuration module not available.")
            log_exception(e, logger, {"action": "load_hierarchy_config"})
    
    # Navigation
    st.markdown("---")
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
    """Render header mapping step with SIS auto-detection."""
    st.subheader("Step 3: Map Headers")
    
    df = wizard_state.get_data("dataframe")
    dataset_type = wizard_state.get_data("dataset_type")
    
    if df is None:
        st.error("No data loaded. Please go back to upload.")
        return
    
    # Get expected headers from SEATS spec (a custom/template spec wins).
    custom_spec = wizard_state.get_data("custom_spec")
    try:
        if custom_spec:
            spec = custom_spec
        else:
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
        # No built-in spec for this dataset type. Custom/template-derived specs
        # (see utils.template_spec) are loaded by load_spec_by_type when present;
        # if none is available we proceed with an empty expectation set so the user
        # can still map and inspect columns rather than hitting a dead fallback.
        expected = {"mandatory": [], "optional": []}
        spec = None
    
    current_headers = df.columns.tolist()
    all_expected = expected.get("mandatory", []) + expected.get("optional", [])
    
    # ============================================
    # Hierarchy-Based Column Detection
    # ============================================
    hierarchy_config = wizard_state.get_data("hierarchy_config")
    hierarchy_mappings = {}
    
    if hierarchy_config:
        try:
            from utils.hierarchy_config import get_column_mappings_from_hierarchy
            
            hierarchy_mappings = get_column_mappings_from_hierarchy(
                hierarchy_config,
                current_headers
            )
            
            if hierarchy_mappings:
                st.markdown("### Hierarchy-Based Mappings")
                st.success(f"✓ Found {len(hierarchy_mappings)} mappings from your hierarchy configuration")
                
                with st.expander("Hierarchy column mappings", expanded=False):
                    for src, dst in hierarchy_mappings.items():
                        st.write(f"- `{src}` → **{dst}**")
                
                # Apply hierarchy mappings button
                if st.button("🏛️ Apply Hierarchy Mappings", key="apply_hierarchy"):
                    existing = wizard_state.get_data("header_mapping", {})
                    combined = {**existing, **hierarchy_mappings}
                    wizard_state.set_data("header_mapping", combined)
                    wizard_state.set_data("hierarchy_mappings_applied", True)
                    st.success(f"Applied {len(hierarchy_mappings)} hierarchy mappings!")
                    st.rerun()
                
                st.markdown("---")
                
        except Exception as e:
            log_exception(e, logger, {"action": "hierarchy_column_mapping"})
    
    # ============================================
    # SIS Auto-Detection Section
    # ============================================
    st.markdown("### SIS System Detection")
    
    try:
        from utils.sis_mapper import (
            SISMapper, SISType, detect_sis_type, 
            suggest_mappings, transform_to_seats
        )
        
        # Auto-detect SIS type
        detection_result = detect_sis_type(df)
        sis_mapper = SISMapper()
        
        # Store detection result
        wizard_state.set_data("sis_detection", detection_result)
        
        # Display detection result
        sis_icons = {
            SISType.BANNER: "🏛️",
            SISType.PEOPLESOFT: "☀️",
            SISType.WORKDAY: "📊",
            SISType.COLLEAGUE: "🎓",
            SISType.JENZABAR: "📚",
            SISType.GENERIC: "📋",
            SISType.UNKNOWN: "❓"
        }
        
        sis_names = {
            SISType.BANNER: "Ellucian Banner",
            SISType.PEOPLESOFT: "Oracle PeopleSoft",
            SISType.WORKDAY: "Workday Student",
            SISType.COLLEAGUE: "Ellucian Colleague",
            SISType.JENZABAR: "Jenzabar",
            SISType.GENERIC: "Generic/Unknown",
            SISType.UNKNOWN: "Unknown"
        }
        
        detected_type = detection_result.detected_type
        confidence_pct = int(detection_result.confidence * 100)
        
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.markdown(f"**Detected SIS:** {sis_icons.get(detected_type, '📋')} {sis_names.get(detected_type, 'Unknown')}")
        with col2:
            st.markdown(f"**Confidence:** {confidence_pct}%")
        with col3:
            if detection_result.matched_indicators:
                st.markdown(f"**Matched:** {len(detection_result.matched_indicators)} patterns")
        
        if detection_result.matched_indicators:
            with st.expander("Detected patterns", expanded=False):
                st.write(", ".join(detection_result.matched_indicators))
        
        # SIS Mapping Options
        st.markdown("---")
        
        # Get SIS-based mapping suggestions
        sis_suggestions = suggest_mappings(df, detected_type)
        high_confidence_mappings = [m for m in sis_suggestions if m.confidence >= 0.6]
        
        if high_confidence_mappings:
            st.success(f"✓ Found {len(high_confidence_mappings)} column mappings from {sis_names.get(detected_type, 'SIS')}")
            
            # Show mapping preview
            with st.expander(f"Preview SIS mappings ({len(high_confidence_mappings)} columns)", expanded=True):
                for mapping in high_confidence_mappings[:15]:
                    conf_icon = "🟢" if mapping.confidence >= 0.8 else "🟡"
                    st.markdown(f"{conf_icon} `{mapping.source_column}` → **{mapping.target_column}** ({int(mapping.confidence*100)}%)")
                if len(high_confidence_mappings) > 15:
                    st.caption(f"... and {len(high_confidence_mappings) - 15} more")
            
            # Apply SIS mappings button
            if st.button("🔄 Apply SIS Mappings", type="primary", key="apply_sis"):
                # Build mapping dict from SIS suggestions
                sis_mapping = {}
                for m in high_confidence_mappings:
                    if m.source_column not in sis_mapping:
                        sis_mapping[m.source_column] = m.target_column
                
                wizard_state.set_data("header_mapping", sis_mapping)
                wizard_state.set_data("sis_mappings_applied", True)
                st.success(f"Applied {len(sis_mapping)} SIS mappings!")
                st.rerun()
            
            # Check if mappings were already applied
            if wizard_state.get_data("sis_mappings_applied"):
                st.info("✓ SIS mappings have been applied. Review below or continue to validation.")
        
        else:
            st.info("No high-confidence SIS mappings found. Use manual mapping below.")
        
        sis_available = True
        
    except ImportError as e:
        st.warning("SIS auto-detection not available. Using manual mapping.")
        sis_available = False
    except Exception as e:
        st.warning(f"SIS detection error: {str(e)}. Using manual mapping.")
        sis_available = False
    
    # ============================================
    # Manual Column Mapping Section
    # ============================================
    st.markdown("---")
    st.markdown("### Manual Column Mapping")
    st.caption("Map your columns to SEATS fields. Columns already mapped via SIS detection are pre-selected.")
    
    # Get any existing mappings (from SIS or previous manual selection)
    existing_mapping = wizard_state.get_data("header_mapping", {})

    # Persisted mapping memory (ported from v2.1): if we've mapped a file with this
    # exact set of headings before, pre-fill those choices automatically.
    from utils.mapping_memory import mapping_signature, get_saved_mapping
    _mm_sig = mapping_signature(wizard_state.get_data("dataset_type") or "", current_headers)
    if not existing_mapping and wizard_state.get_data("mapping_seeded_sig") != _mm_sig:
        _saved_mapping = get_saved_mapping(_mm_sig)
        if _saved_mapping:
            existing_mapping = dict(_saved_mapping)
            wizard_state.set_data("header_mapping", existing_mapping)
            wizard_state.set_data("mapping_seeded_sig", _mm_sig)
            st.info("↩ Applied a remembered mapping for this file layout.")

    # Auto-suggest additional mappings using legacy method
    file_cols_set = set(current_headers)
    auto_suggestions = _suggest_column_mappings(file_cols_set, expected.get("mandatory", []))
    
    # Merge with existing mappings (existing takes priority)
    combined_suggestions = {**auto_suggestions, **existing_mapping}
    
    if auto_suggestions and not existing_mapping:
        st.warning("⚠️ Some columns may need renaming. Suggested mappings:")
        for file_col, spec_col in list(auto_suggestions.items())[:5]:
            st.markdown(f"- `{file_col}` → **{spec_col}**")
    
    # Check for already matching columns
    matching = [col for col in current_headers if col in all_expected]
    missing_mandatory = [f for f in expected.get("mandatory", []) if f not in current_headers and f not in existing_mapping.values()]
    
    col1, col2 = st.columns(2)
    with col1:
        if matching:
            st.success(f"✓ {len(matching)} columns match spec")
    with col2:
        if missing_mandatory:
            st.error(f"✗ {len(missing_mandatory)} mandatory missing")
    
    # Column mapping interface
    st.markdown("**Map each column:**")
    
    mapping = {}
    
    # Group columns by status
    cols_mapped_by_sis = [c for c in current_headers if c in existing_mapping]
    cols_exact_match = [c for c in current_headers if c in all_expected and c not in cols_mapped_by_sis]
    cols_with_suggestions = [c for c in auto_suggestions.keys() if c not in cols_mapped_by_sis and c not in cols_exact_match]
    cols_other = [c for c in current_headers if c not in cols_mapped_by_sis and c not in cols_exact_match and c not in cols_with_suggestions]
    
    # Show SIS-mapped columns first (if any)
    if cols_mapped_by_sis:
        with st.expander(f"SIS-mapped columns ({len(cols_mapped_by_sis)})", expanded=False):
            for col in cols_mapped_by_sis:
                mapped_to = existing_mapping.get(col, col)
                default_idx = all_expected.index(mapped_to) + 1 if mapped_to in all_expected else 0
                selected = st.selectbox(
                    f"'{col}' →",
                    options=["(ignore)"] + all_expected,
                    index=default_idx,
                    key=f"map_{col}"
                )
                if selected != "(ignore)":
                    mapping[col] = selected
    
    # Show columns needing attention
    if cols_with_suggestions:
        st.markdown("**Columns needing attention:**")
        for col in cols_with_suggestions:
            suggested = combined_suggestions.get(col, "(ignore)")
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
    other_cols = cols_exact_match + cols_other
    if other_cols:
        with st.expander(f"Other columns ({len(other_cols)})"):
            for col in other_cols:
                default_idx = all_expected.index(col) + 1 if col in all_expected else 0
                selected = st.selectbox(
                    f"'{col}' →",
                    options=["(ignore)"] + all_expected,
                    index=default_idx,
                    key=f"map_{col}"
                )
                if selected != "(ignore)":
                    mapping[col] = selected
    
    # Merge manual selections with SIS mappings
    final_mapping = {**existing_mapping, **mapping}
    wizard_state.set_data("header_mapping", final_mapping)
    
    # Navigation
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back"):
            wizard_state.previous_step()
            st.rerun()
    with col2:
        if st.button("Continue to Validation", type="primary"):
            # Remember this mapping for the next file with the same headings.
            try:
                from utils.mapping_memory import mapping_signature, save_mapping
                save_mapping(
                    mapping_signature(wizard_state.get_data("dataset_type") or "", current_headers),
                    final_mapping,
                )
            except Exception as exc:  # best-effort; never block the wizard
                log_exception(exc, logger, {"action": "save_mapping_memory"})
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
            from utils.data_quality import analyze_data_quality, DataQualityReport
            from utils.seats_data_handler import load_spec_by_type
            
            # Prefer a custom/template-derived spec if the user supplied one
            # (utils.template_spec); otherwise load the built-in v8.2 spec.
            custom_spec = wizard_state.get_data("custom_spec")
            if custom_spec:
                spec = custom_spec
            else:
                try:
                    spec = load_spec_by_type(dataset_type)
                except Exception:
                    spec = None

            # Run SEATS spec validation
            validation_result = validate_dataset(df_mapped, dataset_type, spec=spec)
            
            # Run data quality analysis
            quality_report = analyze_data_quality(df_mapped, spec)
            
            # Store results for later steps
            wizard_state.set_data("validation_result", validation_result)
            wizard_state.set_data("quality_report", quality_report)
            wizard_state.set_data("dataframe_mapped", df_mapped)
            
            # Convert to legacy format for compatibility with other steps
            # Schema issues (missing columns, wrong order) are errors that block export
            has_schema_errors = len(validation_result.schema_issues) > 0
            has_row_errors = validation_result.to_summary()["total_errors"] > 0
            validation_results = {
                "is_valid": not has_schema_errors and not has_row_errors,
                "errors": [e.to_dict() for e in validation_result.errors],
                "warnings": validation_result.warnings,
                "schema_issues": validation_result.schema_issues,
                "total_errors": validation_result.to_summary()["total_errors"],
                "total_schema_errors": len(validation_result.schema_issues),
                "total_warnings": len(validation_result.warnings),
                "rows_affected": validation_result.to_summary()["rows_affected"],
            }
            wizard_state.set_data("validation_results", validation_results)

            # --- Cross-row integrity checks (ported from SEAtS Validator v2.1) ---
            from utils.integrity_checks import run_all as run_integrity_checks
            integrity_issues = run_integrity_checks(df_mapped, dataset_type)
            wizard_state.set_data("integrity_issues", integrity_issues)
            st.markdown("### Cross-row Integrity Checks")
            if integrity_issues:
                i_err = sum(1 for i in integrity_issues if i["type"] == "error")
                col1, col2 = st.columns(2)
                col1.metric("Integrity errors", i_err)
                col2.metric("Integrity warnings", len(integrity_issues) - i_err)
                st.dataframe(
                    pd.DataFrame(integrity_issues)[["row", "field", "type", "message"]],
                    use_container_width=True,
                )
            else:
                st.success("No cross-row integrity issues found.")

            # --- Profile the data before export (ported from v2.1) ---
            from utils.data_profile import profile_dataframe
            profile_cards = profile_dataframe(df_mapped, dataset_type)
            if profile_cards:
                st.markdown("### Data Profile")
                st.caption("Sanity-check the entity counts before exporting.")
                cols = st.columns(min(4, len(profile_cards)))
                for idx, card in enumerate(profile_cards):
                    with cols[idx % len(cols)]:
                        st.metric(card["label"], f"{card['count']:,}")
                        if card["kind"] == "values" and card["values"]:
                            with st.expander("View values"):
                                st.write(", ".join(str(v) for v in card["values"][:200]))

            # Display Data Quality Issues first
            quality_summary = quality_report.to_summary()
            if quality_summary["total_issues"] > 0:
                st.markdown("### Data Quality Issues")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Issues", quality_summary["total_issues"])
                with col2:
                    st.metric("Auto-Fixable", quality_summary["fixable_issues"])
                with col3:
                    errors = quality_summary["by_severity"].get("error", 0)
                    st.metric("Errors", errors)
                with col4:
                    warnings = quality_summary["by_severity"].get("warning", 0)
                    st.metric("Warnings", warnings)
                
                # Issues by type
                with st.expander("Issues by Type", expanded=False):
                    for issue_type, count in quality_summary["by_type"].items():
                        icon = {
                            "id_field": "🔢",
                            "date_time": "📅",
                            "text_encoding": "📝",
                            "multi_value": "📋",
                            "enum_field": "📊",
                            "structural": "🏗️"
                        }.get(issue_type, "❓")
                        st.write(f"{icon} **{issue_type.replace('_', ' ').title()}**: {count} issue(s)")
                
                # Sample issues
                with st.expander("Sample Issues (first 20)", expanded=False):
                    for issue in quality_report.issues[:20]:
                        severity_color = {
                            "error": "🔴",
                            "warning": "🟡",
                            "info": "🔵"
                        }.get(issue.severity.value, "⚪")
                        
                        row_info = f"Row {issue.row_index}" if issue.row_index is not None else "All rows"
                        col_info = f"[{issue.column}]" if issue.column else ""
                        fix_info = f" → Fix: `{issue.suggested_fix}`" if issue.can_auto_fix and issue.suggested_fix else ""
                        
                        st.markdown(f"{severity_color} **{row_info}** {col_info}: {issue.message}{fix_info}")
                
                st.markdown("---")
            
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
            
            # Build detailed error breakdown
            errors_list = results.get("errors", [])
            errors_by_column = {}
            errors_by_type = {}
            sample_errors = []
            
            for err in errors_list:
                if isinstance(err, dict):
                    col = err.get("field", err.get("column", "Unknown"))
                    err_type = err.get("type", err.get("error_type", "Validation Error"))
                    
                    errors_by_column[col] = errors_by_column.get(col, 0) + 1
                    errors_by_type[err_type] = errors_by_type.get(err_type, 0) + 1
                    
                    if len(sample_errors) < 10:
                        sample_errors.append({
                            "row": err.get("row", err.get("row_index", "?")),
                            "column": col,
                            "message": err.get("message", str(err)),
                            "value": err.get("value", err.get("current_value", ""))
                        })
            
            validation_results = {
                "is_valid": results.get("is_valid", False),
                "errors": errors_list,
                "warnings": results.get("warnings", []),
                "total_errors": len(errors_list),
                "total_warnings": len(results.get("warnings", [])),
                "errors_by_column": errors_by_column,
                "errors_by_type": errors_by_type,
                "sample_errors": sample_errors
            }
            
        except ValueError:
            # No SEAtS spec available for this dataset type — spec validation is
            # skipped rather than falling back to a removed legacy validator.
            validation_results = {
                "is_valid": True,
                "errors": [],
                "warnings": [],
                "total_errors": 0,
                "total_warnings": 0,
                "errors_by_column": {},
                "errors_by_type": {},
                "sample_errors": [],
                "message": f"No SEAtS spec available for '{dataset_type}'; spec validation skipped.",
            }
        
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
    quality_report = wizard_state.get_data("quality_report")
    
    if df is None:
        st.error("No data loaded. Please go back to upload.")
        return
    
    # Load spec and analyze column issues
    try:
        from utils.seats_data_handler import (
            load_spec_by_type,
            get_missing_columns,
            get_ordered_fields,
            detect_column_variations,
            detect_duplicate_columns,
            detect_out_of_spec_columns,
            fix_column_names_and_order
        )
        from utils.data_quality import (
            analyze_data_quality,
            fix_data_quality,
            DataQualityFixer,
            IssueType
        )
        
        spec = load_spec_by_type(dataset_type)
        missing_cols = get_missing_columns(df, spec)
        variations = detect_column_variations(df, spec)
        duplicates = detect_duplicate_columns(df, spec)
        out_of_spec = detect_out_of_spec_columns(df, spec)
        mandatory_fields = spec.get('mandatory_fields', [])
        missing_mandatory = [col for col in missing_cols if col in mandatory_fields]
        missing_optional = [col for col in missing_cols if col not in mandatory_fields]
        
        # Re-analyze quality if not available
        if quality_report is None:
            quality_report = analyze_data_quality(df, spec)
            wizard_state.set_data("quality_report", quality_report)
        
    except Exception as e:
        log_exception(e, logger, {"action": "load_spec_for_autofix"})
        spec = None
        missing_cols = []
        missing_mandatory = []
        missing_optional = []
        variations = {}
        duplicates = {}
        out_of_spec = []
        quality_report = None
    
    has_validation_errors = results and results.get("total_errors", 0) > 0
    has_column_issues = len(missing_cols) > 0 or len(variations) > 0 or len(duplicates) > 0
    has_quality_issues = quality_report and quality_report.to_summary()["total_issues"] > 0
    
    if not has_validation_errors and not has_column_issues and not has_quality_issues:
        st.success("No issues to fix. You can proceed to review.")
    else:
        st.info("Select which issues to auto-fix:")
        
        # ============================================
        # Section 1: Column Structure Fixes
        # ============================================
        if has_column_issues or out_of_spec:
            st.markdown("#### Column Structure Fixes")
            
            # 1a: Column variations (e.g., STUDENT_ID_x -> STUDENT_ID)
            fix_variations = False
            if variations:
                st.warning(f"**{len(variations)} column(s) detected as variations** of spec columns")
                fix_variations = st.checkbox(
                    f"Rename {len(variations)} column variation(s) to correct spec names",
                    value=True,
                    help="Columns like 'STUDENT_ID_x' will be renamed to 'STUDENT_ID'"
                )
                if fix_variations:
                    with st.expander("Column variations to rename", expanded=False):
                        for old_col, (new_col, reason) in variations.items():
                            st.write(f"- `{old_col}` → `{new_col}` ({reason})")
            
            # 1b: Duplicate columns
            fix_duplicates = False
            if duplicates:
                st.warning(f"**{len(duplicates)} spec field(s) have duplicate columns**")
                fix_duplicates = st.checkbox(
                    f"Remove duplicate columns (keep column with most data)",
                    value=True,
                    help="When multiple columns map to the same spec field, keeps the one with most non-empty values"
                )
                if fix_duplicates:
                    with st.expander("Duplicate columns to resolve", expanded=False):
                        for spec_field, dup_cols in duplicates.items():
                            st.write(f"- **{spec_field}**: {', '.join([f'`{c}`' for c in dup_cols])}")
            
            # 1c: Missing columns (ALL spec columns are required)
            fix_missing_cols = False
            if missing_cols:
                st.error(
                    f"**{len(missing_cols)} required column(s) missing.** "
                    f"All columns in the spec must be present in the file."
                )
                if missing_mandatory:
                    st.write(f"Mandatory value fields: {', '.join(missing_mandatory)}")
                if missing_optional:
                    st.write(f"Blank-allowed fields: {', '.join(missing_optional[:10])}"
                             f"{'...' if len(missing_optional) > 10 else ''}")
                
                fix_missing_cols = st.checkbox(
                    f"Insert {len(missing_cols)} missing column(s) in correct spec order",
                    value=True,
                    help="Adds empty columns for all missing fields in the position defined by the SEATS spec"
                )
                if fix_missing_cols:
                    with st.expander("Columns to be inserted", expanded=False):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**Mandatory (values required):**")
                            for col in missing_mandatory:
                                st.write(f"- {col}")
                            if not missing_mandatory:
                                st.write("None")
                        with col2:
                            st.markdown("**Non-mandatory (values can be blank):**")
                            for col in missing_optional[:10]:
                                st.write(f"- {col}")
                            if len(missing_optional) > 10:
                                st.write(f"... and {len(missing_optional) - 10} more")
                            if not missing_optional:
                                st.write("None")
            
            # 1d: Out of spec columns
            fix_out_of_spec = False
            if out_of_spec:
                st.info(f"**{len(out_of_spec)} column(s) not in spec:** {', '.join(out_of_spec[:5])}{'...' if len(out_of_spec) > 5 else ''}")
                fix_out_of_spec = st.checkbox(
                    f"Remove {len(out_of_spec)} column(s) not in spec",
                    value=False,
                    help="Removes columns that are not part of the SEATS specification (use with caution)"
                )
                if fix_out_of_spec:
                    with st.expander("Columns to be removed", expanded=False):
                        for col in out_of_spec:
                            st.write(f"- `{col}`")
            
            # 1e: Reorder columns
            fix_order = st.checkbox(
                "Reorder all columns to match spec order",
                value=True,
                help="Rearranges columns to match the order defined in the SEATS specification"
            )
        else:
            fix_variations = False
            fix_duplicates = False
            fix_missing_cols = False
            fix_out_of_spec = False
            fix_order = False
        
        st.markdown("---")
        
        # ============================================
        # Section 1b: Empty Mandatory Fields
        # ============================================
        empty_mandatory_values = {}  # Store user inputs
        
        try:
            from utils.seats_data_handler import detect_empty_mandatory_fields
            
            empty_mandatory = detect_empty_mandatory_fields(df, spec) if spec else {}
            
            if empty_mandatory:
                st.markdown("#### ⚠️ Empty Mandatory Fields")
                st.error(f"**{len(empty_mandatory)} mandatory field(s) are empty** and need values to pass validation.")
                
                for field_name, field_info in empty_mandatory.items():
                    with st.expander(f"📋 {field_name} ({field_info['empty_pct']}% empty)", expanded=True):
                        st.write(f"**{field_info['empty_count']:,}** of {field_info['total_rows']:,} rows are empty")
                        st.write(f"Field type: `{field_info['field_type']}`")
                        
                        if field_info['format']:
                            st.write(f"Required format: `{field_info['format']}`")
                        
                        # Different input methods based on suggestion
                        if field_name.upper() == 'EVENT_ID':
                            st.info("💡 EVENT_ID can be auto-generated from other fields for consistency")
                            
                            gen_method = st.radio(
                                "Generation method:",
                                options=['composite', 'sequential'],
                                format_func=lambda x: {
                                    'composite': '🔗 Composite (hash of DAY+TIME+ROOM+MODULE+STUDENT - consistent & reproducible)',
                                    'sequential': '🔢 Sequential (EVT000001, EVT000002, ...)'
                                }.get(x, x),
                                key=f"gen_method_{field_name}"
                            )
                            
                            prefix = st.text_input(
                                "ID Prefix:",
                                value="EVT",
                                max_chars=10,
                                key=f"prefix_{field_name}"
                            )
                            
                            empty_mandatory_values[field_name] = {
                                'method': 'auto_generate',
                                'generation_method': gen_method,
                                'prefix': prefix
                            }
                            
                        elif field_info['field_type'] == 'time' and field_info.get('suggestion') == 'batch_entry':
                            # Batch time entry for START_TIME/END_TIME
                            st.info("💡 Enter times per distinct event group instead of per row")
                            
                            try:
                                from utils.seats_data_handler import get_event_groups_summary
                                
                                # Get event groups
                                groups_summary = get_event_groups_summary(df)
                                
                                st.success(f"Found **{groups_summary['total_groups']:,}** distinct event groups from {groups_summary['total_rows']:,} rows")
                                st.caption(f"Grouped by: {', '.join(groups_summary['group_by_fields'])}")
                                
                                # Check if we need both START_TIME and END_TIME
                                # Collect them together for better UX
                                if field_name.upper() == 'START_TIME':
                                    st.markdown("##### Enter times for each event group:")
                                    st.caption("Enter START and END times together. Leave blank to skip a group.")
                                    
                                    # Store batch times in session state
                                    batch_key = "batch_time_entries"
                                    if batch_key not in st.session_state:
                                        st.session_state[batch_key] = {}
                                    
                                    # Show groups in a scrollable container
                                    groups_to_show = groups_summary['groups'][:50]  # Limit for performance
                                    
                                    if len(groups_summary['groups']) > 50:
                                        st.warning(f"Showing first 50 of {groups_summary['total_groups']} groups. Largest groups shown first.")
                                    
                                    # Header row
                                    header_cols = st.columns([3, 2, 1, 1, 1])
                                    with header_cols[0]:
                                        st.markdown("**Module/Event**")
                                    with header_cols[1]:
                                        st.markdown("**Room**")
                                    with header_cols[2]:
                                        st.markdown("**Rows**")
                                    with header_cols[3]:
                                        st.markdown("**Start**")
                                    with header_cols[4]:
                                        st.markdown("**End**")
                                    
                                    st.markdown("---")
                                    
                                    for i, group in enumerate(groups_to_show):
                                        cols = st.columns([3, 2, 1, 1, 1])
                                        
                                        with cols[0]:
                                            st.caption(group['display_name'][:40])
                                        with cols[1]:
                                            st.caption(str(group['room'])[:20] if group['room'] else '-')
                                        with cols[2]:
                                            st.caption(f"{group['row_count']:,}")
                                        with cols[3]:
                                            start = st.text_input(
                                                "Start",
                                                value=st.session_state[batch_key].get(group['key'], {}).get('start_time', ''),
                                                placeholder="HH:MM",
                                                key=f"batch_start_{i}",
                                                label_visibility="collapsed"
                                            )
                                        with cols[4]:
                                            end = st.text_input(
                                                "End",
                                                value=st.session_state[batch_key].get(group['key'], {}).get('end_time', ''),
                                                placeholder="HH:MM",
                                                key=f"batch_end_{i}",
                                                label_visibility="collapsed"
                                            )
                                        
                                        # Store in session state
                                        if start or end:
                                            st.session_state[batch_key][group['key']] = {
                                                'start_time': start,
                                                'end_time': end
                                            }
                                    
                                    # Quick fill options
                                    st.markdown("---")
                                    st.markdown("##### Quick Fill Options")
                                    
                                    qf_cols = st.columns(4)
                                    with qf_cols[0]:
                                        quick_start = st.text_input("Default Start:", value="", placeholder="HH:MM", key="quick_start")
                                    with qf_cols[1]:
                                        quick_end = st.text_input("Default End:", value="", placeholder="HH:MM", key="quick_end")
                                    with qf_cols[2]:
                                        st.write("")  # Spacing
                                        if st.button("Apply to Empty", key="apply_quick_fill"):
                                            for group in groups_summary['groups']:
                                                if group['key'] not in st.session_state[batch_key]:
                                                    st.session_state[batch_key][group['key']] = {}
                                                entry = st.session_state[batch_key][group['key']]
                                                if not entry.get('start_time') and quick_start:
                                                    entry['start_time'] = quick_start
                                                if not entry.get('end_time') and quick_end:
                                                    entry['end_time'] = quick_end
                                            st.rerun()
                                    with qf_cols[3]:
                                        st.write("")
                                        if st.button("Clear All", key="clear_batch"):
                                            st.session_state[batch_key] = {}
                                            st.rerun()
                                    
                                    # Count how many have times entered
                                    filled_count = sum(1 for v in st.session_state[batch_key].values() 
                                                      if v.get('start_time') or v.get('end_time'))
                                    st.info(f"Times entered for {filled_count} of {groups_summary['total_groups']} groups")
                                    
                                    # Store for apply step
                                    empty_mandatory_values['_batch_times'] = {
                                        'method': 'batch',
                                        'time_mappings': st.session_state[batch_key],
                                        'group_by_fields': groups_summary['group_by_fields']
                                    }
                                    
                                else:
                                    # END_TIME - already handled with START_TIME above
                                    st.caption("(END_TIME is entered together with START_TIME above)")
                                
                            except Exception as e:
                                log_exception(e, logger, {"action": "batch_time_entry"})
                                st.error(f"Error loading event groups: {str(e)}")
                                # Fallback to simple default
                                default_time = st.text_input(
                                    f"Default {field_name}:",
                                    value="09:00" if 'START' in field_name.upper() else "10:00",
                                    key=f"default_{field_name}"
                                )
                                if default_time:
                                    empty_mandatory_values[field_name] = {
                                        'method': 'default',
                                        'value': default_time
                                    }
                        
                        elif field_info['field_type'] == 'time':
                            # Regular time field (not START_TIME/END_TIME)
                            st.info("💡 Enter a default time for all empty rows")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                default_time = st.text_input(
                                    f"Default {field_name}:",
                                    value="09:00" if 'START' in field_name.upper() else "10:00",
                                    placeholder="HH:MM (24-hour format)",
                                    key=f"default_{field_name}"
                                )
                            with col2:
                                st.caption("Format: HH:MM (24-hour)")
                                st.caption("Examples: 09:00, 14:30, 17:45")
                            
                            if default_time:
                                empty_mandatory_values[field_name] = {
                                    'method': 'default',
                                    'value': default_time
                                }
                                
                        elif field_info['field_type'] == 'date':
                            st.info("💡 Enter a default date for all empty rows")
                            
                            default_date = st.text_input(
                                f"Default {field_name}:",
                                value="",
                                placeholder="YYYY-MM-DD",
                                key=f"default_{field_name}"
                            )
                            
                            if default_date:
                                empty_mandatory_values[field_name] = {
                                    'method': 'default',
                                    'value': default_date
                                }
                                
                        elif field_info['values']:  # Enum field
                            st.info("💡 Select a default value from allowed options")
                            
                            allowed_values = [v for v in field_info['values'] if v]  # Remove empty
                            default_val = st.selectbox(
                                f"Default {field_name}:",
                                options=[''] + allowed_values,
                                key=f"default_{field_name}"
                            )
                            
                            if default_val:
                                empty_mandatory_values[field_name] = {
                                    'method': 'default',
                                    'value': default_val
                                }
                                
                        else:  # Generic text field
                            st.info("💡 Enter a default value for all empty rows")
                            
                            default_val = st.text_input(
                                f"Default {field_name}:",
                                value="",
                                key=f"default_{field_name}"
                            )
                            
                            if default_val:
                                empty_mandatory_values[field_name] = {
                                    'method': 'default',
                                    'value': default_val
                                }
                
                # Store in wizard state for apply step
                wizard_state.set_data("empty_mandatory_values", empty_mandatory_values)
                
        except Exception as e:
            log_exception(e, logger, {"action": "detect_empty_mandatory"})
            empty_mandatory = {}
        
        st.markdown("---")
        
        # ============================================
        # Section 2: Data Quality Fixes
        # ============================================
        if has_quality_issues and quality_report:
            st.markdown("#### Data Quality Fixes")
            
            quality_summary = quality_report.to_summary()
            fixable_count = quality_summary["fixable_issues"]
            
            st.write(f"Found **{quality_summary['total_issues']}** data quality issues ({fixable_count} auto-fixable)")
            
            # Group fixes by type
            fix_id_fields = False
            fix_date_time = False
            fix_encoding = False
            fix_multi_value = False
            fix_enums = False
            fix_structural = False
            
            by_type = quality_summary.get("by_type", {})
            
            if by_type.get("id_field", 0) > 0:
                id_issues = quality_report.get_by_type(IssueType.ID_FIELD)
                fixable_ids = len([i for i in id_issues if i.can_auto_fix])
                fix_id_fields = st.checkbox(
                    f"🔢 Fix ID field issues ({by_type['id_field']} issues, {fixable_ids} fixable)",
                    value=True,
                    help="Fixes scientific notation, decimal points, special characters in ID fields"
                )
            
            if by_type.get("date_time", 0) > 0:
                dt_issues = quality_report.get_by_type(IssueType.DATE_TIME)
                fixable_dt = len([i for i in dt_issues if i.can_auto_fix])
                fix_date_time = st.checkbox(
                    f"📅 Fix date/time issues ({by_type['date_time']} issues, {fixable_dt} fixable)",
                    value=True,
                    help="Fixes date formats, Excel serial numbers, time formats, missing leading zeros"
                )
            
            if by_type.get("text_encoding", 0) > 0:
                enc_issues = quality_report.get_by_type(IssueType.TEXT_ENCODING)
                fixable_enc = len([i for i in enc_issues if i.can_auto_fix])
                fix_encoding = st.checkbox(
                    f"📝 Fix text/encoding issues ({by_type['text_encoding']} issues, {fixable_enc} fixable)",
                    value=True,
                    help="Removes BOM, hidden characters, non-breaking spaces, zero-width characters"
                )
            
            if by_type.get("multi_value", 0) > 0:
                mv_issues = quality_report.get_by_type(IssueType.MULTI_VALUE)
                fixable_mv = len([i for i in mv_issues if i.can_auto_fix])
                fix_multi_value = st.checkbox(
                    f"📋 Fix multi-value field issues ({by_type['multi_value']} issues, {fixable_mv} fixable)",
                    value=True,
                    help="Fixes wrong separators (comma instead of /), extra spaces around separators"
                )
            
            if by_type.get("enum_field", 0) > 0:
                enum_issues = quality_report.get_by_type(IssueType.ENUM_FIELD)
                fixable_enum = len([i for i in enum_issues if i.can_auto_fix])
                fix_enums = st.checkbox(
                    f"📊 Fix enum field issues ({by_type['enum_field']} issues, {fixable_enum} fixable)",
                    value=True,
                    help="Fixes case issues, expands abbreviations (e.g., 'Male' to 'M')"
                )
            
            if by_type.get("structural", 0) > 0:
                struct_issues = quality_report.get_by_type(IssueType.STRUCTURAL)
                fixable_struct = len([i for i in struct_issues if i.can_auto_fix])
                fix_structural = st.checkbox(
                    f"🏗️ Fix structural issues ({by_type['structural']} issues, {fixable_struct} fixable)",
                    value=True,
                    help="Removes empty rows, duplicate header rows, footer/summary rows"
                )
        else:
            fix_id_fields = False
            fix_date_time = False
            fix_encoding = False
            fix_multi_value = False
            fix_enums = False
            fix_structural = False
        
        st.markdown("---")
        
        # ============================================
        # Section 3: SIS Value Transformations
        # ============================================
        fix_sis_values = False
        sis_detection = wizard_state.get_data("sis_detection")
        
        if sis_detection and sis_detection.detected_type.value != "generic":
            try:
                from utils.sis_mapper import SISMapper, SISType
                
                sis_names = {
                    SISType.BANNER: "Banner",
                    SISType.PEOPLESOFT: "PeopleSoft",
                    SISType.WORKDAY: "Workday",
                    SISType.COLLEAGUE: "Colleague",
                    SISType.JENZABAR: "Jenzabar",
                }
                
                sis_name = sis_names.get(sis_detection.detected_type, "SIS")
                
                st.markdown("#### SIS Value Transformations")
                st.info(f"Detected {sis_name} format. Apply standard value transformations?")
                
                fix_sis_values = st.checkbox(
                    f"🔄 Apply {sis_name} value transformations",
                    value=True,
                    help="Converts SIS-specific codes to SEATS format (e.g., 'Male' to 'M', 'Active' to 'A', date formats)"
                )
                
                if fix_sis_values:
                    with st.expander("Value transformations to apply", expanded=False):
                        st.markdown("**Fields that will be transformed:**")
                        st.write("- GENDER: Male/Female/M/F → M/F/O")
                        st.write("- VISAREQUIRED: Yes/No/True/False → Y/N")
                        st.write("- STUDENT_STATUS: Active/Enrolled/Withdrawn → A/W/C")
                        st.write("- STUDENT_MOA: Full-Time/Part-Time → FT/PT")
                        st.write("- ADMIN_AREA: Undergraduate/Graduate → UG/PG")
                        st.write("- Dates: Various formats → YYYY-MM-DD")
                
            except ImportError:
                pass
        
        st.markdown("---")
        
        # ============================================
        # Section 4: Basic Data Fixes (fallback)
        # ============================================
        st.markdown("#### Additional Data Fixes")
        fix_whitespace = st.checkbox("Trim whitespace from all text fields", value=True)
        fix_case = st.checkbox("Standardize case for enum fields (uppercase)", value=not fix_enums)
        fix_dates_basic = st.checkbox("Standardize date formats to YYYY-MM-DD", value=not fix_date_time)
        
        # ============================================
        # Apply Fixes Button
        # ============================================
        if st.button("Apply Fixes", type="primary"):
            with st.spinner("Applying fixes..."):
                try:
                    df_fixed = df.copy()
                    fixes_applied = []
                    
                    # Fix 1: Column structure fixes (all in one operation)
                    if spec and (fix_variations or fix_duplicates or fix_missing_cols or fix_out_of_spec or fix_order):
                        df_fixed, report = fix_column_names_and_order(
                            df_fixed, spec,
                            rename_variations=fix_variations,
                            remove_duplicates=fix_duplicates,
                            remove_out_of_spec=fix_out_of_spec,
                            insert_missing=fix_missing_cols
                        )
                        
                        if report['renamed']:
                            fixes_applied.append(f"Renamed {len(report['renamed'])} column(s)")
                        if report['removed_duplicates']:
                            fixes_applied.append(f"Removed {len(report['removed_duplicates'])} duplicate column(s)")
                        if report['removed_out_of_spec']:
                            fixes_applied.append(f"Removed {len(report['removed_out_of_spec'])} out-of-spec column(s)")
                        if report['inserted']:
                            fixes_applied.append(f"Inserted {len(report['inserted'])} missing column(s)")
                        if report['reordered']:
                            fixes_applied.append("Reordered columns to match spec")
                    
                    # Fix 1b: Fill empty mandatory fields
                    empty_mandatory_values = wizard_state.get_data("empty_mandatory_values", {})
                    if empty_mandatory_values:
                        try:
                            from utils.seats_data_handler import fill_empty_mandatory_field
                            
                            for field_name, fill_config in empty_mandatory_values.items():
                                # Skip special batch_times key
                                if field_name == '_batch_times':
                                    continue
                                    
                                method = fill_config.get('method', 'default')
                                
                                if method == 'auto_generate':
                                    df_fixed = fill_empty_mandatory_field(
                                        df_fixed,
                                        field_name,
                                        method='auto_generate',
                                        generation_method=fill_config.get('generation_method', 'composite'),
                                        prefix=fill_config.get('prefix', 'EVT')
                                    )
                                    fixes_applied.append(f"Generated {field_name} values")
                                    
                                elif method == 'default':
                                    value = fill_config.get('value')
                                    if value:
                                        df_fixed = fill_empty_mandatory_field(
                                            df_fixed,
                                            field_name,
                                            value=value,
                                            method='default'
                                        )
                                        fixes_applied.append(f"Set {field_name} = '{value}'")
                            
                            # Handle batch time entries
                            batch_times_config = empty_mandatory_values.get('_batch_times')
                            if batch_times_config and batch_times_config.get('time_mappings'):
                                try:
                                    from utils.seats_data_handler import apply_batch_times
                                    
                                    df_fixed, rows_updated = apply_batch_times(
                                        df_fixed,
                                        batch_times_config['time_mappings'],
                                        batch_times_config.get('group_by_fields')
                                    )
                                    
                                    if rows_updated > 0:
                                        fixes_applied.append(f"Set times for {rows_updated:,} rows via batch entry")
                                        
                                except Exception as e:
                                    log_exception(e, logger, {"action": "apply_batch_times"})
                                    st.warning(f"Could not apply batch times: {str(e)}")
                                        
                        except Exception as e:
                            log_exception(e, logger, {"action": "fill_empty_mandatory"})
                            st.warning(f"Could not fill empty mandatory fields: {str(e)}")
                    
                    # Fix 2: Data quality fixes
                    if quality_report and (fix_id_fields or fix_date_time or fix_encoding or fix_multi_value or fix_enums or fix_structural):
                        df_fixed, fix_counts = fix_data_quality(
                            df_fixed, quality_report, spec,
                            fix_ids=fix_id_fields,
                            fix_dates=fix_date_time,
                            fix_times=fix_date_time,
                            fix_encoding=fix_encoding,
                            fix_multi_value=fix_multi_value,
                            fix_enums=fix_enums,
                            fix_structural=fix_structural
                        )
                        
                        for fix_type, count in fix_counts.items():
                            if count > 0:
                                type_label = fix_type.replace('_', ' ').title()
                                fixes_applied.append(f"Fixed {count} {type_label} issue(s)")
                    
                    # Fix 3: SIS value transformations
                    if fix_sis_values and sis_detection:
                        try:
                            from utils.sis_mapper import SISMapper
                            sis_mapper = SISMapper()
                            
                            # Apply value transformations
                            sis_transform_count = 0
                            for seats_col, value_config in sis_mapper.value_mappings.items():
                                if seats_col in df_fixed.columns:
                                    count = sis_mapper._transform_values(df_fixed, seats_col, value_config)
                                    sis_transform_count += count
                            
                            # Apply date conversions
                            date_cols = sis_mapper._identify_date_columns(df_fixed)
                            sis_date_count = 0
                            for col in date_cols:
                                converted = sis_mapper._convert_dates(df_fixed, col)
                                sis_date_count += converted
                            
                            if sis_transform_count > 0:
                                fixes_applied.append(f"Transformed {sis_transform_count} SIS value(s)")
                            if sis_date_count > 0:
                                fixes_applied.append(f"Converted {sis_date_count} SIS date(s)")
                                
                        except Exception as e:
                            log_exception(e, logger, {"action": "sis_transform"})
                    
                    # Fix 4: Basic whitespace trimming
                    if fix_whitespace:
                        for col in df_fixed.select_dtypes(include=["object"]).columns:
                            df_fixed[col] = df_fixed[col].astype(str).str.strip()
                            df_fixed[col] = df_fixed[col].replace('nan', '')
                        fixes_applied.append("Trimmed whitespace")
                    
                    # Fix 5: Standardize case for enum fields (basic)
                    if fix_case and spec and not fix_enums:
                        fields_spec = spec.get('fields', {})
                        enum_fixed = 0
                        for field_name, field_def in fields_spec.items():
                            if field_def.get('type') == 'enum':
                                matching_col = None
                                for col in df_fixed.columns:
                                    if col.upper() == field_name.upper():
                                        matching_col = col
                                        break
                                
                                if matching_col and matching_col in df_fixed.columns:
                                    df_fixed[matching_col] = df_fixed[matching_col].astype(str).str.upper()
                                    df_fixed[matching_col] = df_fixed[matching_col].replace('NAN', '')
                                    enum_fixed += 1
                        if enum_fixed > 0:
                            fixes_applied.append(f"Standardized case for {enum_fixed} enum field(s)")
                    
                    # Fix 6: Date formats (basic)
                    if fix_dates_basic and spec and not fix_date_time:
                        fields_spec = spec.get('fields', {})
                        dates_fixed = 0
                        for field_name, field_def in fields_spec.items():
                            if field_def.get('type') == 'date':
                                matching_col = None
                                for col in df_fixed.columns:
                                    if col.upper() == field_name.upper():
                                        matching_col = col
                                        break
                                
                                if matching_col and matching_col in df_fixed.columns:
                                    try:
                                        date_col = pd.to_datetime(
                                            df_fixed[matching_col],
                                            errors='coerce',
                                            dayfirst=True
                                        )
                                        df_fixed[matching_col] = date_col.dt.strftime('%Y-%m-%d')
                                        df_fixed[matching_col] = df_fixed[matching_col].fillna('')
                                        dates_fixed += 1
                                    except Exception:
                                        pass
                        if dates_fixed > 0:
                            fixes_applied.append(f"Standardized {dates_fixed} date field(s)")
                    
                    wizard_state.set_data("dataframe_fixed", df_fixed)
                    
                    # Show summary
                    st.success("Fixes applied successfully!")
                    for fix in fixes_applied:
                        st.write(f"✓ {fix}")
                    
                    # Show column comparison
                    st.markdown("#### Column Changes")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Before:**")
                        st.write(f"{len(df.columns)} columns, {len(df)} rows")
                        st.caption(", ".join(df.columns[:10]) + ("..." if len(df.columns) > 10 else ""))
                    with col2:
                        st.markdown("**After:**")
                        st.write(f"{len(df_fixed.columns)} columns, {len(df_fixed)} rows")
                        st.caption(", ".join(df_fixed.columns[:10]) + ("..." if len(df_fixed.columns) > 10 else ""))
                    
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
    
    # Count ALL errors (schema + row-level)
    schema_issues = validation_results.get("schema_issues", [])
    row_errors = validation_results.get("errors", [])
    warnings = validation_results.get("warnings", [])
    total_schema = len(schema_issues)
    total_row = len(row_errors)
    total_all = total_schema + total_row
    has_errors = total_all > 0
    
    # Show warning if there are validation errors
    if has_errors:
        st.warning(
            f"This data has {total_all:,} validation error(s) that were not fixed "
            f"({total_schema} schema, {total_row} row-level)."
        )
        
        # Show detailed error breakdown
        with st.expander("Error Breakdown (click to expand)", expanded=True):
            
            # Schema issues
            if schema_issues:
                st.markdown("**Schema Errors:**")
                for issue in schema_issues:
                    st.error(issue)
            
            # Row error breakdown
            if row_errors:
                # Build breakdowns from the stored error dicts
                errors_by_type = {}
                errors_by_column = {}
                for err in row_errors:
                    if isinstance(err, dict):
                        err_type = err.get("error_type", "Unknown")
                        err_col = err.get("column", "Unknown")
                        errors_by_type[err_type] = errors_by_type.get(err_type, 0) + 1
                        errors_by_column[err_col] = errors_by_column.get(err_col, 0) + 1
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Row Errors by Type:**")
                    if errors_by_type:
                        for error_type, count in sorted(errors_by_type.items(), key=lambda x: x[1], reverse=True)[:10]:
                            st.write(f"- {error_type.replace('_', ' ').title()}: {count:,}")
                    else:
                        st.write("No type breakdown available")
                
                with col2:
                    st.markdown("**Row Errors by Column:**")
                    if errors_by_column:
                        for col_name, count in sorted(errors_by_column.items(), key=lambda x: x[1], reverse=True)[:10]:
                            st.write(f"- {col_name}: {count:,}")
                    else:
                        st.write("No column breakdown available")
                
                # Show sample errors
                st.markdown("**Sample Errors (first 5):**")
                for i, err in enumerate(row_errors[:5]):
                    if isinstance(err, dict):
                        row_num = err.get("row", "?")
                        col_name = err.get("column", "?")
                        msg = err.get("message", str(err))
                        st.write(f"{i+1}. Row {row_num}, Column '{col_name}': {msg}")
            
            # Warnings
            if warnings:
                st.markdown("**Warnings:**")
                for w in warnings:
                    st.warning(w)
        
        st.markdown("---")
        st.markdown("**Suggestions:**")
        st.write("- Go back to **Auto-Fix** to apply more fixes")
        st.write("- Check that all required columns are present in the correct order")
        st.write("- Verify mandatory field values are populated")
        st.write("- Ensure date formats are YYYY-MM-DD and enum values match the spec")
        
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
