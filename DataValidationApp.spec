# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('config.py', '.'), ('.env', '.'), ('docs', 'docs'), ('security', 'security'), ('utils', 'utils')],
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
    ],
    hookspath=['hooks'],
    hooksconfig={},
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
