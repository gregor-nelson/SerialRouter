# -*- mode: python ; coding: utf-8 -*-

# Include essential modules and standard library modules used by the app
hiddenimports = [
    # Standard library modules
    'json',
    'threading',
    'logging',
    'logging.handlers',
    'queue',
    'datetime',
    'pathlib',
    'typing',
    'collections',
    'signal',
    'traceback',
    # PyQt6
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.QtSvg',
    'PyQt6.QtSvgWidgets',
    # Serial
    'serial',
    'serial.tools',
    'serial.tools.list_ports',
]

# Exclude heavy Qt modules we definitely don't use
excludes = [
    'PyQt6.QtWebEngine',
    'PyQt6.QtWebEngineCore',
    'PyQt6.QtWebEngineWidgets',
    'PyQt6.QtNetwork',
    'PyQt6.QtMultimedia',
    'PyQt6.QtOpenGL',
    'PyQt6.QtTest',
    'PyQt6.QtQml',
    'PyQt6.QtQuick',
]

import os
# SPECPATH is the directory containing this spec file (scripts/)
# So we just need to go up one level to get project root
project_root = os.path.dirname(SPECPATH)

a = Analysis(
    [os.path.join(project_root, 'main.py')],
    pathex=[project_root],
    binaries=[],
    datas=[
        (os.path.join(project_root, 'src'), 'src'),
        (os.path.join(project_root, 'assets'), 'assets'),
        (os.path.join(project_root, 'guide'), 'guide')
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=2,
)

# Remove __pycache__ from bundled files
a.datas = [x for x in a.datas if '__pycache__' not in x[0]]

pyz = PYZ(a.pure)

# Single-file executable build
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Serial Router',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=os.path.join(project_root, 'scripts', 'version_info.txt'),
    uac_admin=True,
    icon=[os.path.join(project_root, 'assets', 'icons', 'app_icon.ico')],
)
