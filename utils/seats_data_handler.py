"""
SEATS Data Handler

Implements SEATS Master Spec requirements including:
- Leading zeros preservation for ID fields
- Multi-value field parsing (forward-slash, pipe separators)
- Cross-file validation for School/Course/Module consistency
- DELETE field handling for timetables
- Student Tags removal modes

Reference: SEATS Data Interfaces Master Spec V8.2
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
import logging
import re

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


# Singleton instance for convenience
_handler_instance: Optional[SEATSDataHandler] = None

def get_seats_handler() -> SEATSDataHandler:
    """Get or create the SEATS data handler singleton."""
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = SEATSDataHandler()
    return _handler_instance


__all__ = [
    'SEATSDataHandler',
    'get_seats_handler',
    'MultiValueField',
    'CrossFileValidationResult',
    'LEADING_ZERO_FIELDS',
    'FORWARD_SLASH_MULTI_VALUE_FIELDS',
    'PIPE_MULTI_VALUE_FIELDS',
    'CROSS_FILE_MATCH_FIELDS',
]
