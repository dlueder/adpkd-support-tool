# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ("icon.png", './'),
        ("icons/arrow-back-circle-outline.svg", 'icons/'),
        ("icons/arrow-forward-circle-outline.svg", 'icons/'),
        ("icons/bar-chart-sharp.svg", 'icons/'),
        ("icons/cog-sharp.svg", 'icons/'),
        ("icons/crop-sharp.svg", 'icons/'),
        ("icons/cut.svg", 'icons/'),
        ("icons/done.svg", 'icons/'),
        ("icons/folder-open.svg", 'icons/'),
        ("icons/image.svg", 'icons/'),
        ("icons/images.svg", 'icons/'),
        ("icons/reload-outline.svg", 'icons/'),
        ("icons/resetall.png", 'icons/'),
        ("icons/save-sharp.svg", 'icons/'),
        ("icons/scan.svg", 'icons/'),
        ("icons/trash-bin.svg", 'icons/')
    ],
    hiddenimports=['six'],
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
    name='ADPKDTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icon.png"
)
