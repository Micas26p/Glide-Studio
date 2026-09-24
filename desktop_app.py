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

if os.name == "nt":
    try:
        import ctypes
        ctypes.cdll.msvcrt._setmaxstdio(2048)
    except Exception:
        pass


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


def _apply_low_memory_webview_flags() -> None:
    """Configure WebView2 (Edge Chromium) to eliminate bloat without starving UI performance.

    Disables background networking, crashpad, autofill, and unused browser features.
    GPU hardware compositing is kept ENABLED so the GPU accelerates UI rendering smoothly
    without burning CPU cycles on software rasterization.
    """
    flags = " ".join([
        "--disable-features=BackForwardCache,TranslateUI,Translate,MediaRouter,AutofillServerCommunication",
        "--disable-background-networking",
        "--disable-client-side-phishing-detection",
        "--disable-default-apps",
        "--no-pings",
        "--disable-breakpad",
        "--disable-component-update",
        "--disable-domain-reliability",
        "--disable-sync",
    ])
    existing = os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "")
    if existing:
        flags = existing + " " + flags
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = flags


def _cleanup_webview_caches_on_boot() -> None:
    """Aggressively clean WebView2 caches before starting the UI.

    The webview_profile directory accumulates hundreds of MB of shader caches,
    code caches, blob storage, etc. across sessions.  Cleaning these on boot
    prevents stale caches from inflating RAM usage.
    """
    root = default_data_root()
    profile = root / "webview_profile"
    if not profile.exists():
        return
    for name in WEBVIEW_CACHE_DIR_NAMES:
        target = profile / name
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
    # Also clean nested EBWebView caches
    ebwv = profile / "EBWebView"
    if ebwv.is_dir():
        for name in WEBVIEW_CACHE_DIR_NAMES:
            target = ebwv / name
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)


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


DEFAULT_DESKTOP_PORT = 47851


