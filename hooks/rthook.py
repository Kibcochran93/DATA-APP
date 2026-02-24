import os
import sys
import importlib.metadata

def _setup_metadata():
    # Add site-packages to sys.path
    if hasattr(sys, '_MEIPASS'):
        site_packages = os.path.join(sys._MEIPASS, 'Lib', 'site-packages')
        if os.path.exists(site_packages):
            sys.path.append(site_packages)
    
    # Ensure metadata is available
    try:
        importlib.metadata.version('streamlit')
    except importlib.metadata.PackageNotFoundError:
        # Create a dummy metadata if not found
        class DummyMetadata:
            def __init__(self):
                self.version = '1.0.0'
                self.metadata = {}
        
        importlib.metadata._meta = {'streamlit': DummyMetadata()}

_setup_metadata()
