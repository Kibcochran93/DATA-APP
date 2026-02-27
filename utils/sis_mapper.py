"""
SIS to SEATS Mapping Module

Automatically detects and transforms data exports from common Student Information Systems
(Banner, PeopleSoft, Workday, Colleague, Jenzabar) to SEATS format.

Features:
- Auto-detect SIS system type from column names
- Map SIS columns to SEATS columns
- Transform value codes (gender, status, etc.)
- Convert date formats
- Suggest column mappings for manual review
"""

import json
import os
import re
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum


class SISType(Enum):
    """Supported Student Information System types."""
    BANNER = "banner"
    PEOPLESOFT = "peoplesoft"
    WORKDAY = "workday"
    COLLEAGUE = "colleague"
    JENZABAR = "jenzabar"
    POWERCAMPUS = "powercampus"
    GENERIC = "generic"
    UNKNOWN = "unknown"


@dataclass
class ColumnMapping:
    """Represents a column mapping suggestion."""
    source_column: str
    target_column: str
    confidence: float  # 0.0 to 1.0
    sis_type: SISType
    reason: str


@dataclass
class SISDetectionResult:
    """Result of SIS type detection."""
    detected_type: SISType
    confidence: float
    matched_indicators: List[str]
    all_scores: Dict[str, float]


@dataclass
class TransformationReport:
    """Report of transformations applied."""
    columns_mapped: List[ColumnMapping]
    values_transformed: Dict[str, int]  # column -> count
    dates_converted: int
    warnings: List[str]
    unmapped_columns: List[str]


