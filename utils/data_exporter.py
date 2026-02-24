import os
import json
import pandas as pd
from datetime import datetime
from utils.exceptions import SecurityError, ValidationError

class DataExporter:
    def __init__(self, config):
        self.config = config
        self.export_dir = config['export_dir']
        self.supported_formats = config['supported_formats']
        self.max_file_size = config['max_file_size']
        self.retention_days = config['retention_days']
        self.compression = config['compression']
        self.format_configs = config['formats']
        self.export_history = []

    def export_data(self, data, format_type):
        """Export data to the specified format."""
        if format_type not in self.supported_formats:
            raise ValidationError(f"Unsupported format: {format_type}")

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"export_{timestamp}.{format_type}"
        filepath = os.path.join(self.export_dir, filename)

        try:
            if isinstance(data, pd.DataFrame):
                if format_type == 'csv':
                    data.to_csv(filepath, **self.format_configs['csv'])
                elif format_type == 'excel':
                    data.to_excel(filepath, **self.format_configs['excel'])
                elif format_type == 'json':
                    data.to_json(filepath, **self.format_configs['json'])
            elif isinstance(data, (dict, list)):
                if format_type == 'json':
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(data, f, **self.format_configs['json'])
                else:
                    raise ValidationError(f"Format {format_type} not supported for {type(data)}")
            else:
                raise SecurityError("Export failed: Unsupported data type")

            # Check file size
            file_size = os.path.getsize(filepath)
            if file_size > self.max_file_size:
                os.remove(filepath)
                raise SecurityError("Export file too large")

            # Record export
            export_record = {
                'filename': filename,
                'path': filepath,
                'size': file_size,
                'created': datetime.now().isoformat(),
                'format': format_type
            }
            self.export_history.append(export_record)

            return export_record

        except Exception as e:
            if os.path.exists(filepath):
                os.remove(filepath)
            raise SecurityError(f"Export failed: {str(e)}")

    def get_export_history(self):
        """Get the export history."""
        return self.export_history

    def cleanup_exports(self, max_age_days=None):
        """Clean up old export files."""
        if max_age_days is None:
            max_age_days = self.retention_days

        cutoff_date = datetime.now() - pd.Timedelta(days=max_age_days)
        current_history = []

        for record in self.export_history:
            created_date = datetime.fromisoformat(record['created'])
            if created_date > cutoff_date:
                current_history.append(record)
            elif os.path.exists(record['path']):
                os.remove(record['path'])

        self.export_history = current_history 