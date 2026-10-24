from __future__ import annotations

import contextlib
import subprocess
import threading
import time
from typing import Any, Callable

_GPU_FREE_LOCK = threading.Lock()
_GPU_FREE_CACHE: dict[str, float] = {"at": 0.0, "free": -1.0}


def _run_hidden(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    """Executa um comando sem criar janela de console visível no Windows."""
    creationflags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags = subprocess.CREATE_NO_WINDOW
    return subprocess.run(cmd, creationflags=creationflags, **kwargs)


def gpu_free_vram_mb() -> float | None:
    """Memória livre da GPU NVIDIA (MiB) via nvidia-smi, em cache 2 s."""
    with _GPU_FREE_LOCK:
        if time.monotonic() - _GPU_FREE_CACHE["at"] < 2.0:
            value = _GPU_FREE_CACHE["free"]
            return None if value < 0 else value
    free = -1.0
    try:
        out = _run_hidden(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            free = float(out.stdout.strip().splitlines()[0])
    except Exception:
        free = -1.0
    with _GPU_FREE_LOCK:
        _GPU_FREE_CACHE.update(at=time.monotonic(), free=free)
    return None if free < 0 else free


def _log_target(target: Any, msg: str) -> None:
    """Despacha mensagem de log para callback ou atributo log do job."""
    if target is None:
        return
    if callable(target):
        try:
            target(msg)
        except Exception:
            pass
    elif hasattr(target, "log") and isinstance(getattr(target, "log"), list):
        try:
            clean = str(msg)
            if len(clean) > 1800:
                clean = clean[:1800] + " ..."
            target.log.append(clean)
            if len(target.log) > 260:
                del target.log[:80]
        except Exception:
            pass


class HardwareThermalGovernor:
    """Governador Térmico Ativo e Pacer Dinâmico de Hardware para Glide Studio.

    Monitora continuamente a temperatura da GPU/CPU durante o render.
    Quando o hardware atinge níveis térmicos elevados (>83°C em laptops), insere pausas adaptativas
    de alívio térmico (thermal breathers) entre despachos de chunks e blocos de clipes,
    evitando saturação térmica, cortes de energia pelo circuito da placa-mãe e reinícios abruptos.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_gpu_temp: float = 0.0
        self._last_gpu_util: float = 0.0
        self._last_query_time: float = 0.0
        self._cached_interval: float = 3.5
        self._total_breath_time: float = 0.0
        self._interventions_count: int = 0
        self._peak_gpu_temp: float = 0.0
        self._readings: list[float] = []

    def reset(self) -> None:
        with self._lock:
            self._total_breath_time = 0.0
            self._interventions_count = 0
            self._peak_gpu_temp = 0.0
            self._readings.clear()

    def query_gpu_telemetry(self) -> tuple[float, float]:
        now = time.monotonic()
        with self._lock:
            if (now - self._last_query_time) < self._cached_interval and self._last_gpu_temp > 0.0:
                return self._last_gpu_temp, self._last_gpu_util
        try:
            res = _run_hidden(
                ["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if res.returncode == 0 and res.stdout.strip():
                parts = [p.strip() for p in res.stdout.strip().splitlines()[0].split(",")]
                temp = float(parts[0])
                util = float(parts[1]) if len(parts) > 1 else 0.0
                with self._lock:
                    self._last_gpu_temp = temp
                    self._last_gpu_util = util
                    self._last_query_time = now
                    if temp > self._peak_gpu_temp:
                        self._peak_gpu_temp = temp
                    self._readings.append(temp)
                    if len(self._readings) > 300:
                        self._readings = self._readings[-150:]
                return temp, util
        except Exception:
            pass
        with self._lock:
            return self._last_gpu_temp, self._last_gpu_util

    def pace_before_nvenc(self, target: Any = None, completed_count: int = 0, log_callback: Any = None) -> float:
        """Pacing térmico dinâmico invocado antes de cada codificação NVENC."""
        temp, _ = self.query_gpu_telemetry()
        if temp <= 0.0:
            return 0.0

        dest = log_callback or target
        if dest is not None and completed_count == 0:
            completed_count = getattr(dest, "_completed_segments_count", 0)

        pause_sec = 0.0
        if temp >= 88.0:
            pause_sec = 2.0
            _log_target(
                dest,
                f"Governador Térmico: GPU a {temp:.1f}°C (Zona Crítica). Pausa protetora de {pause_sec:.1f}s para arrefecimento passivo.",
            )
        elif temp >= 84.0:
            pause_sec = 0.6
            if completed_count % 15 == 0:
                _log_target(
                    dest,
                    f"Governador Térmico: GPU a {temp:.1f}°C. Pacing preventivo de {pause_sec:.1f}s para dissipação contínua de calor.",
                )
        elif temp >= 80.0:
            pause_sec = 0.15

        if pause_sec > 0.0:
            with self._lock:
                self._interventions_count += 1
                self._total_breath_time += pause_sec
            time.sleep(pause_sec)
        return pause_sec

    def pace_before_chunk(self, *args: Any, **kwargs: Any) -> float:
        """Pacing entre blocos maiores de composição visual (~150s cada).

        Suporta:
          pace_before_chunk(job, chunk_idx, total_chunks)
          pace_before_chunk(chunk_idx, total_chunks, log_callback)
        """
        dest = None
        chunk_idx = 0
        total_chunks = 1

        if len(args) >= 3:
            if isinstance(args[0], int):
                chunk_idx = args[0]
                total_chunks = args[1]
                dest = args[2]
            else:
                dest = args[0]
                chunk_idx = args[1]
                total_chunks = args[2]
        elif len(args) == 2:
            chunk_idx = args[0]
            total_chunks = args[1]
        elif "chunk_idx" in kwargs:
            chunk_idx = kwargs.get("chunk_idx", 0)
            total_chunks = kwargs.get("total_chunks", 1)
            dest = kwargs.get("log_callback") or kwargs.get("job")

        temp, _ = self.query_gpu_telemetry()
        if temp <= 0.0:
            return 0.0

        pause_sec = 0.0
        if temp >= 87.0:
            pause_sec = 2.5
            _log_target(
                dest,
                f"Governador Térmico: GPU a {temp:.1f}°C antes do bloco {chunk_idx + 1}/{total_chunks}. Intervalo de arrefecimento de {pause_sec:.1f}s.",
            )
        elif temp >= 82.0:
            pause_sec = 0.8
            _log_target(
                dest,
                f"Governador Térmico: GPU a {temp:.1f}°C. Pacing preventivo de {pause_sec:.1f}s antes do bloco {chunk_idx + 1}/{total_chunks}.",
            )
        elif temp >= 78.0:
            pause_sec = 0.25

        if pause_sec > 0.0:
            with self._lock:
                self._interventions_count += 1
                self._total_breath_time += pause_sec
            time.sleep(pause_sec)
        return pause_sec

    def get_summary(self) -> dict[str, Any]:
        with self._lock:
            avg_temp = round(sum(self._readings) / max(1, len(self._readings)), 1) if self._readings else 0.0
            return {
                "peak_gpu_temp": round(self._peak_gpu_temp, 1),
                "avg_gpu_temp": avg_temp,
                "thermal_interventions": self._interventions_count,
                "total_cooldown_seconds": round(self._total_breath_time, 2),
            }


HARDWARE_THERMAL_GOVERNOR = HardwareThermalGovernor()
THERMAL_GOVERNOR = HARDWARE_THERMAL_GOVERNOR


class _NvencGate:
    """Limita sessões NVENC simultâneas de forma segura e determinística.

    Na NVIDIA RTX 3050 Laptop (4 GB VRAM) ou placas mobile/consumidor, o chip NVENC é físico
    e único. Abrir mais de 2 sessões em paralelo ou tentar alocar superfícies DirectX quando
    a VRAM está sob pressão causa falha fatal no gerenciador de memória de vídeo do Windows
    (BugCheck 0x10E VIDMM_FATAL_ERROR).
    """

    MIN_FREE_FOR_EXTRA_MB = 1200.0
    MAX_ACTIVE_SESSIONS = 1

    def __init__(self, governor: HardwareThermalGovernor | None = None) -> None:
        self._cond = threading.Condition()
        self._active = 0
        self._governor = governor or HARDWARE_THERMAL_GOVERNOR

    @property
    def active(self) -> int:
        return self._active

    def acquire(self, *args: Any, **kwargs: Any) -> None:
        """Adquire um slot NVENC garantindo concorrência segura e limite térmico.

        Suporta chamadas:
          acquire(job)
          acquire(cancel_check=..., log_callback=..., completed_count=...)
        """
        job = None
        cancel_check = kwargs.get("cancel_check")
        log_callback = kwargs.get("log_callback")
        completed_count = kwargs.get("completed_count", 0)

        if args:
            first = args[0]
            if callable(first):
                cancel_check = first
            else:
                job = first
                if hasattr(job, "cancel_requested"):
                    cancel_check = lambda: getattr(job, "cancel_requested", False)
                if not log_callback:
                    log_callback = job

        waited = False
        with self._cond:
            while True:
                if self._active == 0:
                    break
                if self._active >= self.MAX_ACTIVE_SESSIONS:
                    self._cond.wait(timeout=0.5)
                    continue
                free = gpu_free_vram_mb()
                if free is not None and free >= self.MIN_FREE_FOR_EXTRA_MB:
                    break
                if cancel_check and cancel_check():
                    raise RuntimeError("Render cancelado pelo usuario.")
                if not waited and log_callback:
                    free_str = f"{int(free)} MiB" if free is not None else "aguardando liberação"
                    _log_target(
                        log_callback,
                        f"GPU com memória sob reserva ({free_str}): aguardando liberação antes de codificar próximo clipe NVENC.",
                    )
                waited = True
                self._cond.wait(timeout=0.5)
            self._active += 1
        self._governor.pace_before_nvenc(target=job or log_callback, completed_count=completed_count)

    def release(self) -> None:
        with self._cond:
            self._active = max(0, self._active - 1)
            self._cond.notify_all()


NVENC_GATE = _NvencGate(HARDWARE_THERMAL_GOVERNOR)


def uses_nvenc(cmd: list[str]) -> bool:
    return any(str(arg).endswith("_nvenc") for arg in cmd)


@contextlib.contextmanager
def nvenc_slot(
    cancel_check: Callable[[], bool] | None = None,
    log_callback: Callable[[str], None] | None = None,
    completed_count: int = 0,
    cmd: list[str] | None = None,
):
    """Ocupa uma vaga NVENC durante o bloco, se o comando codificar na NVIDIA."""
    if cmd is not None and not uses_nvenc(cmd):
        yield
        return
    NVENC_GATE.acquire(cancel_check=cancel_check, log_callback=log_callback, completed_count=completed_count)
    try:
        yield
    finally:
        NVENC_GATE.release()
