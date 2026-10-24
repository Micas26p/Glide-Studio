# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

ROOT = Path(SPECPATH)

datas = [
    (str(ROOT / "frontend"), "frontend"),
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "model_packs"), "model_packs"),
]

# Incluir todos os ficheiros de suporte e DLLs nativas do pywebview
datas += collect_data_files("webview")
binaries = collect_dynamic_libs("webview")

# Adicionar DLLs críticas do WebView2 e WebBrowserInterop diretamente na raiz (.) do executável
# para que o runtime do pywebview as localize instantaneamente via sys._MEIPASS
try:
    import webview
    lib_dir = Path(webview.__file__).parent / "lib"
    if lib_dir.exists():
        for dll in lib_dir.glob("*.dll"):
            binaries.append((str(dll), "."))
            datas.append((str(dll), "."))
        x64_loader = lib_dir / "runtimes" / "win-x64" / "native" / "WebView2Loader.dll"
        if x64_loader.exists():
            binaries.append((str(x64_loader), "."))
            datas.append((str(x64_loader), "."))
except Exception:
    pass

hiddenimports = [
    "uvicorn.lifespan.on",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "webview",
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    "pythonnet",
    "clr_loader",
    "cv2",
    "numpy",
    "pypdf",
    "PIL",
    "PIL.Image",
    "PIL.ImageOps",
    "glide_core",
    "glide_core.hardware",
    "glide_core.hardware.thermal_governor",
    "glide_core.subtitles",
    "glide_core.subtitles.time_utils",
    "glide_core.audio",
    "glide_core.audio.sfx_mixer",
]

a = Analysis(
    ["desktop_app.py"],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["scipy", "torch", "torchvision", "tkinter.test"],
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
