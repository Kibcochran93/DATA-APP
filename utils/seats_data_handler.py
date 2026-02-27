"""
SEATS Data Handler

Implements SEATS Master Spec requirements including:
- Leading zeros preservation for ID fields
- Multi-value field parsing (forward-slash, pipe separators)
- Cross-file validation for School/Course/Module consistency
- DELETE field handling for timetables
- Student Tags removal modes
- Field validation based on master specs

Reference: SEATS Data Interfaces Master Spec V8.2
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from dataclasses import dataclass, field
from pathlib import Path
import logging
import re
import json

from utils.debug_logger import setup_logger

logger = setup_logger(__name__)


# Fields that require leading zeros preservation
LEADING_ZERO_FIELDS: Set[str] = {
    # Student Data
    'STUDENT_ID', 'BADGE_NUMBER', 'STUDENT_CODE', 'EXTERNAL_ID',
    'SCHOOL_ID', 'COURSE_ID', 'MODULE_ID', 'PROGRAMME_ID',
    'FEEDER_SCHOOL_CODE',  # URN codes
    
    # Timetable
    'EVENT_ID', 'ROOM_ID', 'SITE_CODE', 'BUILDING_ID', 'TUTOR_ID',
    
    # Staff
    'STAFF_ID', 'EXTERNAL_KEY',
    
    # Badge
    'CARD_ID',
    
    # Device
    'DEVICE_ID',
    
    # Assessment
    'ASSESSMENT_ID', 'COURSE_SESSION_CODE',
    
    # Generic normalized versions
    'student_id', 'badge_number', 'student_code', 'external_id',
    'school_id', 'course_id', 'module_id', 'programme_id',
    'event_id', 'room_id', 'site_code', 'building_id', 'tutor_id',
    'staff_id', 'external_key', 'card_id', 'device_id',
    'assessment_id', 'course_session_code', 'feeder_school_code',
}


# Fields that support multiple values with forward-slash separator
FORWARD_SLASH_MULTI_VALUE_FIELDS: Set[str] = {
    # Room-related (split rooms)
    'ROOM_ID', 'ROOM_NAME',
    'SITE_CODE', 'SITE_NAME',
    'BUILDING_ID', 'BUILDING_NAME',
    
    # Tutor-related (multiple tutors)
    'TUTOR_ID', 'TUTOR', 'TUTOR_NAME',
    
    # Normalized versions
    'room_id', 'room_name', 'site_code', 'site_name',
    'building_id', 'building_name', 'tutor_id', 'tutor', 'tutor_name',
}


# Fields that support multiple values with pipe separator
PIPE_MULTI_VALUE_FIELDS: Set[str] = {
    'BADGE_NUMBER', 'badge_number',
}


# Cross-file matching fields (must be identical between Student and Timetable)
CROSS_FILE_MATCH_FIELDS: Set[str] = {
    'SCHOOL_ID', 'SCHOOL_NAME',
    'COURSE_ID', 'COURSE_NAME',
    'MODULE_ID', 'MODULE_NAME',
    'school_id', 'school_name',
    'course_id', 'course_name',
    'module_id', 'module_name',
}


# Delete field configuration
DELETE_FIELD_CONFIG = {
    'field_name': 'DELETE',
    'valid_values': {'Y', 'N'},  # Case-sensitive per V7.3
    'default_value': 'N',
}


# Student Tags removal modes
TAG_REMOVAL_MODES = {
    'AUTOMATED': 'automated',       # Automatic removal when tag disappears from file
    'MANUAL': 'manual',             # Manual removal only
    'COLUMN_BASED': 'column_based', # Use REMOVE column (Y/N)
}


@dataclass
class MultiValueField:
    """Represents a parsed multi-value field."""
    original: str
    values: List[str]
    separator: str
    
    def __str__(self) -> str:
        return self.original
    
    def to_list(self) -> List[str]:
        return self.values
    
    @classmethod
    def parse(cls, value: Any, separator: str = '/') -> 'MultiValueField':
        """Parse a multi-value field."""
        if pd.isna(value) or value is None:
            return cls(original='', values=[], separator=separator)
        
        str_value = str(value).strip()
        if not str_value:
            return cls(original='', values=[], separator=separator)
        
        values = [v.strip() for v in str_value.split(separator) if v.strip()]
        return cls(original=str_value, values=values, separator=separator)


@dataclass
class CrossFileValidationResult:
    """Result of cross-file validation."""
    is_valid: bool = True
    mismatches: List[Dict[str, Any]] = field(default_factory=list)
    missing_in_student: Set[str] = field(default_factory=set)
    missing_in_timetable: Set[str] = field(default_factory=set)
    warnings: List[str] = field(default_factory=list)
    
    def add_mismatch(self, field: str, student_value: str, timetable_value: str):
        """Add a field mismatch."""
        self.is_valid = False
        self.mismatches.append({
            'field': field,
            'student_value': student_value,
            'timetable_value': timetable_value,
        })


class SEATSDataHandler:
    """
    Handler for SEATS-specific data processing requirements.
    
    Implements Master Spec requirements for:
    - Leading zeros preservation
    - Multi-value field parsing
    - Cross-file validation
    - Delete operations
    """
    
    def __init__(self):
        """Initialize the SEATS data handler."""
        self.logger = logger
    
    def read_csv_preserve_leading_zeros(
        self, 
        file_or_path, 
        leading_zero_columns: Optional[List[str]] = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        Read CSV file while preserving leading zeros in ID fields.
        
        Args:
            file_or_path: File path or file-like object
            leading_zero_columns: Specific columns to preserve (auto-detected if None)
            **kwargs: Additional pandas read_csv arguments
            
        Returns:
            DataFrame with leading zeros preserved
        """
        # First pass: read to detect columns
        if leading_zero_columns is None:
            # Quick peek at headers
            preview_df = pd.read_csv(file_or_path, nrows=0, **kwargs)
            
            # Reset file position if it's a file-like object
            if hasattr(file_or_path, 'seek'):
                file_or_path.seek(0)
            
            # Find columns that need leading zero preservation
            leading_zero_columns = [
                col for col in preview_df.columns 
                if col.upper() in LEADING_ZERO_FIELDS or col in LEADING_ZERO_FIELDS
            ]
        
        # Build dtype dict to read these columns as strings
        dtype_dict = {col: str for col in leading_zero_columns}
        
        # Merge with any existing dtype specification
        existing_dtype = kwargs.pop('dtype', {})
        if isinstance(existing_dtype, dict):
            dtype_dict.update(existing_dtype)
        
        # Read the CSV with string types for ID columns
        df = pd.read_csv(file_or_path, dtype=dtype_dict, **kwargs)
        
        self.logger.info(
            f"Read CSV with leading zeros preserved in {len(leading_zero_columns)} columns: "
            f"{leading_zero_columns}"
        )
        
        return df
    
    def read_excel_preserve_leading_zeros(
        self,
        file_or_path,
        leading_zero_columns: Optional[List[str]] = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        Read Excel file while preserving leading zeros in ID fields.
        
        Args:
            file_or_path: File path or file-like object
            leading_zero_columns: Specific columns to preserve (auto-detected if None)
            **kwargs: Additional pandas read_excel arguments
            
        Returns:
            DataFrame with leading zeros preserved
        """
        # First pass to detect columns
        if leading_zero_columns is None:
            preview_df = pd.read_excel(file_or_path, nrows=0, **kwargs)
            
            if hasattr(file_or_path, 'seek'):
                file_or_path.seek(0)
            
            leading_zero_columns = [
                col for col in preview_df.columns 
                if col.upper() in LEADING_ZERO_FIELDS or col in LEADING_ZERO_FIELDS
            ]
        
        # Build converters dict to read these columns as strings
        converters = {col: str for col in leading_zero_columns}
        
        # Merge with any existing converters
        existing_converters = kwargs.pop('converters', {})
        converters.update(existing_converters)
        
        # Read Excel with string converters for ID columns
        df = pd.read_excel(file_or_path, converters=converters, **kwargs)
        
        self.logger.info(
            f"Read Excel with leading zeros preserved in {len(leading_zero_columns)} columns"
        )
        
        return df
    
    def parse_multi_value_field(
        self, 
        value: Any, 
        field_name: str
    ) -> MultiValueField:
        """
        Parse a multi-value field based on its type.
        
        Args:
            value: The field value to parse
            field_name: Name of the field (determines separator)
            
        Returns:
            MultiValueField with parsed values
        """
        field_upper = field_name.upper() if isinstance(field_name, str) else field_name
        
        # Determine separator based on field type
        if field_name in PIPE_MULTI_VALUE_FIELDS or field_upper in PIPE_MULTI_VALUE_FIELDS:
            separator = '|'
        elif field_name in FORWARD_SLASH_MULTI_VALUE_FIELDS or field_upper in FORWARD_SLASH_MULTI_VALUE_FIELDS:
            separator = '/'
        else:
            # Single value field
            if pd.isna(value) or value is None:
                return MultiValueField(original='', values=[], separator='')
            return MultiValueField(original=str(value), values=[str(value)], separator='')
        
        return MultiValueField.parse(value, separator)
    
    def expand_multi_value_rows(
        self,
        df: pd.DataFrame,
        field_name: str,
        keep_original: bool = False
    ) -> pd.DataFrame:
        """
        Expand rows with multi-value fields into separate rows.
        
        Useful for split rooms/tutors where each value needs its own row.
        
        Args:
            df: DataFrame to expand
            field_name: Column name with multi-values
            keep_original: Whether to keep original combined value
            
        Returns:
            DataFrame with expanded rows
        """
        if field_name not in df.columns:
            return df
        
        # Parse all values in the column
        parsed = df[field_name].apply(lambda x: self.parse_multi_value_field(x, field_name))
        
        # Find rows with multiple values
        multi_value_mask = parsed.apply(lambda x: len(x.values) > 1)
        
        if not multi_value_mask.any():
            return df
        
        # Expand rows
        expanded_rows = []
        
        for idx, row in df.iterrows():
            field_value = parsed[idx]
            
            if len(field_value.values) <= 1:
                expanded_rows.append(row)
            else:
                # Create a row for each value
                for val in field_value.values:
                    new_row = row.copy()
                    new_row[field_name] = val
                    if keep_original:
                        new_row[f'{field_name}_ORIGINAL'] = field_value.original
                    expanded_rows.append(new_row)
        
        result_df = pd.DataFrame(expanded_rows)
        result_df.reset_index(drop=True, inplace=True)
        
        self.logger.info(
            f"Expanded {multi_value_mask.sum()} multi-value rows in '{field_name}' "
            f"to {len(result_df)} total rows"
        )
        
        return result_df
    
    def validate_cross_file_consistency(
        self,
        student_df: pd.DataFrame,
        timetable_df: pd.DataFrame,
        fields_to_check: Optional[List[str]] = None
    ) -> CrossFileValidationResult:
        """
        Validate that School/Course/Module values match between Student and Timetable files.
        
        Per Master Spec: "Data placed in the School, Course, and Module fields within 
        both Student and Timetable files must match and be identical."
        
        Args:
            student_df: Student data DataFrame
            timetable_df: Timetable data DataFrame
            fields_to_check: Specific fields to check (defaults to standard set)
            
        Returns:
            CrossFileValidationResult with validation details
        """
        result = CrossFileValidationResult()
        
        if fields_to_check is None:
            fields_to_check = [
                ('SCHOOL_ID', 'SCHOOL_NAME'),
                ('COURSE_ID', 'COURSE_NAME'),
                ('MODULE_ID', 'MODULE_NAME'),
            ]
        
        for id_field, name_field in fields_to_check:
            # Check both uppercase and lowercase versions
            student_id_col = self._find_column(student_df, id_field)
            student_name_col = self._find_column(student_df, name_field)
            timetable_id_col = self._find_column(timetable_df, id_field)
            timetable_name_col = self._find_column(timetable_df, name_field)
            
            if not all([student_id_col, timetable_id_col]):
                result.warnings.append(
                    f"Cannot validate {id_field}: column not found in one or both files"
                )
                continue
            
            # Get unique ID-Name combinations from each file
            student_combos = self._get_id_name_combos(
                student_df, student_id_col, student_name_col
            )
            timetable_combos = self._get_id_name_combos(
                timetable_df, timetable_id_col, timetable_name_col
            )
            
            # Find mismatches - same ID with different names
            for id_val, student_names in student_combos.items():
                if id_val in timetable_combos:
                    timetable_names = timetable_combos[id_val]
                    if student_names != timetable_names:
                        result.add_mismatch(
                            field=f"{id_field}/{name_field}",
                            student_value=f"{id_val}: {student_names}",
                            timetable_value=f"{id_val}: {timetable_names}"
                        )
            
            # Find IDs in student but not in timetable
            student_only_ids = set(student_combos.keys()) - set(timetable_combos.keys())
            if student_only_ids:
                result.missing_in_timetable.update(
                    f"{id_field}={id_val}" for id_val in student_only_ids
                )
            
            # Find IDs in timetable but not in student
            timetable_only_ids = set(timetable_combos.keys()) - set(student_combos.keys())
            if timetable_only_ids:
                result.missing_in_student.update(
                    f"{id_field}={id_val}" for id_val in timetable_only_ids
                )
        
        if result.mismatches:
            self.logger.warning(
                f"Cross-file validation found {len(result.mismatches)} mismatches"
            )
        
        return result
    
    def _find_column(self, df: pd.DataFrame, field_name: str) -> Optional[str]:
        """Find a column by name (case-insensitive)."""
        for col in df.columns:
            if col.upper() == field_name.upper():
                return col
        return None
    
    def _get_id_name_combos(
        self, 
        df: pd.DataFrame, 
        id_col: str, 
        name_col: Optional[str]
    ) -> Dict[str, Set[str]]:
        """Get unique ID to name mappings."""
        combos: Dict[str, Set[str]] = {}
        
        for idx, row in df.iterrows():
            id_val = str(row.get(id_col, '')).strip()
            if not id_val or id_val == 'nan':
                continue
            
            name_val = ''
            if name_col and name_col in df.columns:
                name_val = str(row.get(name_col, '')).strip()
            
            if id_val not in combos:
                combos[id_val] = set()
            if name_val and name_val != 'nan':
                combos[id_val].add(name_val)
        
        return combos
    
    def process_delete_field(
        self,
        df: pd.DataFrame,
        delete_field: str = 'DELETE'
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Process the DELETE field for timetable data.
        
        Per Master Spec V7.3: DELETE field values "Y" or "N" are case-sensitive.
        
        Args:
            df: DataFrame with DELETE field
            delete_field: Name of the delete field
            
        Returns:
            Tuple of (records_to_keep, records_to_delete)
        """
        delete_col = self._find_column(df, delete_field)
        
        if delete_col is None:
            self.logger.info(f"No {delete_field} column found, keeping all records")
            return df, pd.DataFrame()
        
        # Validate DELETE values (must be exactly 'Y' or 'N', case-sensitive)
        invalid_values = df[~df[delete_col].isin(['Y', 'N', '', np.nan, None])][delete_col].unique()
        if len(invalid_values) > 0:
            self.logger.warning(
                f"Invalid DELETE values found (must be 'Y' or 'N', case-sensitive): {invalid_values}"
            )
        
        # Split records
        delete_mask = df[delete_col] == 'Y'
        records_to_delete = df[delete_mask].copy()
        records_to_keep = df[~delete_mask].copy()
        
        self.logger.info(
            f"DELETE field processing: {len(records_to_keep)} to keep, "
            f"{len(records_to_delete)} marked for deletion"
        )
        
        return records_to_keep, records_to_delete
    
    def validate_hesa_codes(
        self,
        df: pd.DataFrame,
        field_name: str,
        valid_codes: Optional[Set[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Validate HESA codes for nationality/domicile/birth fields.
        
        Per Master Spec: CTY_NATIONALITY, CTY_DOMICILE, CTY_BIRTH should use HESA codes.
        
        Args:
            df: DataFrame to validate
            field_name: Field containing HESA codes
            valid_codes: Set of valid HESA codes (optional)
            
        Returns:
            List of validation errors
        """
        errors = []
        col = self._find_column(df, field_name)
        
        if col is None:
            return errors
        
        # Basic HESA code format: typically 2-3 character country codes
        hesa_pattern = re.compile(r'^[A-Z]{2,3}$|^\d{1,3}$')
        
        for idx, value in df[col].items():
            if pd.isna(value) or value == '':
                continue
            
            str_value = str(value).strip().upper()
            
            # Check format
            if not hesa_pattern.match(str_value):
                errors.append({
                    'row': idx,
                    'field': field_name,
                    'value': value,
                    'error': 'Invalid HESA code format'
                })
            
            # Check against valid codes if provided
            if valid_codes and str_value not in valid_codes:
                errors.append({
                    'row': idx,
                    'field': field_name,
                    'value': value,
                    'error': f'Unknown HESA code: {str_value}'
                })
        
        return errors
    
    def process_student_tags(
        self,
        df: pd.DataFrame,
        removal_mode: str = 'manual',
        remove_field: str = 'REMOVE'
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Process student tags based on removal mode.
        
        Per Master Spec V8.1: Three modes for tag handling:
        1. Automated - tags removed when they disappear from file
        2. Manual - tags only removed through UI
        3. Column-based - use REMOVE column (Y/N)
        
        Args:
            df: DataFrame with tag data
            removal_mode: One of 'automated', 'manual', 'column_based'
            remove_field: Name of the remove column for column_based mode
            
        Returns:
            Tuple of (tags_to_add, tags_to_keep, tags_to_remove)
        """
        if removal_mode == 'manual':
            # In manual mode, all tags in file are to be added/updated
            return df, pd.DataFrame(), pd.DataFrame()
        
        if removal_mode == 'column_based':
            remove_col = self._find_column(df, remove_field)
            
            if remove_col is None:
                self.logger.warning(
                    f"Column-based removal requested but {remove_field} column not found"
                )
                return df, pd.DataFrame(), pd.DataFrame()
            
            remove_mask = df[remove_col].str.upper() == 'Y'
            tags_to_remove = df[remove_mask].copy()
            tags_to_keep = df[~remove_mask].copy()
            
            return tags_to_keep, pd.DataFrame(), tags_to_remove
        
        # Automated mode - return all as "to add", removal handled by comparison
        return df, pd.DataFrame(), pd.DataFrame()
    
    def load_spec(self, spec_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Load a master spec from JSON file.
        
        Args:
            spec_path: Path to the spec JSON file
            
        Returns:
            Spec dictionary
        """
        spec_path = Path(spec_path)
        
        if not spec_path.exists():
            raise FileNotFoundError(f"Spec file not found: {spec_path}")
        
        with open(spec_path, 'r', encoding='utf-8') as f:
            spec = json.load(f)
        
        self.logger.info(f"Loaded spec: {spec.get('dataset_type', 'Unknown')} v{spec.get('version', '?')}")
        return spec
    
    def validate_against_spec(
        self,
        df: pd.DataFrame,
        spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate a DataFrame against a master spec.
        
        Args:
            df: DataFrame to validate
            spec: Master spec dictionary
            
        Returns:
            Validation results dictionary
        """
        results = {
            'is_valid': True,
            'dataset_type': spec.get('dataset_type', 'Unknown'),
            'spec_version': spec.get('version', 'Unknown'),
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'errors': [],
            'warnings': [],
            'field_results': {}
        }
        
        fields_spec = spec.get('fields', {})
        mandatory_fields = spec.get('mandatory_fields', [])
        
        # Check mandatory fields
        for field_name in mandatory_fields:
            col = self._find_column(df, field_name)
            if col is None:
                results['errors'].append({
                    'type': 'missing_mandatory_field',
                    'field': field_name,
                    'message': f"Mandatory field '{field_name}' is missing"
                })
                results['is_valid'] = False
            else:
                # Check for blank values in mandatory field
                blank_count = df[col].isna().sum() + (df[col] == '').sum()
                if blank_count > 0:
                    results['errors'].append({
                        'type': 'blank_mandatory_values',
                        'field': field_name,
                        'message': f"Mandatory field '{field_name}' has {blank_count} blank values",
                        'row_count': int(blank_count)
                    })
                    results['is_valid'] = False
        
        # Validate each field
        for field_name, field_spec in fields_spec.items():
            col = self._find_column(df, field_name)
            
            if col is None:
                if field_spec.get('mandatory', False):
                    # Already handled above
                    pass
                continue
            
            field_result = self._validate_field(df[col], field_name, field_spec)
            results['field_results'][field_name] = field_result
            
            if field_result.get('errors'):
                results['errors'].extend(field_result['errors'])
                results['is_valid'] = False
            
            if field_result.get('warnings'):
                results['warnings'].extend(field_result['warnings'])
        
        return results
    
    def _validate_field(
        self,
        series: pd.Series,
        field_name: str,
        field_spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate a single field against its spec."""
        result = {
            'field': field_name,
            'total_values': len(series),
            'non_null_values': series.notna().sum(),
            'errors': [],
            'warnings': []
        }
        
        field_type = field_spec.get('type', 'str')
        
        # Check enum values
        if field_type == 'enum' and 'values' in field_spec:
            valid_values = set(field_spec['values'])
            invalid_mask = ~series.isin(valid_values) & series.notna() & (series != '')
            invalid_count = invalid_mask.sum()
            
            if invalid_count > 0:
                invalid_examples = series[invalid_mask].head(5).tolist()
                result['errors'].append({
                    'type': 'invalid_enum_value',
                    'field': field_name,
                    'message': f"Field '{field_name}' has {invalid_count} invalid values",
                    'invalid_count': int(invalid_count),
                    'examples': invalid_examples,
                    'valid_values': list(valid_values)[:10]
                })
        
        # Check pattern
        if 'pattern' in field_spec:
            pattern = re.compile(field_spec['pattern'])
            non_null = series.dropna()
            non_null = non_null[non_null != '']
            
            if len(non_null) > 0:
                matches = non_null.astype(str).str.match(pattern)
                invalid_count = (~matches).sum()
                
                if invalid_count > 0:
                    invalid_examples = non_null[~matches].head(5).tolist()
                    result['warnings'].append({
                        'type': 'pattern_mismatch',
                        'field': field_name,
                        'message': f"Field '{field_name}' has {invalid_count} values not matching pattern",
                        'invalid_count': int(invalid_count),
                        'pattern': field_spec['pattern'],
                        'examples': invalid_examples
                    })
        
        # Check max_length
        if 'max_length' in field_spec:
            max_len = field_spec['max_length']
            # Only check non-null, non-empty values
            non_null = series.dropna()
            non_null = non_null[non_null != '']
            if len(non_null) > 0:
                lengths = non_null.astype(str).str.len()
                over_max = lengths > max_len
                over_count = over_max.sum()
                
                if over_count > 0:
                    over_examples = non_null[over_max].head(3).tolist()
                    result['warnings'].append({
                        'type': 'max_length_exceeded',
                        'field': field_name,
                        'message': f"Field '{field_name}' has {over_count} values exceeding max length {max_len}",
                        'over_count': int(over_count),
                        'max_length': max_len,
                        'examples': over_examples
                    })
        
        # Check date format
        if field_type == 'date' and 'format' in field_spec:
            date_format = field_spec['format']
            non_null = series.dropna()
            non_null = non_null[non_null != '']
            
            if len(non_null) > 0:
                try:
                    pd.to_datetime(non_null, format=self._convert_date_format(date_format), errors='raise')
                except Exception:
                    # Try to count how many fail
                    failed_count = 0
                    for val in non_null:
                        try:
                            pd.to_datetime(val, format=self._convert_date_format(date_format))
                        except:
                            failed_count += 1
                    
                    if failed_count > 0:
                        result['warnings'].append({
                            'type': 'date_format_error',
                            'field': field_name,
                            'message': f"Field '{field_name}' has {failed_count} values with invalid date format",
                            'expected_format': date_format,
                            'failed_count': failed_count
                        })
        
        # Check deprecated field
        if field_spec.get('deprecated', False):
            non_null = series.dropna()
            non_null = non_null[non_null != '']
            if len(non_null) > 0:
                result['warnings'].append({
                    'type': 'deprecated_field_used',
                    'field': field_name,
                    'message': f"Deprecated field '{field_name}' contains data. {field_spec.get('notes', '')}"
                })
        
        return result
    
    def _convert_date_format(self, format_str: str) -> str:
        """Convert SEATS date format to Python strftime format."""
        conversions = {
            'YYYY': '%Y',
            'MM': '%m',
            'DD': '%d',
            'HH': '%H',
            'mm': '%M',
            'SS': '%S',
        }
        result = format_str
        for seats_fmt, py_fmt in conversions.items():
            result = result.replace(seats_fmt, py_fmt)
        return result
    
    def normalize_date_column(
        self,
        series: pd.Series,
        target_format: str = '%Y-%m-%d'
    ) -> Tuple[pd.Series, int, List[str]]:
        """
        Normalize date values to YYYY-MM-DD format.
        
        Handles common Excel/CSV date format issues:
        - DD/MM/YYYY (European)
        - MM/DD/YYYY (US)
        - DD-MM-YYYY
        - MM-DD-YYYY
        - Excel serial dates
        
        Args:
            series: Pandas Series containing date values
            target_format: Output format (default YYYY-MM-DD)
            
        Returns:
            Tuple of (normalized series, count of fixes, list of unfixable values)
        """
        result = series.copy()
        fixes_count = 0
        unfixable = []
        
        # Common date patterns to try
        date_patterns = [
            '%Y-%m-%d',      # YYYY-MM-DD (correct format)
            '%d/%m/%Y',      # DD/MM/YYYY (European Excel)
            '%m/%d/%Y',      # MM/DD/YYYY (US Excel)
            '%d-%m-%Y',      # DD-MM-YYYY
            '%m-%d-%Y',      # MM-DD-YYYY
            '%Y/%m/%d',      # YYYY/MM/DD
            '%d.%m.%Y',      # DD.MM.YYYY (some European)
        ]
        
        for idx, value in series.items():
            if pd.isna(value) or value == '':
                continue
                
            str_value = str(value).strip()
            
            # Skip if already in correct format
            if re.match(r'^\d{4}-\d{2}-\d{2}$', str_value):
                continue
            
            # Try to parse with different patterns
            parsed = None
            for pattern in date_patterns:
                try:
                    from datetime import datetime
                    parsed = datetime.strptime(str_value, pattern)
                    break
                except ValueError:
                    continue
            
            # Try pandas datetime parser as fallback
            if parsed is None:
                try:
                    parsed = pd.to_datetime(str_value, dayfirst=True)
                    if hasattr(parsed, 'to_pydatetime'):
                        parsed = parsed.to_pydatetime()
                except:
                    pass
            
            if parsed is not None:
                result.iloc[idx] = parsed.strftime(target_format)
                fixes_count += 1
            else:
                unfixable.append(str_value)
        
        return result, fixes_count, unfixable
    
    def normalize_dates_in_dataframe(
        self,
        df: pd.DataFrame,
        spec: Dict[str, Any]
    ) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
        """
        Normalize all date columns in a DataFrame based on spec.
        
        Args:
            df: DataFrame to process
            spec: Master spec with field definitions
            
        Returns:
            Tuple of (normalized DataFrame, list of changes)
        """
        result_df = df.copy()
        changes = []
        
        fields_spec = spec.get('fields', {})
        
        for field_name, field_spec in fields_spec.items():
            if field_spec.get('type') != 'date':
                continue
            
            col = self._find_column(result_df, field_name)
            if col is None:
                continue
            
            normalized, fixes_count, unfixable = self.normalize_date_column(
                result_df[col]
            )
            
            if fixes_count > 0:
                result_df[col] = normalized
                changes.append({
                    'field': field_name,
                    'fixer': 'date_normalize',
                    'rows_changed': fixes_count,
                    'target_format': 'YYYY-MM-DD'
                })
            
            if unfixable:
                self.logger.warning(
                    f"Could not parse {len(unfixable)} date values in {field_name}: "
                    f"{unfixable[:5]}"
                )
        
        return result_df, changes
    
    def apply_auto_fixes(
        self,
        df: pd.DataFrame,
        spec: Dict[str, Any]
    ) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
        """
        Apply auto-fixes based on spec fixer rules.
        
        Args:
            df: DataFrame to fix
            spec: Master spec dictionary
            
        Returns:
            Tuple of (fixed DataFrame, list of changes made)
        """
        fixed_df = df.copy()
        changes = []
        
        fields_spec = spec.get('fields', {})
        
        for field_name, field_spec in fields_spec.items():
            col = self._find_column(fixed_df, field_name)
            
            if col is None:
                continue
            
            fixer = field_spec.get('fixer')
            
            if fixer == 'uppercase':
                original = fixed_df[col].copy()
                fixed_df[col] = fixed_df[col].astype(str).str.upper()
                changed = (original != fixed_df[col]).sum()
                if changed > 0:
                    changes.append({
                        'field': field_name,
                        'fixer': 'uppercase',
                        'rows_changed': int(changed)
                    })
            
            elif fixer == 'lowercase':
                original = fixed_df[col].copy()
                fixed_df[col] = fixed_df[col].astype(str).str.lower()
                changed = (original != fixed_df[col]).sum()
                if changed > 0:
                    changes.append({
                        'field': field_name,
                        'fixer': 'lowercase',
                        'rows_changed': int(changed)
                    })
            
            elif fixer == 'strip':
                original = fixed_df[col].copy()
                fixed_df[col] = fixed_df[col].astype(str).str.strip()
                changed = (original != fixed_df[col]).sum()
                if changed > 0:
                    changes.append({
                        'field': field_name,
                        'fixer': 'strip',
                        'rows_changed': int(changed)
                    })
            
            # Apply default values
            if 'default' in field_spec:
                default_val = field_spec['default']
                null_mask = fixed_df[col].isna() | (fixed_df[col] == '')
                null_count = null_mask.sum()
                if null_count > 0:
                    fixed_df.loc[null_mask, col] = default_val
                    changes.append({
                        'field': field_name,
                        'fixer': 'default_value',
                        'default': default_val,
                        'rows_changed': int(null_count)
                    })
        
        return fixed_df, changes


# Singleton instance for convenience
_handler_instance: Optional[SEATSDataHandler] = None

def get_seats_handler() -> SEATSDataHandler:
    """Get or create the SEATS data handler singleton."""
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = SEATSDataHandler()
    return _handler_instance


def load_student_spec() -> Dict[str, Any]:
    """Load the Student Data master spec."""
    from config.config import SEATS_SPEC_PATH
    spec_path = Path(SEATS_SPEC_PATH) / 'student_data_spec.json'
    return get_seats_handler().load_spec(spec_path)


def load_timetable_spec() -> Dict[str, Any]:
    """Load the Student Timetable master spec."""
    from config.config import SEATS_SPEC_PATH
    spec_path = Path(SEATS_SPEC_PATH) / 'student_timetable_spec.json'
    return get_seats_handler().load_spec(spec_path)


def load_staff_spec() -> Dict[str, Any]:
    """Load the Staff Data master spec."""
    from config.config import SEATS_SPEC_PATH
    spec_path = Path(SEATS_SPEC_PATH) / 'staff_data_spec.json'
    return get_seats_handler().load_spec(spec_path)


def load_spec_by_type(dataset_type: str) -> Dict[str, Any]:
    """
    Load a master spec by dataset type.
    
    Args:
        dataset_type: Type of dataset (Student, StudentTimetable, Staff, etc.)
        
    Returns:
        Master spec dictionary
        
    Raises:
        ValueError: If dataset type is not recognized
    """
    spec_map = {
        'student': 'student_data_spec.json',
        'studentdata': 'student_data_spec.json',
        'timetable': 'student_timetable_spec.json',
        'studenttimetable': 'student_timetable_spec.json',
        'staff': 'staff_data_spec.json',
        'staffdata': 'staff_data_spec.json',
    }
    
    normalized_type = dataset_type.lower().replace('_', '').replace(' ', '')
    
    if normalized_type not in spec_map:
        available = list(set(spec_map.values()))
        raise ValueError(
            f"Unknown dataset type: '{dataset_type}'. "
            f"Available specs: {available}"
        )
    
    from config.config import SEATS_SPEC_PATH
    spec_path = Path(SEATS_SPEC_PATH) / spec_map[normalized_type]
    return get_seats_handler().load_spec(spec_path)


def get_ordered_fields(spec: Dict[str, Any]) -> List[str]:
    """
    Get all fields from spec in correct position order.
    
    Args:
        spec: Master spec dictionary
        
    Returns:
        List of field names sorted by position
    """
    fields = spec.get('fields', {})
    
    # Sort fields by position
    sorted_fields = sorted(
        fields.items(),
        key=lambda x: x[1].get('position', 999)
    )
    
    return [field_name for field_name, _ in sorted_fields]


def get_missing_columns(df: pd.DataFrame, spec: Dict[str, Any]) -> List[str]:
    """
    Get list of columns missing from dataframe that are in the spec.
    
    Args:
        df: DataFrame to check
        spec: Master spec dictionary
        
    Returns:
        List of missing column names in spec order
    """
    ordered_fields = get_ordered_fields(spec)
    df_columns_upper = {col.upper() for col in df.columns}
    
    missing = []
    for field in ordered_fields:
        if field.upper() not in df_columns_upper:
            missing.append(field)
    
    return missing


def insert_missing_columns(
    df: pd.DataFrame,
    spec: Dict[str, Any],
    columns_to_insert: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Insert missing columns into dataframe in correct spec order.
    
    Args:
        df: DataFrame to modify
        spec: Master spec dictionary
        columns_to_insert: Optional list of specific columns to insert.
                          If None, inserts all missing columns.
        
    Returns:
        DataFrame with missing columns inserted in correct positions
    """
    ordered_fields = get_ordered_fields(spec)
    
    if columns_to_insert is None:
        columns_to_insert = get_missing_columns(df, spec)
    
    if not columns_to_insert:
        return df
    
    # Create a mapping of current columns (case-insensitive)
    current_cols = {col.upper(): col for col in df.columns}
    
    # Build the new column order
    new_columns = []
    df_copy = df.copy()
    
    for field in ordered_fields:
        field_upper = field.upper()
        
        if field_upper in current_cols:
            # Column exists, use original case
            new_columns.append(current_cols[field_upper])
        elif field in columns_to_insert:
            # Add missing column with empty string values
            df_copy[field] = ''
            new_columns.append(field)
    
    # Add any columns from df that aren't in the spec (at the end)
    for col in df.columns:
        if col.upper() not in {f.upper() for f in ordered_fields}:
            if col not in new_columns:
                new_columns.append(col)
    
    # Reorder dataframe
    return df_copy[new_columns]


__all__ = [
    'SEATSDataHandler',
    'get_seats_handler',
    'load_student_spec',
    'load_timetable_spec',
    'load_staff_spec',
    'load_spec_by_type',
    'get_ordered_fields',
    'get_missing_columns',
    'insert_missing_columns',
    'MultiValueField',
    'CrossFileValidationResult',
    'LEADING_ZERO_FIELDS',
    'FORWARD_SLASH_MULTI_VALUE_FIELDS',
    'PIPE_MULTI_VALUE_FIELDS',
    'CROSS_FILE_MATCH_FIELDS',
]
