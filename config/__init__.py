"""
Configuration package for the SEATS application.
"""

from config.config import (
    SESSION_KEYS,
    FILE_CONFIG,
    APP_CONFIG,
    SUPPORTED_ENCODINGS,
    DATASET_TYPES,
    VALIDATION_CONFIG,
    EXPORT_CONFIG,
    SEATS_SPEC_PATH,
    SEATS_RUNTIME_PATH,
    BASE_DIR,
    DATA_DIR,
    LOGS_DIR,
    EXPORTS_DIR,
    get_config,
)

# Constants for backward compatibility
MAX_FILE_SIZE = FILE_CONFIG["max_size"]
ALLOWED_EXTENSIONS = FILE_CONFIG["allowed_extensions"]

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
    "MAX_FILE_SIZE",
    "ALLOWED_EXTENSIONS",
    "get_config",
]
