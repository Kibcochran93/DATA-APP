"""
Authentication module for the SEATS application.

Provides user authentication, authorization, and access control.
"""

from typing import Dict, List, Optional, Union, Any
import hashlib
import os
import json
import logging
from datetime import datetime, timedelta
import jwt
from cryptography.fernet import Fernet

# Use absolute import - not relative
from utils.error_handler import SecurityError

# Global authentication instance
_auth_instance = None


def get_auth_instance() -> 'Authentication':
    """
    Get or create the global authentication instance.
    
    Returns:
        Authentication instance
    """
    global _auth_instance
    if _auth_instance is None:
        from security.config import SecurityConfig, AUTH_CONFIG
        _auth_instance = Authentication(AUTH_CONFIG)
    return _auth_instance


def authenticate_user(username: str, password: str) -> str:
    """
    Authenticate a user and return a JWT token.
    
    Args:
        username: Username
        password: Password
        
    Returns:
        JWT token
        
    Raises:
        SecurityError: If authentication fails
    """
    return get_auth_instance().authenticate(username, password)


def authorize_access(token: str, required_role: Optional[str] = None) -> Dict[str, Any]:
    """
    Verify token and check if user has required role.
    
    Args:
        token: JWT token
        required_role: Optional role requirement
        
    Returns:
        User information from token
        
    Raises:
        SecurityError: If authorization fails
    """
    auth = get_auth_instance()
    user_info = auth.verify_token(token)
    
    if required_role and user_info.get('role') != required_role:
        raise SecurityError(f"Required role '{required_role}' not granted")
        
    return user_info


