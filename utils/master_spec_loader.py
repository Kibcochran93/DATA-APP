# Standard library imports
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, Literal, TypedDict, List, Tuple

# Third-party imports
try:
    import pandas as pd
    import numpy as np
except ImportError as e:
    raise ImportError(f"Required dependencies not installed: {str(e)}")

# Local imports
from utils.import_validator import validate_imports
from utils.debug_logger import setup_logger, log_exception
from helpers.normalization import normalize_header, find_best_match
from config import SEATS_SPEC_PATH, SEATS_RUNTIME_PATH
import streamlit as st
from functools import lru_cache
import re

# Validate imports
validate_imports({
    'pandas': pd,
    'numpy': np
})

# Setup logger
logger = setup_logger(__name__, 'master_spec.log')

# Type definitions
FieldType = Literal["str", "numeric", "date", "enum"]
FieldFixer = Literal["uppercase", "lowercase", "strip", "replace_at", "datetime"]

class FieldFormat(TypedDict):
    type: FieldType
    pattern: Optional[str]
    format: Optional[str]
    values: Optional[List[str]]
    description: Optional[str]
    fixer: Optional[FieldFixer]

class DatasetSpec(TypedDict):
    signature: List[str]
    mandatory: Dict[str, str]
    formats: Dict[str, FieldFormat]
    description: Optional[str]
    version: str

class MasterSpec(TypedDict):
    version: str
    datasets: Dict[str, DatasetSpec]

class SpecJson(TypedDict):
    """Expected structure of the master spec JSON file"""
    version: Optional[str]
    datasets: Dict[str, DatasetSpec]

# Exception classes
class SpecLoadingError(Exception):
    """Base exception for spec loading errors."""
    pass

class SpecFileNotFoundError(SpecLoadingError):
    """Exception for when spec file is not found."""
    pass

class SpecValidationError(SpecLoadingError):
    """Exception for spec validation errors."""
    pass

class JsonValidationError(SpecValidationError):
    """Exception for JSON validation errors."""
    pass

class PathTraversalError(SpecLoadingError):
    """Exception for invalid file paths."""
    pass

def find_file_case_insensitive(folder: Path, expected_name: str) -> Optional[Path]:
    """
    Searches for a file in the folder matching expected_name, ignoring case.
    
    Args:
        folder: Directory to search in
        expected_name: Name of file to find
        
    Returns:
        Path to found file or None if not found
        
    Raises:
        ValueError: If folder is not a directory
        PathTraversalError: If folder is outside DATA_ROOT
    """
    if not folder.is_dir():
        raise ValueError(f"Not a directory: {folder}")
    
    # Prevent path traversal
    if not folder.resolve().is_relative_to(DATA_ROOT):
        raise PathTraversalError(f"Invalid folder path: {folder}")
        
    expected_name_lower = expected_name.lower()
    for file in folder.iterdir():
        if file.name.lower() == expected_name_lower:
            return file
    return None

# Use centralized path configuration
DATA_ROOT = Path(SEATS_SPEC_PATH)
RUNTIME_ROOT = Path(SEATS_RUNTIME_PATH)

def safe_editor_key(sheet_name: str) -> str:
    """
    Create a safe key for Streamlit editor components.
    
    Args:
        sheet_name: Name of the sheet
        
    Returns:
        Safe key string
    """
    return "editor_" + sheet_name.lower().replace(" ", "_").replace(".", "").replace("-", "_")

@lru_cache(maxsize=1)
def get_available_datasets() -> List[str]:
    """
    Get list of available datasets from the spec directory.
    Cached for performance.
    
    Returns:
        List of dataset names
        
    Raises:
        SpecLoadingError: If DATA_ROOT does not exist
    """
    if not DATA_ROOT.exists():
        error_msg = f"DATA_ROOT does not exist: {DATA_ROOT}"
        logger.error(error_msg)
        st.warning(error_msg)
        return []

    try:
        available_datasets = []
        for folder in DATA_ROOT.iterdir():
            if folder.is_dir() and any(folder.glob("master_*_spec.json")):
                available_datasets.append(folder.name)
        return sorted(available_datasets)
    except Exception as e:
        error_msg = f"Error getting available datasets: {str(e)}"
        log_exception(logger, e, "get_available_datasets")
        raise SpecLoadingError(error_msg)

def get_filtered_datasets(expected_headers: Dict[str, Dict]) -> Dict[str, str]:
    """
    Filter datasets based on expected headers.
    
    Args:
        expected_headers: Dictionary of expected headers
        
    Returns:
        Dictionary of filtered datasets with safe editor keys
    """
    return {
        sheet: safe_editor_key(sheet)
        for sheet in expected_headers
        if not any(
            skip in sheet.lower()
            for skip in ["example", "cover page", "revision history", "non lesson"]
        )
    }

