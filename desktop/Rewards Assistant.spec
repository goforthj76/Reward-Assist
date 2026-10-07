# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:/Users/gofor/Documents/Codex/2026-08-06/wh/outputs/rewards_assistant/local_app.py'],
    pathex=[],
    binaries=[('C:/Users/gofor/Documents/Codex/2026-08-06/wh/outputs/rewards_assistant/dist/Dutch Bros Setup.exe', '.')],
    datas=[('C:/Users/gofor/Documents/Codex/2026-08-06/wh/outputs/rewards_assistant/demo', 'demo'), ('C:/Users/gofor/Documents/Codex/2026-08-06/wh/outputs/rewards_assistant/../reward-assist-site/dist/icon-192.png', 'demo'), ('C:/Users/gofor/Documents/Codex/2026-08-06/wh/outputs/rewards_assistant/chrome_extension', 'chrome_extension')],
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
    name='Rewards Assistant',
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
    icon=['C:/Users/gofor/Documents/Codex/2026-08-06/wh/outputs/rewards_assistant/reward-assist.ico'],
)
