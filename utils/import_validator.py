"""
Import validation utilities for the application.
"""

import sys
import importlib
import pkg_resources
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

def validate_imports(required_modules: Dict[str, Any]) -> None:
    """
    Validate that required modules are properly imported.
    
    Args:
        required_modules: Dictionary of module names and their imported instances
        
    Raises:
        ImportError: If any required module is not properly imported
    """
    for name, module in required_modules.items():
        if module is None:
            raise ImportError(f"Required module {name} not properly imported")

def safe_import(module_name: str) -> Any:
    """
    Safely import a module with error handling.
    
    Args:
        module_name: Name of the module to import
        
    Returns:
        Imported module
        
    Raises:
        ImportError: If module cannot be imported
    """
    try:
        return importlib.import_module(module_name)
    except ImportError as e:
        raise ImportError(f"Failed to import {module_name}: {str(e)}")

def check_dependency_versions(required_versions: Dict[str, str]) -> List[Tuple[str, str, str]]:
    """
    Check if installed package versions meet requirements.
    
    Args:
        required_versions: Dictionary of package names and their required versions
        
    Returns:
        List of tuples containing (package_name, required_version, installed_version)
        for packages that don't meet version requirements
    """
    version_mismatches = []
    
    for package, required_version in required_versions.items():
        try:
            installed_version = pkg_resources.get_distribution(package).version
            if not pkg_resources.require(f"{package}{required_version}"):
                version_mismatches.append((package, required_version, installed_version))
        except (pkg_resources.DistributionNotFound, pkg_resources.VersionConflict):
            version_mismatches.append((package, required_version, "not installed"))
            
    return version_mismatches

def validate_project_imports() -> None:
    """
    Validate all project imports and dependencies.
    
    This function should be called at application startup.
    
    Raises:
        ImportError: If any required imports are missing or invalid
    """
    # Required third-party modules
    required_modules = {
        'pandas': safe_import('pandas'),
        'numpy': safe_import('numpy'),
        'streamlit': safe_import('streamlit'),
        'plotly': safe_import('plotly')
    }
    
    # Validate imports
    validate_imports(required_modules)
    
    # Check dependency versions
    required_versions = {
        'pandas': '>=1.3.0',
        'numpy': '>=1.20.0',
        'streamlit': '>=1.0.0',
        'plotly': '>=5.0.0'
    }
    
    version_mismatches = check_dependency_versions(required_versions)
    if version_mismatches:
        error_msg = "Version mismatches found:\n"
        for package, required, installed in version_mismatches:
            error_msg += f"  - {package}: required {required}, installed {installed}\n"
        raise ImportError(error_msg) 