from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any


def _boot_smoke_trace(stage: str):
    if os.environ.get("GLIDE_ULTRA_SMOKE_TEST") != "1" and "--smoke-test" not in sys.argv:
        return
    try:
        marker = Path(os.environ.get("GLIDE_ULTRA_SMOKE_FILE", Path.cwd() / "desktop_smoke_ok.json"))
        trace = marker.with_suffix(marker.suffix + ".trace.log")
        trace.parent.mkdir(parents=True, exist_ok=True)
        with trace.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {stage}\n")
    except Exception:
        pass


_boot_smoke_trace("boot:stdlib-ready")
import uvicorn
_boot_smoke_trace("boot:uvicorn-ready")


HOST = "127.0.0.1"
SERVER_READY_TIMEOUT = 20
APP_VERSION = "1.40.0"
DATA_ROOT: Path | None = None
BACKEND_APP = None
_INSTANCE_MUTEX = None
WINDOW_TITLE = "Glide Studio - App Local"


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def default_data_root() -> Path:
    return Path(os.environ.get("GLIDE_ULTRA_DATA_ROOT", app_dir())).resolve()


def data_root() -> Path:
    return DATA_ROOT or default_data_root()


def load_backend():
    global APP_VERSION, BACKEND_APP, DATA_ROOT
    if BACKEND_APP is None:
        from app import APP_VERSION as backend_version
        from app import DATA_ROOT as backend_data_root
        from app import app as fastapi_app

        APP_VERSION = backend_version
        DATA_ROOT = backend_data_root
        BACKEND_APP = fastapi_app
    return BACKEND_APP


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return int(sock.getsockname()[1])


def wait_for_health(base_url: str, timeout: float = SERVER_READY_TIMEOUT):
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/api/health", timeout=1.5) as response:
                if response.status == 200:
                    return
        except Exception as exc:
            last_error = exc
            time.sleep(0.2)
    raise RuntimeError(f"Motor local nao iniciou a tempo: {last_error}")


def read_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=1.5) as response:
        payload = response.read().decode("utf-8", errors="replace")
    return json.loads(payload)


def post_json(url: str, timeout: float = 8.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8", errors="replace")
    return json.loads(payload)


def show_error(title: str, message: str):
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
            return
        except Exception:
            pass
    print(f"{title}: {message}", file=sys.stderr)


def smoke_requested() -> bool:
    return os.environ.get("GLIDE_ULTRA_SMOKE_TEST") == "1" or "--smoke-test" in sys.argv


def smoke_marker_path() -> Path:
    for arg in sys.argv[1:]:
        if arg.startswith("--smoke-file="):
            return Path(arg.split("=", 1)[1])
    return Path(os.environ.get("GLIDE_ULTRA_SMOKE_FILE", data_root() / "desktop_smoke_ok.json"))


def write_smoke_marker(payload: dict[str, Any]):
    marker = smoke_marker_path()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_smoke_trace(stage: str):
    if not smoke_requested():
        return
    try:
        marker = smoke_marker_path()
        trace = marker.with_suffix(marker.suffix + ".trace.log")
        trace.parent.mkdir(parents=True, exist_ok=True)
        with trace.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {stage}\n")
    except Exception:
        pass


def acquire_single_instance() -> bool:
    global _INSTANCE_MUTEX
    if os.name != "nt":
        return True
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.CreateMutexW(None, False, "Local\\GlideStudioDesktopApp")
        if not handle:
            return True
        if ctypes.get_last_error() == 183:
            kernel32.CloseHandle(handle)
            return False
        _INSTANCE_MUTEX = (kernel32, handle)
        return True
    except Exception:
        return True


def release_single_instance():
    global _INSTANCE_MUTEX
    if not _INSTANCE_MUTEX:
        return
    try:
        kernel32, handle = _INSTANCE_MUTEX
        kernel32.CloseHandle(handle)
    except Exception:
        pass
    _INSTANCE_MUTEX = None


def hidden_subprocess_kwargs() -> dict[str, Any]:
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
        "startupinfo": startupinfo,
    }


def app_icon_path() -> Path:
    return app_dir() / "assets" / "glide_studio.ico"


def set_windows_app_id():
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("GlideStudio.LocalDesktop")
    except Exception:
        pass


def set_native_window_icon(window: Any):
    if os.name != "nt":
        return
    icon = app_icon_path()
    if not icon.exists():
        return
    try:
        import ctypes

        native = getattr(window, "native", None)
        handle = getattr(native, "Handle", None)
        if handle is None:
            return
        hwnd = int(handle)
        user32 = ctypes.windll.user32
        image_icon = 1
        load_from_file = 0x00000010
        wm_seticon = 0x0080
        icon_small = 0
        icon_big = 1
        small = user32.LoadImageW(None, str(icon), image_icon, 16, 16, load_from_file)
        big = user32.LoadImageW(None, str(icon), image_icon, 32, 32, load_from_file)
        if small:
            user32.SendMessageW(hwnd, wm_seticon, icon_small, small)
        if big:
            user32.SendMessageW(hwnd, wm_seticon, icon_big, big)
    except Exception:
        pass


