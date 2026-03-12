"""
Data Quality Detection and Fixing Module

Handles common data quality issues in SEATS data files:
- ID field issues (leading zeros, scientific notation, special chars)
- Date/time issues (mixed formats, Excel serial numbers, invalid dates)
- Text/encoding issues (BOM, hidden characters, non-ASCII)
- Multi-value field issues (wrong separators, extra spaces)
- Enum field issues (case, misspellings, invalid values)
- Structural issues (empty rows, repeated headers, footer rows)
"""

import pandas as pd
import numpy as np
import re
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import unicodedata


class IssueType(Enum):
    """Categories of data quality issues."""
    ID_FIELD = "id_field"
    DATE_TIME = "date_time"
    TEXT_ENCODING = "text_encoding"
    MULTI_VALUE = "multi_value"
    ENUM_FIELD = "enum_field"
    STRUCTURAL = "structural"


class IssueSeverity(Enum):
    """Severity levels for issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class DataQualityIssue:
    """Represents a single data quality issue."""
    issue_type: IssueType
    severity: IssueSeverity
    column: Optional[str]
    row_index: Optional[int]
    message: str
    current_value: Any
    suggested_fix: Optional[str] = None
    can_auto_fix: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "issue_type": self.issue_type.value,
            "severity": self.severity.value,
            "column": self.column,
            "row": self.row_index,
            "message": self.message,
            "current_value": str(self.current_value) if self.current_value is not None else None,
            "suggested_fix": self.suggested_fix,
            "can_auto_fix": self.can_auto_fix
        }


@dataclass
class DataQualityReport:
    """Container for all data quality issues."""
    issues: List[DataQualityIssue] = field(default_factory=list)
    
    def add_issue(self, issue: DataQualityIssue):
        self.issues.append(issue)
    
    def get_by_type(self, issue_type: IssueType) -> List[DataQualityIssue]:
        return [i for i in self.issues if i.issue_type == issue_type]
    
    def get_by_severity(self, severity: IssueSeverity) -> List[DataQualityIssue]:
        return [i for i in self.issues if i.severity == severity]
    
    def get_fixable(self) -> List[DataQualityIssue]:
        return [i for i in self.issues if i.can_auto_fix]
    
    def to_summary(self) -> Dict[str, Any]:
        by_type = {}
        by_severity = {}
        
        for issue in self.issues:
            type_key = issue.issue_type.value
            sev_key = issue.severity.value
            
            by_type[type_key] = by_type.get(type_key, 0) + 1
            by_severity[sev_key] = by_severity.get(sev_key, 0) + 1
        
        return {
            "total_issues": len(self.issues),
            "fixable_issues": len(self.get_fixable()),
            "by_type": by_type,
            "by_severity": by_severity
        }


class DataQualityAnalyzer:
    """
    Analyzes data for quality issues.
    """
    
    # Fields that should preserve leading zeros
    LEADING_ZERO_FIELDS = {
        'STUDENT_ID', 'EVENT_ID', 'COURSE_ID', 'MODULE_ID', 'SCHOOL_ID',
        'ROOM_ID', 'BUILDING_ID', 'SITE_CODE', 'TUTOR_ID', 'STAFF_ID',
        'STAFF_NUMBER', 'BADGE_NUMBER', 'EXTERNAL_KEY', 'DEVICE_ID',
        'ASSESSMENT_ID', 'COURSE_SESSION_CODE', 'MODULE_SESSION_CODE',
        'FEEDER_SCHOOL_CODE', 'GROUP_ID'
    }
    
    # Date field patterns
    DATE_FIELDS = {
        'DAY', 'DATE', 'START_DATE', 'END_DATE', 'DATE_OF_BIRTH', 'DOB',
        'COHORT', 'COHORT_START', 'COHORT_END', 'EXPIRE_DATE', 'DUE_DATE'
    }
    
    # Time field patterns
    TIME_FIELDS = {'START_TIME', 'END_TIME', 'TIME'}
    
    # Multi-value fields with their expected separators
    MULTI_VALUE_FIELDS = {
        'ROOM_ID': '/',
        'ROOM_NAME': '/',
        'BUILDING_ID': '/',
        'BUILDING_NAME': '/',
        'SITE_CODE': '/',
        'SITE_NAME': '/',
        'TUTOR_ID': '/',
        'TUTOR': '/',
        'BADGE_NUMBER': '|'
    }
    
    # Common enum expansions (full text to code)
    ENUM_EXPANSIONS = {
        'GENDER': {
            'MALE': 'M', 'FEMALE': 'F', 'OTHER': 'O',
            'MAN': 'M', 'WOMAN': 'F', 'NON-BINARY': 'O',
            'NONBINARY': 'O', 'M': 'M', 'F': 'F', 'O': 'O'
        },
        'VISAREQUIRED': {
            'YES': 'Y', 'NO': 'N', 'TRUE': 'Y', 'FALSE': 'N',
            '1': 'Y', '0': 'N', 'Y': 'Y', 'N': 'N'
        },
        'IS_MANDATORY': {
            'YES': 'Y', 'NO': 'N', 'TRUE': 'Y', 'FALSE': 'N',
            '1': 'Y', '0': 'N', 'Y': 'Y', 'N': 'N'
        },
        'DELETE': {
            'YES': 'Y', 'NO': 'N', 'TRUE': 'Y', 'FALSE': 'N',
            '1': 'Y', '0': 'N', 'Y': 'Y', 'N': 'N', '': ''
        }
    }
    
    def __init__(self, spec: Optional[Dict] = None):
        """
        Initialize analyzer with optional spec.
        
        Args:
            spec: SEATS Master Spec dictionary
        """
        self.spec = spec or {}
        self.report = DataQualityReport()
    
    def analyze(self, df: pd.DataFrame) -> DataQualityReport:
        """
        Run all quality checks on dataframe.
        
        Args:
            df: DataFrame to analyze
            
        Returns:
            DataQualityReport with all detected issues
        """
        self.report = DataQualityReport()
        
        # Structural checks (file-level)
        self._check_structural_issues(df)
        
        # Column-level checks
        for col in df.columns:
            col_upper = col.upper()
            
            # ID field checks
            if self._is_id_field(col_upper):
                self._check_id_field_issues(df, col)
            
            # Date field checks
            if self._is_date_field(col_upper):
                self._check_date_issues(df, col)
            
            # Time field checks
            if self._is_time_field(col_upper):
                self._check_time_issues(df, col)
            
            # Multi-value field checks
            if self._is_multi_value_field(col_upper):
                self._check_multi_value_issues(df, col)
            
            # Enum field checks
            if self._is_enum_field(col_upper):
                self._check_enum_issues(df, col)
            
            # Text/encoding checks (all text columns)
            if df[col].dtype == 'object':
                self._check_text_encoding_issues(df, col)
        
        return self.report
    
    # =========================================================================
    # Field Type Detection
    # =========================================================================
    
    def _is_id_field(self, col_upper: str) -> bool:
        """Check if column is an ID field."""
        # Check direct match
        if col_upper in self.LEADING_ZERO_FIELDS:
            return True
        # Check spec
        if self.spec:
            field_spec = self.spec.get('fields', {}).get(col_upper, {})
            return field_spec.get('preserve_leading_zeros', False)
        # Check if ends with _ID or _CODE
        return col_upper.endswith('_ID') or col_upper.endswith('_CODE')
    
    def _is_date_field(self, col_upper: str) -> bool:
        """Check if column is a date field."""
        if col_upper in self.DATE_FIELDS:
            return True
        if self.spec:
            field_spec = self.spec.get('fields', {}).get(col_upper, {})
            return field_spec.get('type') == 'date'
        return 'DATE' in col_upper or col_upper == 'DOB' or col_upper == 'DAY'
    
    def _is_time_field(self, col_upper: str) -> bool:
        """Check if column is a time field."""
        if col_upper in self.TIME_FIELDS:
            return True
        if self.spec:
            field_spec = self.spec.get('fields', {}).get(col_upper, {})
            return field_spec.get('type') == 'time'
        return 'TIME' in col_upper
    
    def _is_multi_value_field(self, col_upper: str) -> bool:
        """Check if column supports multiple values."""
        if col_upper in self.MULTI_VALUE_FIELDS:
            return True
        if self.spec:
            field_spec = self.spec.get('fields', {}).get(col_upper, {})
            return field_spec.get('multi_value', False)
        return False
    
    def _is_enum_field(self, col_upper: str) -> bool:
        """Check if column is an enum field."""
        if col_upper in self.ENUM_EXPANSIONS:
            return True
        if self.spec:
            field_spec = self.spec.get('fields', {}).get(col_upper, {})
            return field_spec.get('type') == 'enum' or bool(field_spec.get('values'))
        return False
    
    # =========================================================================
    # Structural Checks
    # =========================================================================
    
    def _check_structural_issues(self, df: pd.DataFrame):
        """Check for structural issues in the data."""
        
        # Check for BOM in first column name
        first_col = df.columns[0] if len(df.columns) > 0 else ""
        if first_col.startswith('\ufeff'):
            self.report.add_issue(DataQualityIssue(
                issue_type=IssueType.TEXT_ENCODING,
                severity=IssueSeverity.WARNING,
                column=first_col,
                row_index=None,
                message="File contains BOM (Byte Order Mark) at start",
                current_value=repr(first_col[:10]),
                suggested_fix="Remove BOM from file or first column name",
                can_auto_fix=True
            ))
        
        # Check for empty rows
        empty_rows = df.index[df.isna().all(axis=1)].tolist()
        if empty_rows:
            self.report.add_issue(DataQualityIssue(
                issue_type=IssueType.STRUCTURAL,
                severity=IssueSeverity.WARNING,
                column=None,
                row_index=None,
                message=f"Found {len(empty_rows)} completely empty row(s)",
                current_value=f"Rows: {empty_rows[:10]}{'...' if len(empty_rows) > 10 else ''}",
                suggested_fix="Remove empty rows",
                can_auto_fix=True
            ))
        
        # Check for repeated header rows
        if len(df) > 1:
            header_cols = set(str(c).upper() for c in df.columns)
            for idx, row in df.iterrows():
                row_vals = set(str(v).upper().strip() for v in row.values if pd.notna(v))
                # If row values match column names significantly, likely a repeated header
                overlap = header_cols.intersection(row_vals)
                if len(overlap) >= len(header_cols) * 0.7 and len(overlap) >= 3:
                    self.report.add_issue(DataQualityIssue(
                        issue_type=IssueType.STRUCTURAL,
                        severity=IssueSeverity.ERROR,
                        column=None,
                        row_index=idx,
                        message="Row appears to be a repeated header row",
                        current_value=str(list(row.values)[:5]),
                        suggested_fix="Remove duplicate header row",
                        can_auto_fix=True
                    ))
        
        # Check for footer/summary rows (last few rows with totals, counts, etc.)
        if len(df) > 3:
            last_rows = df.tail(3)
            for idx, row in last_rows.iterrows():
                first_val = str(row.iloc[0]).upper().strip() if pd.notna(row.iloc[0]) else ""
                if first_val in ['TOTAL', 'TOTALS', 'SUM', 'COUNT', 'END', 'FOOTER', '---']:
                    self.report.add_issue(DataQualityIssue(
                        issue_type=IssueType.STRUCTURAL,
                        severity=IssueSeverity.WARNING,
                        column=None,
                        row_index=idx,
                        message="Row appears to be a footer/summary row",
                        current_value=str(list(row.values)[:5]),
                        suggested_fix="Remove footer/summary row",
                        can_auto_fix=True
                    ))
    
    # =========================================================================
    # ID Field Checks
    # =========================================================================
    
    def _check_id_field_issues(self, df: pd.DataFrame, col: str):
        """Check ID field for issues based on Master Spec constraints.
        
        Generic Excel-corruption checks (scientific notation, decimal IDs) always run.
        Format-specific checks (pattern, max_length, special chars) only run when
        the spec defines constraints for the field.
        """
        col_upper = col.upper()
        field_spec = self.spec.get('fields', {}).get(col_upper, {}) if self.spec else {}
        
        # Extract spec constraints for this field
        spec_pattern = field_spec.get('pattern')
        spec_max_length = field_spec.get('max_length')
        has_spec_constraints = bool(spec_pattern or spec_max_length)
        
        for idx, value in df[col].items():
            if pd.isna(value) or str(value).strip() == '':
                continue
            
            str_val = str(value).strip()
            
            # --- Generic Excel-corruption checks (always run) ---
            
            # Check for scientific notation (e.g., 1.23E+10)
            if re.match(r'^[\d.]+[eE][+-]?\d+$', str_val):
                try:
                    num = float(str_val)
                    fixed = str(int(num)) if num == int(num) else str(num)
                except (ValueError, OverflowError):
                    fixed = str_val
                self.report.add_issue(DataQualityIssue(
                    issue_type=IssueType.ID_FIELD,
                    severity=IssueSeverity.ERROR,
                    column=col,
                    row_index=idx,
                    message="ID in scientific notation (data corrupted by Excel)",
                    current_value=str_val,
                    suggested_fix=fixed,
                    can_auto_fix=True
                ))
                continue
            
            # Check for float values that should be integers
            if re.match(r'^\d+\.0+$', str_val):
                self.report.add_issue(DataQualityIssue(
                    issue_type=IssueType.ID_FIELD,
                    severity=IssueSeverity.WARNING,
                    column=col,
                    row_index=idx,
                    message="ID has decimal point (e.g., '123.0' should be '123')",
                    current_value=str_val,
                    suggested_fix=str_val.split('.')[0],
                    can_auto_fix=True
                ))
                continue
            
            # --- Spec-driven checks (only when spec defines constraints) ---
            
            if not has_spec_constraints:
                # No format rules in spec for this field; skip format checks
                continue
            
            # Check pattern if spec defines one
            if spec_pattern:
                if not re.match(spec_pattern, str_val):
                    self.report.add_issue(DataQualityIssue(
                        issue_type=IssueType.ID_FIELD,
                        severity=IssueSeverity.WARNING,
                        column=col,
                        row_index=idx,
                        message=f"Value does not match required format: {spec_pattern}",
                        current_value=str_val,
                        suggested_fix=None,
                        can_auto_fix=False
                    ))
            
            # Check max_length if spec defines one
            if spec_max_length and len(str_val) > spec_max_length:
                truncated = str_val[:spec_max_length]
                self.report.add_issue(DataQualityIssue(
                    issue_type=IssueType.ID_FIELD,
                    severity=IssueSeverity.WARNING,
                    column=col,
                    row_index=idx,
                    message=f"Value exceeds max length of {spec_max_length} (length: {len(str_val)})",
                    current_value=str_val,
                    suggested_fix=truncated,
                    can_auto_fix=True
                ))
    
    # =========================================================================
    # Date/Time Checks
    # =========================================================================
    
    def _check_date_issues(self, df: pd.DataFrame, col: str):
        """Check date field for common issues."""
        
        # Track formats seen for consistency check
        formats_seen = {}
        
        for idx, value in df[col].items():
            if pd.isna(value) or str(value).strip() == '':
                continue
            
            str_val = str(value).strip()
            
            # Check for Excel serial number (5 digit number)
            if re.match(r'^\d{5}$', str_val):
                try:
                    excel_date = pd.to_datetime('1899-12-30') + pd.Timedelta(days=int(str_val))
                    self.report.add_issue(DataQualityIssue(
                        issue_type=IssueType.DATE_TIME,
                        severity=IssueSeverity.ERROR,
                        column=col,
                        row_index=idx,
                        message="Date appears to be Excel serial number",
                        current_value=str_val,
                        suggested_fix=excel_date.strftime('%Y-%m-%d'),
                        can_auto_fix=True
                    ))
                except:
                    pass
                continue
            
            # Check for already correct format
            if re.match(r'^\d{4}-\d{2}-\d{2}$', str_val):
                formats_seen['YYYY-MM-DD'] = formats_seen.get('YYYY-MM-DD', 0) + 1
                # Validate it's a real date
                try:
                    parsed = datetime.strptime(str_val, '%Y-%m-%d')
                    # Check for obviously wrong dates
                    if parsed.year < 1900 or parsed.year > 2100:
                        self.report.add_issue(DataQualityIssue(
                            issue_type=IssueType.DATE_TIME,
                            severity=IssueSeverity.WARNING,
                            column=col,
                            row_index=idx,
                            message=f"Date year seems invalid: {parsed.year}",
                            current_value=str_val,
                            suggested_fix=None,
                            can_auto_fix=False
                        ))
                except ValueError:
                    self.report.add_issue(DataQualityIssue(
                        issue_type=IssueType.DATE_TIME,
                        severity=IssueSeverity.ERROR,
                        column=col,
                        row_index=idx,
                        message="Invalid date (e.g., Feb 31)",
                        current_value=str_val,
                        suggested_fix=None,
                        can_auto_fix=False
                    ))
                continue
            
            # Check for DD/MM/YYYY or MM/DD/YYYY
            if re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', str_val):
                parts = str_val.split('/')
                day_or_month1, day_or_month2, year = int(parts[0]), int(parts[1]), parts[2]
                
                # Determine if DD/MM or MM/DD based on values
                if day_or_month1 > 12:
                    detected_format = 'DD/MM/YYYY'
                    suggested = f"{year}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                elif day_or_month2 > 12:
                    detected_format = 'MM/DD/YYYY'
                    suggested = f"{year}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
                else:
                    # Ambiguous - assume DD/MM/YYYY (more common internationally)
                    detected_format = 'DD/MM/YYYY (assumed)'
                    suggested = f"{year}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                
                formats_seen[detected_format] = formats_seen.get(detected_format, 0) + 1
                
                self.report.add_issue(DataQualityIssue(
                    issue_type=IssueType.DATE_TIME,
                    severity=IssueSeverity.WARNING,
                    column=col,
                    row_index=idx,
                    message=f"Date format is {detected_format}, should be YYYY-MM-DD",
                    current_value=str_val,
                    suggested_fix=suggested,
                    can_auto_fix=True
                ))
                continue
            
            # Check for DD-MM-YYYY
            if re.match(r'^\d{1,2}-\d{1,2}-\d{4}$', str_val):
                parts = str_val.split('-')
                suggested = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                self.report.add_issue(DataQualityIssue(
                    issue_type=IssueType.DATE_TIME,
                    severity=IssueSeverity.WARNING,
                    column=col,
                    row_index=idx,
                    message="Date format is DD-MM-YYYY, should be YYYY-MM-DD",
                    current_value=str_val,
                    suggested_fix=suggested,
                    can_auto_fix=True
                ))
                continue
            
            # Check for datetime combined (should be date only)
            if re.match(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}', str_val):
                date_part = str_val[:10]
                self.report.add_issue(DataQualityIssue(
                    issue_type=IssueType.DATE_TIME,
                    severity=IssueSeverity.WARNING,
                    column=col,
                    row_index=idx,
                    message="Date contains time component, should be date only",
                    current_value=str_val,
                    suggested_fix=date_part,
                    can_auto_fix=True
                ))
        
        # Check for mixed formats in column
        if len(formats_seen) > 1:
            self.report.add_issue(DataQualityIssue(
                issue_type=IssueType.DATE_TIME,
                severity=IssueSeverity.ERROR,
                column=col,
                row_index=None,
                message=f"Mixed date formats in column: {list(formats_seen.keys())}",
                current_value=str(formats_seen),
                suggested_fix="Standardize all dates to YYYY-MM-DD",
                can_auto_fix=True
            ))
    
    def _check_time_issues(self, df: pd.DataFrame, col: str):
        """Check time field for common issues."""
        
        for idx, value in df[col].items():
            if pd.isna(value) or str(value).strip() == '':
                continue
            
            str_val = str(value).strip()
            
            # Check for correct format HH:MM
            if re.match(r'^\d{2}:\d{2}$', str_val):
                # Validate hours and minutes
                hours, mins = map(int, str_val.split(':'))
                if hours > 23 or mins > 59:
                    self.report.add_issue(DataQualityIssue(
                        issue_type=IssueType.DATE_TIME,
                        severity=IssueSeverity.ERROR,
                        column=col,
                        row_index=idx,
                        message=f"Invalid time value: hours={hours}, minutes={mins}",
                        current_value=str_val,
                        suggested_fix=None,
                        can_auto_fix=False
                    ))
                continue
            
            # Check for H:MM format (missing leading zero)
            if re.match(r'^\d:\d{2}$', str_val):
                suggested = f"0{str_val}"
                self.report.add_issue(DataQualityIssue(
                    issue_type=IssueType.DATE_TIME,
                    severity=IssueSeverity.WARNING,
                    column=col,
                    row_index=idx,
                    message="Time missing leading zero",
                    current_value=str_val,
                    suggested_fix=suggested,
                    can_auto_fix=True
                ))
                continue
            
            # Check for HH:MM:SS format (should be HH:MM)
            if re.match(r'^\d{2}:\d{2}:\d{2}$', str_val):
                suggested = str_val[:5]
                self.report.add_issue(DataQualityIssue(
                    issue_type=IssueType.DATE_TIME,
                    severity=IssueSeverity.WARNING,
                    column=col,
                    row_index=idx,
                    message="Time has seconds, should be HH:MM only",
                    current_value=str_val,
                    suggested_fix=suggested,
                    can_auto_fix=True
                ))
                continue
            
            # Check for 12-hour format with AM/PM
            if re.match(r'^\d{1,2}:\d{2}\s*(AM|PM|am|pm)$', str_val, re.IGNORECASE):
                # Convert to 24-hour
                match = re.match(r'^(\d{1,2}):(\d{2})\s*(AM|PM)$', str_val, re.IGNORECASE)
                if match:
                    hours, mins, period = int(match.group(1)), match.group(2), match.group(3).upper()
                    if period == 'PM' and hours != 12:
                        hours += 12
                    elif period == 'AM' and hours == 12:
                        hours = 0
                    suggested = f"{hours:02d}:{mins}"
                    self.report.add_issue(DataQualityIssue(
                        issue_type=IssueType.DATE_TIME,
                        severity=IssueSeverity.WARNING,
                        column=col,
                        row_index=idx,
                        message="Time in 12-hour format, should be 24-hour HH:MM",
                        current_value=str_val,
                        suggested_fix=suggested,
                        can_auto_fix=True
                    ))
    
    # =========================================================================
    # Text/Encoding Checks
    # =========================================================================
    
    def _check_text_encoding_issues(self, df: pd.DataFrame, col: str):
        """Check text field for encoding and character issues."""
        
        # Sample to avoid performance issues on large datasets
        sample_size = min(1000, len(df))
        sample_indices = df.index[:sample_size]
        
        for idx in sample_indices:
            value = df.loc[idx, col]
            if pd.isna(value):
                continue
            
            str_val = str(value)
            
            # Check for hidden characters
            hidden_chars = []
            for char in str_val:
                if unicodedata.category(char) in ('Cc', 'Cf', 'Co', 'Cs'):
                    if char not in ('\n', '\r', '\t'):
                        hidden_chars.append((char, hex(ord(char))))
            
            if hidden_chars:
                self.report.add_issue(DataQualityIssue(
                    issue_type=IssueType.TEXT_ENCODING,
                    severity=IssueSeverity.WARNING,
                    column=col,
                    row_index=idx,
                    message=f"Hidden/control characters found: {hidden_chars[:3]}",
                    current_value=repr(str_val[:50]),
                    suggested_fix="Remove hidden characters",
                    can_auto_fix=True
                ))
            
            # Check for non-breaking spaces
            if '\xa0' in str_val or '\u00a0' in str_val:
                self.report.add_issue(DataQualityIssue(
                    issue_type=IssueType.TEXT_ENCODING,
                    severity=IssueSeverity.WARNING,
                    column=col,
                    row_index=idx,
                    message="Non-breaking spaces found",
                    current_value=repr(str_val[:50]),
                    suggested_fix="Replace with regular spaces",
                    can_auto_fix=True
                ))
            
            # Check for zero-width characters
            zero_width = ['\u200b', '\u200c', '\u200d', '\ufeff']
            for zw in zero_width:
                if zw in str_val:
                    self.report.add_issue(DataQualityIssue(
                        issue_type=IssueType.TEXT_ENCODING,
                        severity=IssueSeverity.WARNING,
                        column=col,
                        row_index=idx,
                        message="Zero-width characters found",
                        current_value=repr(str_val[:50]),
                        suggested_fix="Remove zero-width characters",
                        can_auto_fix=True
                    ))
                    break
    
    # =========================================================================
    # Multi-Value Field Checks
    # =========================================================================
    
    def _check_multi_value_issues(self, df: pd.DataFrame, col: str):
        """Check multi-value field for separator issues."""
        
        col_upper = col.upper()
        expected_sep = self.MULTI_VALUE_FIELDS.get(col_upper)
        
        if not expected_sep:
            # Check spec
            if self.spec:
                field_spec = self.spec.get('fields', {}).get(col_upper, {})
                expected_sep = field_spec.get('separator', '/')
            else:
                expected_sep = '/'
        
        wrong_seps = {',': 'comma', ';': 'semicolon', '\\': 'backslash'}
        
        for idx, value in df[col].items():
            if pd.isna(value) or str(value).strip() == '':
                continue
            
            str_val = str(value).strip()
            
            # Check for wrong separator
            for wrong_sep, sep_name in wrong_seps.items():
                if wrong_sep in str_val and expected_sep not in str_val:
                    self.report.add_issue(DataQualityIssue(
                        issue_type=IssueType.MULTI_VALUE,
                        severity=IssueSeverity.WARNING,
                        column=col,
                        row_index=idx,
                        message=f"Using {sep_name} separator, should use '{expected_sep}'",
                        current_value=str_val,
                        suggested_fix=str_val.replace(wrong_sep, expected_sep),
                        can_auto_fix=True
                    ))
                    break
            
            # Check for spaces around separator
            if expected_sep in str_val:
                # Check for " / " instead of "/"
                if f' {expected_sep} ' in str_val or f' {expected_sep}' in str_val or f'{expected_sep} ' in str_val:
                    cleaned = re.sub(rf'\s*{re.escape(expected_sep)}\s*', expected_sep, str_val)
                    if cleaned != str_val:
                        self.report.add_issue(DataQualityIssue(
                            issue_type=IssueType.MULTI_VALUE,
                            severity=IssueSeverity.WARNING,
                            column=col,
                            row_index=idx,
                            message=f"Extra spaces around '{expected_sep}' separator",
                            current_value=str_val,
                            suggested_fix=cleaned,
                            can_auto_fix=True
                        ))
    
    # =========================================================================
    # Enum Field Checks
    # =========================================================================
    
    def _check_enum_issues(self, df: pd.DataFrame, col: str):
        """Check enum field for invalid values."""
        
        col_upper = col.upper()
        
        # Get valid values from spec or defaults
        valid_values = set()
        expansions = self.ENUM_EXPANSIONS.get(col_upper, {})
        
        if self.spec:
            field_spec = self.spec.get('fields', {}).get(col_upper, {})
            spec_values = field_spec.get('values', [])
            valid_values = set(v.upper() for v in spec_values if v)
        
        if not valid_values and expansions:
            valid_values = set(expansions.values())
        
        for idx, value in df[col].items():
            if pd.isna(value) or str(value).strip() == '':
                continue
            
            str_val = str(value).strip()
            str_upper = str_val.upper()
            
            # Check if value needs expansion
            if str_upper in expansions:
                correct_val = expansions[str_upper]
                if str_val != correct_val:
                    self.report.add_issue(DataQualityIssue(
                        issue_type=IssueType.ENUM_FIELD,
                        severity=IssueSeverity.WARNING,
                        column=col,
                        row_index=idx,
                        message=f"Value should be '{correct_val}' not '{str_val}'",
                        current_value=str_val,
                        suggested_fix=correct_val,
                        can_auto_fix=True
                    ))
                continue
            
            # Check case
            if valid_values and str_upper in valid_values and str_val != str_upper:
                self.report.add_issue(DataQualityIssue(
                    issue_type=IssueType.ENUM_FIELD,
                    severity=IssueSeverity.WARNING,
                    column=col,
                    row_index=idx,
                    message=f"Value should be uppercase: '{str_upper}'",
                    current_value=str_val,
                    suggested_fix=str_upper,
                    can_auto_fix=True
                ))
                continue
            
            # Check for invalid value
            if valid_values and str_upper not in valid_values:
                # Find closest match
                closest = None
                for valid in valid_values:
                    if str_upper.startswith(valid) or valid.startswith(str_upper):
                        closest = valid
                        break
                
                self.report.add_issue(DataQualityIssue(
                    issue_type=IssueType.ENUM_FIELD,
                    severity=IssueSeverity.ERROR,
                    column=col,
                    row_index=idx,
                    message=f"Invalid value, allowed: {sorted(valid_values)[:10]}",
                    current_value=str_val,
                    suggested_fix=closest,
                    can_auto_fix=closest is not None
                ))


class DataQualityFixer:
    """
    Fixes data quality issues detected by DataQualityAnalyzer.
    """
    
    def __init__(self, spec: Optional[Dict] = None):
        """
        Initialize fixer with optional spec.
        
        Args:
            spec: SEATS Master Spec dictionary
        """
        self.spec = spec or {}
    
    def fix_all(
        self,
        df: pd.DataFrame,
        report: DataQualityReport,
        fix_ids: bool = True,
        fix_dates: bool = True,
        fix_times: bool = True,
        fix_encoding: bool = True,
        fix_multi_value: bool = True,
        fix_enums: bool = True,
        fix_structural: bool = True
    ) -> Tuple[pd.DataFrame, Dict[str, int]]:
        """
        Apply all auto-fixable fixes to dataframe.
        
        Args:
            df: DataFrame to fix
            report: DataQualityReport from analyzer
            fix_*: Flags to enable/disable specific fix types
            
        Returns:
            Tuple of (fixed DataFrame, dict of fix counts by type)
        """
        df_fixed = df.copy()
        fix_counts = {
            'id_field': 0,
            'date_time': 0,
            'text_encoding': 0,
            'multi_value': 0,
            'enum_field': 0,
            'structural': 0
        }
        
        # Pre-convert ID field columns to string to avoid dtype warnings
        if fix_ids:
            id_columns = [
                'STUDENT_ID', 'EVENT_ID', 'COURSE_ID', 'MODULE_ID', 'STAFF_ID',
                'ROOM_ID', 'SCHOOL_ID', 'SITE_ID', 'FACULTY_ID', 'BADGE_NUMBER',
                'TUTOR_ID', 'CAS_NUMBER', 'VISA_NUMBER'
            ]
            for col in df_fixed.columns:
                if col.upper() in id_columns or col.upper().endswith('_ID'):
                    if col in df_fixed.columns and pd.api.types.is_numeric_dtype(df_fixed[col].dtype):
                        df_fixed[col] = df_fixed[col].astype(object)
        
        # Track rows to remove (structural issues)
        rows_to_remove = set()
        
        for issue in report.get_fixable():
            if not issue.can_auto_fix or issue.suggested_fix is None:
                continue
            
            # Structural fixes
            if issue.issue_type == IssueType.STRUCTURAL:
                if not fix_structural:
                    continue
                if issue.row_index is not None:
                    rows_to_remove.add(issue.row_index)
                    fix_counts['structural'] += 1
                continue
            
            # Column-level fixes
            col = issue.column
            idx = issue.row_index
            
            if col is None or col not in df_fixed.columns:
                continue
            
            # Check fix type flags
            if issue.issue_type == IssueType.ID_FIELD and not fix_ids:
                continue
            if issue.issue_type == IssueType.DATE_TIME and not fix_dates and not fix_times:
                continue
            if issue.issue_type == IssueType.TEXT_ENCODING and not fix_encoding:
                continue
            if issue.issue_type == IssueType.MULTI_VALUE and not fix_multi_value:
                continue
            if issue.issue_type == IssueType.ENUM_FIELD and not fix_enums:
                continue
            
            # Apply fix
            if idx is not None:
                # Ensure column can accept the fix value (convert to object if needed)
                if issue.suggested_fix is not None:
                    current_dtype = df_fixed[col].dtype
                    # If column is numeric and fix is string, convert column to object
                    if pd.api.types.is_numeric_dtype(current_dtype) and isinstance(issue.suggested_fix, str):
                        df_fixed[col] = df_fixed[col].astype(object)
                    df_fixed.loc[idx, col] = issue.suggested_fix
            else:
                # Column-wide fix (like mixed date formats)
                # This would need special handling per issue type
                pass
            
            fix_counts[issue.issue_type.value] += 1
        
        # Remove structural issue rows
        if rows_to_remove:
            df_fixed = df_fixed.drop(index=list(rows_to_remove))
            df_fixed = df_fixed.reset_index(drop=True)
        
        # Fix BOM in column names
        if fix_encoding:
            new_cols = []
            for col in df_fixed.columns:
                if col.startswith('\ufeff'):
                    new_cols.append(col[1:])
                    fix_counts['text_encoding'] += 1
                else:
                    new_cols.append(col)
            df_fixed.columns = new_cols
        
        return df_fixed, fix_counts
    
    def fix_id_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fix common ID field issues."""
        df_fixed = df.copy()
        
        # Get ID columns
        id_cols = [col for col in df_fixed.columns 
                   if col.upper() in DataQualityAnalyzer.LEADING_ZERO_FIELDS
                   or col.upper().endswith('_ID')
                   or col.upper().endswith('_CODE')]
        
        for col in id_cols:
            df_fixed[col] = df_fixed[col].apply(self._fix_id_value)
        
        return df_fixed
    
    def _fix_id_value(self, value) -> str:
        """Fix a single ID value."""
        if pd.isna(value):
            return ''
        
        str_val = str(value).strip()
        
        # Fix scientific notation
        if re.match(r'^[\d.]+[eE][+-]?\d+$', str_val):
            try:
                num = float(str_val)
                if num == int(num):
                    return str(int(num))
                return str(num)
            except:
                pass
        
        # Fix decimal (123.0 -> 123)
        if re.match(r'^\d+\.0+$', str_val):
            return str_val.split('.')[0]
        
        return str_val
    
    def fix_dates(self, df: pd.DataFrame, date_cols: Optional[List[str]] = None) -> pd.DataFrame:
        """Fix date formatting to YYYY-MM-DD."""
        df_fixed = df.copy()
        
        if date_cols is None:
            date_cols = [col for col in df_fixed.columns 
                        if col.upper() in DataQualityAnalyzer.DATE_FIELDS]
        
        for col in date_cols:
            df_fixed[col] = df_fixed[col].apply(self._fix_date_value)
        
        return df_fixed
    
    def _fix_date_value(self, value) -> str:
        """Fix a single date value to YYYY-MM-DD."""
        if pd.isna(value) or str(value).strip() == '':
            return ''
        
        str_val = str(value).strip()
        
        # Already correct
        if re.match(r'^\d{4}-\d{2}-\d{2}$', str_val):
            return str_val
        
        # Excel serial number
        if re.match(r'^\d{5}$', str_val):
            try:
                excel_date = pd.to_datetime('1899-12-30') + pd.Timedelta(days=int(str_val))
                return excel_date.strftime('%Y-%m-%d')
            except:
                pass
        
        # Try pandas parsing with dayfirst
        try:
            parsed = pd.to_datetime(str_val, dayfirst=True, errors='coerce')
            if pd.notna(parsed):
                return parsed.strftime('%Y-%m-%d')
        except:
            pass
        
        return str_val
    
    def fix_times(self, df: pd.DataFrame, time_cols: Optional[List[str]] = None) -> pd.DataFrame:
        """Fix time formatting to HH:MM."""
        df_fixed = df.copy()
        
        if time_cols is None:
            time_cols = [col for col in df_fixed.columns 
                        if col.upper() in DataQualityAnalyzer.TIME_FIELDS]
        
        for col in time_cols:
            df_fixed[col] = df_fixed[col].apply(self._fix_time_value)
        
        return df_fixed
    
    def _fix_time_value(self, value) -> str:
        """Fix a single time value to HH:MM."""
        if pd.isna(value) or str(value).strip() == '':
            return ''
        
        str_val = str(value).strip()
        
        # Already correct
        if re.match(r'^\d{2}:\d{2}$', str_val):
            return str_val
        
        # Missing leading zero (9:00 -> 09:00)
        if re.match(r'^\d:\d{2}$', str_val):
            return f"0{str_val}"
        
        # Has seconds (09:00:00 -> 09:00)
        if re.match(r'^\d{2}:\d{2}:\d{2}$', str_val):
            return str_val[:5]
        
        # 12-hour format
        match = re.match(r'^(\d{1,2}):(\d{2})\s*(AM|PM)$', str_val, re.IGNORECASE)
        if match:
            hours, mins, period = int(match.group(1)), match.group(2), match.group(3).upper()
            if period == 'PM' and hours != 12:
                hours += 12
            elif period == 'AM' and hours == 12:
                hours = 0
            return f"{hours:02d}:{mins}"
        
        return str_val
    
    def fix_encoding(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fix text encoding issues."""
        df_fixed = df.copy()
        
        # Fix column names
        new_cols = []
        for col in df_fixed.columns:
            new_col = col
            if new_col.startswith('\ufeff'):
                new_col = new_col[1:]
            new_cols.append(new_col)
        df_fixed.columns = new_cols
        
        # Fix text values
        for col in df_fixed.select_dtypes(include=['object']).columns:
            df_fixed[col] = df_fixed[col].apply(self._fix_encoding_value)
        
        return df_fixed
    
    def _fix_encoding_value(self, value) -> str:
        """Fix encoding issues in a single value."""
        if pd.isna(value):
            return ''
        
        str_val = str(value)
        
        # Remove BOM
        str_val = str_val.replace('\ufeff', '')
        
        # Replace non-breaking spaces
        str_val = str_val.replace('\xa0', ' ').replace('\u00a0', ' ')
        
        # Remove zero-width characters
        for zw in ['\u200b', '\u200c', '\u200d', '\ufeff']:
            str_val = str_val.replace(zw, '')
        
        # Remove other control characters (except newlines/tabs)
        result = []
        for char in str_val:
            cat = unicodedata.category(char)
            if cat not in ('Cc', 'Cf', 'Co', 'Cs') or char in '\n\r\t':
                result.append(char)
        
        return ''.join(result)


def analyze_data_quality(df: pd.DataFrame, spec: Optional[Dict] = None) -> DataQualityReport:
    """
    Convenience function to analyze data quality.
    
    Args:
        df: DataFrame to analyze
        spec: Optional SEATS spec dictionary
        
    Returns:
        DataQualityReport with all detected issues
    """
    analyzer = DataQualityAnalyzer(spec)
    return analyzer.analyze(df)


def fix_data_quality(
    df: pd.DataFrame,
    report: DataQualityReport,
    spec: Optional[Dict] = None,
    **kwargs
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    Convenience function to fix data quality issues.
    
    Args:
        df: DataFrame to fix
        report: DataQualityReport from analyze_data_quality
        spec: Optional SEATS spec dictionary
        **kwargs: Passed to DataQualityFixer.fix_all()
        
    Returns:
        Tuple of (fixed DataFrame, fix counts)
    """
    fixer = DataQualityFixer(spec)
    return fixer.fix_all(df, report, **kwargs)


__all__ = [
    'IssueType',
    'IssueSeverity',
    'DataQualityIssue',
    'DataQualityReport',
    'DataQualityAnalyzer',
    'DataQualityFixer',
    'analyze_data_quality',
    'fix_data_quality',
]
