import unittest
from unittest.mock import patch, MagicMock
import streamlit as st
import pandas as pd
from controller.export_controller import handle_export
from utils.exceptions import DataError

class TestExportController(unittest.TestCase):
    def setUp(self):
        # Mock session state
        st.session_state = {}
        st.session_state.user = {'role': 'admin'}
        st.session_state.df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
        
    @patch('controller.export_controller.render_export_options')
    @patch('controller.export_controller.render_export_history')
    def test_handle_export_with_data(self, mock_render_history, mock_render_options):
        # Execute
        handle_export()
        
        # Assert
        mock_render_options.assert_called_once_with(st.session_state.df, st.session_state.user['role'])
        mock_render_history.assert_called_once_with(st.session_state.user['role'])
        
    @patch('controller.export_controller.render_export_options')
    @patch('controller.export_controller.render_export_history')
    def test_handle_export_without_data(self, mock_render_history, mock_render_options):
        # Setup
        st.session_state.df = None
        
        # Execute
        handle_export()
        
        # Assert
        mock_render_options.assert_not_called()
        mock_render_history.assert_not_called()

    @patch('controller.export_controller.render_export_options')
    @patch('controller.export_controller.render_export_history')
    def test_handle_export_without_user(self, mock_render_history, mock_render_options):
        # Setup
        st.session_state.user = None
        
        # Execute
        handle_export()
        
        # Assert
        mock_render_options.assert_not_called()
        mock_render_history.assert_not_called()

    @patch('controller.export_controller.render_export_options')
    @patch('controller.export_controller.render_export_history')
    def test_handle_export_with_empty_dataframe(self, mock_render_history, mock_render_options):
        # Setup
        st.session_state.df = pd.DataFrame()
        
        # Execute
        handle_export()
        
        # Assert
        mock_render_options.assert_called_once_with(st.session_state.df, st.session_state.user['role'])
        mock_render_history.assert_called_once_with(st.session_state.user['role'])

    @patch('controller.export_controller.render_export_options')
    @patch('controller.export_controller.render_export_history')
    def test_handle_export_with_invalid_role(self, mock_render_history, mock_render_options):
        # Setup
        st.session_state.user = {'role': 'invalid_role'}
        
        # Execute
        handle_export()
        
        # Assert
        mock_render_options.assert_called_once_with(st.session_state.df, st.session_state.user['role'])
        mock_render_history.assert_called_once_with(st.session_state.user['role'])

if __name__ == '__main__':
    unittest.main() 