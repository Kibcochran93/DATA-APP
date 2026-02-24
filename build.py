import os
import sys
import shutil
from pathlib import Path

def clean_build_dirs():
    """Clean build and dist directories."""
    dirs_to_clean = ['build', 'dist']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)

def create_env_file():
    """Create a default .env file if it doesn't exist."""
    if not os.path.exists('.env'):
        env_content = """# Application Configuration
APP_ENV=development
DEBUG=True

# Security Settings
JWT_SECRET=your-secret-key-here
ENCRYPTION_KEY=your-encryption-key-here

# File Settings
MAX_FILE_SIZE=10485760  # 10MB
ALLOWED_EXTENSIONS=.csv,.xlsx,.json

# Logging
LOG_LEVEL=INFO
LOG_FILE=app.log

# Redis (optional)
REDIS_ENABLED=false
REDIS_URL=redis://localhost:6379/0
"""
        with open('.env', 'w') as f:
            f.write(env_content)
        print("Created default .env file")

def verify_required_files():
    """Verify that all required files exist."""
    required_files = [
        'app.py',
        'config.py',
        'requirements.txt'
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print("Error: The following required files are missing:")
        for file in missing_files:
            print(f"  - {file}")
        sys.exit(1)

def create_runtime_hook():
    """Create a runtime hook to handle metadata."""
    hook_content = """import os
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
"""
    os.makedirs('hooks', exist_ok=True)
    with open('hooks/rthook.py', 'w') as f:
        f.write(hook_content)

def create_spec_file():
    """Create PyInstaller spec file."""
    # Get list of data files that exist
    data_files = []
    for item in [
        ('config.py', '.'),
        ('.env', '.'),
        ('ui_components.py', '.'),
        ('wizard_controller.py', '.'),
        ('docs', 'docs'),
        ('security', 'security'),
        ('utils', 'utils'),
        ('autho', 'autho'),
        ('protection', 'protection'),
        ('monitoring', 'monitoring'),
        ('controller', 'controller'),
        ('core', 'core'),
        ('config', 'config'),
        ('helpers', 'helpers'),
        ('components', 'components'),
        ('data', 'data'),
    ]:
        if os.path.exists(item[0]):
            data_files.append(item)
        else:
            print(f"Warning: {item[0]} not found, skipping...")

    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas={data_files},
    hiddenimports=[
        'streamlit',
        'pandas',
        'numpy',
        'python-dotenv',
        'cryptography',
        'pyjwt',
        'openpyxl',
        'xlrd',
        'fuzzywuzzy',
        'python-Levenshtein',
        'zipfile36',
        'tqdm',
        'streamlit-extras',
        'plotly',
        'importlib.metadata',
        'importlib_metadata',
        'pkg_resources.py2_warn',
        'chardet',
        'psutil',
        'pydantic',
    ],
    hookspath=['hooks'],
    hooksconfig={{}},
    runtime_hooks=['hooks/rthook.py'],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DataValidationApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
"""
    with open('DataValidationApp.spec', 'w') as f:
        f.write(spec_content)

def build_executable():
    """Build the executable using PyInstaller."""
    try:
        print("Starting build process...")
        
        # Verify required files
        verify_required_files()
        
        # Create .env file if it doesn't exist
        create_env_file()
        
        # Create runtime hook
        create_runtime_hook()
        
        # Clean previous builds
        clean_build_dirs()
        
        # Create spec file
        create_spec_file()
        
        print("Running PyInstaller...")
        # Run PyInstaller with more verbose output
        result = os.system('pyinstaller --clean DataValidationApp.spec')
        
        if result != 0:
            raise Exception("PyInstaller build failed")
        
        # Create version file
        version_file = Path('dist/version.txt')
        version_file.write_text('1.0.0')
        
        print("\nBuild completed successfully!")
        print("Executable location: dist/DataValidationApp.exe")
        print("\nNote: Please review the .env file and update the security keys before distribution.")
        
    except Exception as e:
        print(f"\nBuild failed: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    build_executable()
