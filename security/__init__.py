"""
Security module for the SEATS application.
"""
from autho.auth import authenticate_user, authorize_access
from security.config import SecurityConfig

__all__ = ['authenticate_user', 'authorize_access', 'SecurityConfig'] 