class Authentication:
    """Handles user authentication and access control."""
    
    # Valid roles
    VALID_ROLES = {'admin', 'user', 'viewer'}
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize authentication with configuration.
        
        Args:
            config: Dictionary containing authentication configuration
        """
        self.config = config
        self.secret_key = config['jwt']['secret_key']
        self.token_expiry = config['jwt']['token_expiry']
        self.users_file = config['users']['file_path']
        self.logger = logging.getLogger(__name__)
        
        # Initialize encryption for sensitive data
        key = config['encryption']['key']
        if isinstance(key, str):
            key = key.encode()
        elif isinstance(key, bytes):
            pass
        else:
            key = Fernet.generate_key()
        
        self.fernet = Fernet(key)
        
        # Load users if file exists
        self.users = self._load_users()
    
    def _load_users(self) -> Dict[str, Dict[str, Any]]:
        """Load users from file."""
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"Failed to load users: {str(e)}")
            # Return empty dict instead of raising to allow fresh start
            return {}
    
    def _save_users(self) -> None:
        """Save users to file."""
        try:
            os.makedirs(os.path.dirname(self.users_file), exist_ok=True)
            with open(self.users_file, 'w') as f:
                json.dump(self.users, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save users: {str(e)}")
            raise SecurityError("Failed to save users")
    
    def _hash_password(self, password: str) -> str:
        """Hash password using PBKDF2."""
        try:
            salt = os.urandom(16)
            key = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode(),
                salt,
                100000
            )
            return f"{salt.hex()}:{key.hex()}"
        except Exception as e:
            self.logger.error(f"Password hashing failed: {str(e)}")
            raise SecurityError("Password hashing failed")
    
    def _verify_password(self, stored: str, provided: str) -> bool:
        """Verify password against stored hash."""
        try:
            salt_hex, key_hex = stored.split(':')
            salt = bytes.fromhex(salt_hex)
            key = bytes.fromhex(key_hex)
            
            new_key = hashlib.pbkdf2_hmac(
                'sha256',
                provided.encode(),
                salt,
                100000
            )
            return key == new_key
        except Exception as e:
            self.logger.error(f"Password verification failed: {str(e)}")
            return False
    
    def register_user(self, username: str, password: str, role: str = 'user') -> None:
        """
        Register a new user.
        
        Args:
            username: Username
            password: Password
            role: User role (default: 'user')
            
        Raises:
            SecurityError: If registration fails
        """
        try:
            if username in self.users:
                raise SecurityError("Username already exists")
            
            if role not in self.VALID_ROLES:
                raise SecurityError(f"Invalid role: {role}. Must be one of: {self.VALID_ROLES}")
            
            self.users[username] = {
                'password_hash': self._hash_password(password),
                'role': role,
                'created_at': datetime.utcnow().isoformat(),
                'last_login': None
            }
            self._save_users()
            
        except SecurityError:
            raise
        except Exception as e:
            self.logger.error(f"User registration failed: {str(e)}")
            raise SecurityError(f"User registration failed: {str(e)}")
    
    def authenticate(self, username: str, password: str) -> str:
        """
        Authenticate user and return JWT token.
        
        Args:
            username: Username
            password: Password
            
        Returns:
            JWT token
            
        Raises:
            SecurityError: If authentication fails
        """
        try:
            if username not in self.users:
                raise SecurityError("Invalid username or password")
            
            user = self.users[username]
            if not self._verify_password(user['password_hash'], password):
                raise SecurityError("Invalid username or password")
            
            # Update last login
            user['last_login'] = datetime.utcnow().isoformat()
            self._save_users()
            
            # Generate JWT token
            token = jwt.encode(
                {
                    'username': username,
                    'role': user['role'],
                    'exp': datetime.utcnow() + timedelta(seconds=self.token_expiry)
                },
                self.secret_key,
                algorithm='HS256'
            )
            
            return token
            
        except SecurityError:
            raise
        except Exception as e:
            self.logger.error(f"Authentication failed: {str(e)}")
            raise SecurityError("Authentication failed")
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify JWT token and return user info.
        
        Args:
            token: JWT token to verify
            
        Returns:
            Dictionary containing user info
            
        Raises:
            SecurityError: If token verification fails
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            username = payload['username']
            
            if username not in self.users:
                raise SecurityError("Invalid token")
                
            return {
                'username': username,
                'role': payload['role']
            }
        except jwt.ExpiredSignatureError:
            raise SecurityError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise SecurityError(f"Invalid token: {str(e)}")
        except Exception as e:
            self.logger.error(f"Token verification failed: {str(e)}")
            raise SecurityError("Token verification failed")
    
    def change_password(self, username: str, old_password: str, new_password: str) -> None:
        """
        Change user password.
        
        Args:
            username: Username
            old_password: Current password
            new_password: New password
            
        Raises:
            SecurityError: If password change fails
        """
        try:
            if username not in self.users:
                raise SecurityError("User not found")
            
            user = self.users[username]
            if not self._verify_password(user['password_hash'], old_password):
                raise SecurityError("Invalid username or password")
            
            user['password_hash'] = self._hash_password(new_password)
            self._save_users()
            
        except SecurityError:
            raise
        except Exception as e:
            self.logger.error(f"Password change failed: {str(e)}")
            raise SecurityError(f"Password change failed: {str(e)}")
    
    def update_role(self, username: str, new_role: str, admin_username: str) -> None:
        """
        Update user role (admin only).
        
        Args:
            username: Username to update
            new_role: New role
            admin_username: Admin username performing the action
            
        Raises:
            SecurityError: If role update fails
        """
        try:
            if admin_username not in self.users or self.users[admin_username]['role'] != 'admin':
                raise SecurityError("Unauthorized")
            
            if username not in self.users:
                raise SecurityError("User not found")
            
            if new_role not in self.VALID_ROLES:
                raise SecurityError(f"Invalid role: {new_role}")
            
            self.users[username]['role'] = new_role
            self._save_users()
            
        except SecurityError:
            raise
        except Exception as e:
            self.logger.error(f"Role update failed: {str(e)}")
            raise SecurityError(f"Role update failed: {str(e)}")
    
    def delete_user(self, username: str, admin_username: str) -> None:
        """
        Delete user (admin only).
        
        Args:
            username: Username to delete
            admin_username: Admin username performing the action
            
        Raises:
            SecurityError: If user deletion fails
        """
        try:
            if admin_username not in self.users or self.users[admin_username]['role'] != 'admin':
                raise SecurityError("Unauthorized")
            
            if username not in self.users:
                raise SecurityError("User not found")
            
            if username == admin_username:
                raise SecurityError("Cannot delete yourself")
            
            del self.users[username]
            self._save_users()
            
        except SecurityError:
            raise
        except Exception as e:
            self.logger.error(f"User deletion failed: {str(e)}")
            raise SecurityError(f"User deletion failed: {str(e)}")
    
    def list_users(self, admin_username: str) -> List[Dict[str, Any]]:
        """
        List all users (admin only).
        
        Args:
            admin_username: Admin username
            
        Returns:
            List of user information (excluding password hashes)
            
        Raises:
            SecurityError: If not authorized
        """
        if admin_username not in self.users or self.users[admin_username]['role'] != 'admin':
            raise SecurityError("Unauthorized")
        
        return [
            {
                'username': username,
                'role': info['role'],
                'created_at': info.get('created_at'),
                'last_login': info.get('last_login')
            }
            for username, info in self.users.items()
        ]


__all__ = [
    'Authentication',
    'authenticate_user',
    'authorize_access',
    'get_auth_instance'
]
