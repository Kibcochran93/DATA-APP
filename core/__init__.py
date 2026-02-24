"""
Core module for the SEATS application.

Provides centralized access to core services and utilities.
"""

from typing import Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from utils.data_cleaner import DataCleaner

logger = logging.getLogger(__name__)

# Singleton instance
_data_cleaner_instance: Optional["DataCleaner"] = None


def get_data_cleaner() -> "DataCleaner":
    """
    Get or create the singleton DataCleaner instance.
    
    Returns:
        DataCleaner: The singleton data cleaner instance
    """
    global _data_cleaner_instance
    
    if _data_cleaner_instance is None:
        from utils.data_cleaner import DataCleaner
        _data_cleaner_instance = DataCleaner()
        logger.debug("Created new DataCleaner instance")
    
    return _data_cleaner_instance


def reset_data_cleaner() -> None:
    """
    Reset the DataCleaner singleton instance.
    
    Useful for testing or when configuration changes.
    """
    global _data_cleaner_instance
    _data_cleaner_instance = None
    logger.debug("Reset DataCleaner instance")


__all__ = [
    'get_data_cleaner',
    'reset_data_cleaner'
]
