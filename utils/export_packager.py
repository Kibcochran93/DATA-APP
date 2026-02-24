"""
Export packaging utilities for the SEATS application.
"""
from typing import Any, Dict, List, Tuple
import json
import zipfile
import io
import pandas as pd
from datetime import datetime
from utils.debug_logger import setup_logger

# Initialize logger
logger = setup_logger(__name__)

class ExportPackager:
    """Handles packaging and exporting of datasets."""
    
    def __init__(self):
        """Initialize the export packager."""
        self.logger = setup_logger(__name__)
        
    def create_export_package(
        self,
        df: pd.DataFrame,
        dataset_type: str,
        validation_results: Dict[str, Any],
        spec_version: str = "1.0"
    ) -> Tuple[bytes, str]:
        """
        Create an export package containing the dataset and metadata.
        
        Args:
            df: DataFrame to export
            dataset_type: Type of dataset
            validation_results: Validation results
            spec_version: Specification version
            
        Returns:
            Tuple of (zip_content, filename)
            
        Raises:
            ValueError: If export fails
        """
        try:
            # Create in-memory zip file
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Add dataset
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                zip_file.writestr('dataset.csv', csv_buffer.getvalue())
                
                # Add metadata
                metadata = {
                    'dataset_type': dataset_type,
                    'spec_version': spec_version,
                    'export_date': datetime.now().isoformat(),
                    'row_count': len(df),
                    'column_count': len(df.columns),
                    'validation_results': validation_results
                }
                zip_file.writestr('metadata.json', json.dumps(metadata, indent=2))
                
            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{dataset_type}_export_{timestamp}.zip"
            
            return zip_buffer.getvalue(), filename
            
        except Exception as e:
            self.logger.error(f"Export package creation failed: {str(e)}")
            raise ValueError(f"Failed to create export package: {str(e)}")

def package_dataset(data: Dict[str, Any], format: str = 'json') -> bytes:
    """Package dataset for export."""
    if format == 'json':
        return json.dumps(data).encode('utf-8')
    return b''

def validate_export_format(format: str) -> bool:
    """Validate export format."""
    return format in ['json', 'csv', 'excel']

def prepare_export(data: Dict[str, Any], format: str) -> bytes:
    """Prepare data for export."""
    if not validate_export_format(format):
        raise ValueError(f"Unsupported export format: {format}")
    return package_dataset(data, format) 