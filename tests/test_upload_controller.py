import unittest
from unittest.mock import patch, MagicMock
import streamlit as st
import pandas as pd
from controller.upload_controller import handle_file_upload

class TestUploadController(unittest.TestCase):
    def setUp(self):
        # Mock session state
        st.session_state = {}
        st.session_state.monitoring = MagicMock()
        st.session_state.protection = MagicMock()
        
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
        # Setup
        mock_read_csv.return_value = self.df
        mock_validator_instance = MagicMock()
        mock_validator.return_value = mock_validator_instance
        mock_validator_instance.validate_dataframe.return_value = {'is_valid': True}
        mock_validator_instance.sanitize_input.return_value = self.df
        st.session_state.protection.mask_pii.return_value = self.df
        
        # Execute
        handle_file_upload(self.uploaded_file)
        
        # Assert
        mock_validator_instance.validate_file.assert_called_once_with(self.uploaded_file)
        mock_validator_instance.validate_dataframe.assert_called_once_with(self.df)
        mock_validator_instance.sanitize_input.assert_called_once_with(self.df)
        st.session_state.protection.mask_pii.assert_called_once_with(self.df)
        self.assertEqual(st.session_state.df, self.df)
        
    @patch('controller.upload_controller.InputValidator')
    @patch('controller.upload_controller.pd.read_excel')
    def test_handle_file_upload_excel(self, mock_read_excel, mock_validator):
        # Setup
        self.uploaded_file.name = 'test.xlsx'
        mock_read_excel.return_value = self.df
        mock_validator_instance = MagicMock()
        mock_validator.return_value = mock_validator_instance
        mock_validator_instance.validate_dataframe.return_value = {'is_valid': True}
        mock_validator_instance.sanitize_input.return_value = self.df
        st.session_state.protection.mask_pii.return_value = self.df
        
        # Execute
        handle_file_upload(self.uploaded_file)
        
        # Assert
        mock_validator_instance.validate_file.assert_called_once_with(self.uploaded_file)
        mock_validator_instance.validate_dataframe.assert_called_once_with(self.df)
        mock_validator_instance.sanitize_input.assert_called_once_with(self.df)
        st.session_state.protection.mask_pii.assert_called_once_with(self.df)
        self.assertEqual(st.session_state.df, self.df)
        
    @patch('controller.upload_controller.InputValidator')
    @patch('controller.upload_controller.pd.read_csv')
    def test_handle_file_upload_validation_failed(self, mock_read_csv, mock_validator):
        # Setup
        mock_read_csv.return_value = self.df
        mock_validator_instance = MagicMock()
        mock_validator.return_value = mock_validator_instance
        mock_validator_instance.validate_dataframe.return_value = {'is_valid': False, 'issues': ['Issue 1']}
        
        # Execute
        handle_file_upload(self.uploaded_file)
        
        # Assert
        mock_validator_instance.validate_file.assert_called_once_with(self.uploaded_file)
        mock_validator_instance.validate_dataframe.assert_called_once_with(self.df)
        self.assertNotIn('df', st.session_state)
        
    @patch('controller.upload_controller.InputValidator')
    @patch('controller.upload_controller.pd.read_csv')
    def test_handle_file_upload_security_error(self, mock_read_csv, mock_validator):
        # Setup
        mock_read_csv.return_value = self.df
        mock_validator_instance = MagicMock()
        mock_validator.return_value = mock_validator_instance
        mock_validator_instance.validate_file.side_effect = SecurityError("Security error")
        
        # Execute
        handle_file_upload(self.uploaded_file)
        
        # Assert
        mock_validator_instance.validate_file.assert_called_once_with(self.uploaded_file)
        self.assertNotIn('df', st.session_state)
        
    @patch('controller.upload_controller.InputValidator')
    @patch('controller.upload_controller.pd.read_csv')
    def test_handle_file_upload_general_error(self, mock_read_csv, mock_validator):
        # Setup
        mock_read_csv.return_value = self.df
        mock_validator_instance = MagicMock()
        mock_validator.return_value = mock_validator_instance
        mock_validator_instance.validate_file.side_effect = Exception("General error")
        
        # Execute
        handle_file_upload(self.uploaded_file)
        
        # Assert
        mock_validator_instance.validate_file.assert_called_once_with(self.uploaded_file)
        self.assertNotIn('df', st.session_state)

if __name__ == '__main__':
    unittest.main() 