def _port_is_free(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((HOST, int(port)))
        return True
    except OSError:
        return False


def _latest_webview_origin_port(root: Path) -> int | None:
    """Porta da origem WebView usada mais recentemente (onde estão rascunhos/definições)."""
    idb = root / "webview_profile" / "EBWebView" / "Default" / "IndexedDB"
    try:
        entries = [
            item for item in idb.iterdir()
            if item.is_dir() and item.name.startswith("http_127.0.0.1_") and item.name.endswith(".indexeddb.leveldb")
        ]
    except OSError:
        return None
    entries.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    for item in entries:
        digits = item.name[len("http_127.0.0.1_"):].split(".", 1)[0]
        if digits.isdigit():
            return int(digits)
    return None


def choose_desktop_port() -> int:
    """Porta estável entre arranques.

    O IndexedDB/localStorage do WebView é por origem (host:porta). Com uma porta
    aleatória a cada arranque, o rascunho do AUTO e as preferências "desapareciam"
    e cada sessão criava uma nova cópia dos ficheiros no perfil. Reutiliza a porta
    guardada; na primeira vez adota a origem mais recente para não perder o rascunho.
    """
    root = default_data_root()
    config = root / "desktop_port.json"
    candidates: list[int] = []
    try:
        saved = int(json.loads(config.read_text(encoding="utf-8")).get("port") or 0)
        if saved:
            candidates.append(saved)
    except Exception:
        latest = _latest_webview_origin_port(root)
        if latest:
            candidates.append(latest)
    candidates.append(DEFAULT_DESKTOP_PORT)
    for index, port in enumerate(candidates):
        if 1024 < port < 65536 and _port_is_free(port):
            # Só memoriza a porta preferida; um recurso temporário (porta ocupada por
            # outra instância) não pode substituir a origem onde está o rascunho.
            if index == 0:
                try:
                    config.write_text(json.dumps({"port": port}), encoding="utf-8")
                except OSError:
                    pass
            return port
    return find_free_port()


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
    marker.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


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
        self.port = choose_desktop_port()
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


class PageCrashRecovery:
    """Decide quando recarregar a página após o WebView2 matar o processo da UI.

    Com o Windows sem memória o renderer é encerrado e fica o ecrã "This page is
    having a problem"; o backend (e o render) continua vivo, basta recarregar.
    Limita as tentativas para não entrar em ciclo se a memória continuar esgotada.
    """

    # COREWEBVIEW2_PROCESS_FAILED_KIND: 1 = renderer terminou, 2 = renderer sem resposta
    RECOVERABLE_KINDS = {1, 2}

    def __init__(self, max_reloads: int = 8, window_seconds: float = 600.0):
        self.max_reloads = max_reloads
        self.window_seconds = window_seconds
        self.reloads: list[float] = []

    def next_delay(self, kind: int, now: float | None = None) -> float | None:
        """Segundos até recarregar, ou None quando não se deve recarregar."""
        if kind not in self.RECOVERABLE_KINDS:
            return None
        now = time.monotonic() if now is None else now
        self.reloads = [t for t in self.reloads if now - t < self.window_seconds]
        if len(self.reloads) >= self.max_reloads:
            return None
        self.reloads.append(now)
        # Recuo progressivo: dá tempo ao Windows para libertar memória antes de recarregar
        return min(30.0, 2.0 * (2 ** (len(self.reloads) - 1)))


class UiFreezeWatchdog:
    """Deteta a UI congelada (JS bloqueado ou página sem pintar) pelo batimento da página."""

    def __init__(self, stale_after: float = 25.0, grace: float = 45.0):
        self.stale_after = stale_after
        self.grace = grace
        self.last_action = time.monotonic()

    def is_frozen(self, now: float, last_beat: float, page_visible: bool, minimized: bool, foreground: bool) -> bool:
        if minimized or not (page_visible or foreground):
            return False  # minimizada/tapada: o Chromium pára de pintar de propósito
        if now - self.last_action < self.grace:
            return False  # a página ainda está a (re)carregar
        return now - max(last_beat, self.last_action) > self.stale_after

    def mark_action(self, now: float | None = None) -> None:
        self.last_action = time.monotonic() if now is None else now


def _window_flags(hwnd: int) -> tuple[bool, bool]:
    """(minimizada, em primeiro plano) via Win32; (False, False) se indisponível."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        return bool(user32.IsIconic(hwnd)), user32.GetForegroundWindow() == hwnd
    except Exception:
        return False, False


def _kill_webview_renderers(browser_pid: int) -> int:
    """Termina só os renderers filhos do WebView2 do Glide (dispara ProcessFailed -> recarregar)."""
    if not browser_pid:
        return 0
    script = (
        f"Get-CimInstance Win32_Process -Filter \"ParentProcessId={int(browser_pid)} AND Name='msedgewebview2.exe'\" | "
        "Where-Object { $_.CommandLine -like '*--type=renderer*' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force; $_.ProcessId }"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=20, **hidden_subprocess_kwargs(),
        ).stdout
        return len([line for line in out.split() if line.strip().isdigit()])
    except Exception:
        return 0


def attach_page_crash_recovery(window: Any, url: str) -> None:
    """Liga o evento ProcessFailed do WebView2 e o watchdog de congelamento a um recarregamento automático."""
    policy = PageCrashRecovery()
    watchdog = UiFreezeWatchdog()
    attached = {"done": False, "hwnd": 0, "browser_pid": 0}

    def reload_page():
        """Navega de novo no thread da UI (o renderer é recriado se tiver morrido)."""
        core = attached.get("core")
        try:
            from System import Func, Type
            if core is None:
                window.load_url(url)
                return
            window.native.Invoke(Func[Type](lambda: core.Navigate(url) or None))
        except Exception as exc:
            print(f"[desktop] falha ao recarregar a UI: {exc}", file=sys.stderr)

    def watch_loop():
        try:
            import app as backend
        except Exception:
            return
        while True:
            time.sleep(5.0)
            if not attached["hwnd"]:
                continue
            beat = backend.UI_HEARTBEAT
            minimized, foreground = _window_flags(attached["hwnd"])
            now = time.monotonic()
            if not watchdog.is_frozen(now, float(beat.get("at") or 0.0), bool(beat.get("visible")), minimized, foreground):
                continue
            watchdog.mark_action(now)
            if policy.next_delay(2, now=now) is None:
                continue  # demasiadas recuperações seguidas: não entrar em ciclo
            # Um renderer preso não obedece a Navigate/Reload. Terminá-lo faz o WebView2
            # disparar ProcessFailed, que recarrega a página num processo novo.
            killed = _kill_webview_renderers(attached["browser_pid"])
            print(f"[desktop] UI congelada ha {now - float(beat.get('at') or 0.0):.0f}s; renderers terminados={killed}", file=sys.stderr)
            if not killed:
                reload_page()

    def on_process_failed(_sender, args):
        try:
            kind = int(args.ProcessFailedKind)
        except Exception:
            kind = -1
        delay = policy.next_delay(kind)
        print(f"[desktop] WebView2 ProcessFailed kind={kind}; recarregar em {delay}s", file=sys.stderr)
        if delay is None:
            return
        watchdog.mark_action()
        if kind == 2:
            # Sem resposta: recarregar não chega ao renderer preso; terminá-lo gera kind=1.
            threading.Thread(target=_kill_webview_renderers, args=(attached["browser_pid"],), daemon=True).start()
            return
        threading.Timer(delay, reload_page).start()

    def attach():
        browser = getattr(getattr(window, "native", None), "browser", None)
        core = getattr(getattr(browser, "webview", None), "CoreWebView2", None)
        if core is None or attached["done"]:
            return
        core.ProcessFailed += on_process_failed
        attached["core"] = core
        attached["hwnd"] = int(window.native.Handle.ToInt64())
        try:
            attached["browser_pid"] = int(core.BrowserProcessId)
        except Exception:
            pass
        attached["done"] = True
        threading.Thread(target=watch_loop, name="glide-ui-watchdog", daemon=True).start()

    def on_loaded():
        if attached["done"]:
            return
        try:
            from System import Func, Type
            window.native.Invoke(Func[Type](lambda: attach() or None))
        except Exception as exc:
            print(f"[desktop] recuperação da página indisponível: {exc}", file=sys.stderr)

    window.events.loaded += on_loaded


def run_native_app(runtime: DesktopRuntime):
    import webview

    _apply_low_memory_webview_flags()
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
    if os.name == "nt":
        attach_page_crash_recovery(window, url)
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
    _cleanup_webview_caches_on_boot()
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

