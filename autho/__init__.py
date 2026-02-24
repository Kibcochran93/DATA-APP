"""
Authentication package for the SEATS application.
"""

from autho.auth import (
    Authentication,
    authenticate_user,
    authorize_access,
    get_auth_instance
)

__all__ = [
    'Authentication',
    'authenticate_user',
    'authorize_access',
    'get_auth_instance'
]
