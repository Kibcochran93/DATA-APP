"""
Application configuration module for the SEATS application.

Contains session keys, application settings, and configuration constants.
"""

import os
from pathlib import Path
from typing import Dict, Any, List

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
EXPORTS_DIR = DATA_DIR / "exports"
RUNTIME_DIR = DATA_DIR / "runtime"

# Ensure directories exist
for directory in [DATA_DIR, LOGS_DIR, EXPORTS_DIR, RUNTIME_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Session state keys
SESSION_KEYS: Dict[str, str] = {
    # Data state
    "dataframe": "df",
    "original_dataframe": "df_original",
    "validation_results": "validation_results",
    "cleaned_dataframe": "df_cleaned",
    
    # Authentication state
    "user": "user",
    "token": "token",
    "auth": "auth",
    "is_authenticated": "is_authenticated",
    
    # Services
    "protection": "protection",
    "monitoring": "monitoring",
    
    # UI state
    "current_page": "current_page",
    "selected_dataset": "selected_dataset",
    "header_mapping": "header_mapping",
    "show_advanced": "show_advanced",
    
    # Processing state
    "upload_complete": "upload_complete",
    "validation_complete": "validation_complete",
    "export_ready": "export_ready",
    
    # Wizard state
    "wizard_step": "wizard_step",
    "wizard_data": "wizard_data",
}

# File configuration
FILE_CONFIG: Dict[str, Any] = {
    "max_size": int(os.getenv("MAX_FILE_SIZE", 10485760)),  # 10MB default
    "allowed_extensions": [".csv", ".xlsx", ".xls", ".json"],
    "chunk_size": int(os.getenv("CHUNK_SIZE", 1048576)),  # 1MB default
    "upload_timeout": int(os.getenv("UPLOAD_TIMEOUT", 30)),
}

# Application settings
APP_CONFIG: Dict[str, Any] = {
    "app_name": "SEATS Data Validator",
    "version": "1.0.0",
    "debug": os.getenv("DEBUG", "False").lower() == "true",
    "environment": os.getenv("APP_ENV", "production"),
    "log_level": os.getenv("LOG_LEVEL", "INFO"),
}

# Supported encodings for file upload
SUPPORTED_ENCODINGS: List[str] = [
    "utf-8",
    "utf-8-sig",
    "latin-1",
    "iso-8859-1",
    "cp1252",
    "ascii",
]

# Dataset types
DATASET_TYPES: List[str] = [
    "Student",
    "Staff",
    "Timetable",
    "Room",
    "Activity",
    "Assessment",
    "AssessmentEvent",
    "BadgeId",
    "CustomFields",
    "Device",
    "GenericEvent",
    "StudentSwipe",
    "StudentTags",
]

# Validation settings
VALIDATION_CONFIG: Dict[str, Any] = {
    "max_errors_display": 100,
    "fuzzy_match_threshold": 80,
    "auto_fix_enabled": True,
    "strict_mode": False,
}

# Export settings
EXPORT_CONFIG: Dict[str, Any] = {
    "formats": ["csv", "xlsx", "json"],
    "include_validation_report": True,
    "include_original": False,
    "compress_output": False,
}

# Path configurations
SEATS_SPEC_PATH = Path(os.getenv(
    "SEATS_SPEC_PATH",
    str(DATA_DIR / "master")
))

SEATS_RUNTIME_PATH = Path(os.getenv(
    "SEATS_RUNTIME_PATH",
    str(RUNTIME_DIR)
))


def get_config() -> Dict[str, Any]:
    """
    Get complete application configuration.
    
    Returns:
        Dictionary containing all configuration settings
    """
    return {
        "app": APP_CONFIG,
        "file": FILE_CONFIG,
        "validation": VALIDATION_CONFIG,
        "export": EXPORT_CONFIG,
        "paths": {
            "base": str(BASE_DIR),
            "data": str(DATA_DIR),
            "logs": str(LOGS_DIR),
            "exports": str(EXPORTS_DIR),
            "specs": str(SEATS_SPEC_PATH),
            "runtime": str(SEATS_RUNTIME_PATH),
        },
    }


__all__ = [
    "SESSION_KEYS",
    "FILE_CONFIG",
    "APP_CONFIG",
    "SUPPORTED_ENCODINGS",
    "DATASET_TYPES",
    "VALIDATION_CONFIG",
    "EXPORT_CONFIG",
    "SEATS_SPEC_PATH",
    "SEATS_RUNTIME_PATH",
    "BASE_DIR",
    "DATA_DIR",
    "LOGS_DIR",
    "EXPORTS_DIR",
    "get_config",
]