class SISMapper:
    """
    Maps SIS data exports to SEATS format.
    """
    
    def __init__(self, mapping_file: Optional[str] = None):
        """
        Initialize the SIS mapper.
        
        Args:
            mapping_file: Path to SIS mapping JSON file. If None, uses default.
        """
        self.mapping_config = self._load_mapping_config(mapping_file)
        self.column_mappings = self.mapping_config.get("column_mappings", {})
        self.value_mappings = self.mapping_config.get("value_mappings", {})
        self.detection_rules = self.mapping_config.get("auto_detection_rules", {})
    
    def _load_mapping_config(self, mapping_file: Optional[str] = None) -> Dict:
        """Load the SIS mapping configuration."""
        if mapping_file is None:
            # Default paths to search
            search_paths = [
                Path("/home/claude/DATA-APP/data/mappings/sis_to_seats_mapping.json"),
                Path("data/mappings/sis_to_seats_mapping.json"),
                Path("./data/mappings/sis_to_seats_mapping.json"),
                Path("/app/data/mappings/sis_to_seats_mapping.json"),
            ]
            
            for path in search_paths:
                if path.exists():
                    mapping_file = str(path)
                    break
        
        if mapping_file and os.path.exists(mapping_file):
            with open(mapping_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # Return empty config if not found
        return {}
    
    def detect_sis_type(self, df: pd.DataFrame) -> SISDetectionResult:
        """
        Auto-detect the SIS system type from column names.
        
        Args:
            df: DataFrame to analyze
            
        Returns:
            SISDetectionResult with detected type and confidence
        """
        columns_upper = set(col.upper() for col in df.columns)
        
        scores = {}
        matched = {}
        
        # Check each SIS type's indicators
        sis_indicators = {
            SISType.BANNER: self.detection_rules.get("banner_indicators", []),
            SISType.PEOPLESOFT: self.detection_rules.get("peoplesoft_indicators", []),
            SISType.WORKDAY: self.detection_rules.get("workday_indicators", []),
            SISType.COLLEAGUE: self.detection_rules.get("colleague_indicators", []),
            SISType.JENZABAR: self.detection_rules.get("jenzabar_indicators", []),
        }
        
        for sis_type, indicators in sis_indicators.items():
            matches = []
            for indicator in indicators:
                indicator_upper = indicator.upper()
                # Check for exact match or partial match in column names
                for col in columns_upper:
                    if indicator_upper in col or col.startswith(indicator_upper):
                        matches.append(indicator)
                        break
            
            score = len(matches) / max(len(indicators), 1) if indicators else 0
            scores[sis_type.value] = score
            matched[sis_type.value] = matches
        
        # Find best match
        best_type = SISType.GENERIC
        best_score = 0.0
        best_matches = []
        
        for sis_type, score in scores.items():
            if score > best_score:
                best_score = score
                best_type = SISType(sis_type)
                best_matches = matched.get(sis_type, [])
        
        # If no strong match, mark as generic
        if best_score < 0.2:
            best_type = SISType.GENERIC
        
        return SISDetectionResult(
            detected_type=best_type,
            confidence=best_score,
            matched_indicators=best_matches,
            all_scores=scores
        )
    
    def suggest_column_mappings(
        self,
        df: pd.DataFrame,
        sis_type: Optional[SISType] = None
    ) -> List[ColumnMapping]:
        """
        Suggest column mappings from source to SEATS format.
        
        Args:
            df: DataFrame with source columns
            sis_type: Optional SIS type. If None, auto-detects.
            
        Returns:
            List of ColumnMapping suggestions
        """
        if sis_type is None:
            detection = self.detect_sis_type(df)
            sis_type = detection.detected_type
        
        suggestions = []
        source_columns = list(df.columns)
        source_upper = {col.upper(): col for col in source_columns}
        
        for seats_col, mapping_info in self.column_mappings.items():
            # Get mappings for the detected SIS type
            sis_key = sis_type.value
            sis_mappings = mapping_info.get(sis_key, [])
            generic_mappings = mapping_info.get("generic", [])
            
            # Combine SIS-specific and generic mappings
            all_mappings = sis_mappings + generic_mappings
            
            best_match = None
            best_confidence = 0.0
            best_reason = ""
            
            for pattern in all_mappings:
                pattern_upper = pattern.upper()
                
                # Exact match
                if pattern_upper in source_upper:
                    if best_confidence < 1.0:
                        best_match = source_upper[pattern_upper]
                        best_confidence = 1.0
                        best_reason = f"Exact match: {pattern}"
                    break
                
                # Partial match (column contains pattern or vice versa)
                for src_upper, src_original in source_upper.items():
                    if pattern_upper in src_upper or src_upper in pattern_upper:
                        confidence = 0.8
                        if confidence > best_confidence:
                            best_match = src_original
                            best_confidence = confidence
                            best_reason = f"Partial match: {pattern}"
                    
                    # Fuzzy match using common variations
                    elif self._fuzzy_match(pattern_upper, src_upper):
                        confidence = 0.6
                        if confidence > best_confidence:
                            best_match = src_original
                            best_confidence = confidence
                            best_reason = f"Fuzzy match: {pattern}"
            
            if best_match:
                suggestions.append(ColumnMapping(
                    source_column=best_match,
                    target_column=seats_col,
                    confidence=best_confidence,
                    sis_type=sis_type,
                    reason=best_reason
                ))
        
        # Sort by confidence descending
        suggestions.sort(key=lambda x: x.confidence, reverse=True)
        
        return suggestions
    
    def _fuzzy_match(self, pattern: str, column: str) -> bool:
        """Check for fuzzy matches between pattern and column name."""
        # Remove common separators and compare
        p_clean = re.sub(r'[_\-\s]', '', pattern)
        c_clean = re.sub(r'[_\-\s]', '', column)
        
        if p_clean == c_clean:
            return True
        
        # Check if one is substring of other (min 4 chars)
        if len(p_clean) >= 4 and len(c_clean) >= 4:
            if p_clean in c_clean or c_clean in p_clean:
                return True
        
        return False
    
    def transform_dataframe(
        self,
        df: pd.DataFrame,
        column_mappings: Optional[List[ColumnMapping]] = None,
        apply_value_transforms: bool = True,
        convert_dates: bool = True
    ) -> Tuple[pd.DataFrame, TransformationReport]:
        """
        Transform a DataFrame from SIS format to SEATS format.
        
        Args:
            df: Source DataFrame
            column_mappings: Column mappings to apply. If None, auto-suggests.
            apply_value_transforms: Whether to transform value codes
            convert_dates: Whether to convert date formats
            
        Returns:
            Tuple of (transformed DataFrame, TransformationReport)
        """
        if column_mappings is None:
            column_mappings = self.suggest_column_mappings(df)
        
        df_transformed = df.copy()
        report = TransformationReport(
            columns_mapped=[],
            values_transformed={},
            dates_converted=0,
            warnings=[],
            unmapped_columns=[]
        )
        
        # Build rename mapping (only high confidence)
        rename_map = {}
        mapped_sources = set()
        
        for mapping in column_mappings:
            if mapping.confidence >= 0.6:  # Only use reasonably confident mappings
                if mapping.source_column not in mapped_sources:
                    rename_map[mapping.source_column] = mapping.target_column
                    mapped_sources.add(mapping.source_column)
                    report.columns_mapped.append(mapping)
        
        # Apply column renames
        df_transformed = df_transformed.rename(columns=rename_map)
        
        # Track unmapped columns
        for col in df.columns:
            if col not in mapped_sources:
                report.unmapped_columns.append(col)
        
        # Apply value transformations
        if apply_value_transforms:
            for seats_col, value_config in self.value_mappings.items():
                if seats_col in df_transformed.columns:
                    count = self._transform_values(
                        df_transformed, seats_col, value_config
                    )
                    if count > 0:
                        report.values_transformed[seats_col] = count
        
        # Convert dates
        if convert_dates:
            date_cols = self._identify_date_columns(df_transformed)
            for col in date_cols:
                converted = self._convert_dates(df_transformed, col)
                report.dates_converted += converted
        
        return df_transformed, report
    
    def _transform_values(
        self,
        df: pd.DataFrame,
        column: str,
        value_config: Dict
    ) -> int:
        """Transform values in a column according to mapping rules."""
        mappings = value_config.get("mappings", {})
        count = 0
        
        # Build reverse lookup: source_value -> seats_value
        reverse_map = {}
        for seats_val, source_vals in mappings.items():
            for src in source_vals:
                reverse_map[src.upper()] = seats_val
        
        def transform_value(val):
            nonlocal count
            if pd.isna(val):
                return val
            
            val_upper = str(val).strip().upper()
            if val_upper in reverse_map:
                new_val = reverse_map[val_upper]
                if str(val).upper() != new_val:
                    count += 1
                return new_val
            return val
        
        df[column] = df[column].apply(transform_value)
        return count
    
    def _identify_date_columns(self, df: pd.DataFrame) -> List[str]:
        """Identify columns that likely contain dates."""
        date_keywords = [
            'DATE', 'DOB', 'BIRTH', 'START', 'END', 'COHORT',
            'ADMIT', 'ENTRY', 'GRADUATION', 'ENROLLED'
        ]
        
        date_cols = []
        for col in df.columns:
            col_upper = col.upper()
            for keyword in date_keywords:
                if keyword in col_upper:
                    date_cols.append(col)
                    break
        
        return date_cols
    
    def _convert_dates(self, df: pd.DataFrame, column: str) -> int:
        """Convert dates to YYYY-MM-DD format."""
        count = 0
        
        def convert_date(val):
            nonlocal count
            if pd.isna(val) or str(val).strip() == '':
                return ''
            
            str_val = str(val).strip()
            
            # Already in correct format
            if re.match(r'^\d{4}-\d{2}-\d{2}$', str_val):
                return str_val
            
            # Try various formats
            formats_to_try = [
                '%d-%b-%Y',  # 15-JAN-2025 (Banner)
                '%d-%b-%y',  # 15-JAN-25 (Banner)
                '%m/%d/%Y',  # 01/15/2025 (US)
                '%d/%m/%Y',  # 15/01/2025 (UK/EU)
                '%Y/%m/%d',  # 2025/01/15
                '%m-%d-%Y',  # 01-15-2025
                '%d-%m-%Y',  # 15-01-2025
                '%Y%m%d',    # 20250115
            ]
            
            for fmt in formats_to_try:
                try:
                    from datetime import datetime
                    parsed = datetime.strptime(str_val, fmt)
                    count += 1
                    return parsed.strftime('%Y-%m-%d')
                except ValueError:
                    continue
            
            # Try pandas parsing as fallback
            try:
                parsed = pd.to_datetime(str_val, dayfirst=True, errors='coerce')
                if pd.notna(parsed):
                    count += 1
                    return parsed.strftime('%Y-%m-%d')
            except:
                pass
            
            return str_val
        
        df[column] = df[column].apply(convert_date)
        return count
    
    def get_unmapped_seats_columns(
        self,
        df: pd.DataFrame,
        seats_spec: Dict
    ) -> List[str]:
        """
        Get SEATS columns that aren't present in the DataFrame.
        
        Args:
            df: Transformed DataFrame
            seats_spec: SEATS specification dictionary
            
        Returns:
            List of missing SEATS column names
        """
        seats_fields = list(seats_spec.get("fields", {}).keys())
        df_cols_upper = set(col.upper() for col in df.columns)
        
        missing = []
        for field in seats_fields:
            if field.upper() not in df_cols_upper:
                missing.append(field)
        
        return missing


def detect_sis_type(df: pd.DataFrame) -> SISDetectionResult:
    """
    Convenience function to detect SIS type.
    
    Args:
        df: DataFrame to analyze
        
    Returns:
        SISDetectionResult
    """
    mapper = SISMapper()
    return mapper.detect_sis_type(df)


def suggest_mappings(
    df: pd.DataFrame,
    sis_type: Optional[SISType] = None
) -> List[ColumnMapping]:
    """
    Convenience function to suggest column mappings.
    
    Args:
        df: DataFrame with source columns
        sis_type: Optional SIS type
        
    Returns:
        List of ColumnMapping suggestions
    """
    mapper = SISMapper()
    return mapper.suggest_column_mappings(df, sis_type)


def transform_to_seats(
    df: pd.DataFrame,
    sis_type: Optional[SISType] = None
) -> Tuple[pd.DataFrame, TransformationReport]:
    """
    Convenience function to transform DataFrame to SEATS format.
    
    Args:
        df: Source DataFrame
        sis_type: Optional SIS type
        
    Returns:
        Tuple of (transformed DataFrame, TransformationReport)
    """
    mapper = SISMapper()
    
    if sis_type:
        mappings = mapper.suggest_column_mappings(df, sis_type)
    else:
        mappings = mapper.suggest_column_mappings(df)
    
    return mapper.transform_dataframe(df, mappings)


__all__ = [
    'SISType',
    'SISMapper',
    'ColumnMapping',
    'SISDetectionResult',
    'TransformationReport',
    'detect_sis_type',
    'suggest_mappings',
    'transform_to_seats',
]
