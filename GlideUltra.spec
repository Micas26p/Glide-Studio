# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

ROOT = Path(SPECPATH)

datas = [
    (str(ROOT / "frontend"), "frontend"),
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "model_packs"), "model_packs"),
]

hiddenimports = [
    "uvicorn.lifespan.on",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "cv2",
    "numpy",
    "pypdf",
    "PIL",
    "PIL.Image",
    "PIL.ImageOps",
]

a = Analysis(
    ["desktop_app.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["scipy", "torch", "torchvision", "webview", "clr_loader", "pythonnet", "tkinter.test"],
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
    name="Glide Studio",
    icon=str(ROOT / "assets" / "glide_studio.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
