import zipfile
import io
import os
import hashlib
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import pandas as pd
from utils.debug_logger import setup_logger
from utils.exceptions import ValidationError, DataError
from core.data_cleaner import DataCleaner

logger = setup_logger(__name__, "export_packager.log")

class ExportPackager:
    """Handles packaging of exports into ZIP files with conflict resolution."""
    
    def __init__(self, temp_dir: Optional[str] = None):
        """
        Initialize packager with temporary directory.
        
        Args:
            temp_dir: Optional temporary directory path
        """
        self.temp_dir = temp_dir or tempfile.mkdtemp(prefix="seats_export_")
        os.makedirs(self.temp_dir, exist_ok=True)
        self.data_cleaner = DataCleaner()
        
    def __del__(self):
        """Cleanup temporary directory on deletion."""
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Failed to cleanup temp directory: {str(e)}")
            
    def _generate_unique_filename(self, base_name: str, content_hash: str) -> str:
        """
        Generate unique filename using timestamp and content hash.
        
        Args:
            base_name: Base filename
            content_hash: Hash of file content
            
        Returns:
            Unique filename
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{base_name}_{timestamp}_{content_hash[:8]}"
        
    def _calculate_content_hash(self, content: bytes) -> str:
        """
        Calculate SHA-256 hash of content.
        
        Args:
            content: Content to hash
            
        Returns:
            Content hash
        """
        return hashlib.sha256(content).hexdigest()
        
    def _handle_conflict(self, zip_file: zipfile.ZipFile, filename: str, content: bytes) -> str:
        """
        Handle filename conflicts in ZIP file.
        
        Args:
            zip_file: ZIP file object
            filename: Original filename
            content: File content
            
        Returns:
            New filename to use
        """
        # Check if file exists in ZIP
        if filename in zip_file.namelist():
            # Generate unique name
            content_hash = self._calculate_content_hash(content)
            base_name = os.path.splitext(filename)[0]
            new_filename = self._generate_unique_filename(base_name, content_hash)
            logger.info(f"File conflict resolved: {filename} -> {new_filename}")
            return new_filename
        return filename
        
    def create_export_package(
        self,
        df: pd.DataFrame,
        dataset_type: str,
        validation_results: Optional[Dict[str, Any]] = None,
        spec_version: str = "1.0",
        strip_pii: bool = True
    ) -> Tuple[bytes, str]:
        """
        Create a ZIP package containing the cleaned CSV and README.
        
        Args:
            df: Cleaned DataFrame to export
            dataset_type: Type of dataset being exported
            validation_results: Optional validation results to include in README
            spec_version: Version of the spec used for validation
            strip_pii: Whether to strip PII data from debug views
            
        Returns:
            Tuple of (ZIP file contents, filename)
        """
        try:
            # Create temporary directory for this export
            export_dir = os.path.join(self.temp_dir, f"export_{datetime.now().strftime('%Y%m%d%H%M%S')}")
            os.makedirs(export_dir, exist_ok=True)
            
            # Strip PII data if requested
            if strip_pii:
                df = self.data_cleaner.strip_personal_data(df, dataset_type)
            
            # Generate CSV content
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_content = csv_buffer.getvalue().encode('utf-8')
            
            # Generate README content
            readme_content = self._generate_readme(
                dataset_type=dataset_type,
                row_count=len(df),
                timestamp=datetime.now(),
                spec_version=spec_version,
                validation_results=validation_results
            ).encode('utf-8')
            
            # Create ZIP file
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Add CSV with conflict resolution
                csv_filename = f"{dataset_type}.csv"
                csv_filename = self._handle_conflict(zip_file, csv_filename, csv_content)
                zip_file.writestr(csv_filename, csv_content)
                
                # Add README with conflict resolution
                readme_filename = "README.txt"
                readme_filename = self._handle_conflict(zip_file, readme_filename, readme_content)
                zip_file.writestr(readme_filename, readme_content)
            
            # Generate unique ZIP filename
            zip_content = zip_buffer.getvalue()
            content_hash = self._calculate_content_hash(zip_content)
            zip_filename = self._generate_unique_filename(f"{dataset_type}_export", content_hash) + ".zip"
            
            # Cleanup temporary files
            try:
                shutil.rmtree(export_dir)
                logger.info(f"Cleaned up export directory: {export_dir}")
            except Exception as e:
                logger.error(f"Failed to cleanup export directory: {str(e)}")
            
            return zip_content, zip_filename
            
        except Exception as e:
            logger.error(f"Export package creation failed: {str(e)}")
            raise DataError(f"Failed to create export package: {str(e)}")
            
    def _generate_readme(
        self,
        dataset_type: str,
        row_count: int,
        timestamp: datetime,
        spec_version: str,
        validation_results: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate README content for the export package.
        
        Args:
            dataset_type: Type of dataset being exported
            row_count: Number of rows in the dataset
            timestamp: Export timestamp
            spec_version: Version of the spec used for validation
            validation_results: Optional validation results to include
            
        Returns:
            README content
        """
        lines = [
            "SEAtS IGNITE Smart Data Intake Mapper Export",
            "==========================================",
            f"Dataset: {dataset_type}",
            f"Timestamp: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Rows: {row_count}",
            f"Spec Version: {spec_version}",
            ""
        ]
        
        if validation_results:
            lines.extend([
                "Validation Results",
                "-----------------",
                f"Total Issues: {len(validation_results.get('issues', []))}",
                ""
            ])
            
            if validation_results.get('issues'):
                lines.append("Issues Found:")
                for issue in validation_results['issues']:
                    lines.append(f"- {issue}")
                    
        return "\n".join(lines) 