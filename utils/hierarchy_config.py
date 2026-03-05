"""
SEAtS Data Hierarchy Configuration Module

Provides UI and logic for institutions to configure their data hierarchy
mapping to SEAtS terminology.

SEAtS supports 5 hierarchy levels:
1. Faculty (optional) - Highest level
2. School (mandatory) - Required for all imports
3. Programme (optional) - Academic program level
4. Course (mandatory) - Course/Route level
5. Module (mandatory) - Lowest level, individual classes

Reference: SEAtS Getting Started With Data Hierarchy 2024/2025
"""

import streamlit as st
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import json
from pathlib import Path


@dataclass
class HierarchyLevel:
    """Represents a level in the data hierarchy."""
    level: int
    seats_name: str
    seats_id_field: str
    seats_name_field: str
    is_mandatory: bool
    import_files: List[str]
    description: str
    common_synonyms: List[str] = field(default_factory=list)


# SEAtS standard hierarchy levels
SEATS_HIERARCHY = [
    HierarchyLevel(
        level=1,
        seats_name="Faculty",
        seats_id_field="FACULTY_ID",
        seats_name_field="FACULTY_NAME",
        is_mandatory=False,
        import_files=["Student"],
        description="Highest organizational level (e.g., Faculty of Engineering, College of Arts)",
        common_synonyms=["College", "Division", "Campus", "Institute"]
    ),
    HierarchyLevel(
        level=2,
        seats_name="School",
        seats_id_field="SCHOOL_ID",
        seats_name_field="SCHOOL_NAME",
        is_mandatory=True,
        import_files=["Student", "Timetable"],
        description="Department or school within a faculty",
        common_synonyms=["Department", "Unit", "Center", "Institute", "Division"]
    ),
    HierarchyLevel(
        level=3,
        seats_name="Programme",
        seats_id_field="PROGRAMME_ID",
        seats_name_field="PROGRAMME_NAME",
        is_mandatory=False,
        import_files=["Student"],
        description="Academic program or degree pathway",
        common_synonyms=["Program", "Degree", "Major", "Pathway", "Track"]
    ),
    HierarchyLevel(
        level=4,
        seats_name="Course",
        seats_id_field="COURSE_ID",
        seats_name_field="COURSE_NAME",
        is_mandatory=True,
        import_files=["Student", "Timetable"],
        description="Course or route within a programme",
        common_synonyms=["Route", "Specialization", "Concentration", "Stream", "Option"]
    ),
    HierarchyLevel(
        level=5,
        seats_name="Module",
        seats_id_field="MODULE_ID",
        seats_name_field="MODULE_NAME",
        is_mandatory=True,
        import_files=["Student", "Timetable"],
        description="Individual class, subject, or unit of study",
        common_synonyms=["Class", "Subject", "Unit", "Section", "Course Section"]
    ),
]