def confirm_close_if_rendering(runtime: "DesktopRuntime") -> bool:
    if not runtime.has_active_render():
        return True
    message = (
        "Existe um render ativo no Glide Studio.\n\n"
        "Se fechar agora, o render pode ser interrompido.\n"
        "Deseja fechar mesmo assim?"
    )
    if os.name == "nt":
        try:
            import ctypes

            response = ctypes.windll.user32.MessageBoxW(None, message, WINDOW_TITLE, 0x34)
            return response == 6
        except Exception:
            return False
    return False


def browser_profile_root() -> Path:
    return data_root() / "browser_app_profile"


def cleanup_browser_profiles():
    root = browser_profile_root()
    if not root.exists():
        return
    for item in root.iterdir():
        try:
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)
        except Exception:
            pass
    try:
        root.rmdir()
    except Exception:
        pass


WEBVIEW_CACHE_DIR_NAMES = {
    "blob_storage",
    "BrowserMetrics",
    "Cache",
    "CacheStorage",
    "Code Cache",
    "component_crx_cache",
    "Crashpad",
    "DawnCache",
    "DawnGraphiteCache",
    "DawnWebGPUCache",
    "GPUCache",
    "GrShaderCache",
    "hyphen-data",
    "ShaderCache",
    "Speech Recognition",
    "Subresource Filter",
}


def _safe_runtime_child(path: Path) -> Path | None:
    try:
        root = data_root().resolve()
        resolved = path.resolve()
    except Exception:
        return None
    if resolved == root or root not in resolved.parents:
        return None
    return resolved


def cleanup_desktop_runtime_data() -> None:
    """Remove browser/runtime caches after WebView and FFmpeg released their files."""
    root = data_root()
    profile = root / "webview_profile"
    if profile.exists():
        try:
            candidates = [
                path
                for path in profile.rglob("*")
                if path.is_dir() and path.name in WEBVIEW_CACHE_DIR_NAMES
            ]
        except Exception:
            candidates = []
        for path in sorted(candidates, key=lambda item: len(item.parts), reverse=True):
            resolved = _safe_runtime_child(path)
            if resolved:
                shutil.rmtree(resolved, ignore_errors=True)

    cleanup_browser_profiles()
    for name in ("temp_uploads", "renders", "cta_cache", "build", "__pycache__", ".verification-artifacts"):
        path = _safe_runtime_child(root / name)
        if path:
            shutil.rmtree(path, ignore_errors=True)

    for pattern in ("build_*.log", "smoke_*.log", "desktop_smoke*.log", "*.trace.log"):
        try:
            for path in root.glob(pattern):
                resolved = _safe_runtime_child(path)
                if resolved and resolved.is_file():
                    resolved.unlink(missing_ok=True)
        except Exception:
            continue


class DesktopRuntime:
    def __init__(self):
        backend_app = load_backend()
        self.port = find_free_port()
        self.base_url = f"http://{HOST}:{self.port}"
        self.server = uvicorn.Server(
            uvicorn.Config(
                backend_app,
                host=HOST,
                port=self.port,
                log_level="warning",
                log_config=None,
                access_log=False,
                reload=False,
            )
        )
        self.thread = threading.Thread(target=self.server.run, name="glide-ultra-api", daemon=True)

    def start(self):
        os.environ["GLIDE_ULTRA_DESKTOP"] = "1"
        os.environ["GLIDE_ULTRA_PORT"] = str(self.port)
        os.chdir(app_dir())
        self.thread.start()
        wait_for_health(self.base_url)

    def stop(self):
        self.server.should_exit = True

    def stop_and_wait(self):
        self.stop()
        self.thread.join(timeout=5)

    def prepare_shutdown(self):
        try:
            return post_json(f"{self.base_url}/api/maintenance/prepare-shutdown")
        except Exception:
            return {}

    def has_active_render(self) -> bool:
        try:
            status = read_json(f"{self.base_url}/api/desktop")
        except Exception:
            return False
        return bool(status.get("active_jobs"))

    def desktop_status(self) -> dict[str, Any]:
        try:
            return read_json(f"{self.base_url}/api/desktop")
        except Exception:
            return {}


