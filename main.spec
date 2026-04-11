# -*- mode: python ; coding: utf-8 -*-

import os
import sys

icon_path = os.path.join('gui', 'assets', 'app_icon.ico') if sys.platform.startswith('win') else os.path.join('gui', 'assets', 'app_icon.png')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('gui/assets', 'gui/assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[icon_path],
)
