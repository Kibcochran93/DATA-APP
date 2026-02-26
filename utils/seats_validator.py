"""
Generic SEATS data validation with row-level error detection.
Works with any dataset type by loading rules from Master Spec JSON.

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
    dataset_type: str = "Unknown"
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
            "dataset_type": self.dataset_type,
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
        dataset_type: Type of dataset (e.g., 'Timetable', 'Student', 'Staff')
        spec_path: Optional custom path to spec file
        
    Returns:
        Dictionary containing spec configuration
    """
    # Normalize dataset type for file paths
    dataset_lower = dataset_type.lower().replace(" ", "")
    
    # Default paths to search for spec files
    search_paths = [
        Path(spec_path) if spec_path else None,
        Path(f"/app/data/master/{dataset_type}/master_{dataset_lower}_spec.json"),
        Path(f"/app/data/master/{dataset_lower}/master_{dataset_lower}_spec.json"),
        Path(f"data/master/{dataset_type}/master_{dataset_lower}_spec.json"),
        Path(f"data/master/{dataset_lower}/master_{dataset_lower}_spec.json"),
        Path(f"./data/master/{dataset_type}/master_{dataset_lower}_spec.json"),
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


class SEATSValidator:
    """
    Generic SEATS data validator.
    
    Validates any dataset type against its Master Spec JSON file.
    The Master Spec is the authoritative source for:
    - Mandatory vs optional columns
    - Date/time formats
    - Enum values
    - Validation patterns
    """
    
    # Default format rules (used when spec doesn't specify)
    DEFAULT_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
    DEFAULT_DATE_FORMAT = "YYYY-MM-DD"
    DEFAULT_TIME_PATTERN = r"^\d{2}:\d{2}$"
    DEFAULT_TIME_FORMAT = "HH:MM"
    DEFAULT_BOOLEAN_VALUES = ["Y", "N"]
    
    # Common date field names
    DATE_FIELDS = ["DAY", "DATE", "START_DATE", "END_DATE", "DATE_OF_BIRTH", "DOB", 
                   "EXPIRE_DATE", "DUE_DATE", "RECORDED_DATE"]
    
    # Common time field names
    TIME_FIELDS = ["START_TIME", "END_TIME", "TIME"]
    
    # Common boolean field names
    BOOLEAN_FIELDS = ["IS_MANDATORY", "DELETE", "VIRTUAL_ATTENDANCE", "VISAREQUIRED",
                      "IS_SUPER_USER", "IS_GROUP_ASSESSMENT", "APPLY_TO_MODULE"]
    
    def __init__(self, dataset_type: str, spec: Optional[Dict] = None, spec_path: Optional[str] = None):
        """
        Initialize validator for a specific dataset type.
        
        Args:
            dataset_type: Type of dataset (e.g., 'Timetable', 'Student', 'Staff')
            spec: Optional pre-loaded specification dictionary
            spec_path: Optional path to master spec JSON file
        """
        self.dataset_type = dataset_type
        
        # Load spec from file if not provided
        if spec is None:
            spec = load_master_spec(dataset_type, spec_path)
        
        self.spec = spec
        self.result = ValidationResult(dataset_type=dataset_type)
        
        # Extract configuration from spec
        self._load_spec_config()
    
    def _load_spec_config(self):
        """Load configuration from master spec."""
        # Get spec version
        self.spec_version = self.spec.get("version", "unknown")
        
        # Handle different spec formats
        if "signature" in self.spec and "mandatory" in self.spec:
            # New format: signature list + mandatory dict
            signature = self.spec.get("signature", [])
            mandatory_dict = self.spec.get("mandatory", {})
            self.mandatory_columns = [f for f in signature if mandatory_dict.get(f, "N") == "Y"]
            self.optional_columns = [f for f in signature if mandatory_dict.get(f, "N") != "Y"]
        elif "datasets" in self.spec and self.dataset_type in self.spec["datasets"]:
            # Nested format with datasets key
            dataset_spec = self.spec["datasets"][self.dataset_type]
            signature = dataset_spec.get("signature", [])
            mandatory_dict = dataset_spec.get("mandatory", {})
            self.mandatory_columns = [f for f in signature if mandatory_dict.get(f, "N") == "Y"]
            self.optional_columns = [f for f in signature if mandatory_dict.get(f, "N") != "Y"]
            self.spec = dataset_spec
        elif "mandatory" in self.spec and isinstance(self.spec["mandatory"], list):
            # Legacy format: direct lists
            self.mandatory_columns = self.spec.get("mandatory", [])
            self.optional_columns = self.spec.get("optional", [])
        else:
            # No spec found - use empty lists
            self.mandatory_columns = []
            self.optional_columns = []
        
        # Get format rules from spec
        self.format_rules = self.spec.get("formats", {})
        
        # Build enum values lookup from format rules
        self.enum_values = {}
        for field, rule in self.format_rules.items():
            if isinstance(rule, dict) and rule.get("type") == "enum":
                self.enum_values[field.upper()] = rule.get("values", [])
    
    def validate(self, df: pd.DataFrame) -> ValidationResult:
        """
        Run all validations on the dataframe against Master Spec.
        
        Args:
            df: DataFrame to validate
            
        Returns:
            ValidationResult with all errors and warnings
        """
        self.result = ValidationResult(dataset_type=self.dataset_type)
        self.result.spec_version = self.spec_version
        
        # Schema-level checks
        self._validate_schema(df)
        
        # Row-level checks (only if we have spec rules)
        if self.mandatory_columns or self.format_rules:
            self._validate_rows(df)
        
        # Generate summary
        self.result.summary = self.result.to_summary()
        
        return self.result
    
    def _validate_schema(self, df: pd.DataFrame):
        """Validate column schema against master spec."""
        # Check for duplicate column names (from pandas merge)
        duplicate_bases = {}
        for col in df.columns:
            col_upper = col.upper()
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
        if self.mandatory_columns:
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
        if self.mandatory_columns or self.optional_columns:
            all_expected = set(c.upper() for c in self.mandatory_columns + self.optional_columns)
            for col in df.columns:
                col_upper = col.strip().upper()
                if col_upper.endswith('_X') or col_upper.endswith('_Y'):
                    normalized = col_upper[:-2]
                else:
                    normalized = col_upper
                
                if normalized not in all_expected and normalized:
                    self.result.warnings.append(
                        f"Unexpected column: {col} - not in SEATS Master Spec for {self.dataset_type}"
                    )
    
    def _validate_rows(self, df: pd.DataFrame):
        """Validate each row for data quality issues per Master Spec."""
        col_map = {c.upper(): c for c in df.columns}
        
        for idx, row in df.iterrows():
            # Validate mandatory fields are not empty
            self._validate_mandatory_fields(idx, row, col_map)
            
            # Validate date fields
            for field in self.DATE_FIELDS:
                if self._get_actual_column_name(col_map, field):
                    self._validate_date_field(idx, row, col_map, field)
            
            # Validate time fields
            for field in self.TIME_FIELDS:
                if self._get_actual_column_name(col_map, field):
                    self._validate_time_field(idx, row, col_map, field)
            
            # Validate boolean fields
            for field in self.BOOLEAN_FIELDS:
                if self._get_actual_column_name(col_map, field):
                    self._validate_boolean_field(idx, row, col_map, field)
            
            # Validate enum fields from spec
            for field, valid_values in self.enum_values.items():
                if self._get_actual_column_name(col_map, field):
                    self._validate_enum_field(idx, row, col_map, field, valid_values)
            
            # Validate time sequence if both START_TIME and END_TIME exist
            if self._get_actual_column_name(col_map, "START_TIME") and self._get_actual_column_name(col_map, "END_TIME"):
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
    
    def _is_field_mandatory(self, field: str) -> bool:
        """Check if field is mandatory per spec."""
        return field.upper() in [m.upper() for m in self.mandatory_columns]
    
    def _validate_mandatory_fields(self, idx: int, row, col_map: Dict):
        """Check mandatory fields are not empty per Master Spec."""
        for field in self.mandatory_columns:
            actual_col = self._get_actual_column_name(col_map, field)
            if not actual_col:
                continue
            
            value = self._get_column_value(row, col_map, field)
            
            if pd.isna(value) or str(value).strip() == "":
                # Check for special cases (virtual/distance lessons don't need rooms)
                if field.upper() in ["ROOM_ID", "ROOM_NAME"]:
                    lesson_type = self._get_column_value(row, col_map, "LESSON_TYPE")
                    lesson_type_str = str(lesson_type).strip().upper() if not pd.isna(lesson_type) else ""
                    if lesson_type_str in ["V", "DI"]:
                        continue
                
                # Check for time fields with virtual/distance lessons
                if field.upper() in ["START_TIME", "END_TIME"]:
                    lesson_type = self._get_column_value(row, col_map, "LESSON_TYPE")
                    lesson_type_str = str(lesson_type).strip().upper() if not pd.isna(lesson_type) else ""
                    if lesson_type_str in ["V", "DI"]:
                        continue
                
                self.result.add_error(ValidationError(
                    row_index=idx,
                    column=actual_col,
                    error_type="missing_mandatory",
                    message=f"{field} is mandatory per SEATS Master Spec and cannot be empty",
                    current_value=value,
                    suggestion=f"Provide a valid {field}"
                ))
    
    def _validate_date_field(self, idx: int, row, col_map: Dict, field: str):
        """Validate date format field against Master Spec."""
        actual_col = self._get_actual_column_name(col_map, field)
        if not actual_col:
            return
        
        value = self._get_column_value(row, col_map, field)
        
        # Get expected format from spec or use default
        format_rule = self._get_format_rule(field)
        expected_format = format_rule.get("format", self.DEFAULT_DATE_FORMAT)
        pattern = format_rule.get("pattern", self.DEFAULT_DATE_PATTERN)
        
        if pd.isna(value) or str(value).strip() == "":
            if self._is_field_mandatory(field):
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
        expected_format = format_rule.get("format", self.DEFAULT_TIME_FORMAT)
        pattern = format_rule.get("pattern", self.DEFAULT_TIME_PATTERN)
        
        if pd.isna(value) or str(value).strip() == "":
            # Check for virtual/distance lessons
            lesson_type = self._get_column_value(row, col_map, "LESSON_TYPE")
            lesson_type_str = str(lesson_type).strip().upper() if not pd.isna(lesson_type) else ""
            
            if lesson_type_str not in ["DI", "V"] and self._is_field_mandatory(field):
                self.result.add_error(ValidationError(
                    row_index=idx,
                    column=actual_col,
                    error_type="missing_value",
                    message=f"{field} is empty but required per SEATS Master Spec",
                    current_value=value,
                    expected_format=expected_format,
                    suggestion=f"Provide time in {expected_format} format"
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
        valid_values = format_rule.get("values", self.DEFAULT_BOOLEAN_VALUES)
        
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


def validate_dataset(df: pd.DataFrame, dataset_type: str, spec: Optional[Dict] = None, spec_path: Optional[str] = None) -> ValidationResult:
    """
    Validate any dataset against its SEATS Master Spec.
    
    Args:
        df: DataFrame to validate
        dataset_type: Type of dataset (e.g., 'Timetable', 'Student', 'Staff')
        spec: Optional pre-loaded specification (Master Spec)
        spec_path: Optional path to master spec JSON file
        
    Returns:
        ValidationResult with all errors
    """
    validator = SEATSValidator(dataset_type=dataset_type, spec=spec, spec_path=spec_path)
    return validator.validate(df)


# Backwards compatibility aliases
def validate_timetable(df: pd.DataFrame, spec: Optional[Dict] = None, spec_path: Optional[str] = None) -> ValidationResult:
    """Validate timetable data. Alias for validate_dataset with dataset_type='Timetable'."""
    return validate_dataset(df, "Timetable", spec, spec_path)


def validate_student(df: pd.DataFrame, spec: Optional[Dict] = None, spec_path: Optional[str] = None) -> ValidationResult:
    """Validate student data. Alias for validate_dataset with dataset_type='Student'."""
    return validate_dataset(df, "Student", spec, spec_path)


def validate_staff(df: pd.DataFrame, spec: Optional[Dict] = None, spec_path: Optional[str] = None) -> ValidationResult:
    """Validate staff data. Alias for validate_dataset with dataset_type='Staff'."""
    return validate_dataset(df, "Staff", spec, spec_path)