def browser_candidates() -> list[tuple[str, Path]]:
    candidates: list[tuple[str, Path]] = []

    def add(label: str, value: str | Path | None):
        if not value:
            return
        path = Path(value)
        if path.exists() and path.is_file():
            resolved = path.resolve()
            if all(existing != resolved for _, existing in candidates):
                candidates.append((label, resolved))

    chrome_paths = [
        shutil.which("chrome"),
        shutil.which("chrome.exe"),
        Path(os.environ.get("ProgramFiles", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
    ]
    edge_paths = [
        shutil.which("msedge"),
        shutil.which("msedge.exe"),
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    ]
    for item in chrome_paths:
        add("Chrome", item)
    for item in edge_paths:
        add("Edge", item)
    return candidates


def launch_browser_app(browser: Path, label: str, url: str, profile_dir: Path) -> subprocess.Popen:
    profile_dir.mkdir(parents=True, exist_ok=True)
    args = [
        str(browser),
        f"--app={url}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--disable-background-mode",
        "--disable-translate",
        "--disable-component-extensions-with-background-pages",
        "--disable-features=Translate",
    ]
    options = hidden_subprocess_kwargs()
    return subprocess.Popen(
        args,
        cwd=str(app_dir()),
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **options,
    )


def run_browser_app(runtime: DesktopRuntime):
    url = f"{runtime.base_url}/?desktop=1&v={APP_VERSION}"
    last_error: Exception | None = None
    cleanup_browser_profiles()
    try:
        for label, browser in browser_candidates():
            profile_dir = browser_profile_root() / f"{label.lower()}_{runtime.port}"
            try:
                process = launch_browser_app(browser, label, url, profile_dir)
                process.wait()
                return
            except Exception as exc:
                last_error = exc
            finally:
                shutil.rmtree(profile_dir, ignore_errors=True)
        message = (
            "Nao encontrei Google Chrome nem Microsoft Edge para abrir em modo app.\n\n"
            "Instale o Chrome ou Edge e abra novamente o Glide Studio."
        )
        if last_error:
            message += f"\n\nDetalhe tecnico: {last_error}"
        show_error("Glide Studio", message)
    finally:
        cleanup_browser_profiles()


def run_native_app(runtime: DesktopRuntime):
    import webview

    set_windows_app_id()
    url = f"{runtime.base_url}/?desktop=1&v={APP_VERSION}"
    window = webview.create_window(
        WINDOW_TITLE,
        url,
        width=1500,
        height=950,
        min_size=(1080, 680),
        background_color="#080b0a",
        confirm_close=False,
        text_select=True,
        zoomable=False,
    )
    if window is None:
        raise RuntimeError("Nao foi possivel criar a janela nativa do Glide Studio.")

    def on_closing():
        if confirm_close_if_rendering(runtime):
            return True
        return False

    def on_before_show():
        set_native_window_icon(window)

    window.events.closing += on_closing
    window.events.before_show += on_before_show
    webview.start(
        private_mode=False,
        storage_path=str(data_root() / "webview_profile"),
        icon=str(app_icon_path()),
    )


def smoke_test(runtime: DesktopRuntime):
    paths = [
        "/api/health",
        "/api/config",
        "/api/cta-assets",
        "/",
        "/favicon.ico",
        "/static/app.js",
        "/static/modules/runtime-config.js",
        "/static/style.css",
        "/assets/glide_studio_icon_256.png",
        "/assets/glide_studio.ico",
        "/assets/glide_studio_icon_32.png",
        "/assets/glide_studio_icon_48.png",
        "/assets/glide_studio_icon.png",
        "/assets/site.webmanifest",
    ]
    results = {}
    visual_face_detector = {}
    for path in paths:
        write_smoke_trace(f"smoke:request:{path}")
        with urllib.request.urlopen(runtime.base_url + path, timeout=20) as response:
            if response.status != 200:
                raise RuntimeError(f"Smoke test falhou em {path}: HTTP {response.status}")
            results[path] = response.status
            if path == "/api/health":
                try:
                    payload = json.loads(response.read().decode("utf-8"))
                    visual_face_detector = payload.get("visual_face_detector") or {}
                except Exception:
                    visual_face_detector = {}
    write_smoke_marker({
        "ok": True,
        "paths": results,
        "version": APP_VERSION,
        "visual_face_detector": visual_face_detector,
    })


def main():
    runtime: DesktopRuntime | None = None
    smoke = smoke_requested()
    write_smoke_trace("main:start")
    if not smoke and not acquire_single_instance():
        show_error("Glide Studio", "O Glide Studio ja esta aberto. Use a janela existente.")
        return
    try:
        write_smoke_trace("runtime:create")
        runtime = DesktopRuntime()
        write_smoke_trace("runtime:start")
        runtime.start()
        write_smoke_trace("runtime:ready")
        if smoke:
            write_smoke_trace("smoke:requests")
            smoke_test(runtime)
            write_smoke_trace("smoke:complete")
            runtime.stop_and_wait()
            write_smoke_trace("runtime:stopped")
            return
        try:
            run_native_app(runtime)
        except Exception:
            run_browser_app(runtime)
    except Exception as exc:
        if runtime:
            runtime.stop_and_wait()
        if smoke:
            write_smoke_trace(f"smoke:error:{type(exc).__name__}:{exc}")
            write_smoke_marker({"ok": False, "error": str(exc), "version": APP_VERSION})
            raise SystemExit(1)
        show_error("Glide Studio", str(exc))
        raise
    finally:
        if runtime and not smoke:
            runtime.prepare_shutdown()
            runtime.stop_and_wait()
        cleanup_desktop_runtime_data()
        release_single_instance()


if __name__ == "__main__":
    main()

