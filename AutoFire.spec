# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['autofire_ui.py'],
    pathex=[],
    binaries=[],
    datas=[('README.md', '.'), ('README_MULTI_SLOT.md', '.'), ('MULTI_SLOT_FIX.md', '.'), ('RELEASE_NOTES_v2.1.0.md', '.')],
    hiddenimports=['keyboard'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'test_autofire_ui_tk', 'test_multi_slot', 'test_autofire_runner'],
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
    name='AutoFire',
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
    icon='NONE',
)
