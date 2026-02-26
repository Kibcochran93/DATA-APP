"""Tests for upload controller."""

import pytest
from unittest.mock import patch, MagicMock
import streamlit as st
import pandas as pd
from controller.upload_controller import handle_file_upload
from utils.exceptions import SecurityError


class TestUploadController:
    """Test cases for upload controller."""
    
    @pytest.fixture(autouse=True)
    def setup(self, mock_streamlit_session_state, mock_monitoring, mock_protection):
        """Set up test fixtures."""
        self.session_state = mock_streamlit_session_state
        self.session_state.monitoring = mock_monitoring
        self.session_state.protection = mock_protection
        
        # Mock file upload
        self.uploaded_file = MagicMock()
        self.uploaded_file.name = 'test.csv'
        self.uploaded_file.size = 1024
        self.uploaded_file.type = 'text/csv'
        
        # Mock DataFrame
        self.df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
    
    @patch('controller.upload_controller.InputValidator')
    @patch('controller.upload_controller.pd.read_csv')
    def test_handle_file_upload_csv(self, mock_read_csv, mock_validator):
        """Test CSV file upload handling."""
        # Setup
        mock_read_csv.return_value = self.df
        mock_validator_instance = MagicMock()
        mock_validator.return_value = mock_validator_instance
        mock_validator_instance.validate_dataframe.return_value = {'is_valid': True}
        mock_validator_instance.sanitize_input.return_value = self.df
        
        # Mock SEATS handler
        with patch('controller.upload_controller.get_seats_handler') as mock_get_handler:
            mock_handler = MagicMock()
            mock_handler.read_csv_preserve_leading_zeros.return_value = self.df
            mock_get_handler.return_value = mock_handler
            
            # Execute
            result = handle_file_upload(self.uploaded_file)
            
            # Assert
            mock_validator_instance.validate_file.assert_called_once_with(self.uploaded_file)
            assert result is not None
            assert result.equals(self.df)
    
    @patch('controller.upload_controller.InputValidator')
    @patch('controller.upload_controller.pd.read_excel')
    def test_handle_file_upload_excel(self, mock_read_excel, mock_validator):
        """Test Excel file upload handling."""
        # Setup
        self.uploaded_file.name = 'test.xlsx'
        mock_read_excel.return_value = self.df
        mock_validator_instance = MagicMock()
        mock_validator.return_value = mock_validator_instance
        mock_validator_instance.validate_dataframe.return_value = {'is_valid': True}
        mock_validator_instance.sanitize_input.return_value = self.df
        
        # Mock SEATS handler
        with patch('controller.upload_controller.get_seats_handler') as mock_get_handler:
            mock_handler = MagicMock()
            mock_handler.read_excel_preserve_leading_zeros.return_value = self.df
            mock_get_handler.return_value = mock_handler
            
            # Execute
            result = handle_file_upload(self.uploaded_file)
            
            # Assert
            mock_validator_instance.validate_file.assert_called_once_with(self.uploaded_file)
            assert result is not None
            assert result.equals(self.df)
    
    @patch('controller.upload_controller.InputValidator')
    def test_handle_file_upload_validation_failed(self, mock_validator):
        """Test file upload with validation failure - shows warning but continues."""
        # Setup
        mock_validator_instance = MagicMock()
        mock_validator.return_value = mock_validator_instance
        mock_validator_instance.validate_dataframe.return_value = {'is_valid': False, 'issues': ['Issue 1']}
        mock_validator_instance.sanitize_input.return_value = self.df
        
        # Mock SEATS handler
        with patch('controller.upload_controller.get_seats_handler') as mock_get_handler:
            mock_handler = MagicMock()
            mock_handler.read_csv_preserve_leading_zeros.return_value = self.df
            mock_get_handler.return_value = mock_handler
            
            # Execute - implementation shows warning but still processes file
            result = handle_file_upload(self.uploaded_file)
            
            # Assert - file is still processed and stored
            mock_validator_instance.validate_file.assert_called_once_with(self.uploaded_file)
            # The implementation stores df even with validation warnings
            assert result is not None
    
    @patch('controller.upload_controller.InputValidator')
    @patch('controller.upload_controller.pd.read_csv')
    def test_handle_file_upload_security_error(self, mock_read_csv, mock_validator):
        """Test file upload with security error."""
        # Setup
        mock_read_csv.return_value = self.df
        mock_validator_instance = MagicMock()
        mock_validator.return_value = mock_validator_instance
        mock_validator_instance.validate_file.side_effect = SecurityError("Security error")
        
        # Execute
        handle_file_upload(self.uploaded_file)
        
        # Assert
        mock_validator_instance.validate_file.assert_called_once_with(self.uploaded_file)
        assert 'df' not in self.session_state or self.session_state.get('df') is None
    
    @patch('controller.upload_controller.InputValidator')
    @patch('controller.upload_controller.pd.read_csv')
    def test_handle_file_upload_general_error(self, mock_read_csv, mock_validator):
        """Test file upload with general error."""
        # Setup
        mock_read_csv.return_value = self.df
        mock_validator_instance = MagicMock()
        mock_validator.return_value = mock_validator_instance
        mock_validator_instance.validate_file.side_effect = Exception("General error")
        
        # Execute
        handle_file_upload(self.uploaded_file)
        
        # Assert
        mock_validator_instance.validate_file.assert_called_once_with(self.uploaded_file)
        assert 'df' not in self.session_state or self.session_state.get('df') is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
