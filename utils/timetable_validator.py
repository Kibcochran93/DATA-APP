"""
Timetable-specific validation logic with row-level error detection.
Returns detailed error information including row indices for UI highlighting.

Loads validation rules from SEATS Master Data Specification JSON files.
The Master Spec is the authoritative source for all validation rules.
"""

import pandas as pd
import re
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class ErrorSeverity(Enum):
    WARNING = "warning"
    

@dataclass
class ValidationError:
    """Represents a single validation error with location info."""
    row_index: int
    column: str
    error_type: str
    message: str
    current_value: Any
    expected_format: Optional[str] = None
    severity: ErrorSeverity = ErrorSeverity.WARNING
    suggestion: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "row": self.row_index,
            "column": self.column,
            "error_type": self.error_type,
            "message": self.message,
            "current_value": str(self.current_value) if self.current_value is not None else "EMPTY",
            "expected_format": self.expected_format,
            "severity": self.severity.value,
            "suggestion": self.suggestion
        }


@dataclass
class ValidationResult:
    """Container for all validation results."""
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    schema_issues: List[str] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)
    spec_version: str = "unknown"
    
    def add_error(self, error: ValidationError):
        self.errors.append(error)
        
    def get_error_rows(self) -> List[int]:
        """Get unique list of row indices with errors."""
        return sorted(list(set(e.row_index for e in self.errors)))
    
    def get_errors_by_row(self, row_index: int) -> List[ValidationError]:
        """Get all errors for a specific row."""
        return [e for e in self.errors if e.row_index == row_index]
    
    def get_errors_by_column(self, column: str) -> List[ValidationError]:
        """Get all errors for a specific column."""
        return [e for e in self.errors if e.column == column]
    
    def get_error_cells(self) -> List[Tuple[int, str]]:
        """Get list of (row, column) tuples for all error cells."""
        return [(e.row_index, e.column) for e in self.errors]
    
    def to_summary(self) -> Dict[str, Any]:
        """Generate summary statistics."""
        error_types = {}
        columns_affected = {}
        
        for e in self.errors:
            error_types[e.error_type] = error_types.get(e.error_type, 0) + 1
            columns_affected[e.column] = columns_affected.get(e.column, 0) + 1
            
        return {
            "total_errors": len(self.errors),
            "rows_affected": len(self.get_error_rows()),
            "error_types": error_types,
            "columns_affected": columns_affected,
            "schema_issues": self.schema_issues,
            "spec_version": self.spec_version
        }


