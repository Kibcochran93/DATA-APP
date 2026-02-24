import streamlit as st
from typing import Optional, Tuple, Dict, List
import pandas as pd
import chardet
from pathlib import Path
import re
from config import MAX_FILE_SIZE, SUPPORTED_ENCODINGS, ALLOWED_EXTENSIONS
from utils.debug_logger import setup_logger, log_exception
import io
import time
import os

logger = setup_logger(__name__, "file_uploader.log")

class FileUploadError(Exception):
    """Base exception for file upload errors."""
    pass

class FileValidationError(FileUploadError):
    """Exception for file validation errors."""
    pass

class FileEncodingError(FileUploadError):
    """Exception for file encoding errors."""
    pass

class FileSizeError(FileUploadError):
    """Exception for file size errors."""
    pass

def validate_file_size(file_size: int) -> bool:
    """
    Validate file size against maximum allowed size.
    
    Args:
        file_size: Size of file in bytes
        
    Returns:
        True if file size is within limits
        
    Raises:
        FileSizeError: If file size exceeds limit
    """
    try:
        if file_size > MAX_FILE_SIZE:
            raise FileSizeError(
                f"File size ({file_size} bytes) exceeds maximum allowed size "
                f"({MAX_FILE_SIZE} bytes)"
            )
        return True
    except Exception as e:
        log_exception(logger, e, "validate_file_size")
        raise FileSizeError(f"Error validating file size: {str(e)}")

def validate_file_extension(filename: str) -> bool:
    """
    Validate file extension against allowed extensions.
    
    Args:
        filename: Filename to validate
        
    Returns:
        True if extension is allowed
        
    Raises:
        FileValidationError: If filename is invalid
    """
    try:
        if not filename.strip():
            raise FileValidationError("Filename cannot be empty")
            
        # Normalize path to prevent path traversal
        filename = os.path.normpath(filename)
        if filename.startswith('..') or filename.startswith('/'):
            raise FileValidationError("Invalid file path")
            
        extension = Path(filename).suffix.lower()
        if not extension:
            raise FileValidationError("File has no extension")
            
        return extension in ALLOWED_EXTENSIONS
        
    except Exception as e:
        log_exception(logger, e, "validate_file_extension")
        raise FileValidationError(f"Error validating file extension: {str(e)}")

def detect_encoding(file_content: bytes) -> str:
    """
    Detect file encoding.
    
    Args:
        file_content: File content in bytes
        
    Returns:
        Detected encoding
        
    Raises:
        FileEncodingError: If encoding cannot be detected
    """
    try:
        result = chardet.detect(file_content)
        if not result['encoding']:
            raise FileEncodingError("Could not detect file encoding")
            
        if result['encoding'] not in SUPPORTED_ENCODINGS:
            raise FileEncodingError(
                f"Unsupported encoding: {result['encoding']}. "
                f"Supported encodings: {', '.join(SUPPORTED_ENCODINGS)}"
            )
            
        return result['encoding']
        
    except Exception as e:
        log_exception(logger, e, "detect_encoding")
        raise FileEncodingError(f"Error detecting file encoding: {str(e)}")

def file_uploader_component() -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    File upload component with validation and error handling.
    
    Returns:
        Tuple of (DataFrame, error_message)
    """
    try:
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=ALLOWED_EXTENSIONS,
            help="Upload a CSV or Excel file"
        )
        
        if uploaded_file is not None:
            # Validate file size
            file_size = len(uploaded_file.getvalue())
            validate_file_size(file_size)
            
            # Validate file extension
            if not validate_file_extension(uploaded_file.name):
                raise FileValidationError(
                    f"Invalid file extension. Allowed extensions: "
                    f"{', '.join(ALLOWED_EXTENSIONS)}"
                )
            
            # Detect encoding
            file_content = uploaded_file.getvalue()
            encoding = detect_encoding(file_content)
            
            # Read file based on extension
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(
                        io.BytesIO(file_content),
                        encoding=encoding,
                        on_bad_lines='warn'
                    )
                elif uploaded_file.name.endswith(('.xls', '.xlsx')):
                    df = pd.read_excel(io.BytesIO(file_content))
                else:
                    raise FileValidationError("Unsupported file format")
                
                # Clean up
                uploaded_file.close()
                return df, None
                
            except pd.errors.EmptyDataError:
                raise FileValidationError("File is empty")
            except pd.errors.ParserError as e:
                raise FileValidationError(f"Error parsing file: {str(e)}")
            except Exception as e:
                raise FileValidationError(f"Error reading file: {str(e)}")
                
    except FileSizeError as e:
        error_msg = f"File size error: {str(e)}"
        log_exception(logger, e, "file_uploader_component")
        return None, error_msg
    except FileValidationError as e:
        error_msg = f"File validation error: {str(e)}"
        log_exception(logger, e, "file_uploader_component")
        return None, error_msg
    except FileEncodingError as e:
        error_msg = f"File encoding error: {str(e)}"
        log_exception(logger, e, "file_uploader_component")
        return None, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        log_exception(logger, e, "file_uploader_component")
        return None, error_msg
    
    return None, None 