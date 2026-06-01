# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['UOVidCompiler_GUI.py'],
    pathex=[],
    binaries=[],
    datas=[('icons', 'icons'), ('Music', 'Music'), ('Intros', 'Intros'), ('ffmpeg', 'ffmpeg')],
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
    name='BMagic_AutoVidCompiler_PERFECT',
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
    icon=['icons\\AutoVideoCompiler_icon.ico'],
)