def load_master_spec(dataset_type: str, spec_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load master specification from JSON file.
    The Master Spec is the authoritative source for validation rules.
    
    Args:
        dataset_type: Type of dataset (e.g., 'Timetable', 'Student')
        spec_path: Optional custom path to spec file
        
    Returns:
        Dictionary containing spec configuration
    """
    # Default paths to search for spec files
    search_paths = [
        Path(spec_path) if spec_path else None,
        Path(f"/app/data/master/{dataset_type}/master_{dataset_type.lower()}_spec.json"),
        Path(f"/app/data/master/timetable/master_timetable_spec.json"),
        Path(f"data/master/{dataset_type}/master_{dataset_type.lower()}_spec.json"),
        Path(f"./data/master/{dataset_type}/master_{dataset_type.lower()}_spec.json"),
    ]
    
    for path in search_paths:
        if path and path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    spec = json.load(f)
                return spec
            except (json.JSONDecodeError, IOError):
                continue
    
    # Return empty spec if not found (will use defaults)
    return {}


class TimetableValidator:
    """
    Validates timetable data against SEATS Master Data Specification.
    
    The Master Spec JSON file is the authoritative source for:
    - Mandatory vs optional columns
    - Date/time formats
    - Enum values (LESSON_TYPE, etc.)
    - Validation patterns
    
    Falls back to SEATS V8.2 defaults if spec file not found.
    """
    
    # Default Timetable spec per SEATS Master Data Interface Specification V8.2
    # These are ONLY used as fallback if master spec JSON not found
    DEFAULT_MANDATORY_COLUMNS = [
        "EVENT_ID", "DAY", "START_TIME", "END_TIME", 
        "ROOM_ID", "ROOM_NAME", "COURSE_ID", "COURSE_NAME",
        "MODULE_ID", "MODULE_NAME", "SCHOOL_ID", "SCHOOL_NAME"
    ]
    
    DEFAULT_OPTIONAL_COLUMNS = [
        "STUDENT_ID", "COURSE_SESSION_CODE", "MODULE_SESSION_CODE", "LESSON_TYPE",
        "SITE_CODE", "SITE_NAME", "TUTOR_ID", "TUTOR",
        "LESSON_DESCRIPTION", "BUILDING_ID", "BUILDING_NAME",
        "GROUP_ID", "GROUP_NAME", "IS_MANDATORY", "ATTENDANCE_STATUS",
        "CLASSLINK", "DELETE", "VIRTUAL_ATTENDANCE", "MODULE_GROUP",
        "COLLEGE_YEAR"
    ]
    
    # Default format rules per SEATS V8.2 spec
    DEFAULT_FORMAT_RULES = {
        "DAY": {"type": "date", "format": "YYYY-MM-DD", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        "START_TIME": {"type": "time", "format": "HH:MM", "pattern": r"^\d{2}:\d{2}$"},
        "END_TIME": {"type": "time", "format": "HH:MM", "pattern": r"^\d{2}:\d{2}$"},
        "IS_MANDATORY": {"type": "enum", "values": ["Y", "N"]},
        "DELETE": {"type": "enum", "values": ["Y", "N"]},
        "VIRTUAL_ATTENDANCE": {"type": "enum", "values": ["Y", "N"]},
    }
    
    def __init__(self, spec: Optional[Dict] = None, spec_path: Optional[str] = None):
        """
        Initialize validator with spec from master JSON or defaults.
        
        Args:
            spec: Optional pre-loaded specification dictionary
            spec_path: Optional path to master spec JSON file
        """
        # Load spec from file if not provided
        if spec is None:
            spec = load_master_spec("Timetable", spec_path)
        
        self.spec = spec
        self.result = ValidationResult()
        
        # Extract configuration from spec or use defaults
        self._load_spec_config()
    
    def _load_spec_config(self):
        """Load configuration from master spec or use defaults."""
        # Get spec version
        self.spec_version = self.spec.get("version", "unknown")
        
        # Get mandatory/optional columns from spec
        if "signature" in self.spec and "mandatory" in self.spec:
            # New format: signature list + mandatory dict
            signature = self.spec.get("signature", [])
            mandatory_dict = self.spec.get("mandatory", {})
            self.mandatory_columns = [f for f in signature if mandatory_dict.get(f, "N") == "Y"]
            self.optional_columns = [f for f in signature if mandatory_dict.get(f, "N") != "Y"]
        elif "datasets" in self.spec and "Timetable" in self.spec["datasets"]:
            # Nested format with datasets key
            timetable_spec = self.spec["datasets"]["Timetable"]
            signature = timetable_spec.get("signature", [])
            mandatory_dict = timetable_spec.get("mandatory", {})
            self.mandatory_columns = [f for f in signature if mandatory_dict.get(f, "N") == "Y"]
            self.optional_columns = [f for f in signature if mandatory_dict.get(f, "N") != "Y"]
            self.spec = timetable_spec  # Use timetable-specific spec
        elif "mandatory" in self.spec and isinstance(self.spec["mandatory"], list):
            # Legacy format: direct lists
            self.mandatory_columns = self.spec.get("mandatory", self.DEFAULT_MANDATORY_COLUMNS)
            self.optional_columns = self.spec.get("optional", self.DEFAULT_OPTIONAL_COLUMNS)
        else:
            # Use defaults
            self.mandatory_columns = self.DEFAULT_MANDATORY_COLUMNS
            self.optional_columns = self.DEFAULT_OPTIONAL_COLUMNS
        
        # Get format rules from spec
        self.format_rules = self.spec.get("formats", self.DEFAULT_FORMAT_RULES)
        
        # Get valid LESSON_TYPE values from spec or use defaults
        lesson_type_spec = self.format_rules.get("LESSON_TYPE", {})
        self.valid_lesson_types = lesson_type_spec.get("values", [])
        if not self.valid_lesson_types:
            # Default lesson types if not in spec
            self.valid_lesson_types = ["L", "LA", "T", "A", "F", "O", "V", "DI"]
        
    def validate(self, df: pd.DataFrame) -> ValidationResult:
        """
        Run all validations on the dataframe against Master Spec.
        
        Args:
            df: Timetable dataframe to validate
            
        Returns:
            ValidationResult with all errors and warnings
        """
        self.result = ValidationResult()
        self.result.spec_version = self.spec_version
        
        # Schema-level checks
        self._validate_schema(df)
        
        # Row-level checks
        self._validate_rows(df)
        
        # Generate summary
        self.result.summary = self.result.to_summary()
        
        return self.result
    
    def _validate_schema(self, df: pd.DataFrame):
        """Validate column schema against master spec."""
        # Check for duplicate column names (e.g., STUDENT_ID_x, STUDENT_ID_y from pandas merge)
        duplicate_bases = {}
        for col in df.columns:
            col_upper = col.upper()
            # Remove _x, _y suffixes that pandas adds during merges
            if col_upper.endswith('_X') or col_upper.endswith('_Y'):
                base_name = col_upper[:-2]
            else:
                base_name = col_upper
            
            if base_name not in duplicate_bases:
                duplicate_bases[base_name] = []
            duplicate_bases[base_name].append(col)
        
        for base, variants in duplicate_bases.items():
            if len(variants) > 1:
                self.result.schema_issues.append(
                    f"Duplicate column detected: {', '.join(variants)} - "
                    f"appears to be result of a pandas merge. Should be single '{base}' column."
                )
        
        # Check for missing mandatory columns (per Master Spec)
        normalized_cols = set()
        for c in df.columns:
            col_upper = c.strip().upper()
            if col_upper.endswith('_X') or col_upper.endswith('_Y'):
                normalized_cols.add(col_upper[:-2])
            else:
                normalized_cols.add(col_upper)
        
        for mandatory in self.mandatory_columns:
            if mandatory.upper() not in normalized_cols:
                self.result.schema_issues.append(
                    f"Missing mandatory column: {mandatory} (per SEATS Master Spec)"
                )
        
        # Check for columns with trailing whitespace
        for col in df.columns:
            if col != col.strip():
                self.result.schema_issues.append(
                    f"Column '{col}' has leading/trailing whitespace. Should be '{col.strip()}'"
                )
        
        # Check for unexpected columns (not in spec)
        all_expected = set(c.upper() for c in self.mandatory_columns + self.optional_columns)
        for col in df.columns:
            col_upper = col.strip().upper()
            if col_upper.endswith('_X') or col_upper.endswith('_Y'):
                normalized = col_upper[:-2]
            else:
                normalized = col_upper
            
            if normalized not in all_expected and normalized:
                self.result.warnings.append(
                    f"Unexpected column: {col} - not in SEATS Master Spec"
                )
    
    def _validate_rows(self, df: pd.DataFrame):
        """Validate each row for data quality issues per Master Spec."""
        col_map = {c.upper(): c for c in df.columns}
        
        for idx, row in df.iterrows():
            # Validate DAY field - format from spec (default YYYY-MM-DD)
            self._validate_date_field(idx, row, col_map, "DAY")
            
            # Validate time fields
            self._validate_time_field(idx, row, col_map, "START_TIME")
            self._validate_time_field(idx, row, col_map, "END_TIME")
            
            # Validate mandatory fields are not empty
            self._validate_mandatory_not_empty(idx, row, col_map)
            
            # Validate LESSON_TYPE enum if column exists
            if self.valid_lesson_types:
                self._validate_enum_field(idx, row, col_map, "LESSON_TYPE", self.valid_lesson_types)
            
            # Validate boolean fields
            self._validate_boolean_field(idx, row, col_map, "IS_MANDATORY")
            self._validate_boolean_field(idx, row, col_map, "DELETE")
            self._validate_boolean_field(idx, row, col_map, "VIRTUAL_ATTENDANCE")
            
            # Cross-field validation
            self._validate_time_sequence(idx, row, col_map)
    
    def _get_column_value(self, row, col_map: Dict, field: str):
        """Safely get column value handling different naming conventions."""
        field_upper = field.upper()
        if field_upper in col_map:
            return row[col_map[field_upper]]
        if f"{field_upper}_X" in col_map:
            return row[col_map[f"{field_upper}_X"]]
        return None
    
    def _get_actual_column_name(self, col_map: Dict, field: str) -> Optional[str]:
        """Get actual column name from dataframe."""
        field_upper = field.upper()
        if field_upper in col_map:
            return col_map[field_upper]
        if f"{field_upper}_X" in col_map:
            return col_map[f"{field_upper}_X"]
        return None
    
    def _get_format_rule(self, field: str) -> Dict:
        """Get format rule for a field from Master Spec."""
        return self.format_rules.get(field.upper(), self.format_rules.get(field, {}))
    
    def _validate_date_field(self, idx: int, row, col_map: Dict, field: str):
        """Validate date format field against Master Spec."""
        actual_col = self._get_actual_column_name(col_map, field)
        if not actual_col:
            return
            
        value = self._get_column_value(row, col_map, field)
        
        # Get expected format from spec
        format_rule = self._get_format_rule(field)
        expected_format = format_rule.get("format", "YYYY-MM-DD")
        pattern = format_rule.get("pattern", r"^\d{4}-\d{2}-\d{2}$")
        
        if pd.isna(value) or str(value).strip() == "":
            if field.upper() in [m.upper() for m in self.mandatory_columns]:
                self.result.add_error(ValidationError(
                    row_index=idx,
                    column=actual_col,
                    error_type="missing_value",
                    message=f"{field} is empty but required per SEATS Master Spec",
                    current_value=value,
                    expected_format=expected_format,
                    suggestion="Provide a valid date"
                ))
            return
        
        str_value = str(value).strip()
        
        if not re.match(pattern, str_value):
            detected_format = self._detect_date_format(str_value)
            self.result.add_error(ValidationError(
                row_index=idx,
                column=actual_col,
                error_type="invalid_date_format",
                message=f"Date format should be {expected_format} per SEATS Master Spec, found: {str_value}",
                current_value=str_value,
                expected_format=expected_format,
                suggestion=f"Convert from {detected_format} to {expected_format}" if detected_format else f"Use {expected_format} format"
            ))
    
    def _detect_date_format(self, value: str) -> Optional[str]:
        """Attempt to detect the date format used."""
        if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
            return "YYYY-MM-DD"
        if re.match(r"^\d{2}/\d{2}/\d{4}$", value):
            parts = value.split("/")
            try:
                if int(parts[0]) > 12:
                    return "DD/MM/YYYY"
                elif int(parts[1]) > 12:
                    return "MM/DD/YYYY"
            except ValueError:
                pass
            return "DD/MM/YYYY or MM/DD/YYYY (ambiguous)"
        if re.match(r"^\d{2}-\d{2}-\d{4}$", value):
            return "DD-MM-YYYY"
        return None
    
    def _validate_time_field(self, idx: int, row, col_map: Dict, field: str):
        """Validate time format field against Master Spec."""
        actual_col = self._get_actual_column_name(col_map, field)
        if not actual_col:
            return
            
        value = self._get_column_value(row, col_map, field)
        
        format_rule = self._get_format_rule(field)
        expected_format = format_rule.get("format", "HH:MM")
        pattern = format_rule.get("pattern", r"^\d{2}:\d{2}$")
        
        if pd.isna(value) or str(value).strip() == "":
            lesson_type = self._get_column_value(row, col_map, "LESSON_TYPE")
            lesson_type_str = str(lesson_type).strip().upper() if not pd.isna(lesson_type) else ""
            
            # V (Virtual) and DI (Distance/Independent) may allow empty times
            if lesson_type_str not in ["DI", "V"]:
                if field.upper() in [m.upper() for m in self.mandatory_columns]:
                    self.result.add_error(ValidationError(
                        row_index=idx,
                        column=actual_col,
                        error_type="missing_value",
                        message=f"{field} is empty but required for lesson type '{lesson_type_str}' per SEATS Master Spec",
                        current_value=value,
                        expected_format=expected_format,
                        suggestion=f"Provide time in {expected_format} format or change lesson type to DI/V"
                    ))
            return
        
        str_value = str(value).strip()
        
        if not re.match(pattern, str_value):
            self.result.add_error(ValidationError(
                row_index=idx,
                column=actual_col,
                error_type="invalid_time_format",
                message=f"Time format should be {expected_format} per SEATS Master Spec, found: {str_value}",
                current_value=str_value,
                expected_format=expected_format,
                suggestion=f"Use 24-hour format {expected_format} (e.g., 09:00, 14:30)"
            ))
    
    def _validate_mandatory_not_empty(self, idx: int, row, col_map: Dict):
        """Check mandatory fields are not empty per Master Spec."""
        mandatory_data_fields = ["EVENT_ID", "COURSE_ID", "MODULE_ID", "SCHOOL_ID"]
        
        for field in mandatory_data_fields:
            if field.upper() not in [m.upper() for m in self.mandatory_columns]:
                continue
                
            actual_col = self._get_actual_column_name(col_map, field)
            if not actual_col:
                continue
                
            value = self._get_column_value(row, col_map, field)
            
            if pd.isna(value) or str(value).strip() == "":
                self.result.add_error(ValidationError(
                    row_index=idx,
                    column=actual_col,
                    error_type="missing_mandatory",
                    message=f"{field} is mandatory per SEATS Master Spec and cannot be empty",
                    current_value=value,
                    suggestion=f"Provide a valid {field}"
                ))
        
        # Check ROOM_ID and ROOM_NAME
        lesson_type = self._get_column_value(row, col_map, "LESSON_TYPE")
        lesson_type_str = str(lesson_type).strip().upper() if not pd.isna(lesson_type) else ""
        
        room_not_required_types = ["V", "DI"]
        
        if lesson_type_str not in room_not_required_types:
            for field in ["ROOM_ID", "ROOM_NAME"]:
                if field.upper() not in [m.upper() for m in self.mandatory_columns]:
                    continue
                    
                actual_col = self._get_actual_column_name(col_map, field)
                if not actual_col:
                    continue
                
                value = self._get_column_value(row, col_map, field)
                
                if pd.isna(value) or str(value).strip() == "":
                    self.result.add_error(ValidationError(
                        row_index=idx,
                        column=actual_col,
                        error_type="missing_room",
                        message=f"{field} is empty but required for lesson type '{lesson_type_str}' per SEATS Master Spec",
                        current_value=value,
                        suggestion=f"Provide {field} or change lesson type to V/DI for virtual/distance"
                    ))
    
    def _validate_enum_field(self, idx: int, row, col_map: Dict, field: str, valid_values: List[str]):
        """Validate enum field values against Master Spec."""
        actual_col = self._get_actual_column_name(col_map, field)
        if not actual_col:
            return
            
        value = self._get_column_value(row, col_map, field)
        
        if pd.isna(value) or str(value).strip() == "":
            return
        
        str_value = str(value).strip().upper()
        valid_upper = [v.upper() for v in valid_values]
        
        if str_value not in valid_upper:
            self.result.add_error(ValidationError(
                row_index=idx,
                column=actual_col,
                error_type="invalid_enum",
                message=f"Invalid {field}: {value} (not in SEATS Master Spec)",
                current_value=value,
                expected_format=f"One of: {', '.join(valid_values)}",
                suggestion=f"Use valid {field} code per SEATS Master Spec"
            ))
    
    def _validate_boolean_field(self, idx: int, row, col_map: Dict, field: str):
        """Validate boolean Y/N fields per Master Spec."""
        actual_col = self._get_actual_column_name(col_map, field)
        if not actual_col:
            return
            
        value = self._get_column_value(row, col_map, field)
        
        if pd.isna(value) or str(value).strip() == "":
            return
        
        str_value = str(value).strip().upper()
        
        format_rule = self._get_format_rule(field)
        valid_values = format_rule.get("values", ["Y", "N"])
        
        if str_value not in [v.upper() for v in valid_values]:
            self.result.add_error(ValidationError(
                row_index=idx,
                column=actual_col,
                error_type="invalid_boolean",
                message=f"{field} should be {' or '.join(valid_values)} per SEATS Master Spec, found: {value}",
                current_value=value,
                expected_format=f"{' or '.join(valid_values)}",
                suggestion=f"Use {valid_values[0]} for yes, {valid_values[1]} for no"
            ))
    
    def _validate_time_sequence(self, idx: int, row, col_map: Dict):
        """Validate END_TIME is after START_TIME."""
        start_col = self._get_actual_column_name(col_map, "START_TIME")
        end_col = self._get_actual_column_name(col_map, "END_TIME")
        
        if not start_col or not end_col:
            return
        
        start_value = self._get_column_value(row, col_map, "START_TIME")
        end_value = self._get_column_value(row, col_map, "END_TIME")
        
        if pd.isna(start_value) or pd.isna(end_value):
            return
        if str(start_value).strip() == "" or str(end_value).strip() == "":
            return
        
        try:
            start_str = str(start_value).strip()
            end_str = str(end_value).strip()
            
            time_pattern = r"^\d{2}:\d{2}$"
            if re.match(time_pattern, start_str) and re.match(time_pattern, end_str):
                start_parts = [int(x) for x in start_str.split(":")]
                end_parts = [int(x) for x in end_str.split(":")]
                
                start_minutes = start_parts[0] * 60 + start_parts[1]
                end_minutes = end_parts[0] * 60 + end_parts[1]
                
                if end_minutes <= start_minutes:
                    self.result.add_error(ValidationError(
                        row_index=idx,
                        column=end_col,
                        error_type="time_sequence",
                        message=f"END_TIME ({end_str}) must be after START_TIME ({start_str})",
                        current_value=end_str,
                        suggestion="Ensure end time is later than start time"
                    ))
        except (ValueError, IndexError):
            pass


def validate_timetable(df: pd.DataFrame, spec: Optional[Dict] = None, spec_path: Optional[str] = None) -> ValidationResult:
    """
    Convenience function to validate timetable data against SEATS Master Spec.
    
    Args:
        df: Timetable dataframe
        spec: Optional pre-loaded specification (Master Spec)
        spec_path: Optional path to master spec JSON file
        
    Returns:
        ValidationResult with all errors
    """
    validator = TimetableValidator(spec=spec, spec_path=spec_path)
    return validator.validate(df)
