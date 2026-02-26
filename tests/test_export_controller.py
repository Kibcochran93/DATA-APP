"""Tests for export controller."""

import pytest
from unittest.mock import patch, MagicMock
import streamlit as st
import pandas as pd
from controller.export_controller import handle_export
from utils.exceptions import DataError


class TestExportController:
    """Test cases for export controller."""
    
    @pytest.fixture(autouse=True)
    def setup(self, mock_streamlit_session_state):
        """Set up test fixtures."""
        self.session_state = mock_streamlit_session_state
        self.session_state.user = {'role': 'admin'}
        self.session_state.df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
    
    @patch('controller.export_controller.render_export_options')
    @patch('controller.export_controller.render_export_history')
    def test_handle_export_with_data(self, mock_render_history, mock_render_options):
        """Test export with valid data."""
        # Execute
        handle_export()
        
        # Assert
        mock_render_options.assert_called_once_with(self.session_state.df, self.session_state.user['role'])
        mock_render_history.assert_called_once_with(self.session_state.user['role'])
    
    @patch('controller.export_controller.render_export_options')
    @patch('controller.export_controller.render_export_history')
    def test_handle_export_without_data(self, mock_render_history, mock_render_options):
        """Test export without data."""
        # Setup
        self.session_state.df = None
        
        # Execute
        handle_export()
        
        # Assert
        mock_render_options.assert_not_called()
        mock_render_history.assert_not_called()
    
    @patch('controller.export_controller.render_export_options')
    @patch('controller.export_controller.render_export_history')
    def test_handle_export_without_user(self, mock_render_history, mock_render_options):
        """Test export without user."""
        # Setup
        self.session_state.user = None
        
        # Execute
        handle_export()
        
        # Assert
        mock_render_options.assert_not_called()
        mock_render_history.assert_not_called()
    
    @patch('controller.export_controller.render_export_options')
    @patch('controller.export_controller.render_export_history')
    def test_handle_export_with_empty_dataframe(self, mock_render_history, mock_render_options):
        """Test export with empty DataFrame."""
        # Setup
        self.session_state.df = pd.DataFrame()
        
        # Execute
        handle_export()
        
        # Assert
        mock_render_options.assert_called_once_with(self.session_state.df, self.session_state.user['role'])
        mock_render_history.assert_called_once_with(self.session_state.user['role'])
    
    @patch('controller.export_controller.render_export_options')
    @patch('controller.export_controller.render_export_history')
    def test_handle_export_with_invalid_role(self, mock_render_history, mock_render_options):
        """Test export with invalid role."""
        # Setup
        self.session_state.user = {'role': 'invalid_role'}
        
        # Execute
        handle_export()
        
        # Assert
        mock_render_options.assert_called_once_with(self.session_state.df, self.session_state.user['role'])
        mock_render_history.assert_called_once_with(self.session_state.user['role'])


if __name__ == '__main__':
    pytest.main([__file__, '-v']) 