def enforce_schema_version(spec_json: Dict) -> None:
    """
    Enforce schema version compatibility.
    
    Args:
        spec_json: The loaded JSON spec
        
    Raises:
        SpecValidationError: If version is incompatible
    """
    version = spec_json.get("version", "1.0")
    
    # Load version manifest
    version_manifest_path = DATA_ROOT / "version.json"
    if version_manifest_path.exists():
        with open(version_manifest_path) as f:
            manifest = json.load(f)
            expected_version = manifest.get("expected_version", "2.0")
            compatible_versions = manifest.get("compatibility", ["2.0", "2.1"])
            
            if version not in compatible_versions:
                raise SpecValidationError(
                    f"Incompatible schema version: {version}. "
                    f"Expected {expected_version} or compatible versions: {compatible_versions}"
                )
    else:
        # Default version check if no manifest
        if version not in ["2.0", "2.1"]:
            raise SpecValidationError(f"Incompatible schema version: {version}. Expected 2.0 or 2.1")

def validate_json_spec(spec_json: Dict) -> None:
    """
    Validate the structure of the JSON spec.
    
    Args:
        spec_json: The loaded JSON spec
        
    Raises:
        JsonValidationError: If the JSON structure is invalid
    """
    if not isinstance(spec_json, dict):
        raise JsonValidationError("Spec must be a JSON object")
    
    # Check for required top-level structure
    if not any(key in spec_json for key in ["version", "datasets"]):
        # Legacy format: direct dataset spec
        if not all(isinstance(v, dict) for v in spec_json.values()):
            raise JsonValidationError("Invalid spec structure: must contain dataset definitions")
    else:
        # New format: with version and datasets
        if not isinstance(spec_json.get("datasets", {}), dict):
            raise JsonValidationError("Invalid spec structure: 'datasets' must be an object")
        
        # Enforce schema version
        enforce_schema_version(spec_json)
        
        # Validate each dataset
        for dataset_name, dataset in spec_json["datasets"].items():
            if not isinstance(dataset.get("signature"), list):
                raise JsonValidationError(f"Invalid signature in dataset {dataset_name}")
            if not isinstance(dataset.get("mandatory"), dict):
                raise JsonValidationError(f"Invalid mandatory fields in dataset {dataset_name}")
            if not isinstance(dataset.get("formats"), dict):
                raise JsonValidationError(f"Invalid format rules in dataset {dataset_name}")
            
            # Validate field types and patterns
            for field_name, field_format in dataset.get("formats", {}).items():
                if not isinstance(field_format.get("type"), str):
                    raise JsonValidationError(f"Invalid type for field {field_name} in dataset {dataset_name}")
                if field_format["type"] not in ["str", "numeric", "date", "enum"]:
                    raise JsonValidationError(f"Unsupported type '{field_format['type']}' for field {field_name}")
                
                # Validate pattern if present
                if "pattern" in field_format:
                    try:
                        re.compile(field_format["pattern"])
                    except re.error:
                        raise JsonValidationError(f"Invalid regex pattern for field {field_name} in dataset {dataset_name}")