@dataclass
class InstitutionHierarchy:
    """Institution's custom hierarchy configuration."""
    institution_name: str = ""
    level_mappings: Dict[int, Dict[str, str]] = field(default_factory=dict)
    # level_mappings: {level: {"custom_name": "Department", "custom_id_field": "DEPT_ID", ...}}
    enabled_levels: List[int] = field(default_factory=lambda: [2, 4, 5])  # Default: School, Course, Module
    
    def to_dict(self) -> Dict:
        return {
            "institution_name": self.institution_name,
            "level_mappings": self.level_mappings,
            "enabled_levels": self.enabled_levels
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'InstitutionHierarchy':
        return cls(
            institution_name=data.get("institution_name", ""),
            level_mappings=data.get("level_mappings", {}),
            enabled_levels=data.get("enabled_levels", [2, 4, 5])
        )


def get_hierarchy_level(level: int) -> Optional[HierarchyLevel]:
    """Get hierarchy level by number."""
    for h in SEATS_HIERARCHY:
        if h.level == level:
            return h
    return None


def render_hierarchy_explanation() -> None:
    """Render the data hierarchy explanation walkthrough."""
    
    st.markdown("### 📊 Understanding SEAtS Data Hierarchy")
    
    # Introduction
    with st.expander("📖 What is Data Hierarchy?", expanded=True):
        st.markdown("""
        The **Data Hierarchy** in SEAtS refers to the different levels within your institution's 
        teaching structure. SEAtS allows for **5 levels**, from Faculty (highest) to Module (lowest).
        
        A student's association to these levels is established through the import of **Student** and 
        **Timetable** data. Getting this hierarchy right is crucial for:
        
        - **Accurate reporting** on attendance and engagement
        - **Data integrity** ensuring students are correctly associated
        - **Security model** limiting what users can see based on hierarchy levels
        """)
    
    # Visual hierarchy diagram
    st.markdown("#### Hierarchy Levels")
    
    cols = st.columns(5)
    for i, level in enumerate(SEATS_HIERARCHY):
        with cols[i]:
            mandatory_badge = "🔴 Required" if level.is_mandatory else "⚪ Optional"
            st.markdown(f"""
            <div style="text-align: center; padding: 10px; border: 2px solid {'#dc3545' if level.is_mandatory else '#6c757d'}; border-radius: 8px; margin: 5px;">
                <div style="font-size: 24px; font-weight: bold;">Level {level.level}</div>
                <div style="font-size: 18px; color: #0066cc;">{level.seats_name}</div>
                <div style="font-size: 12px;">{mandatory_badge}</div>
            </div>
            """, unsafe_allow_html=True)
    
    # Hierarchy table
    with st.expander("📋 Detailed Hierarchy Reference", expanded=False):
        st.markdown("""
        | Level | SEAtS Name | ID Field | Name Field | Mandatory | Import File |
        |:-----:|:-----------|:---------|:-----------|:---------:|:------------|
        | 1 | Faculty | FACULTY_ID | FACULTY_NAME | No | Student |
        | 2 | School | SCHOOL_ID | SCHOOL_NAME | **Yes** | Student & Timetable |
        | 3 | Programme | PROGRAMME_ID | PROGRAMME_NAME | No | Student |
        | 4 | Course | COURSE_ID | COURSE_NAME | **Yes** | Student & Timetable |
        | 5 | Module | MODULE_ID | MODULE_NAME | **Yes** | Student & Timetable |
        """)
        
        st.info("""
        **Note:** All level names can be renamed to match your institution's terminology. 
        For example, 'Course' can be renamed to 'Route' or 'Programme' to 'Degree'.
        """)


def render_hierarchy_mapping(
    wizard_state,
    show_explanation: bool = True
) -> Optional[InstitutionHierarchy]:
    """
    Render the hierarchy mapping interface.
    
    Args:
        wizard_state: WizardState instance
        show_explanation: Whether to show the explanation section
        
    Returns:
        InstitutionHierarchy if configured, None otherwise
    """
    
    if show_explanation:
        render_hierarchy_explanation()
        st.markdown("---")
    
    st.markdown("### 🏛️ Map Your Institution's Hierarchy")
    st.caption("Configure how your data maps to SEAtS hierarchy levels")
    
    # Load existing config from wizard state
    existing_config = wizard_state.get_data("hierarchy_config")
    if existing_config:
        config = InstitutionHierarchy.from_dict(existing_config)
    else:
        config = InstitutionHierarchy()
    
    # Institution name (optional)
    institution_name = st.text_input(
        "Institution Name (optional)",
        value=config.institution_name,
        placeholder="e.g., State University, Community College",
        key="hierarchy_institution_name"
    )
    config.institution_name = institution_name
    
    st.markdown("#### Select Active Hierarchy Levels")
    st.caption("Choose which levels your institution uses. Mandatory levels cannot be disabled.")
    
    # Level selection with mapping
    enabled_levels = []
    level_mappings = {}
    
    for level in SEATS_HIERARCHY:
        col1, col2, col3 = st.columns([1, 2, 2])
        
        with col1:
            # Checkbox to enable/disable (mandatory ones are always checked)
            if level.is_mandatory:
                st.checkbox(
                    f"Level {level.level}: {level.seats_name}",
                    value=True,
                    disabled=True,
                    key=f"level_enable_{level.level}",
                    help="This level is mandatory and cannot be disabled"
                )
                enabled_levels.append(level.level)
            else:
                is_enabled = st.checkbox(
                    f"Level {level.level}: {level.seats_name}",
                    value=level.level in config.enabled_levels,
                    key=f"level_enable_{level.level}",
                    help=f"Enable if your institution uses {level.seats_name.lower()} level"
                )
                if is_enabled:
                    enabled_levels.append(level.level)
        
        # Only show mapping options if level is enabled
        if level.level in enabled_levels or level.is_mandatory:
            with col2:
                # Custom name for this level
                existing_custom = config.level_mappings.get(str(level.level), {})
                custom_name = st.text_input(
                    f"Your term for '{level.seats_name}'",
                    value=existing_custom.get("custom_name", level.seats_name),
                    placeholder=f"e.g., {', '.join(level.common_synonyms[:2])}",
                    key=f"level_name_{level.level}",
                    help=f"Common alternatives: {', '.join(level.common_synonyms)}"
                )
                
                level_mappings[str(level.level)] = {
                    "seats_name": level.seats_name,
                    "custom_name": custom_name,
                    "seats_id_field": level.seats_id_field,
                    "seats_name_field": level.seats_name_field,
                    "is_mandatory": level.is_mandatory
                }
            
            with col3:
                st.caption(f"Maps to: `{level.seats_id_field}`, `{level.seats_name_field}`")
                st.caption(f"Import: {', '.join(level.import_files)}")
    
    config.enabled_levels = sorted(enabled_levels)
    config.level_mappings = level_mappings
    
    # Save to wizard state
    wizard_state.set_data("hierarchy_config", config.to_dict())
    
    # Show summary
    st.markdown("---")
    st.markdown("#### 📝 Configuration Summary")
    
    summary_cols = st.columns(2)
    with summary_cols[0]:
        st.markdown("**Active Levels:**")
        for lvl in config.enabled_levels:
            level_info = get_hierarchy_level(lvl)
            custom = level_mappings.get(str(lvl), {})
            custom_name = custom.get("custom_name", level_info.seats_name)
            mandatory = "🔴" if level_info.is_mandatory else "⚪"
            
            if custom_name != level_info.seats_name:
                st.write(f"{mandatory} Level {lvl}: {custom_name} (SEAtS: {level_info.seats_name})")
            else:
                st.write(f"{mandatory} Level {lvl}: {level_info.seats_name}")
    
    with summary_cols[1]:
        st.markdown("**Required Fields in Your Data:**")
        for lvl in config.enabled_levels:
            level_info = get_hierarchy_level(lvl)
            if level_info.is_mandatory:
                st.write(f"- `{level_info.seats_id_field}` and `{level_info.seats_name_field}`")
    
    return config


def render_hierarchy_quick_select(wizard_state) -> Optional[str]:
    """
    Render a quick hierarchy preset selector.
    
    Returns:
        Selected preset name or None
    """
    
    st.markdown("#### 🚀 Quick Setup")
    st.caption("Select a preset that matches your institution type")
    
    presets = {
        "UK University (Standard)": {
            "enabled": [1, 2, 4, 5],  # Faculty, School, Course, Module
            "names": {
                "1": "Faculty",
                "2": "School",
                "4": "Programme",
                "5": "Module"
            }
        },
        "US College (Simple)": {
            "enabled": [2, 4, 5],  # Department, Course, Section
            "names": {
                "2": "Department",
                "4": "Course",
                "5": "Section"
            }
        },
        "US University (Full)": {
            "enabled": [1, 2, 3, 4, 5],  # All levels
            "names": {
                "1": "College",
                "2": "Department",
                "3": "Major",
                "4": "Course",
                "5": "Section"
            }
        },
        "Community College": {
            "enabled": [2, 4, 5],
            "names": {
                "2": "Division",
                "4": "Course",
                "5": "Section"
            }
        },
        "Vocational/Technical": {
            "enabled": [2, 4, 5],
            "names": {
                "2": "Department",
                "4": "Program",
                "5": "Class"
            }
        },
        "Custom": {
            "enabled": [2, 4, 5],
            "names": {}
        }
    }
    
    selected = st.selectbox(
        "Institution Type",
        options=list(presets.keys()),
        index=5,  # Default to Custom
        key="hierarchy_preset"
    )
    
    if selected != "Custom":
        preset = presets[selected]
        
        # Show what this preset configures
        with st.expander(f"Preview: {selected}", expanded=True):
            st.write("**Enabled Levels:**")
            for lvl in preset["enabled"]:
                name = preset["names"].get(str(lvl), get_hierarchy_level(lvl).seats_name)
                st.write(f"- Level {lvl}: {name}")
        
        if st.button(f"Apply '{selected}' Preset", type="primary"):
            # Apply preset to config
            config = InstitutionHierarchy()
            config.enabled_levels = preset["enabled"]
            for lvl_str, name in preset["names"].items():
                lvl = int(lvl_str)
                level_info = get_hierarchy_level(lvl)
                config.level_mappings[lvl_str] = {
                    "seats_name": level_info.seats_name,
                    "custom_name": name,
                    "seats_id_field": level_info.seats_id_field,
                    "seats_name_field": level_info.seats_name_field,
                    "is_mandatory": level_info.is_mandatory
                }
            
            wizard_state.set_data("hierarchy_config", config.to_dict())
            st.success(f"Applied '{selected}' preset!")
            st.rerun()
    
    return selected


def get_column_mappings_from_hierarchy(
    hierarchy_config: Dict,
    source_columns: List[str]
) -> Dict[str, str]:
    """
    Generate column mapping suggestions based on hierarchy configuration.
    
    Args:
        hierarchy_config: Hierarchy configuration dict
        source_columns: List of columns in source data
        
    Returns:
        Dict mapping source column to SEATS column
    """
    mappings = {}
    level_mappings = hierarchy_config.get("level_mappings", {})
    
    # Build lookup of custom names to SEATS fields
    custom_to_seats = {}
    for lvl_str, level_config in level_mappings.items():
        custom_name = level_config.get("custom_name", "").upper()
        seats_id = level_config.get("seats_id_field", "")
        seats_name = level_config.get("seats_name_field", "")
        
        if custom_name:
            # Map variations like DEPARTMENT_ID -> SCHOOL_ID
            custom_to_seats[f"{custom_name}_ID"] = seats_id
            custom_to_seats[f"{custom_name}_NAME"] = seats_name
            custom_to_seats[f"{custom_name}ID"] = seats_id
            custom_to_seats[f"{custom_name}NAME"] = seats_name
            custom_to_seats[custom_name] = seats_name  # Just the name
    
    # Check source columns against custom mappings
    for col in source_columns:
        col_upper = col.upper()
        if col_upper in custom_to_seats:
            mappings[col] = custom_to_seats[col_upper]
    
    return mappings


# Export main components
__all__ = [
    'HierarchyLevel',
    'InstitutionHierarchy',
    'SEATS_HIERARCHY',
    'render_hierarchy_explanation',
    'render_hierarchy_mapping',
    'render_hierarchy_quick_select',
    'get_hierarchy_level',
    'get_column_mappings_from_hierarchy'
]
