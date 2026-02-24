import pandas as pd
from datetime import datetime
from helpers.normalization import normalize_header_list, find_best_match
from typing import Dict, List, Union, Any
import re
from utils.input_validator import validate_dataset, validate_schema, validate_headers
from utils.data_cleaner import DataCleaner
import logging

logger = logging.getLogger(__name__)

def resolve_dataset_type(dataset_type: str, expected_headers: dict) -> str:
    if dataset_type in expected_headers:
        return dataset_type
    if len(expected_headers) == 1:
        return next(iter(expected_headers))
    raise KeyError(f"Cannot resolve dataset_type '{dataset_type}' from keys: {list(expected_headers.keys())}")

def get_unexpected_fields(df: pd.DataFrame, dataset_type: str, expected_headers: dict):
    dataset_type = resolve_dataset_type(dataset_type, expected_headers)
    expected = set(expected_headers[dataset_type].get("mandatory", []) +
                   expected_headers[dataset_type].get("optional", []))
    found = set(normalize_header_list(df.columns))
    return sorted(list(found - expected))

def validate_missing_fields(df: pd.DataFrame, dataset_type: str, expected_headers: dict):
    dataset_type = resolve_dataset_type(dataset_type, expected_headers)
    required = set(expected_headers[dataset_type].get("mandatory", []))
    found = set(normalize_header_list(df.columns))
    return sorted(list(required - found))

def validate_field_formats(df: pd.DataFrame, dataset_type: str, format_rules: dict):
    dataset_type = resolve_dataset_type(dataset_type, format_rules)
    errors = []
    
    for col in df.columns:
        normalized_col = normalize_header(col)
        if normalized_col in format_rules.get(dataset_type, {}):
            rule = format_rules[dataset_type][normalized_col]
            if not validate_field_format(df[col], rule):
                errors.append(f"Invalid format for {col}")
    
    return errors

def validate_field_format(series: pd.Series, rule: dict) -> bool:
    """
    Validate field format according to rules.
    
    Args:
        series: Pandas Series containing values to validate
        rule: Dictionary containing validation rules
        
    Returns:
        bool: True if all values pass validation
    """
    try:
        # Handle empty/null values
        if series.isna().all():
            return not rule.get("validation", {}).get("required", False)
            
        # Type validation
        field_type = rule.get("type", "str")
        if field_type == "numeric":
            if not pd.to_numeric(series, errors='coerce').notna().all():
                return False
        elif field_type == "date":
            if "format" not in rule:
                return False
            try:
                pd.to_datetime(series, format=rule["format"], errors='raise')
            except ValueError:
                return False
                
        # Pattern validation
        if "pattern" in rule:
            pattern = re.compile(rule["pattern"])
            if not series.astype(str).str.match(pattern).all():
                return False
                
        # Enum validation
        if "values" in rule:
            valid_values = set(rule["values"])
            if not series.isin(valid_values).all():
                return False
                
        return True
        
    except Exception as e:
        logger.error(f"Field format validation error: {str(e)}")
        return False

def check_referential_integrity(df: pd.DataFrame, ref_df: pd.DataFrame, key_field: str, validation_rule: dict = None) -> List[str]:
    """
    Check referential integrity between datasets.
    
    Args:
        df: Source DataFrame
        ref_df: Reference DataFrame
        key_field: Field to check
        validation_rule: Optional validation rule containing foreign key config
        
    Returns:
        List of error messages
    """
    errors = []
    
    # Validate field existence
    if key_field not in df.columns or key_field not in ref_df.columns:
        errors.append(f"Key field {key_field} not found in both datasets")
        return errors
    
    # Get reference field if specified in validation rule
    ref_field = key_field
    if validation_rule and "foreign_key" in validation_rule:
        ref_field = validation_rule["foreign_key"].get("field", key_field)
        if ref_field not in ref_df.columns:
            errors.append(f"Reference field {ref_field} not found in target dataset")
            return errors
    
    # Check for missing keys
    df_keys = set(df[key_field].dropna())
    ref_keys = set(ref_df[ref_field].dropna())
    
    missing_keys = df_keys - ref_keys
    if missing_keys:
        error_msg = f"Found {len(missing_keys)} keys in dataset not present in reference"
        if len(missing_keys) <= 5:  # Show examples if few
            error_msg += f": {sorted(list(missing_keys))}"
        errors.append(error_msg)
    
    # Check for null values if required
    if validation_rule and validation_rule.get("required", False):
        null_count = df[key_field].isna().sum()
        if null_count > 0:
            errors.append(f"Found {null_count} null values in required foreign key field {key_field}")
    
    return errors

def auto_fix_fields(
    df: pd.DataFrame,
    validation_results: Dict[str, Any],
    format_rules: dict,
    log_changes: bool = False
) -> pd.DataFrame:
    """
    Apply auto-fix rules based on validation results and format rules.
    
    Args:
        df: DataFrame to fix
        validation_results: Validation results containing issues to fix
        format_rules: Format rules from JSON spec
        log_changes: Whether to log changes
        
    Returns:
        Fixed DataFrame
    """
    try:
        # Store original values for logging
        original_df = df.copy()
        
        # Initialize cleaner
        cleaner = DataCleaner()
        
        # Use cleaner's auto-fix functionality
        fixed_df = cleaner.auto_fix_dataframe(df, format_rules, log_changes)
        
        # Log changes if requested
        if log_changes:
            for column in fixed_df.columns:
                if not fixed_df[column].equals(original_df[column]):
                    changed_mask = fixed_df[column] != original_df[column]
                    changed_indices = changed_mask[changed_mask].index
                    for idx in changed_indices:
                        logger.info(
                            f"Auto-fix applied to {column} at index {idx}: "
                            f"'{original_df.loc[idx, column]}' -> '{fixed_df.loc[idx, column]}'"
                        )
        
        # Validate fixes
        post_fix_validation = validate_field_formats(fixed_df, next(iter(format_rules.keys())), format_rules)
        if post_fix_validation:
            logger.warning(f"Post-fix validation issues: {post_fix_validation}")
            
        return fixed_df
        
    except Exception as e:
        logger.error(f"Auto-fix failed: {str(e)}")
        return df
