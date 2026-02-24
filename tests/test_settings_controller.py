import unittest
from unittest.mock import patch, MagicMock
import streamlit as st
from controller.settings_controller import handle_settings

class TestSettingsController(unittest.TestCase):
    def setUp(self):
        # Mock session state
        st.session_state = {}
        st.session_state.user = {'role': 'admin'}
        
    @patch('controller.settings_controller.render_user_management')
    def test_handle_settings_admin(self, mock_render_user_management):
        # Execute
        handle_settings()
        
        # Assert
        mock_render_user_management.assert_called_once()
        
    @patch('controller.settings_controller.render_user_management')
    def test_handle_settings_non_admin(self, mock_render_user_management):
        # Setup
        st.session_state.user['role'] = 'user'
        
        # Execute
        handle_settings()
        
        # Assert
        mock_render_user_management.assert_not_called()

if __name__ == '__main__':
    unittest.main() 