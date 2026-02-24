import unittest
from unittest.mock import patch, MagicMock
import streamlit as st
from controller.monitoring_controller import handle_monitoring

class TestMonitoringController(unittest.TestCase):
    def setUp(self):
        # Mock session state
        st.session_state = {}
        st.session_state.user = {'role': 'admin'}
        
    @patch('controller.monitoring_controller.render_monitoring_dashboard')
    def test_handle_monitoring_admin(self, mock_render_dashboard):
        # Execute
        handle_monitoring()
        
        # Assert
        mock_render_dashboard.assert_called_once()
        
    @patch('controller.monitoring_controller.render_monitoring_dashboard')
    def test_handle_monitoring_non_admin(self, mock_render_dashboard):
        # Setup
        st.session_state.user['role'] = 'user'
        
        # Execute
        handle_monitoring()
        
        # Assert
        mock_render_dashboard.assert_not_called()

if __name__ == '__main__':
    unittest.main() 