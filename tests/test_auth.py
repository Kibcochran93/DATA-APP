import pytest
import os
import json
import tempfile
from datetime import datetime, timedelta
import jwt
from autho.auth import Authentication
from security.config import AUTH_CONFIG, ERROR_MESSAGES
from utils.exceptions import SecurityError

@pytest.fixture
def temp_users_file():
    """Create a temporary users file for testing."""
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
        json.dump({}, f)
    yield f.name
    os.unlink(f.name)

@pytest.fixture
def auth(temp_users_file):
    """Create an Authentication instance for testing."""
    config = AUTH_CONFIG.copy()
    config['users']['file_path'] = temp_users_file
    return Authentication(config)

@pytest.fixture
def admin_user(auth):
    """Create an admin user for testing."""
    auth.register_user('admin', 'Admin123!', 'admin')
    return 'admin'

@pytest.fixture
def regular_user(auth):
    """Create a regular user for testing."""
    auth.register_user('user', 'User123!', 'user')
    return 'user'

class TestUserRegistration:
    def test_register_user(self, auth):
        """Test user registration."""
        auth.register_user('test', 'Test123!', 'user')
        assert 'test' in auth.users
        assert auth.users['test']['role'] == 'user'
    
    def test_register_duplicate_user(self, auth, regular_user):
        """Test registering duplicate username."""
        with pytest.raises(SecurityError) as exc_info:
            auth.register_user(regular_user, 'Test123!', 'user')
        assert exc_info.value.message == ERROR_MESSAGES['username_exists']
    
    def test_register_user_with_invalid_role(self, auth):
        """Test registering user with invalid role."""
        with pytest.raises(SecurityError) as exc_info:
            auth.register_user('test', 'Test123!', 'invalid_role')
        assert "Invalid role" in exc_info.value.message

class TestAuthentication:
    def test_authenticate_valid_user(self, auth, regular_user):
        """Test authentication with valid credentials."""
        token = auth.authenticate(regular_user, 'User123!')
        assert token is not None
        payload = jwt.decode(token, AUTH_CONFIG['jwt']['secret_key'], algorithms=['HS256'])
        assert payload['username'] == regular_user
        assert payload['role'] == 'user'
    
    def test_authenticate_invalid_username(self, auth):
        """Test authentication with invalid username."""
        with pytest.raises(SecurityError) as exc_info:
            auth.authenticate('nonexistent', 'Test123!')
        assert exc_info.value.message == ERROR_MESSAGES['invalid_credentials']
    
    def test_authenticate_invalid_password(self, auth, regular_user):
        """Test authentication with invalid password."""
        with pytest.raises(SecurityError) as exc_info:
            auth.authenticate(regular_user, 'WrongPass123!')
        assert exc_info.value.message == ERROR_MESSAGES['invalid_credentials']

class TestTokenVerification:
    def test_verify_valid_token(self, auth, regular_user):
        """Test verification of valid token."""
        token = auth.authenticate(regular_user, 'User123!')
        payload = auth.verify_token(token)
        assert payload['username'] == regular_user
        assert payload['role'] == 'user'
    
    def test_verify_expired_token(self, auth, regular_user):
        """Test verification of expired token."""
        # Create expired token
        payload = {
            'username': regular_user,
            'role': 'user',
            'exp': datetime.utcnow() - timedelta(seconds=1)
        }
        token = jwt.encode(payload, AUTH_CONFIG['jwt']['secret_key'], algorithm='HS256')
        
        with pytest.raises(SecurityError) as exc_info:
            auth.verify_token(token)
        assert exc_info.value.message == ERROR_MESSAGES['token_expired']
    
    def test_verify_invalid_token(self, auth):
        """Test verification of invalid token."""
        with pytest.raises(SecurityError) as exc_info:
            auth.verify_token('invalid_token')
        assert "Invalid token" in exc_info.value.message

class TestPasswordManagement:
    def test_change_password(self, auth, regular_user):
        """Test password change."""
        auth.change_password(regular_user, 'User123!', 'NewPass123!')
        # Verify old password no longer works
        with pytest.raises(SecurityError) as exc_info:
            auth.authenticate(regular_user, 'User123!')
        assert exc_info.value.message == ERROR_MESSAGES['invalid_credentials']
        # Verify new password works
        token = auth.authenticate(regular_user, 'NewPass123!')
        assert token is not None
    
    def test_change_password_invalid_current(self, auth, regular_user):
        """Test password change with invalid current password."""
        with pytest.raises(SecurityError) as exc_info:
            auth.change_password(regular_user, 'WrongPass123!', 'NewPass123!')
        assert exc_info.value.message == ERROR_MESSAGES['invalid_credentials']

class TestUserManagement:
    def test_update_role(self, auth, admin_user, regular_user):
        """Test role update by admin."""
        auth.update_role(regular_user, 'viewer', admin_user)
        assert auth.users[regular_user]['role'] == 'viewer'
    
    def test_update_role_unauthorized(self, auth, regular_user):
        """Test role update by non-admin."""
        with pytest.raises(SecurityError) as exc_info:
            auth.update_role(regular_user, 'viewer', regular_user)
        assert "Unauthorized" in exc_info.value.message
    
    def test_delete_user(self, auth, admin_user, regular_user):
        """Test user deletion by admin."""
        auth.delete_user(regular_user, admin_user)
        assert regular_user not in auth.users
    
    def test_delete_user_unauthorized(self, auth, regular_user):
        """Test user deletion by non-admin."""
        with pytest.raises(SecurityError) as exc_info:
            auth.delete_user(regular_user, regular_user)
        assert "Unauthorized" in exc_info.value.message

class TestErrorHandling:
    @pytest.mark.skipif(os.geteuid() == 0, reason="File permission tests don't work as root")
    def test_load_users_error(self, auth):
        """Test error handling when loading users."""
        # Make users file unreadable
        os.chmod(auth.users_file, 0o000)
        with pytest.raises(SecurityError) as exc_info:
            auth._load_users()
        assert "Failed to load users" in exc_info.value.message
        # Restore permissions for cleanup
        os.chmod(auth.users_file, 0o644)
    
    @pytest.mark.skipif(os.geteuid() == 0, reason="File permission tests don't work as root")
    def test_save_users_error(self, auth, regular_user):
        """Test error handling when saving users."""
        # Make users file unwritable
        os.chmod(auth.users_file, 0o444)
        with pytest.raises(SecurityError) as exc_info:
            auth.register_user('test', 'Test123!', 'user')
        assert "Failed to save users" in exc_info.value.message
        # Restore permissions for cleanup
        os.chmod(auth.users_file, 0o644)
