import json
import os
from pathlib import Path
import re
from typing import Dict, Any, Optional

def infer_type_from_format(format_str: str) -> str:
    """Infer the type from the legacy format string."""
    format_str = format_str.lower()
    if "date" in format_str or "dd/mm/yyyy" in format_str:
        return "date"
    elif "numeric" in format_str:
        return "numeric"
    elif "enum" in format_str:
        return "enum"
    else:
        return "str"

def create_pattern_from_format(format_str: str) -> Optional[str]:
    """Create a regex pattern from the legacy format string."""
    format_str = format_str.lower()
    
    # Handle common patterns
    if "alphanumeric" in format_str:
        # Extract max length if present
        match = re.search(r'(\d+)', format_str)
        max_len = int(match.group(1)) if match else 300
        return f"^[A-Za-z0-9]{{1,{max_len}}}$"
    
    elif "text" in format_str:
        # Extract max length if present
        match = re.search(r'max\s*(\d+)', format_str)
        max_len = int(match.group(1)) if match else 200
        return f"^.{{1,{max_len}}}$"
    
    elif "numeric" in format_str:
        match = re.search(r'(\d+)', format_str)
        max_len = int(match.group(1)) if match else 1
        return f"^\\d{{1,{max_len}}}$"
    
    return None

def convert_format_to_dict(format_str: str, field_name: str, descriptions: Dict[str, str]) -> Dict[str, Any]:
    """Convert a legacy format string to the new dictionary format."""
    field_type = infer_type_from_format(format_str)
    pattern = create_pattern_from_format(format_str)
    
    result = {
        "type": field_type,
        "description": descriptions.get(field_name, "")
    }
    
    if pattern:
        result["pattern"] = pattern
    
    if field_type == "date":
        result["format"] = "%d/%m/%Y"
    
    # Handle special cases for enums
    if field_type == "enum":
        # Extract values from description if available
        desc = descriptions.get(field_name, "")
        if ":" in desc:
            values = [v.strip() for v in desc.split(":")[1].split(",")]
            result["values"] = values
    
    return result

def convert_spec_file(file_path: Path) -> None:
    """Convert a single spec file from legacy to new format."""
    print(f"Converting {file_path}...")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            spec = json.load(f)
        
        # Get the dataset type (first key in the spec)
        dataset_type = next(iter(spec.keys()))
        dataset_spec = spec[dataset_type]
        
        # Get field descriptions
        descriptions = dataset_spec.get("field_descriptions", {})
        
        # Convert formats
        old_formats = dataset_spec.get("formats", {})
        new_formats = {}
        
        for field, format_str in old_formats.items():
            if isinstance(format_str, str):
                new_formats[field] = convert_format_to_dict(format_str, field, descriptions)
            else:
                # Already in new format
                new_formats[field] = format_str
        
        # Update the spec
        dataset_spec["formats"] = new_formats
        
        # Write back to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(spec, f, indent=2)
        
        print(f"Successfully converted {file_path}")
        
    except Exception as e:
        print(f"Error converting {file_path}: {str(e)}")

def main():
    """Convert all master spec files in the data/master directory."""
    master_dir = Path("data/master")
    
    # Find all master spec JSON files
    spec_files = []
    for root, _, files in os.walk(master_dir):
        for file in files:
            if file.startswith("master_") and file.endswith("_spec.json"):
                spec_files.append(Path(root) / file)
    
    print(f"Found {len(spec_files)} spec files to convert")
    
    # Convert each file
    for spec_file in spec_files:
        convert_spec_file(spec_file)
    
    print("Conversion complete!")

if __name__ == "__main__":
    main() 