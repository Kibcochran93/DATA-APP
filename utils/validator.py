import re
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Union

def validate_dataset(data: pd.DataFrame, spec: Dict) -> Dict[str, Any]:
    """Validate a dataset against its specification."""
    results = {
        "is_valid": True,
        "schema_errors": [],
        "format_errors": {},
        "referential_errors": []
    }
    
    # Validate schema
    validate_schema(data, spec, results)
    
    # Validate formats
    validate_formats(data, spec, results)
    
    # Validate referential integrity
    validate_referential_integrity(data, spec, results)
    
    # Update overall validity
    results["is_valid"] = (
        not results["schema_errors"] and
        not results["format_errors"] and
        not results["referential_errors"]
    )
    
    return results

def validate_schema(data: pd.DataFrame, spec: Dict, results: Dict[str, Any]) -> None:
    """Validate the schema of the dataset."""
    # Check required fields
    missing_fields = set(spec["required_fields"]) - set(data.columns)
    if missing_fields:
        results["schema_errors"].append(f"Missing required fields: {', '.join(missing_fields)}")
    
    # Check optional fields
    unknown_fields = set(data.columns) - set(spec["required_fields"]) - set(spec.get("optional_fields", []))
    if unknown_fields:
        results["warnings"].append(f"Unknown fields found: {', '.join(unknown_fields)}")

def validate_formats(data: pd.DataFrame, spec: Dict, results: Dict[str, Any]) -> None:
    """Validate the format of each field."""
    format_rules = spec.get("format_rules", {})
    
    for field, rules in format_rules.items():
        if field not in data.columns:
            continue
            
        field_errors = []
        
        # Check pattern if specified
        if "pattern" in rules:
            pattern = re.compile(rules["pattern"])
            invalid_rows = data[~data[field].astype(str).str.match(pattern)]
            if not invalid_rows.empty:
                field_errors.append(f"Invalid format in rows: {invalid_rows.index.tolist()}")
        
        # Check type if specified
        if "type" in rules:
            try:
                convert_to_type(data[field], rules["type"])
            except Exception as e:
                field_errors.append(f"Type conversion failed: {str(e)}")
        
        if field_errors:
            results["format_errors"][field] = field_errors

def validate_referential_integrity(data: pd.DataFrame, spec: Dict, results: Dict[str, Any]) -> None:
    """Validate referential integrity constraints."""
    constraints = spec.get("referential_constraints", [])
    
    for constraint in constraints:
        source_field = constraint.get("source_field")
        target_field = constraint.get("target_field")
        target_data = constraint.get("target_data")
        
        if not all([source_field, target_field, target_data]):
            continue
            
        if source_field not in data.columns:
            results["referential_errors"].append(f"Source field {source_field} not found")
            continue
            
        invalid_values = set(data[source_field]) - set(target_data[target_field])
        if invalid_values:
            results["referential_errors"].append(
                f"Invalid values in {source_field}: {invalid_values}"
            )

def convert_to_type(data: pd.Series, target_type: str) -> pd.Series:
    """Convert data to the specified type."""
    if target_type == "int":
        return pd.to_numeric(data, errors="coerce").astype("Int64")
    elif target_type == "float":
        return pd.to_numeric(data, errors="coerce")
    elif target_type == "date":
        return pd.to_datetime(data, errors="coerce")
    elif target_type == "bool":
        return data.map({"true": True, "false": False, "yes": True, "no": False})
    elif target_type == "str":
        return data.astype(str)
    else:
        raise ValueError(f"Unsupported type: {target_type}")

def auto_fix_fields(
    data: pd.DataFrame,
    validation_results: Dict[str, Any],
    format_rules: Dict[str, Dict],
    log_changes: bool = False
) -> pd.DataFrame:
    """Attempt to automatically fix validation issues."""
    fixed_data = data.copy()
    changes_log = []
    
    # Fix format issues
    for field, errors in validation_results.get("format_errors", {}).items():
        if field not in format_rules:
            continue
            
        rules = format_rules[field]
        
        # Fix whitespace
        if rules.get("type") == "str":
            fixed_data[field] = fixed_data[field].astype(str).str.strip()
            if log_changes:
                changes_log.append(f"Stripped whitespace from {field}")
        
        # Fix case for enum values
        if rules.get("type") == "enum":
            fixed_data[field] = fixed_data[field].str.upper()
            if log_changes:
                changes_log.append(f"Converted {field} to uppercase")
        
        # Fix date format
        if rules.get("type") == "date":
            try:
                fixed_data[field] = pd.to_datetime(fixed_data[field], errors="coerce")
                if log_changes:
                    changes_log.append(f"Fixed date format in {field}")
            except:
                pass
    
    return fixed_data 