def load_master_spec(dataset_type: str, developer_mode: bool = False) -> Tuple[Dict, Dict, Dict]:
    """
    Load and process master specification for a dataset type.
    
    The spec file should be a JSON file with the following structure:
    {
        "version": "1.0",  # Optional
        "datasets": {      # Optional in legacy format
            "DatasetType": {
                "signature": ["FIELD1", "FIELD2", ...],
                "mandatory": {"FIELD1": "Y", "FIELD2": "N", ...},
                "formats": {
                    "FIELD1": {
                        "pattern": "regex_pattern",
                        "type": "str|numeric|date|enum",
                        "description": "field description"
                    }
                },
                "description": "Optional dataset description",
                "version": "Optional version string"
            }
        }
    }
    
    Args:
        dataset_type: Type of dataset to load
        developer_mode: Whether to show additional debug information
        
    Returns:
        Tuple of (expected_headers, format_rules, column_examples)
        
    Raises:
        SpecFileNotFoundError: If spec file is not found
        SpecValidationError: If spec validation fails
    """
    try:
        dataset_folder = DATA_ROOT / dataset_type
        if not dataset_folder.exists():
            error_msg = f"Dataset folder not found: {dataset_folder}"
            logger.error(error_msg)
            st.error(f"❌ {error_msg}")
            return {}, {}, {}

        # Find JSON spec file
        spec_file = find_file_case_insensitive(dataset_folder, f"master_{dataset_type.lower()}_spec.json")
        if not spec_file:
            error_msg = f"No JSON spec file found in {dataset_folder}"
            logger.error(error_msg)
            st.error(f"❌ {error_msg}")
            st.info(f"📁 Files in folder: {[f.name for f in dataset_folder.iterdir()]}")
            return {}, {}, {}

        logger.info(f"Reading JSON spec file: {spec_file}")
        st.info(f"📄 Reading: {spec_file}")

        # Load and validate the JSON spec with retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with open(spec_file, "r", encoding="utf-8") as f:
                    spec_json = json.load(f)
                validate_json_spec(spec_json)
                break
            except (IOError, json.JSONDecodeError, JsonValidationError) as e:
                if attempt == max_retries - 1:
                    error_msg = f"Failed to read {spec_file}: {str(e)}"
                    log_exception(logger, e, "load_master_spec")
                    st.error(f"❌ {error_msg}")
                    return {}, {}, {}
                time.sleep(1)  # Wait before retry

        # Get the dataset spec
        if "datasets" in spec_json:
            # New format
            if dataset_type not in spec_json["datasets"]:
                error_msg = f"Dataset type '{dataset_type}' not found in spec"
                logger.error(error_msg)
                st.error(f"❌ {error_msg}")
                return {}, {}, {}
            spec = spec_json["datasets"][dataset_type]
        else:
            # Legacy format
            if dataset_type in spec_json:
                spec = spec_json[dataset_type]
            else:
                # fallback: use the first key
                spec = next(iter(spec_json.values()))

        # Build expected_headers, format_rules, column_examples from JSON
        expected_headers = {
            dataset_type: {
                "mandatory": [f for f in spec.get("signature", []) if spec.get("mandatory", {}).get(f, "N") == "Y"],
                "optional": [f for f in spec.get("signature", []) if spec.get("mandatory", {}).get(f, "N") != "Y"]
            }
        }
        format_rules = {
            dataset_type: spec.get("formats", {})
        }
        column_examples = {
            dataset_type: {f: "" for f in spec.get("signature", [])}
        }

        return expected_headers, format_rules, column_examples

    except Exception as e:
        error_msg = f"Error loading master spec for {dataset_type}: {str(e)}"
        log_exception(logger, e, "load_master_spec")
        raise SpecLoadingError(error_msg)

@lru_cache(maxsize=128)
def get_spec_description(dataset_type: str) -> str:
    # Load JSON spec
    spec_path = Path(f'/app/data/master/{dataset_type}/master_{dataset_type}_spec.json')
    if spec_path.exists():
        with open(spec_path) as f:
            spec = json.load(f)
        return spec.get('description', '')
    return ''

class MasterSpecLoader:
    def __init__(self, spec_path: str):
        self.spec_path = spec_path
        self.spec = self._load_spec()
        
    def _load_spec(self) -> Dict[str, Any]:
        with open(self.spec_path, 'r') as f:
            return json.load(f)
            
    def get_dataset_spec(self, dataset_type: str) -> Dict[str, Any]:
        """Get the specification for a specific dataset type."""
        normalized_type = normalize_header(dataset_type)
        return self.spec.get(normalized_type, {})
        
    def get_expected_headers(self, dataset_type: str) -> Dict[str, list]:
        """Get the expected headers for a dataset type."""
        spec = self.get_dataset_spec(dataset_type)
        return {
            'mandatory': [normalize_header(h) for h in spec.get('mandatory_fields', [])],
            'optional': [normalize_header(h) for h in spec.get('optional_fields', [])]
        }
        
    def get_format_rules(self, dataset_type: str) -> Dict[str, Any]:
        """Get the format rules for a dataset type."""
        spec = self.get_dataset_spec(dataset_type)
        rules = {}
        for field, rule in spec.get('format_rules', {}).items():
            rules[normalize_header(field)] = rule
        return rules
        
    def get_validation_rules(self, dataset_type: str) -> Dict[str, Any]:
        """Get the validation rules for a dataset type."""
        spec = self.get_dataset_spec(dataset_type)
        rules = {}
        for field, rule in spec.get('validation_rules', {}).items():
            rules[normalize_header(field)] = rule
        return rules
        
    def get_reference_fields(self, dataset_type: str) -> Dict[str, str]:
        """Get the reference fields for a dataset type."""
        spec = self.get_dataset_spec(dataset_type)
        refs = {}
        for field, ref in spec.get('reference_fields', {}).items():
            refs[normalize_header(field)] = ref
        return refs