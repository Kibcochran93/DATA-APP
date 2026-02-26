"""Tests for monitoring controller."""

import pytest
from unittest.mock import patch, MagicMock
import streamlit as st
from controller.monitoring_controller import handle_monitoring


class TestMonitoringController:
    """Test cases for monitoring controller."""
    
    @pytest.fixture(autouse=True)
    def setup(self, mock_streamlit_session_state):
        """Set up test fixtures."""
        self.session_state = mock_streamlit_session_state
        self.session_state.user = {'role': 'admin'}
    
    @patch('controller.monitoring_controller.render_monitoring_dashboard')
    def test_handle_monitoring_admin(self, mock_render_dashboard):
        """Test monitoring page for admin user."""
        # Execute
        handle_monitoring()
        
        # Assert
        mock_render_dashboard.assert_called_once()
    
    @patch('controller.monitoring_controller.render_monitoring_dashboard')
    def test_handle_monitoring_non_admin(self, mock_render_dashboard):
        """Test monitoring page for non-admin user."""
        # Setup
        self.session_state.user['role'] = 'user'
        
        # Execute
        handle_monitoring()
        
        # Assert
        mock_render_dashboard.assert_not_called()


if __name__ == '__main__':
    pytest.main([__file__, '-v']) 