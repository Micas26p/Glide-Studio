from __future__ import annotations

import json
import ctypes
import hashlib
import math
import os
import platform
import queue
import re
import shutil
import subprocess
import struct
import sys
import threading
import time
import uuid
import wave
import zipfile
import xml.etree.ElementTree as ET
from array import array
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from glide_config import load_config_bundle
from glide_audio_master import first_pass_filter, limiter_value, parse_loudnorm_output, second_pass_filter, summary as audio_master_report
from glide_director import (
    DIRECTOR_VERSION,
    build_energy_map,
    build_narrative_blocks,
    categories_for_text,
    categories_for_path,
    clip_number_hint,
    confidence_summary,
    direct_timeline,
    fingerprint_from_bytes,
    fold_text,
    keyword_terms,
    media_signature,
)
from glide_intelligence_db import IntelligenceDB, stable_hash
from glide_music_history import avoid_recent_music, channel_music_scores, load_music_history, record_music_usage
from glide_render_graph import RenderGraph
from glide_render_plan import build_render_plan, write_render_plan
from glide_sound_design import write_sound_design_map

APP_VERSION = "1.40.0"
RENDER_PIPELINE_VERSION = "render_graph_6_budget"
RENDER_PERFORMANCE_VERSION = "performance_7_fast_finish"

SOURCE_ROOT = Path(__file__).resolve().parent
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", SOURCE_ROOT)).resolve()
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else SOURCE_ROOT
DATA_ROOT = Path(os.environ.get("GLIDE_ULTRA_DATA_ROOT", APP_DIR)).resolve()

ROOT = SOURCE_ROOT
FRONTEND = RESOURCE_ROOT / "frontend"
ASSETS = RESOURCE_ROOT / "assets"
CONFIG_ROOT = ASSETS / "config"
UPLOAD_ROOT = DATA_ROOT / "temp_uploads"
PROJECT_MEDIA_ROOT = DATA_ROOT / "project_media"
EXPORT_ROOT = DATA_ROOT / "exports"
RENDER_ROOT = DATA_ROOT / "renders"  # legacy alias kept for compatibility
CTA_CACHE_ROOT = DATA_ROOT / "cta_cache"
MUSIC_HISTORY_FILE = DATA_ROOT / "music_history.json"
RENDER_PERFORMANCE_FILE = DATA_ROOT / "render_performance.json"
QUEUE_PROJECTS_FILE = DATA_ROOT / "queue_projects.json"
APP_SETTINGS_FILE = DATA_ROOT / "app_settings.json"
DROPZONE_ROOT = DATA_ROOT / "DROPZONE"
DROPZONE_OUTPUT_ROOT = DATA_ROOT / "OUTPUT"
VISUAL_CLEAN_CACHE_FILE = DATA_ROOT / "visual_clean_cache.json"
INTELLIGENCE_DB_FILE = DATA_ROOT / "glide_intelligence.sqlite3"
RENDER_GRAPH_CACHE_ROOT = DATA_ROOT / "render_graph_cache"
MODEL_PACK_ROOT = DATA_ROOT / "model_packs" / "mobileclip"
REFERENCE_STYLE_ROOT = DATA_ROOT / "reference_styles"
AUTOMATOR_STAGING_ROOT = UPLOAD_ROOT / "automator_sessions"
YUNET_MODEL_PATH = ASSETS / "models" / "face_detection_yunet_2023mar.onnx"

VISUAL_LANGUAGE_PACKAGES: dict[str, dict[str, Any]] = {
    "dark_doc": {
        "label": "Documentario sombrio",
        "cut_rhythm": "medium_slow",
        "text_animation": "documentary",
        "transition_family": "soft_cut_rise",
        "fx_density": 0.42,
        "music_behavior": "low_tension_ducked",
        "image_motion": "slow_zoom_focus",
        "intensity": 0.62,
    },
    "modern_explainer": {
        "label": "Explicativo moderno",
        "cut_rhythm": "medium",
        "text_animation": "clean_slide",
        "transition_family": "soft_swipe",
        "fx_density": 0.36,
        "music_behavior": "light_pulse",
        "image_motion": "parallax_cards",
        "intensity": 0.54,
    },
    "dramatic_history": {
        "label": "Historia dramatica",
        "cut_rhythm": "dynamic_slow",
        "text_animation": "archive_reveal",
        "transition_family": "fade_impact",
        "fx_density": 0.45,
        "music_behavior": "cinematic_rises",
        "image_motion": "documentary_scan",
        "intensity": 0.66,
    },
    "tech_cyber": {
        "label": "Tech/cyber",
        "cut_rhythm": "fast_precise",
        "text_animation": "digital_glitch",
        "transition_family": "glitch_cut",
        "fx_density": 0.50,
        "music_behavior": "electronic_ducked",
        "image_motion": "hud_scan",
        "intensity": 0.72,
    },
    "finance": {
        "label": "Financeiro",
        "cut_rhythm": "medium_fast",
        "text_animation": "number_counter",
        "transition_family": "cash_swipe_cut",
        "fx_density": 0.44,
        "music_behavior": "confident_pulse",
        "image_motion": "data_focus",
        "intensity": 0.58,
    },
}

SAFE_STARTUP_LOG_PATTERNS = (
    "build_*.log",
    "smoke_*.log",
    "desktop_smoke*.json",
    "desktop_smoke*.log",
    "desktop_smoke*.trace.log",
    "qa_server*.log",
    "*.err.log",
    "*.out.log",
    "*.trace.log",
)
SAFE_SHUTDOWN_LOG_PATTERNS = (
    "build_*.log",
    "smoke_*.log",
    "desktop_smoke*.log",
    "desktop_smoke*.trace.log",
    "qa_server*.log",
    "*.err.log",
    "*.out.log",
    "*.trace.log",
)
SAFE_STARTUP_DIR_NAMES = {
    ".verification-artifacts",
    ".pytest_cache",
}
SAFE_AGED_DIR_POLICIES = {
    "__pycache__": 12 * 60 * 60,
    "build": 24 * 60 * 60,
}
SAFE_OLD_PROFILE_DIR_NAMES = {
    "webview_profile",
    "browser_app_profile",
}
SAFE_TEMP_SUFFIXES = {
    ".tmp",
    ".part",
}
SAFE_TEMP_FILE_ROOT_NAMES = {
    "temp_uploads",
    "cta_cache",
    "render_graph_cache",
}
SAFE_SHUTDOWN_EMPTY_ROOT_NAMES = {
    "temp_uploads",
    "renders",
    "cta_cache",
}
SAFE_SHUTDOWN_REMOVE_DIR_NAMES = {
    ".verification-artifacts",
    ".pytest_cache",
    "__pycache__",
    "build",
}
for folder in (
    UPLOAD_ROOT,
    PROJECT_MEDIA_ROOT,
    EXPORT_ROOT,
    RENDER_ROOT,
    CTA_CACHE_ROOT,
    RENDER_GRAPH_CACHE_ROOT,
    MODEL_PACK_ROOT,
    AUTOMATOR_STAGING_ROOT,
    DROPZONE_ROOT,
    DROPZONE_OUTPUT_ROOT,
):
    folder.mkdir(parents=True, exist_ok=True)

INTELLIGENCE_DB = IntelligenceDB(INTELLIGENCE_DB_FILE)
MEDIA_INDEX_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="glide-media-index")
AUTOMATOR_SESSION_LOCK = threading.RLock()
AUTOMATOR_SESSIONS: dict[str, dict[str, Any]] = {}
AUTOMATOR_SESSION_TTL_SECONDS = 4 * 60 * 60


def _maintenance_safe_child(path: Path) -> Path | None:
    try:
        resolved = path.resolve()
        root = DATA_ROOT.resolve()
    except Exception:
        return None
    if resolved == root or root not in resolved.parents:
        return None
    protected_roots = {
        PROJECT_MEDIA_ROOT.resolve(),
        EXPORT_ROOT.resolve(),
        DROPZONE_ROOT.resolve(),
        DROPZONE_OUTPUT_ROOT.resolve(),
        ASSETS.resolve(),
        FRONTEND.resolve(),
        MODEL_PACK_ROOT.parent.resolve(),
    }
    if any(resolved == item or item in resolved.parents for item in protected_roots):
        return None
    return resolved


def _maintenance_path_size(path: Path) -> int:
    total = 0
    try:
        if path.is_file():
            return int(path.stat().st_size)
        for item in path.rglob("*"):
            if item.is_file():
                total += int(item.stat().st_size)
    except Exception:
        pass
    return total


def _maintenance_human_bytes(size: int | float) -> str:
    value = float(size or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} TB"


def _remove_maintenance_item(path: Path, summary: dict[str, Any], bucket: str) -> None:
    resolved = _maintenance_safe_child(path)
    if not resolved or not resolved.exists():
        return
    try:
        recovered = _maintenance_path_size(resolved)
        if resolved.is_dir():
            shutil.rmtree(resolved, ignore_errors=False)
        else:
            resolved.unlink(missing_ok=True)
        summary["removed"][bucket] = int(summary["removed"].get(bucket, 0)) + 1
        summary["bytes_recovered"] = int(summary.get("bytes_recovered", 0)) + recovered
    except Exception as exc:
        errors = summary.setdefault("errors", [])
        if isinstance(errors, list) and len(errors) < 12:
            errors.append(f"{resolved.name}: {exc}")


def _cleanup_temp_files_inside(root: Path, cutoff: float, summary: dict[str, Any]) -> None:
    resolved_root = _maintenance_safe_child(root)
    if not resolved_root or not resolved_root.exists() or not resolved_root.is_dir():
        return
    if resolved_root.name not in SAFE_TEMP_FILE_ROOT_NAMES:
        return
    try:
        for path in resolved_root.rglob("*"):
            try:
                if (
                    path.is_file()
                    and path.suffix.lower() in SAFE_TEMP_SUFFIXES
                    and path.stat().st_mtime < cutoff
                ):
                    _remove_maintenance_item(path, summary, "temp_files")
            except Exception:
                continue
    except Exception as exc:
        errors = summary.setdefault("errors", [])
        if isinstance(errors, list) and len(errors) < 12:
            errors.append(f"{resolved_root.name}: {exc}")


def safe_startup_cleanup() -> dict[str, Any]:
    """Remove only whitelisted generated artifacts. Never delete projects, media or exports."""
    summary: dict[str, Any] = {
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "removed": {
            "render_graph_cache": 0,
            "safe_dirs": 0,
            "old_profiles": 0,
            "old_uploads": 0,
            "automator_sessions": 0,
            "logs": 0,
            "temp_files": 0,
        },
        "bytes_recovered": 0,
        "errors": [],
    }
    try:
        graph = RenderGraph(
            db=INTELLIGENCE_DB,
            cache_root=RENDER_GRAPH_CACHE_ROOT,
            job_id="startup-maintenance",
            project_id="",
        )
        cleanup = graph.cleanup(force=False)
        removed = int(cleanup.get("removed") or 0)
        reclaimed = int(cleanup.get("reclaimed_bytes") or 0)
        summary["removed"]["render_graph_cache"] = removed
        summary["bytes_recovered"] = int(summary.get("bytes_recovered", 0)) + reclaimed
    except Exception as exc:
        summary["errors"].append(f"render_graph_cache: {exc}")

    for name in SAFE_STARTUP_DIR_NAMES:
        _remove_maintenance_item(DATA_ROOT / name, summary, "safe_dirs")
    for name, min_age_seconds in SAFE_AGED_DIR_POLICIES.items():
        folder = DATA_ROOT / name
        try:
            if folder.exists() and folder.stat().st_mtime < time.time() - float(min_age_seconds):
                _remove_maintenance_item(folder, summary, "safe_dirs")
        except Exception:
            pass

    profile_cutoff = time.time() - 7 * 24 * 60 * 60
    for name in SAFE_OLD_PROFILE_DIR_NAMES:
        folder = DATA_ROOT / name
        try:
            if folder.exists() and folder.stat().st_mtime < profile_cutoff:
                _remove_maintenance_item(folder, summary, "old_profiles")
        except Exception:
            pass

    upload_cutoff = time.time() - 48 * 60 * 60
    try:
        UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
        for folder in UPLOAD_ROOT.iterdir():
            if folder.is_dir() and folder.stat().st_mtime < upload_cutoff:
                _remove_maintenance_item(folder, summary, "old_uploads")
    except Exception as exc:
        summary["errors"].append(f"temp_uploads: {exc}")

    automator_cutoff = time.time() - AUTOMATOR_SESSION_TTL_SECONDS
    try:
        for folder in AUTOMATOR_STAGING_ROOT.iterdir():
            if folder.is_dir() and folder.stat().st_mtime < automator_cutoff:
                _remove_maintenance_item(folder, summary, "automator_sessions")
    except Exception as exc:
        summary["errors"].append(f"automator_sessions: {exc}")

    log_cutoff = time.time() - 12 * 60 * 60
    for pattern in SAFE_STARTUP_LOG_PATTERNS:
        try:
            for path in DATA_ROOT.glob(pattern):
                if path.is_file() and path.stat().st_mtime < log_cutoff:
                    _remove_maintenance_item(path, summary, "logs")
        except Exception:
            continue

    temp_cutoff = time.time() - 6 * 60 * 60
    for path in DATA_ROOT.glob(".*.tmp"):
        try:
            if path.is_file() and path.suffix.lower() in SAFE_TEMP_SUFFIXES and path.stat().st_mtime < temp_cutoff:
                _remove_maintenance_item(path, summary, "temp_files")
        except Exception:
            continue
    for root in (UPLOAD_ROOT, CTA_CACHE_ROOT, RENDER_GRAPH_CACHE_ROOT):
        _cleanup_temp_files_inside(root, temp_cutoff, summary)
    summary["space_recovered"] = _maintenance_human_bytes(int(summary.get("bytes_recovered") or 0))
    return summary


def _empty_maintenance_root(root: Path, summary: dict[str, Any], bucket: str) -> None:
    resolved_root = _maintenance_safe_child(root)
    if not resolved_root or resolved_root.name not in SAFE_SHUTDOWN_EMPTY_ROOT_NAMES:
        return
    resolved_root.mkdir(parents=True, exist_ok=True)
    try:
        for child in list(resolved_root.iterdir()):
            _remove_maintenance_item(child, summary, bucket)
    except Exception as exc:
        errors = summary.setdefault("errors", [])
        if isinstance(errors, list) and len(errors) < 12:
            errors.append(f"{resolved_root.name}: {exc}")


def safe_shutdown_cleanup() -> dict[str, Any]:
    """Clear disposable runtime data while preserving projects, exports and useful analysis caches."""
    summary: dict[str, Any] = {
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "removed": {
            "active_jobs": 0,
            "runtime_items": 0,
            "generated_caches": 0,
            "build_artifacts": 0,
            "logs": 0,
            "temp_files": 0,
        },
        "bytes_recovered": 0,
        "errors": [],
    }

    # Closing the desktop app is an explicit stop. Terminate FFmpeg first so no
    # process keeps temporary segments locked while cleanup runs.
    for job in list(JOBS.values()):
        if str(getattr(job, "status", "")) not in {"created", "uploading", "ready", "running", "paused"}:
            continue
        try:
            job.cancel_requested = True
            job.cancelled_at = time.time()
            _terminate_job_processes(job)
            job.status = "cancelled"
            summary["removed"]["active_jobs"] += 1
        except Exception as exc:
            if len(summary["errors"]) < 12:
                summary["errors"].append(f"job {getattr(job, 'id', '')}: {exc}")

    for root in (UPLOAD_ROOT, RENDER_ROOT):
        _empty_maintenance_root(root, summary, "runtime_items")
    _empty_maintenance_root(CTA_CACHE_ROOT, summary, "generated_caches")

    for name in SAFE_SHUTDOWN_REMOVE_DIR_NAMES:
        _remove_maintenance_item(DATA_ROOT / name, summary, "build_artifacts")

    for pattern in SAFE_SHUTDOWN_LOG_PATTERNS:
        try:
            for path in DATA_ROOT.glob(pattern):
                if path.is_file():
                    _remove_maintenance_item(path, summary, "logs")
        except Exception:
            continue

    for path in DATA_ROOT.glob(".*.tmp"):
        if path.is_file() and path.suffix.lower() in SAFE_TEMP_SUFFIXES:
            _remove_maintenance_item(path, summary, "temp_files")
    for root in (UPLOAD_ROOT, CTA_CACHE_ROOT, RENDER_GRAPH_CACHE_ROOT):
        _cleanup_temp_files_inside(root, float("inf"), summary)

    summary["space_recovered"] = _maintenance_human_bytes(int(summary.get("bytes_recovered") or 0))
    summary["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    return summary


STARTUP_CLEANUP_SUMMARY: dict[str, Any] = {}


def startup_maintenance_worker() -> None:
    global STARTUP_CLEANUP_SUMMARY
    STARTUP_CLEANUP_SUMMARY = safe_startup_cleanup()


threading.Thread(target=startup_maintenance_worker, daemon=True, name="glide-startup-maintenance").start()


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(text, encoding=encoding)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mts", ".m2ts"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".webm"}
SRT_EXTS = {".srt"}
SCRIPT_GUIDE_EXTS = {".txt", ".docx", ".pdf", ".html", ".htm"}
MIN_SUBTITLE_SECONDS = 0.65
MIN_VIDEO_SPEED = 0.80

CTA_SOURCE_DIR = ASSETS / "cta" / "source"
SFX_SOURCE_DIR = ASSETS / "sfx"
SFX_SOURCE_DIRS = (
    SFX_SOURCE_DIR,
    APP_DIR / "assets" / "sfx",
    DATA_ROOT / "sfx",
    Path.home() / "Music" / "Efeitos de video",
    Path.home() / "Music" / "Efeitos de vídeo",
)
SFX_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}
SFX_INDEX_LOCK = threading.Lock()
SFX_ASSET_CACHE: list[Path] | None = None
SFX_DURATION_CACHE: dict[str, float] = {}
SFX_TIMING_CACHE: dict[str, dict[str, float]] = {}
SFX_RENDER_PROFILE_CACHE: dict[str, dict[str, float]] = {}
CACHE_MAINTENANCE_LOCK = threading.Lock()
CACHE_WARM_LOCK = threading.Lock()
VIDEO_HEALTH_CACHE: dict[str, dict[str, Any]] = {}


def is_image_path(path: Path | str) -> bool:
    return Path(str(path)).suffix.lower() in IMAGE_EXTS


def is_video_path(path: Path | str) -> bool:
    return Path(str(path)).suffix.lower() in VIDEO_EXTS


def image_duration_default(options: dict[str, Any] | None = None) -> float:
    options = options or {}
    try:
        value = float(options.get("imageDefaultDurationSeconds") or 4.0)
    except Exception:
        value = 4.0
    return max(2.5, min(8.0, value))


IMAGE_MOTIONS = ("zoom_in", "pan_right", "zoom_out", "pan_left")


def probe_image_dimensions(path: Path | str) -> tuple[int, int]:
    """Obtém largura e altura da imagem de forma ultrarrápida (PIL com fallback FFprobe)."""
    try:
        from PIL import Image
        with Image.open(str(path)) as img:
            return int(img.width), int(img.height)
    except Exception:
        pass
    try:
        cmd = [
            FFPROBE, "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0",
            str(path)
        ]
        out = subprocess.check_output(cmd, timeout=3.0, stderr=subprocess.DEVNULL).decode().strip()
        parts = out.split("x")
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
    except Exception:
        pass
    return 1920, 1080


IMAGE_FOCAL_CACHE: dict[str, tuple[float, float]] = {}


def probe_image_focal_anchor(path: Path | str | None, cwd: Path | None = None) -> tuple[float, float]:
    """Calcula o centróide ponderado de energia visual e contraste em <1.5ms para guiar o Ken Burns."""
    default_focal = (0.50, 0.38)
    if not path:
        return default_focal
    resolved = _resolved_media_path(path, cwd)
    if not resolved.exists():
        return default_focal

    try:
        st = resolved.stat()
        cache_key = f"{resolved.name}:{st.st_size}:{int(st.st_mtime)}"
    except Exception:
        cache_key = str(resolved)

    cached = IMAGE_FOCAL_CACHE.get(cache_key)
    if cached is not None:
        return cached

    try:
        from PIL import Image, ImageFilter
        with Image.open(resolved) as img:
            # Thumbnail ultrarrápido em escala de cinza
            small = img.convert("L").resize((120, 80), Image.Resampling.BILINEAR)
            edges = small.filter(ImageFilter.FIND_EDGES)
            pixels = list(edges.getdata())
            w, h = small.size

            total_weight = 0.0
            weighted_x = 0.0
            weighted_y = 0.0

            threshold = 35.0
            for idx, val in enumerate(pixels):
                if val > threshold:
                    x = idx % w
                    y = idx // w
                    weight = float(val)
                    total_weight += weight
                    weighted_x += x * weight
                    weighted_y += y * weight

            if total_weight > 100.0:
                raw_cx = (weighted_x / total_weight) / float(w)
                raw_cy = (weighted_y / total_weight) / float(h)
                safe_cx = max(0.28, min(0.72, round(raw_cx, 3)))
                safe_cy = max(0.25, min(0.60, round(raw_cy, 3)))
                result = (safe_cx, safe_cy)
            else:
                result = default_focal
    except Exception:
        result = default_focal

    IMAGE_FOCAL_CACHE[cache_key] = result
    return result


def image_motion_for(path: Path | str, index: int = 0) -> str:
    """Retorna um dos 4 movimentos cinematográficos suaves sem repetições consecutivas."""
    return IMAGE_MOTIONS[index % len(IMAGE_MOTIONS)]
VISUAL_CLEAN_CACHE_VERSION = 9
VISUAL_CLEAN_CACHE_LOCK = threading.RLock()
VISUAL_CLEAN_CACHE: dict[str, dict[str, Any]] = {}
VIDEO_TINY_FILE_MB = 0.22
VIDEO_BLACK_YAVG_MAX = 12.0
VIDEO_BLACK_YMAX_MAX = 28.0
VIDEO_VISIBLE_RANGE_MIN = 7.0
VISUAL_CLEAN_FRAME_W = 96
VISUAL_CLEAN_FRAME_H = 54
VISUAL_CLEAN_SAMPLE_COUNT = 3
YUNET_FRAME_W = 320
YUNET_FRAME_H = 180
YUNET_LOCK = threading.RLock()
YUNET_DETECTOR: Any | None = None
YUNET_RUNTIME_ERROR = ""
SUBTITLE_ANIMATIONS = {
    "mixed", "pop", "spring", "kinetic", "blur_rise", "slide", "zoom", "fade", "cinematic", "pulse", "glitch", "typewriter", "shake", "none",
    "random_text", "documentary", "archive", "digital", "stamp", "money", "warning", "industrial", "luxury",
}
SUBTITLE_SFX_POOLS: dict[str, list[str]] = {
    "fade": ["subtitle_shimmer", "subtitle_air", "subtitle_luxury_doc"],
    "pop": ["subtitle_bullet_pop", "subtitle_title_slam", "subtitle_hit"],
    "spring": ["subtitle_bullet_pop", "subtitle_hit", "subtitle_pulse"],
    "kinetic": ["subtitle_swipe", "subtitle_air", "subtitle_click"],
    "blur_rise": ["subtitle_luxury_doc", "subtitle_air", "subtitle_shimmer"],
    "slide": ["subtitle_swipe", "subtitle_whoosh"],
    "zoom": ["subtitle_zoom", "subtitle_air"],
    "cinematic": ["subtitle_luxury_doc", "subtitle_shimmer", "subtitle_air"],
    "pulse": ["subtitle_pulse", "subtitle_shimmer"],
    "glitch": ["subtitle_glitch_reveal", "subtitle_glitch"],
    "typewriter": ["subtitle_type_classic", "subtitle_type", "subtitle_click"],
    "shake": ["subtitle_shake", "subtitle_hit"],
    "random_text": ["subtitle_air", "subtitle_swipe", "subtitle_zoom", "subtitle_title_slam", "subtitle_archive_caption", "subtitle_glitch_reveal"],
    "documentary": ["subtitle_luxury_doc", "subtitle_archive_caption", "subtitle_shimmer"],
    "archive": ["subtitle_archive_caption", "subtitle_click"],
    "digital": ["subtitle_digital_typing", "subtitle_data_scan", "subtitle_glitch_reveal"],
    "stamp": ["subtitle_stamp", "subtitle_hit"],
    "money": ["subtitle_money_counter", "subtitle_click"],
    "warning": ["subtitle_warning_alert", "subtitle_hit"],
    "industrial": ["subtitle_industrial_metal", "subtitle_hit"],
    "luxury": ["subtitle_luxury_doc", "subtitle_shimmer"],
    "mixed": ["subtitle_bullet_pop", "subtitle_air", "subtitle_swipe", "subtitle_zoom", "subtitle_shimmer", "subtitle_luxury_doc"],
    "none": [],
}
SUBTITLE_VARIANT_SFX: dict[str, tuple[str, float, float, str]] = {
    "fade": ("subtitle_shimmer", 0.000, 0.00, "inicio"),
    "rise": ("subtitle_air", 0.000, -0.05, "inicio"),
    "blur_rise": ("subtitle_luxury_doc", 0.000, 0.00, "inicio"),
    "spring": ("subtitle_bullet_pop", 0.000, 0.12, "inicio"),
    "kinetic": ("subtitle_swipe", 0.000, 0.10, "inicio"),
    "slide_left": ("subtitle_swipe", 0.000, 0.08, "inicio"),
    "slide_right": ("subtitle_swipe", 0.000, 0.08, "inicio"),
    "pop": ("subtitle_bullet_pop", 0.000, 0.12, "inicio"),
    "pop_soft": ("subtitle_bullet_pop", 0.000, 0.05, "inicio"),
    "zoom_in": ("subtitle_zoom", 0.000, 0.06, "inicio"),
    "zoom_soft": ("subtitle_zoom", 0.000, 0.00, "inicio"),
    "cinema_drop": ("subtitle_luxury_doc", 0.000, 0.00, "inicio"),
    "pulse_in": ("subtitle_pulse", 0.000, 0.08, "inicio"),
    "glitch": ("subtitle_glitch_reveal", 0.000, 0.12, "inicio"),
    "typewriter": ("subtitle_type_classic", 0.000, 0.02, "inicio"),
    "shake": ("subtitle_shake", 0.000, 0.10, "inicio"),
}
TRANSITION_SFX_POOLS: dict[str, list[str]] = {
    "fade": ["transition_air", "transition_whoosh"],
    "random": ["transition_whoosh", "transition_swipe", "transition_archive", "transition_digital_glitch", "transition_flash", "transition_map"],
    "random_soft": ["transition_air", "transition_swipe", "transition_whoosh"],
    "random_cinematic": ["transition_whoosh", "transition_sweep", "transition_bass_hit", "transition_air"],
    "random_documentary": ["transition_archive", "transition_documentary", "transition_map", "transition_air"],
    "random_glitch": ["transition_digital_glitch", "transition_vhs", "transition_flash", "transition_futuristic"],
    "random_industrial": ["transition_industrial", "transition_mechanical", "transition_bass_hit"],
    "random_fast": ["transition_swipe", "transition_flash", "transition_whoosh"],
    "whoosh": ["transition_whoosh", "transition_sweep"],
    "swipe": ["transition_swipe", "transition_whoosh"],
    "smoothleft": ["transition_swipe", "transition_air"],
    "wiperight": ["transition_swipe", "transition_whoosh"],
    "flash": ["transition_flash"],
    "archive": ["transition_archive"],
    "vhs": ["transition_vhs"],
    "digital_glitch": ["transition_digital_glitch", "transition_futuristic"],
    "mechanical": ["transition_mechanical", "transition_industrial"],
    "money": ["transition_money"],
    "map": ["transition_map"],
    "futuristic": ["transition_futuristic", "transition_digital_glitch"],
    "bass_hit": ["transition_bass_hit"],
    "glass": ["transition_glass"],
    "industrial": ["transition_industrial", "transition_mechanical"],
}
SFX_EFFECT_SPECS: dict[str, dict[str, Any]] = {
    "subtitle_air": {"duration": 0.36, "volume_db": -10.2, "anchor": "inicio"},
    "subtitle_shimmer": {"duration": 0.42, "volume_db": -10.0, "anchor": "inicio"},
    "subtitle_swipe": {"duration": 0.32, "volume_db": -16.8, "anchor": "inicio"},
    "subtitle_whoosh": {"duration": 0.32, "volume_db": -9.9, "anchor": "inicio"},
    "subtitle_zoom": {"duration": 0.36, "volume_db": -9.8, "anchor": "inicio"},
    "subtitle_hit": {"duration": 0.22, "volume_db": -8.7, "anchor": "pico"},
    "subtitle_click": {"duration": 0.12, "volume_db": -10.4, "anchor": "inicio"},
    "subtitle_pulse": {"duration": 0.28, "volume_db": -9.4, "anchor": "pico"},
    "subtitle_glitch": {"duration": 0.24, "volume_db": -9.1, "anchor": "inicio"},
    "subtitle_type": {"duration": 0.34, "volume_db": -10.4, "anchor": "inicio"},
    "subtitle_shake": {"duration": 0.24, "volume_db": -8.9, "anchor": "pico"},
    "subtitle_type_classic": {"duration": 0.34, "volume_db": -10.2, "anchor": "inicio"},
    "subtitle_digital_typing": {"duration": 0.30, "volume_db": -9.8, "anchor": "inicio"},
    "subtitle_money_counter": {"duration": 0.36, "volume_db": -9.6, "anchor": "inicio"},
    "subtitle_title_slam": {"duration": 0.24, "volume_db": -8.3, "anchor": "pico"},
    "subtitle_glitch_reveal": {"duration": 0.26, "volume_db": -9.0, "anchor": "inicio"},
    "subtitle_stamp": {"duration": 0.24, "volume_db": -8.6, "anchor": "pico"},
    "subtitle_archive_caption": {"duration": 0.38, "volume_db": -10.1, "anchor": "inicio"},
    "subtitle_warning_alert": {"duration": 0.26, "volume_db": -8.7, "anchor": "pico"},
    "subtitle_industrial_metal": {"duration": 0.32, "volume_db": -9.0, "anchor": "pico"},
    "subtitle_luxury_doc": {"duration": 0.42, "volume_db": -10.4, "anchor": "inicio"},
    "subtitle_bullet_pop": {"duration": 0.18, "volume_db": -9.0, "anchor": "pico"},
    "subtitle_data_scan": {"duration": 0.30, "volume_db": -9.8, "anchor": "inicio"},
    "transition_air": {"duration": 0.34, "volume_db": -12.2, "anchor": "inicio"},
    "transition_whoosh": {"duration": 0.46, "volume_db": -11.7, "anchor": "pico"},
    "transition_sweep": {"duration": 0.50, "volume_db": -11.8, "anchor": "pico"},
    "transition_swipe": {"duration": 0.34, "volume_db": -11.6, "anchor": "inicio"},
    "transition_flash": {"duration": 0.24, "volume_db": -12.0, "anchor": "pico"},
    "transition_archive": {"duration": 0.34, "volume_db": -12.0, "anchor": "inicio"},
    "transition_documentary": {"duration": 0.44, "volume_db": -12.3, "anchor": "inicio"},
    "transition_vhs": {"duration": 0.30, "volume_db": -12.1, "anchor": "pico"},
    "transition_digital_glitch": {"duration": 0.26, "volume_db": -11.8, "anchor": "pico"},
    "transition_mechanical": {"duration": 0.42, "volume_db": -11.6, "anchor": "pico"},
    "transition_industrial": {"duration": 0.42, "volume_db": -11.5, "anchor": "pico"},
    "transition_money": {"duration": 0.30, "volume_db": -11.9, "anchor": "inicio"},
    "transition_map": {"duration": 0.32, "volume_db": -12.2, "anchor": "inicio"},
    "transition_futuristic": {"duration": 0.36, "volume_db": -11.9, "anchor": "inicio"},
    "transition_bass_hit": {"duration": 0.36, "volume_db": -11.3, "anchor": "pico"},
    "transition_glass": {"duration": 0.28, "volume_db": -12.0, "anchor": "pico"},
    "transition_suspense": {"duration": 0.62, "volume_db": -12.3, "anchor": "cauda", "suspense_only": True},
    "image_soft_in": {"duration": 0.34, "volume_db": -12.0, "anchor": "inicio"},
    "image_parallax_peak": {"duration": 0.38, "volume_db": -12.3, "anchor": "pico"},
    "graphic_arrow_draw": {"duration": 0.26, "volume_db": -11.5, "anchor": "inicio"},
    "graphic_highlight_pulse": {"duration": 0.22, "volume_db": -10.9, "anchor": "pico"},
    "data_counter_tick": {"duration": 0.30, "volume_db": -11.1, "anchor": "inicio"},
    "cut_soft_tick": {"duration": 0.14, "volume_db": -13.4, "anchor": "pico"},
    "camera_zoom_breath": {"duration": 0.34, "volume_db": -12.2, "anchor": "pico"},
}
MUSIC_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
PRESET_MUSIC_GENRES = {
    "cinematic": {
        "label": "Cinematic",
        "dirs": (
            ASSETS / "music" / "cinematic",
            APP_DIR / "assets" / "music" / "cinematic",
            Path.home() / "Music" / "Cinematic",
        ),
    },
    "ambient": {
        "label": "Ambiente",
        "dirs": (
            ASSETS / "music" / "ambient",
            APP_DIR / "assets" / "music" / "ambient",
            Path.home() / "Music" / "Ambient",
            Path.home() / "Music" / "Ambiente",
        ),
        "files": (
            Path.home() / "Music" / "Yt music 1.MP3",
            Path.home() / "Music" / "Yt music 2.MP3",
            Path.home() / "Music" / "Yt music 3.MP3",
        ),
    },
}
PRESET_MUSIC_MAX_FILES = 72
PRESET_MUSIC_SPLIT_AFTER = 600.0
PRESET_MUSIC_PART_SECONDS = 300.0
PRESET_MUSIC_SAMPLE_LIMIT = 8
try:
    (DATA_ROOT / "sfx").mkdir(parents=True, exist_ok=True)
except Exception:
    pass
CTA_LANGUAGES: dict[str, dict[str, Any]] = {
    "pt": {"label": "Português", "source": "cta_portugues.mp4", "kind": "chroma", "text": "INSCREVA-SE"},
    "en": {"label": "English", "source": "cta_english.mov", "kind": "chroma", "text": "SUBSCRIBE"},
    "es": {"label": "Español", "source": "cta_espanol.mov", "kind": "chroma", "text": "SUSCRIBETE"},
    "fr": {"label": "Français", "source": "cta_francais.mov", "kind": "chroma", "text": "ABONNEZ-VOUS"},
    "ru": {"label": "Russkiy", "source": "cta_russian.mp4", "kind": "chroma", "text": "PODPISHITES"},
    "de": {"label": "Deutsch", "source": "cta_german.mp4", "kind": "chroma", "text": "ABONNIEREN", "remove_top_text": 0.38},
    "it": {"label": "Italiano", "source": "cta_italiano.mp4", "kind": "chroma", "text": "ISCRIVITI"},
    "pl": {"label": "Polski", "source": "cta_polski.mp4", "kind": "chroma", "text": "SUBSKRYBUJ"},
}
CTA_REQUIRED = True
CTA_OCCURRENCES = 2
INTRO_DURATION_DEFAULT = 4.0
INTRO_MUSIC_DB_DEFAULT = -20.0
AUTO_SFX_MIN_DB = -16.0
AUTO_SFX_MAX_DB = -5.8
AUTO_SFX_DEFAULT_DB = -10.0
PROJECT_TONES = {"auto", "suspense", "emotional", "explanatory", "energetic", "historical", "tech"}
DYNAMIC_PAUSE_MAX_COUNT = 8
DYNAMIC_PAUSE_MAX_RATIO = 0.04
CTA_POSITION_PRESETS = {
    "top_left": {"x": "W*0.04", "y": "H*0.06"},
    "top_center": {"x": "(W-w)/2", "y": "H*0.06"},
    "top_right": {"x": "W-w-W*0.04", "y": "H*0.06"},
    "middle_left": {"x": "W*0.04", "y": "(H-h)/2"},
    "center": {"x": "(W-w)/2", "y": "(H-h)/2"},
    "middle_right": {"x": "W-w-W*0.04", "y": "(H-h)/2"},
    "bottom_left": {"x": "W*0.04", "y": "H-h-H*0.08"},
    "bottom_center": {"x": "(W-w)/2", "y": "H-h-H*0.08"},
    "bottom_right": {"x": "W-w-W*0.04", "y": "H-h-H*0.08"},
}

app = FastAPI(title="Glide Studio", version=APP_VERSION)

@app.middleware("http")
async def no_cache_middleware(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    elif path.startswith("/static/") or path.startswith("/assets/") or path == "/favicon.ico":
        response.headers["Cache-Control"] = "public, max-age=86400, immutable"
    else:
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response

app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")
app.mount("/assets", StaticFiles(directory=str(ASSETS)), name="assets")


def natural_key(text: str):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", text)]


def safe_name(name: str) -> str:
    name = name.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^a-zA-Z0-9._()\-\s]", "_", name).strip()
    return name or f"file_{uuid.uuid4().hex}"


def safe_video_basename(name: str) -> str:
    raw = (name or "").replace("\\", "/").split("/")[-1]
    raw = re.sub(r"\.[mM][pP]4$", "", raw).strip()
    raw = re.sub(r"[^a-zA-Z0-9._()\-\s]", "_", raw)
    raw = re.sub(r"\s+", " ", raw).strip(" ._-")
    reserved = {
        "con", "prn", "aux", "nul",
        "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
        "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
    }
    if not raw or raw.lower() in reserved:
        return ""
    return raw[:90].strip(" ._-")


def next_numeric_output_name(search_folder: Path | None = None) -> str:
    highest = 0
    folders = [search_folder] if search_folder else []
    folders.append(EXPORT_ROOT)
    try:
        for folder in folders:
            if not folder:
                continue
            for path in (folder.rglob("*.mp4") if folder.exists() else []):
                if path.stem.isdigit():
                    highest = max(highest, int(path.stem))
    except Exception:
        pass
    return f"{highest + 1:03d}.mp4"


def output_name_from_options(options: dict[str, Any]) -> str:
    custom = safe_video_basename(str(options.get("outputName") or ""))
    search_folder = None
    try:
        _, folder = final_output_folder_from_options(options)
        search_folder = folder
    except Exception:
        search_folder = None
    name = f"{custom}.mp4" if custom else next_numeric_output_name(search_folder)
    if bool(options.get("sampleRender")):
        stem = Path(name).stem or "amostra"
        return f"{stem}_amostra.mp4"
    return name


def safe_folder_component(value: str, fallback: str = "project") -> str:
    raw = safe_video_basename(value)
    if not raw:
        raw = fallback
    return raw[:72].strip(" ._-") or fallback


def human_bytes(size: int | float) -> str:
    value = float(max(0, size))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} GB"


def path_size(path: Path) -> int:
    try:
        if path.is_file():
            return path.stat().st_size
        total = 0
        for item in path.rglob("*"):
            try:
                if item.is_file():
                    total += item.stat().st_size
            except Exception:
                pass
        return total
    except Exception:
        return 0


def default_downloads_dir() -> Path:
    base = Path(os.environ.get("USERPROFILE") or str(Path.home()))
    downloads = base / "Downloads"
    return downloads if downloads.exists() or base.exists() else Path.home()


def unique_output_path(folder: Path, filename: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    safe_filename = safe_name(filename or "video.mp4")
    if not safe_filename.lower().endswith(".mp4"):
        safe_filename += ".mp4"
    target = folder / safe_filename
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    for index in range(2, 10000):
        candidate = folder / f"{stem}_{index:02d}{suffix}"
        if not candidate.exists():
            return candidate
    return folder / f"{stem}_{uuid.uuid4().hex[:6]}{suffix}"


def final_output_folder_from_options(options: dict[str, Any]) -> tuple[str, Path | None]:
    mode = str(options.get("finalOutputMode") or "downloads").strip().lower()
    if mode not in {"downloads", "custom", "browser_download"}:
        mode = "downloads"
    if mode == "browser_download":
        return mode, None
    if mode == "custom":
        raw = str(options.get("finalOutputFolder") or "").strip()
        if not raw:
            return "downloads", default_downloads_dir()
        folder = Path(os.path.expandvars(os.path.expanduser(raw)))
        return mode, folder
    return mode, default_downloads_dir()


def deliver_final_video(job: Job, source: Path) -> Path:
    mode, folder = final_output_folder_from_options(job.options)
    summary: dict[str, Any] = {
        "mode": mode,
        "source": str(source),
        "download_hint": "browser" if mode == "browser_download" else "local_folder",
    }
    if mode == "browser_download" or folder is None:
        summary["path"] = str(source)
        summary["label"] = "Download pelo navegador"
        summary["ok"] = True
        job.delivery_summary = summary
        return source
    try:
        target = unique_output_path(folder, source.name)
        shutil.copy2(source, target)
        summary.update({
            "ok": True,
            "path": str(target),
            "folder": str(target.parent),
            "label": "Downloads" if mode == "downloads" else "Pasta definida pelo usuario",
        })
        try:
            if source.exists() and source.resolve() != target.resolve():
                source.unlink()
                summary["internal_mp4_removed"] = True
        except Exception as exc:
            summary["internal_cleanup_warning"] = str(exc)
        job.delivery_summary = summary
        return target
    except Exception as exc:
        summary.update({
            "ok": False,
            "error": str(exc),
            "path": str(source),
            "label": "Falha ao copiar destino final",
        })
        job.delivery_summary = summary
        _append_log(job, f"DELIVERY_ERROR: {exc}")
        raise RuntimeError(f"Falha ao salvar o MP4 final na pasta de saída: {exc}") from exc


def find_bin(name: str) -> str | None:
    exe_name = name + (".exe" if os.name == "nt" and not name.lower().endswith(".exe") else "")
    for folder in (DATA_ROOT, APP_DIR, SOURCE_ROOT, RESOURCE_ROOT):
        local = folder / exe_name
        if local.exists():
            return str(local)
    return shutil.which(name)


FFMPEG = find_bin("ffmpeg")
FFPROBE = find_bin("ffprobe")
_ENCODER_CACHE: dict[str, bool] = {}
_ENCODER_CACHE_AT: dict[str, float] = {}
_ENCODER_LIST_CACHE = ""
_ENCODER_LIST_CACHE_AT = 0.0
_ENCODER_CACHE_LOCK = threading.RLock()
DESKTOP_HEARTBEAT_AT = time.time()
CACHE_WARM_STATUS: dict[str, Any] = {"running": False, "items": 0, "errors": []}
RENDER_PERFORMANCE_LOCK = threading.RLock()
SEMANTIC_MODEL_LOCK = threading.RLock()
SEMANTIC_MODEL_SESSION: Any | None = None
SEMANTIC_MODEL_EMBEDDINGS: tuple[list[str], Any] | None = None


@dataclass
class Job:
    id: str
    status: str = "created"  # created/uploading/ready/running/done/error/cancelled
    percent: float = 0.0
    message: str = "Criado"
    output: str | None = None
    output_dir: str | None = None
    error: str | None = None
    log: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    expected_files: int = 0
    uploaded_files: int = 0
    manifest: list[dict[str, Any]] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)
    upload_paths: dict[str, Path] = field(default_factory=dict)
    upload_names: dict[str, str] = field(default_factory=dict)
    stage: str = "created"
    stage_label: str = "Criado"
    timeline_summary: dict[str, Any] = field(default_factory=dict)
    subtitle_summary: dict[str, Any] = field(default_factory=dict)
    subtitle_timing_summary: dict[str, Any] = field(default_factory=dict)
    caption_summary: dict[str, Any] = field(default_factory=dict)
    layer_collision_summary: dict[str, Any] = field(default_factory=dict)
    background_music_summary: dict[str, Any] = field(default_factory=dict)
    cta_summary: dict[str, Any] = field(default_factory=dict)
    intro_summary: dict[str, Any] = field(default_factory=dict)
    audio_health_summary: dict[str, Any] = field(default_factory=dict)
    audio_analysis: dict[str, Any] = field(default_factory=dict)
    sound_fx_summary: dict[str, Any] = field(default_factory=dict)
    preflight_summary: dict[str, Any] = field(default_factory=dict)
    auto_fix_summary: dict[str, Any] = field(default_factory=dict)
    emotion_summary: dict[str, Any] = field(default_factory=dict)
    ducking_summary: dict[str, Any] = field(default_factory=dict)
    dynamic_pause_summary: dict[str, Any] = field(default_factory=dict)
    strong_moments_summary: dict[str, Any] = field(default_factory=dict)
    recovery_summary: dict[str, Any] = field(default_factory=dict)
    delivery_summary: dict[str, Any] = field(default_factory=dict)
    turbo_summary: dict[str, Any] = field(default_factory=dict)
    render_plan: dict[str, Any] = field(default_factory=dict)
    render_decisions: dict[str, Any] = field(default_factory=dict)
    editorial_intelligence_plan: dict[str, Any] = field(default_factory=dict)
    render_graph_run: dict[str, Any] = field(default_factory=dict)
    director_summary: dict[str, Any] = field(default_factory=dict)
    energy_summary: dict[str, Any] = field(default_factory=dict)
    confidence_summary: dict[str, Any] = field(default_factory=dict)
    continuity_summary: dict[str, Any] = field(default_factory=dict)
    anti_repeat_summary: dict[str, Any] = field(default_factory=dict)
    audio_master_summary: dict[str, Any] = field(default_factory=dict)
    learning_summary: dict[str, Any] = field(default_factory=dict)
    subtitle_cues: list["SubtitleCue"] = field(default_factory=list)
    srt_path: Path | str | None = None
    work: Path | None = None
    export_dir: Path | None = None
    thread_started: bool = False
    encoder_logged: bool = False
    cancel_requested: bool = False
    cancelled_at: float | None = None
    current_process: Any | None = field(default=None, repr=False)
    current_processes: list[Any] = field(default_factory=list, repr=False)
    process_lock: Any = field(default_factory=threading.RLock, repr=False)
    performance_breakdown: dict[str, Any] = field(default_factory=dict)
    performance_marks: dict[str, float] = field(default_factory=dict, repr=False)
    estimated_total_seconds: float = 0.0
    estimated_render_duration: float = 0.0
    estimate_confidence: str = "heuristic"
    render_budget_seconds: float = 0.0
    render_deadline_at: float = 0.0
    render_budget_state: str = "pending"
    render_budget_fallbacks: list[str] = field(default_factory=list)
    stage_progress_seconds: float = 0.0
    stage_progress_total: float = 0.0


class RenderCancelled(RuntimeError):
    pass


class RenderBudgetExceeded(RuntimeError):
    pass


@dataclass
class SegmentPlan:
    source: Path
    raw_duration: float
    target_duration: float
    source_index: int
    cycle: int
    media_kind: str = "video"
    image_motion: str = ""
    source_offset: float = 0.0
    is_reversed: bool = False
    is_outro: bool = False


@dataclass
class SubtitleCue:
    start: float
    end: float
    text: str


JOBS: dict[str, Job] = {}
QUEUE_LOCK = threading.RLock()


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def clean_ui_text(value: Any) -> Any:
    if isinstance(value, str):
        text = value.replace("Â·", "-").replace("Â ", " ")
        if "Ã" in text or "Â" in text or "�" in text:
            try:
                repaired = text.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
                if repaired.strip():
                    text = repaired
            except Exception:
                pass
        return text.replace("�", "").strip() if text else text
    if isinstance(value, list):
        return [clean_ui_text(item) for item in value]
    if isinstance(value, tuple):
        return tuple(clean_ui_text(item) for item in value)
    if isinstance(value, dict):
        return {key: clean_ui_text(item) for key, item in value.items()}
    return value


def _load_visual_clean_cache() -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(VISUAL_CLEAN_CACHE_FILE.read_text(encoding="utf-8"))
        if int(payload.get("version") or 0) != VISUAL_CLEAN_CACHE_VERSION:
            return {}
        entries = payload.get("entries")
        if isinstance(entries, dict):
            return {
                str(key): value
                for key, value in entries.items()
                if isinstance(value, dict)
            }
    except Exception:
        pass
    return {}


def _save_visual_clean_cache() -> None:
    with VISUAL_CLEAN_CACHE_LOCK:
        entries = list(VISUAL_CLEAN_CACHE.items())[-2400:]
        payload = {
            "version": VISUAL_CLEAN_CACHE_VERSION,
            "updatedAt": _now_iso(),
            "entries": dict(entries),
        }
        try:
            atomic_write_text(
                VISUAL_CLEAN_CACHE_FILE,
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            )
        except Exception:
            pass


VISUAL_CLEAN_CACHE.update(_load_visual_clean_cache())


def _default_queue_project(name: str | None = None) -> dict[str, Any]:
    project_id = uuid.uuid4().hex[:10]
    label = (name or "").strip() or f"Projeto {project_id[:4].upper()}"
    return {
        "id": project_id,
        "name": label[:80],
        "status": "draft",
        "media": {"videos": [], "audios": [], "background_music": [], "texts": [], "captions": [], "script_guides": []},
        "options": {
            "smartVisualDirector": True,
            "autoDirector": True,
            "directorDecisionMode": "balanced",
            "visualCleanFilter": True,
            "visualFilterLevel": "normal",
            "adaptiveVisualFilter": False,
            "healthyRenderThreshold": 70,
            "renderBudgetEnabled": True,
            "renderPriority": "balanced",
            "renderExecutionProfile": "efficient_intelligent",
            "renderBudgetTurboMultiplier": 1.35,
            "renderBudgetEfficientMultiplier": 2.7,
            "renderBudgetQualityMultiplier": 4.0,
            "safeRenderMode": False,
            "platformMasterProfile": "youtube_long",
            "semanticVisualIndex": True,
            "channelLearning": True,
            "energyEditing": True,
            "antiRepeat": True,
            "continuityMatch": False,
            "continuityOutliersOnly": True,
            "backgroundMusicDucking": True,
            "adaptiveDucking": True,
            "dynamicPauses": False,
            "dynamicPauseIntensity": "disabled",
            "strongMomentEnhance": False,
            "subtitleEditorialGrammar": True,
            "cinematicOpeningPolicy": "auto_contextual",
            "captionStyle": {
                "preset": "clean_two_lines", "font": "Arial", "size": 38,
                "position": 10, "alignment": "center", "primary": "#FFFFFF",
                "outline": "#111111", "outline_size": 2.0, "box": False,
            },
            "audioMastering": True,
            "scoreVisualWindows": False,
            "adaptiveQualityBoost": False,
            "queueAutoTest": True,
            "styleSource": "glide_package",
            "referenceStyleEnabled": False,
            "referenceStyleVideo": None,
            "referenceStyleMode": "inspiration",
            "visualLanguagePackage": "dark_doc",
            "styleIntensity": "balanced",
        },
        "referenceStyleVideo": None,
        "referenceStyleMode": "inspiration",
        "subtitleInfo": None,
        "captionInfo": None,
        "scriptGuideInfo": None,
        "scriptGuidePlan": None,
        "musicGenre": "cinematic",
        "outputName": "",
        "outputFile": None,
        "outputDir": None,
        "jobId": None,
        "error": None,
        "estimatedSize": None,
        "lastRenderSummary": None,
        "directorState": None,
        "timelineHistory": [],
        "confidenceSummary": None,
        "audioMasterSummary": None,
        "renderGraphRun": None,
        "retryCount": 0,
        "retryHistory": [],
        "createdAt": _now_iso(),
        "updatedAt": _now_iso(),
    }


def _load_queue_projects() -> list[dict[str, Any]]:
    candidates = (QUEUE_PROJECTS_FILE, QUEUE_PROJECTS_FILE.with_suffix(".json.bak"))
    for candidate in candidates:
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
            projects = data.get("projects", data if isinstance(data, list) else [])
            if isinstance(projects, list):
                return [item for item in projects if isinstance(item, dict) and item.get("id")]
        except Exception:
            continue
    return []


def _save_queue_projects(projects: list[dict[str, Any]]) -> None:
    QUEUE_PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": APP_VERSION,
        "updatedAt": _now_iso(),
        "projects": projects,
    }
    if QUEUE_PROJECTS_FILE.exists():
        try:
            json.loads(QUEUE_PROJECTS_FILE.read_text(encoding="utf-8"))
            shutil.copy2(QUEUE_PROJECTS_FILE, QUEUE_PROJECTS_FILE.with_suffix(".json.bak"))
        except Exception:
            pass
    atomic_write_text(QUEUE_PROJECTS_FILE, json.dumps(payload, ensure_ascii=False, indent=2))


def _load_app_settings() -> dict[str, Any]:
    try:
        if APP_SETTINGS_FILE.exists():
            data = json.loads(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {"version": APP_VERSION, "global": {}, "updatedAt": None}


def _save_app_settings(settings: dict[str, Any]) -> None:
    APP_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(settings or {})
    payload["version"] = APP_VERSION
    payload["updatedAt"] = _now_iso()
    atomic_write_text(APP_SETTINGS_FILE, json.dumps(payload, ensure_ascii=False, indent=2))


QUEUE_PROJECTS: list[dict[str, Any]] = _load_queue_projects()


def _migrate_queue_projects_v115() -> None:
    changed = False
    option_defaults = {
        "smartVisualDirector": True,
        "autoDirector": True,
        "directorDecisionMode": "balanced",
        "visualCleanFilter": True,
        "visualFilterLevel": "normal",
        "adaptiveVisualFilter": False,
        "healthyRenderThreshold": 70,
        "renderPriority": "balanced",
        "renderExecutionProfile": "efficient_intelligent",
        "renderBudgetEnabled": True,
        "renderBudgetTurboMultiplier": 1.35,
        "renderBudgetEfficientMultiplier": 2.7,
        "renderBudgetQualityMultiplier": 4.0,
        "safeRenderMode": False,
        "platformMasterProfile": "youtube_long",
        "semanticVisualIndex": True,
        "channelLearning": True,
        "energyEditing": True,
        "antiRepeat": True,
        "continuityMatch": False,
        "continuityOutliersOnly": True,
        "backgroundMusicDucking": True,
        "adaptiveDucking": True,
        "dynamicPauses": False,
        "dynamicPauseIntensity": "disabled",
        "strongMomentEnhance": False,
        "subtitleEditorialGrammar": True,
        "audioMastering": True,
        "scoreVisualWindows": False,
        "adaptiveQualityBoost": False,
        "queueAutoTest": True,
        "styleSource": "glide_package",
        "referenceStyleEnabled": False,
        "referenceStyleVideo": None,
        "referenceStyleMode": "inspiration",
        "visualLanguagePackage": "dark_doc",
        "styleIntensity": "balanced",
        "smartSubtitlePlacement": False,
        "subtitleAnimation": "mixed",
        "smartCtaPlacement": True,
        "ctaMaxOccurrences": 2,
    }
    project_defaults: dict[str, Any] = {
        "referenceStyleVideo": None,
        "directorState": None,
        "timelineHistory": [],
        "confidenceSummary": None,
        "audioMasterSummary": None,
        "renderGraphRun": None,
        "retryCount": 0,
        "retryHistory": [],
    }
    for project in QUEUE_PROJECTS:
        options = project.get("options")
        if not isinstance(options, dict):
            options = {}
            project["options"] = options
            changed = True
        for key, value in option_defaults.items():
            if key not in options:
                options[key] = value
                changed = True
        for key, value in project_defaults.items():
            if key not in project:
                project[key] = json.loads(json.dumps(value))
                changed = True
    if changed:
        _save_queue_projects(QUEUE_PROJECTS)


_migrate_queue_projects_v115()


def _migrate_editorial_policy_v122() -> None:
    changed = False
    policy = {
        "backgroundMusicDucking": True,
        "adaptiveDucking": True,
        "dynamicPauses": False,
        "dynamicPauseIntensity": "disabled",
        "strongMomentEnhance": False,
        "continuityMatch": False,
        "continuityOutliersOnly": True,
        "subtitleEditorialGrammar": True,
        "editorialPolicyVersion": 2,
    }
    for project in QUEUE_PROJECTS:
        options = project.setdefault("options", {})
        if not isinstance(options, dict):
            options = {}
            project["options"] = options
        if int(options.get("editorialPolicyVersion") or 0) >= 2:
            continue
        options.update(policy)
        project["updatedAt"] = _now_iso()
        changed = True
    if changed:
        _save_queue_projects(QUEUE_PROJECTS)


_migrate_editorial_policy_v122()


def _migrate_text_caption_layers_v126() -> None:
    changed = False
    for project in QUEUE_PROJECTS:
        media = project.get("media")
        if not isinstance(media, dict):
            media = {}
            project["media"] = media
            changed = True
        legacy = [str(item) for item in (media.get("subtitles") or []) if str(item).strip()]
        if "texts" not in media:
            media["texts"] = legacy
            changed = True
        if "captions" not in media:
            media["captions"] = []
            changed = True
        if "subtitles" in media:
            media.pop("subtitles", None)
            changed = True
        options = project.get("options") if isinstance(project.get("options"), dict) else {}
        project["options"] = options
        if "textStyle" not in options and isinstance(options.get("subtitleStyle"), dict):
            options["textStyle"] = dict(options["subtitleStyle"])
            changed = True
        if "cinematicOpeningPolicy" not in options:
            options["cinematicOpeningPolicy"] = "auto_contextual"
            changed = True
        if "captionStyle" not in options:
            options["captionStyle"] = {
                "preset": "clean_two_lines", "font": "Arial", "size": 38,
                "position": 10, "alignment": "center", "primary": "#FFFFFF",
                "outline": "#111111", "outline_size": 2.0, "box": False,
            }
            changed = True
        if "captionInfo" not in project:
            project["captionInfo"] = None
            changed = True
    if changed:
        _save_queue_projects(QUEUE_PROJECTS)


_migrate_text_caption_layers_v126()


def _migrate_script_guides_v127() -> None:
    changed = False
    for project in QUEUE_PROJECTS:
        media = project.get("media")
        if not isinstance(media, dict):
            media = {}
            project["media"] = media
            changed = True
        if "script_guides" not in media:
            media["script_guides"] = []
            changed = True
        if "scriptGuideInfo" not in project:
            project["scriptGuideInfo"] = None
            changed = True
        if "scriptGuidePlan" not in project:
            project["scriptGuidePlan"] = None
            changed = True
    if changed:
        _save_queue_projects(QUEUE_PROJECTS)


_migrate_script_guides_v127()


def _find_queue_project(project_id: str) -> dict[str, Any] | None:
    return next((item for item in QUEUE_PROJECTS if item.get("id") == project_id), None)


def _project_media_dir(project_id: str) -> Path:
    return PROJECT_MEDIA_ROOT / safe_folder_component(project_id, "project")[:48]


def _project_media_index_path(project_id: str) -> Path:
    return _project_media_dir(project_id) / "media_index.json"


def _load_project_media_index(project_id: str) -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(_project_media_index_path(project_id).read_text(encoding="utf-8"))
        items = payload.get("items") if isinstance(payload, dict) else {}
        return {
            str(key): value
            for key, value in (items or {}).items()
            if isinstance(value, dict)
        }
    except Exception:
        return {}


def _save_project_media_index(project_id: str, items: dict[str, dict[str, Any]]) -> None:
    atomic_write_text(
        _project_media_index_path(project_id),
        json.dumps(
            {"version": APP_VERSION, "updatedAt": _now_iso(), "items": items},
            ensure_ascii=False,
            indent=2,
        ),
    )


def _reference_style_dir(project_id: str) -> Path:
    return REFERENCE_STYLE_ROOT / safe_folder_component(project_id, "project")[:48]


def _reference_style_dna_path(project_id: str) -> Path:
    return _reference_style_dir(project_id) / "style_dna.json"


def _script_guide_dir(project_id: str) -> Path:
    return _project_media_dir(project_id) / "script_guides"


def _script_guide_plan_path(project_id: str) -> Path:
    return _script_guide_dir(project_id) / "script_guide_plan.json"


def _read_txt_script(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except Exception:
            continue
    return data.decode("utf-8", errors="ignore")


def _read_docx_script(path: Path) -> str:
    paragraphs: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            xml_data = archive.read("word/document.xml")
    except Exception as exc:
        raise ValueError(f"DOCX invalido ou protegido: {exc}") from exc
    try:
        root = ET.fromstring(xml_data)
    except Exception as exc:
        raise ValueError(f"DOCX sem texto legivel: {exc}") from exc
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    for paragraph in root.findall(".//w:p", ns):
        runs = [node.text or "" for node in paragraph.findall(".//w:t", ns)]
        text = "".join(runs).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def _read_pdf_script(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as exc:
        raise ValueError("Suporte PDF indisponivel: instale pypdf ou envie TXT/DOCX.") from exc
    try:
        reader = PdfReader(str(path))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as exc:
        raise ValueError(f"PDF invalido, protegido ou sem texto extraivel: {exc}") from exc
    text = "\n\n".join(page for page in pages if page)
    if not text.strip():
        raise ValueError("PDF parece imagem; converta para texto ou DOCX.")
    return text


def _read_html_script(path: Path) -> str:
    from html.parser import HTMLParser

    class ScriptHTMLTextParser(HTMLParser):
        block_tags = {"p", "div", "section", "article", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}

        def __init__(self) -> None:
            super().__init__()
            self.parts: list[str] = []
            self.skip_depth = 0

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            tag = tag.lower()
            if tag in {"script", "style", "noscript"}:
                self.skip_depth += 1
            elif tag in self.block_tags:
                self.parts.append("\n")

        def handle_endtag(self, tag: str) -> None:
            tag = tag.lower()
            if tag in {"script", "style", "noscript"} and self.skip_depth:
                self.skip_depth -= 1
            elif tag in self.block_tags:
                self.parts.append("\n")

        def handle_data(self, data: str) -> None:
            if not self.skip_depth and data.strip():
                self.parts.append(data.strip())

    parser = ScriptHTMLTextParser()
    parser.feed(_read_txt_script(path))
    text = "\n".join(line.strip() for line in " ".join(parser.parts).splitlines() if line.strip())
    if not text.strip():
        raise ValueError("HTML nao contem texto extraivel.")
    return text


def extract_script_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        text = _read_txt_script(path)
    elif suffix == ".docx":
        text = _read_docx_script(path)
    elif suffix == ".pdf":
        text = _read_pdf_script(path)
    elif suffix in {".html", ".htm"}:
        text = _read_html_script(path)
    else:
        raise ValueError(f"Formato de roteiro nao suportado: {suffix}")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) < 20:
        raise ValueError("Roteiro vazio ou curto demais para interpretacao.")
    return text


_SCRIPT_HEADING_RE = re.compile(
    r"^\s*(?:#{1,3}\s+|(?:cap[ií]tulo|chapter|parte|bloco|intro(?:du[cç][aã]o)?|conclus[aã]o|encerramento|cta)\b|(?:top\s*)?\#?\d{1,2}[\).\-\:]\s+|posi[cç][aã]o\s+\d{1,2}\b)",
    re.IGNORECASE,
)
_SCRIPT_RANKING_RE = re.compile(r"\b(?:top\s*\d+|ranking|posi[cç][aã]o|#\d+|\d{1,2}[ºª]?\s*lugar)\b", re.IGNORECASE)
_SCRIPT_CTA_RE = re.compile(r"\b(?:inscrev|subscribe|like|curt|comenta|compartilh|cta|chamada para a[cç][aã]o)\b", re.IGNORECASE)
_SCRIPT_EDIT_RE = re.compile(r"\b(?:mostrar|imagem|video|v[ií]deo|mapa|zoom|destaque|seta|grafico|gr[aá]fico|corte|transi[cç][aã]o)\b", re.IGNORECASE)


def _script_keywords(text: str, limit: int = 12) -> list[str]:
    stop = {
        "para", "como", "com", "uma", "por", "que", "dos", "das", "nas", "nos", "the",
        "and", "with", "from", "del", "della", "este", "esta", "esse", "isso", "quando",
        "onde", "sobre", "mais", "menos", "entre", "pela", "pelo", "tambem", "também",
    }
    words = re.findall(r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9_\-]{2,}", fold_text(text))
    counts: dict[str, int] = {}
    for word in words:
        if word in stop or len(word) < 3:
            continue
        counts[word] = counts.get(word, 0) + 1
    return [word for word, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def _script_block_type(text: str, index: int, total: int) -> tuple[str, str]:
    lower = fold_text(text)
    if _SCRIPT_CTA_RE.search(text):
        return "cta", "palavras de chamada para acao"
    if _SCRIPT_RANKING_RE.search(text):
        return "topico_ranking", "padrao de ranking/lista detectado"
    if any(token in lower for token in ("compar", "versus", " vs ", "diferen", "melhor", "pior")):
        return "comparacao", "termos de comparacao"
    if any(token in lower for token in ("revel", "surpre", "segredo", "verdade", "impacto")):
        return "revelacao", "termos de revelacao/impacto"
    if index == 0 or any(token in lower for token in ("introducao", "intro", "abertura")):
        return "introducao", "inicio do roteiro"
    if index >= max(0, total - 1) or any(token in lower for token in ("conclusao", "encerramento", "final")):
        return "encerramento", "fechamento do roteiro"
    return "explicacao", "bloco explicativo"


def extract_script_editorial_structure(text: str) -> dict[str, Any]:
    """Extrai estrutura editorial profissional de roteiros (Capítulos, Cenas Obrigatórias, Hook, Reversão, CTA)."""
    structure: dict[str, Any] = {
        "mandatory_scenes": [],
        "chapters": [],
        "hook": None,
        "main_reversal": None,
        "cta_phrases": [],
        "cta_target_time": None,
    }

    # 1. Cenas Obrigatórias (Mandatory scenes / Escenas obligatorias / Cenas obrigatórias)
    mandatory_match = re.search(
        r"(?:mandatory scenes?|escenas obligatorias?|cenas obrigat[oó]rias?):\s*(.*?)(?=\n\s*(?:main turn|main reversal|giro principal|documentary base|base documental|full script|roteiro completo|\Z))",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if mandatory_match:
        m_text = mandatory_match.group(1).strip()
        scene_parts = re.split(r"(?:scene|escena|cena)\s*\d+:\s*", m_text, flags=re.IGNORECASE)
        for part in scene_parts:
            cleaned = part.strip().rstrip(".,;")
            if len(cleaned) > 5:
                raw_words = re.findall(r"[a-z0-9áéíóúãõâêîôûçñ]{3,}", cleaned.lower())
                stopwords = {
                    "the", "and", "about", "across", "begin", "with", "from", "are", "have", "that",
                    "this", "into", "later", "para", "com", "uma", "dos", "das", "por", "que", "los", "las"
                }
                keywords = [w for w in raw_words if w not in stopwords and not w.isdigit()]
                structure["mandatory_scenes"].append({
                    "description": cleaned[:300],
                    "keywords": keywords[:16],
                    "target_time": None,
                })

    # 2. Capítulos (Chapter 1 | 0:00-2:20 | ... or Capítulo 1 | ...)
    chapter_matches = re.finditer(
        r"(?:chapter|cap[ií]tulo)\s*(\d+)\s*\|\s*([\d:]+)\s*-\s*([\d:]+)\s*\|\s*([^\n|]+)\|\s*([^\n]+)",
        text,
        re.IGNORECASE,
    )
    for match in chapter_matches:
        chap_num = match.group(1)
        start_str = match.group(2)
        end_str = match.group(3)
        duration_str = match.group(4).strip()
        content_str = match.group(5).strip()

        def _parse_ts(s: str) -> float:
            parts = [float(p) for p in s.strip().split(":")]
            if len(parts) == 2:
                return parts[0] * 60.0 + parts[1]
            elif len(parts) == 3:
                return parts[0] * 3600.0 + parts[1] * 60.0 + parts[2]
            return 0.0

        start_sec = _parse_ts(start_str)
        end_sec = _parse_ts(end_str)
        structure["chapters"].append({
            "chapter": int(chap_num),
            "start": start_sec,
            "end": end_sec,
            "duration_str": duration_str,
            "title": content_str[:120],
            "keywords": _script_keywords(content_str, limit=8),
        })

    # 3. Hook
    hook_match = re.search(r"hook:\s*([^\n]+)", text, re.IGNORECASE)
    if hook_match:
        structure["hook"] = hook_match.group(1).strip()

    # 4. Main Reversal / Giro Principal
    reversal_match = re.search(r"(?:main reversal|main turn|giro principal):\s*([^\n]+)", text, re.IGNORECASE)
    if reversal_match:
        structure["main_reversal"] = reversal_match.group(1).strip()

    # 5. Call To Action (Frases finais de inscrição/engajamento)
    cta_patterns = [
        r"(?:subscribe to|suscr[ií]bete a|inscreva-se no|subscribe|comente|tell us in the comments|comentarios|siguiente caso|next case)[^\n.]*",
    ]
    for cp in cta_patterns:
        for m in re.finditer(cp, text, re.IGNORECASE):
            match_txt = m.group(0).strip()
            if len(match_txt) >= 8 and match_txt not in structure["cta_phrases"]:
                structure["cta_phrases"].append(match_txt[:120])

    return structure


def analyze_script_guide(path: Path, *, project_id: str = "", rel: str = "", srt_cues: list[SubtitleCue] | None = None) -> dict[str, Any]:
    text = extract_script_text(path)
    raw_lines = [line.strip() for line in text.splitlines()]
    blocks: list[dict[str, Any]] = []
    current_title = ""
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_lines
        body = "\n".join(line for line in current_lines if line).strip()
        if not current_title and not body:
            return
        if not body and current_title:
            body = current_title
        blocks.append({"title": current_title or f"Bloco {len(blocks) + 1}", "text": body})
        current_title = ""
        current_lines = []

    for line in raw_lines:
        if not line:
            if len("\n".join(current_lines)) > 700:
                flush()
            continue
        is_heading = bool(_SCRIPT_HEADING_RE.search(line)) or (len(line) <= 88 and line.isupper())
        if is_heading and (current_title or current_lines):
            flush()
            current_title = line
        elif is_heading and not current_lines:
            current_title = line
        else:
            current_lines.append(line)
            if len("\n".join(current_lines)) > 1400:
                flush()
    flush()
    if not blocks:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        blocks = [{"title": f"Bloco {i + 1}", "text": paragraph} for i, paragraph in enumerate(paragraphs[:30])]

    total_blocks = len(blocks)
    interpreted: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, block in enumerate(blocks[:80]):
        combined = f"{block.get('title')}\n{block.get('text')}".strip()
        kind, reason = _script_block_type(combined, index, total_blocks)
        keywords = _script_keywords(combined, limit=10)
        edit_hints = sorted(set(match.group(0).lower() for match in _SCRIPT_EDIT_RE.finditer(combined)))[:8]
        confidence = 0.72
        if block.get("title"):
            confidence += 0.08
        if keywords:
            confidence += 0.06
        if kind in {"topico_ranking", "cta", "comparacao", "revelacao"}:
            confidence += 0.08
        confidence = min(0.94, confidence)
        interpreted.append({
            "index": index,
            "title": str(block.get("title") or f"Bloco {index + 1}")[:160],
            "type": kind,
            "text": str(block.get("text") or "")[:1400],
            "keywords": keywords,
            "edit_hints": edit_hints,
            "confidence": round(confidence, 3),
            "reason": reason,
            "priority": "high" if kind in {"topico_ranking", "cta", "revelacao"} else "normal",
            "estimated_position": round(index / max(1, total_blocks), 4),
        })

    if len(blocks) > len(interpreted):
        warnings.append(f"{len(blocks) - len(interpreted)} bloco(s) extras foram resumidos para manter o plano leve.")

    editorial = extract_script_editorial_structure(text)

    if srt_cues:
        cue_texts = [fold_text(cue.text) for cue in srt_cues[:500]]
        for block in interpreted:
            block_words = set(_script_keywords(block.get("text") or "", limit=8))
            best_score = 0
            best_index = -1
            for cue_index, cue_text in enumerate(cue_texts):
                if not block_words:
                    continue
                score = sum(1 for word in block_words if word in cue_text)
                if score > best_score:
                    best_score = score
                    best_index = cue_index
            if best_index >= 0:
                cue = srt_cues[best_index]
                block["matched_cue_index"] = best_index
                block["target_time"] = round(cue.start, 3)
                block["timing_source"] = "textos_srt"
            else:
                block["timing_source"] = "estimated_order"

        # Vincular timing das Cenas Obrigatórias
        for scene in editorial["mandatory_scenes"]:
            s_words = set(scene.get("keywords") or [])
            best_score = 0
            best_t = None
            for cue_index, cue_text in enumerate(cue_texts):
                if not s_words:
                    continue
                score = sum(1 for w in s_words if w in cue_text)
                if score > best_score:
                    best_score = score
                    best_t = round(srt_cues[cue_index].start, 3)
            if best_t is not None and best_score >= 1:
                scene["target_time"] = best_t

        # Vincular timing do CTA final
        for cta_p in editorial["cta_phrases"]:
            p_words = set(_script_keywords(cta_p, limit=4))
            for cue_index, cue in enumerate(srt_cues):
                # CTA costuma estar nos últimos 30% do vídeo
                if cue_index >= int(len(srt_cues) * 0.60):
                    c_text = fold_text(cue.text)
                    if any(w in c_text for w in p_words if len(w) >= 4):
                        editorial["cta_target_time"] = round(cue.start, 3)
                        break
            if editorial["cta_target_time"]:
                break
    else:
        warnings.append("Timing real sera confirmado quando Textos/SRT e audio estiverem disponiveis.")

    title = interpreted[0]["title"] if interpreted else path.stem
    plan = {
        "version": APP_VERSION,
        "kind": "script_guide_plan",
        "source": {
            "name": path.name,
            "rel": rel or path.name,
            "format": path.suffix.lower().lstrip("."),
            "project_id": project_id,
            "chars": len(text),
        },
        "title": title,
        "summary": {
            "blocks": len(interpreted),
            "ranking_detected": any(block["type"] == "topico_ranking" for block in interpreted),
            "cta_detected": any(block["type"] == "cta" for block in interpreted) or bool(editorial["cta_phrases"]),
            "mandatory_scenes_count": len(editorial["mandatory_scenes"]),
            "chapters_count": len(editorial["chapters"]),
            "avg_confidence": round(sum(block["confidence"] for block in interpreted) / max(1, len(interpreted)), 3),
        },
        "blocks": interpreted,
        "mandatory_scenes": editorial["mandatory_scenes"],
        "chapters": editorial["chapters"],
        "hook": editorial["hook"],
        "main_reversal": editorial["main_reversal"],
        "cta_phrases": editorial["cta_phrases"],
        "cta_target_time": editorial["cta_target_time"],
        "keywords": _script_keywords(text, limit=24),
        "warnings": warnings,
        "createdAt": _now_iso(),
    }
    return plan


def attach_script_guide_plan_to_job(job: Job) -> None:
    if isinstance(job.options.get("scriptGuidePlan"), dict):
        return
    candidates: list[tuple[str, Path]] = []
    for item in job.manifest:
        rel = str(item.get("rel") or item.get("name") or "").replace("\\", "/")
        kind = str(item.get("kind") or "").lower()
        path = job.upload_paths.get(rel) or job.upload_paths.get(Path(rel).name)
        if not path:
            continue
        if kind == "script_guide" or path.suffix.lower() in SCRIPT_GUIDE_EXTS:
            candidates.append((rel, path))
    if not candidates:
        return
    rel, path = candidates[0]
    try:
        plan = analyze_script_guide(path, project_id=str(job.options.get("queueProjectId") or ""), rel=rel)
        job.options["scriptGuidePlan"] = plan
        job.options["scriptGuideInfo"] = {
            "name": Path(rel).name,
            "rel": rel,
            "format": path.suffix.lower().lstrip("."),
            "blocks": int(plan.get("summary", {}).get("blocks") or 0),
            "confidence": float(plan.get("summary", {}).get("avg_confidence") or 0.0),
            "warnings": list(plan.get("warnings") or []),
            "updatedAt": _now_iso(),
        }
        if job.export_dir:
            atomic_write_text(job.export_dir / "script_guide_plan.json", json.dumps(plan, ensure_ascii=False, indent=2))
        _append_log(job, f"Roteiro guia interpretado: {job.options['scriptGuideInfo']['blocks']} bloco(s).")
    except Exception as exc:
        job.options["scriptGuideInfo"] = {
            "name": path.name,
            "rel": rel,
            "format": path.suffix.lower().lstrip("."),
            "blocks": 0,
            "confidence": 0,
            "warnings": [human_render_error(exc)],
            "updatedAt": _now_iso(),
        }
        _append_log(job, f"Roteiro guia ignorado: {human_render_error(exc)}")


def _style_intensity_value(value: str | None) -> float:
    value = str(value or "balanced").lower()
    if value == "low":
        return 0.72
    if value == "high":
        return 1.22
    return 1.0


def visual_language_package(options: dict[str, Any] | None) -> dict[str, Any]:
    key = str((options or {}).get("visualLanguagePackage") or "dark_doc").strip().lower()
    package = VISUAL_LANGUAGE_PACKAGES.get(key) or VISUAL_LANGUAGE_PACKAGES["dark_doc"]
    return {"key": key if key in VISUAL_LANGUAGE_PACKAGES else "dark_doc", **package}


def normalized_reference_style_mode(options: dict[str, Any] | None) -> str:
    value = fold_text(str((options or {}).get("referenceStyleMode") or "inspiration"))
    if value in {"reference", "referencia", "referência", "precise", "preciso"}:
        return "reference"
    return "inspiration"


def reference_style_eagle_active(options: dict[str, Any] | None) -> bool:
    options = options or {}
    if options.get("smartVisualDirector") is False or options.get("autoDirector") is False:
        return False
    priority = str(options.get("renderPriority") or options.get("render_priority") or "balanced").lower()
    return priority not in {"max", "turbo", "turbo_production", "production_max"}


def _public_reference_style(meta: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(meta, dict):
        return None
    clean = {
        "name": meta.get("name") or "video_referencia",
        "size": int(meta.get("size") or 0),
        "updatedAt": meta.get("updatedAt"),
        "analyzedAt": meta.get("analyzedAt"),
        "styleDna": meta.get("styleDna") if isinstance(meta.get("styleDna"), dict) else None,
        "available": bool(meta.get("path")),
    }
    return clean


def reference_style_profile(options: dict[str, Any] | None) -> dict[str, Any]:
    options = options or {}
    ref = options.get("referenceStyleVideo") if isinstance(options.get("referenceStyleVideo"), dict) else None
    dna = ref.get("styleDna") if isinstance(ref, dict) and isinstance(ref.get("styleDna"), dict) else None
    reference_enabled = bool(options.get("referenceStyleEnabled")) and bool(ref)
    package = visual_language_package(options)
    intensity = str(options.get("styleIntensity") or "balanced").lower()
    requested_mode = normalized_reference_style_mode(options)
    effective_mode = requested_mode
    mode_state = "inactive"
    guidance_strength = 0.0
    if reference_enabled and dna:
        if requested_mode == "reference":
            mode_state = "reference_precise_active"
            guidance_strength = 0.85
        else:
            mode_state = "inspiration_active"
            guidance_strength = 0.65
    source = "reference_dna" if reference_enabled and dna else "glide_package"
    fallback_reason = ""
    if reference_enabled and not dna:
        fallback_reason = "Referência anexada, mas ainda sem análise suficiente; pacote Glide usado como fallback."
    profile = {
        "source": source,
        "styleSource": source,
        "referenceEnabled": reference_enabled,
        "referenceAvailable": bool(ref),
        "referenceAnalyzed": bool(dna),
        "referenceName": (ref or {}).get("name") if ref else None,
        "referenceModeRequested": requested_mode,
        "referenceModeEffective": effective_mode,
        "referenceModeState": mode_state,
        "referenceGuidanceStrength": round(guidance_strength, 3),
        "styleCopyPolicy": "guia_de_edicao_sem_copiar_frames_ou_reutilizar_conteudo",
        "package": package,
        "intensity": intensity if intensity in {"low", "balanced", "high"} else "balanced",
        "motionGraphicsPremium": bool(options.get("motionGraphicsPremium", False)),
        "fallbackReason": fallback_reason,
    }
    if dna:
        scene = dna.get("scene") if isinstance(dna.get("scene"), dict) else {}
        audio = dna.get("audio") if isinstance(dna.get("audio"), dict) else {}
        event_style = dna.get("event_style") if isinstance(dna.get("event_style"), dict) else {}
        text_profile = dna.get("text_profile") if isinstance(dna.get("text_profile"), dict) else (dna.get("text") if isinstance(dna.get("text"), dict) else {})
        profile["dna"] = {
            "cutsPerMinute": scene.get("cuts_per_minute"),
            "averageShotSeconds": scene.get("average_shot_seconds"),
            "medianShotSeconds": scene.get("median_shot_seconds"),
            "motionDensity": (dna.get("motion") or {}).get("density"),
            "meanVolumeDb": audio.get("mean_volume_db"),
            "maxVolumeDb": audio.get("max_volume_db"),
            "textPresence": text_profile.get("presence"),
            "textDensity": text_profile.get("density"),
            "eventIntensity": event_style.get("intensity"),
            "transitionFxDensity": event_style.get("transition_fx_density"),
            "imageEventFxDensity": event_style.get("image_event_fx_density"),
            "arrowHighlightDensity": event_style.get("arrow_highlight_density"),
            "storytellingEnergyCurve": dna.get("energy_curve"),
            "storytellingPattern": (dna.get("storytelling") or {}).get("pattern") if isinstance(dna.get("storytelling"), dict) else None,
        }
    return profile


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def scene_rhythm_profile_from_style(style: dict[str, Any] | None) -> dict[str, Any]:
    style = style if isinstance(style, dict) else {}
    package = style.get("package") if isinstance(style.get("package"), dict) else {}
    dna = style.get("dna") if isinstance(style.get("dna"), dict) else {}
    intensity = str(style.get("intensity") or "balanced").lower()
    cut_rhythm = str(package.get("cut_rhythm") or "medium")
    dna_average_shot = _safe_float(dna.get("averageShotSeconds"), 0.0)
    cuts_per_minute = _safe_float(dna.get("cutsPerMinute"), 0.0)
    package_average_shot = {
        "fast_precise": 2.4,
        "medium_fast": 3.0,
        "medium": 3.8,
        "medium_slow": 4.5,
        "dynamic_slow": 4.2,
    }.get(cut_rhythm, 3.8)
    guidance_strength = max(0.0, min(1.0, _safe_float(style.get("referenceGuidanceStrength"), 0.0)))
    if dna_average_shot > 0 and style.get("source") == "reference_dna":
        average_shot = package_average_shot * (1.0 - guidance_strength) + dna_average_shot * guidance_strength
    else:
        average_shot = package_average_shot
    if intensity == "high":
        average_shot *= 0.86
    elif intensity == "low":
        average_shot *= 1.16
    role_multipliers = {
        "introduction": 0.86,
        "explanation": 1.00,
        "conflict": 0.76,
        "reveal": 0.70,
        "conclusion": 1.24,
        "cta": 0.94,
    }
    role_targets = {
        role: round(max(1.2, min(7.5, average_shot * mult)), 2)
        for role, mult in role_multipliers.items()
    }
    return {
        "source": style.get("source") or "glide_package",
        "reference_mode": style.get("referenceModeEffective") or "package",
        "reference_guidance_strength": round(guidance_strength, 3),
        "package": package.get("id") or package.get("label") or "glide",
        "cut_rhythm": cut_rhythm,
        "average_shot_seconds": round(average_shot, 2),
        "cuts_per_minute": round(cuts_per_minute or (60.0 / max(1.0, average_shot)), 2),
        "role_targets": role_targets,
        "motion_graphics": package.get("image_motion") or "auto_cinematic",
        "text_animation": package.get("text_animation") or "cinematic",
        "fx_density": package.get("fx_density") or "balanced",
        "note": "Ritmo por cena derivado do Style DNA quando analisado; pacote Glide usado como fallback.",
    }


def image_motion_graphics_filter(style: dict[str, Any] | None) -> tuple[str, str]:
    style = style if isinstance(style, dict) else {}
    package = style.get("package") if isinstance(style.get("package"), dict) else {}
    motion_graphics = str(package.get("image_motion") or "auto_cinematic")
    if bool(style.get("motionGraphicsPremium")):
        return (
            ",drawbox=x=34:y=34:w=iw-68:h=ih-68:color=white@0.095:t=2,"
            "drawbox=x=iw*0.08:y=ih*0.78:w=iw*0.34:h=2:color=0x6fffe9@0.26:t=fill,"
            "drawbox=x=iw*0.68:y=ih*0.16:w=iw*0.16:h=ih*0.08:color=white@0.075:t=fill,"
            "drawbox=x=iw*0.72:y=ih*0.28:w=iw*0.14:h=ih*0.06:color=0x6fffe9@0.10:t=fill",
            "motion premium: moldura, foco e camadas parallax",
        )
    if style.get("source") == "reference_dna":
        motion_density = _safe_float((style.get("dna") or {}).get("motionDensity"), 0.0)
        motion_graphics = "reference_dynamic" if motion_density >= 0.45 else "reference_clean"
    if motion_graphics in {"documentary_scan", "slow_zoom_focus", "reference_clean"}:
        return (
            ",drawbox=x=36:y=36:w=iw-72:h=ih-72:color=white@0.10:t=2,"
            "drawbox=x=iw*0.10:y=ih*0.82:w=iw*0.28:h=2:color=0x6fffe9@0.20:t=fill",
            "moldura documental + linha de foco",
        )
    if motion_graphics in {"hud_scan", "reference_dynamic"}:
        return (
            ",drawgrid=w=iw/8:h=ih/8:t=1:c=0x6fffe9@0.075,"
            "drawbox=x=iw*0.12:y=ih*0.16:w=iw*0.34:h=2:color=0x6fffe9@0.22:t=fill",
            "scan HUD leve + grade sutil",
        )
    if motion_graphics == "data_focus":
        return (
            ",drawbox=x=iw*0.08:y=ih*0.72:w=iw*0.38:h=ih*0.13:color=black@0.16:t=fill,"
            "drawbox=x=iw*0.08:y=ih*0.72:w=iw*0.38:h=2:color=0x6fffe9@0.26:t=fill",
            "cartao documental para dados",
        )
    if motion_graphics == "parallax_cards":
        return (
            ",drawbox=x=iw*0.66:y=ih*0.16:w=iw*0.18:h=ih*0.10:color=white@0.09:t=fill,"
            "drawbox=x=iw*0.70:y=ih*0.30:w=iw*0.16:h=ih*0.08:color=0x6fffe9@0.12:t=fill",
            "camadas parallax discretas",
        )
    return ("", "movimento cinematografico limpo")


def _parse_reference_scene_cuts(video_path: Path, duration: float) -> list[float]:
    if not FFMPEG or duration <= 0:
        return []
    vf = "fps=12,scale=320:-2,select='gt(scene,0.18)',showinfo"
    cmd = [
        FFMPEG,
        "-hide_banner",
        "-nostats",
        "-i",
        str(video_path),
        "-vf",
        vf,
        "-an",
        "-f",
        "null",
        "-",
    ]
    try:
        p = _run_hidden(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=90)
        output = f"{p.stdout or ''}\n{p.stderr or ''}"
    except Exception:
        return []
    cuts: list[float] = []
    for match in re.finditer(r"pts_time:([0-9]+(?:\.[0-9]+)?)", output):
        try:
            t = float(match.group(1))
        except Exception:
            continue
        if 0.08 < t < max(0.1, duration - 0.08):
            if not cuts or abs(t - cuts[-1]) > 0.18:
                cuts.append(round(t, 3))
    return cuts[:5000]


def _parse_reference_audio(video_path: Path) -> dict[str, Any]:
    result = {"mean_volume_db": None, "max_volume_db": None, "silences": []}
    if not FFMPEG:
        return result
    try:
        p = _run_hidden([
            FFMPEG, "-hide_banner", "-nostats", "-i", str(video_path),
            "-af", "silencedetect=noise=-35dB:d=0.35,volumedetect", "-vn", "-f", "null", "-",
        ], capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=75)
        output = f"{p.stdout or ''}\n{p.stderr or ''}"
        mean = re.search(r"mean_volume:\s*(-?[0-9.]+)\s*dB", output)
        peak = re.search(r"max_volume:\s*(-?[0-9.]+)\s*dB", output)
        if mean:
            result["mean_volume_db"] = float(mean.group(1))
        if peak:
            result["max_volume_db"] = float(peak.group(1))
        starts = [float(m.group(1)) for m in re.finditer(r"silence_start:\s*([0-9.]+)", output)]
        ends = [float(m.group(1)) for m in re.finditer(r"silence_end:\s*([0-9.]+)", output)]
        silences = []
        for index, start in enumerate(starts[:80]):
            end = ends[index] if index < len(ends) else start
            if end > start:
                silences.append({"start": round(start, 3), "end": round(end, 3), "duration": round(end - start, 3)})
        result["silences"] = silences
    except Exception:
        pass
    return result


def _reference_video_signature(video_path: Path) -> dict[str, Any]:
    try:
        stat = video_path.stat()
        return {
            "path_name": video_path.name,
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
            "signature": media_signature(video_path),
        }
    except Exception:
        return {"path_name": video_path.name, "size": 0, "mtime_ns": 0, "signature": media_signature(video_path)}


def _probe_reference_video_info(video_path: Path) -> dict[str, Any]:
    info = {"fps": 30.0, "width": 0, "height": 0, "video_bitrate": 0, "audio_bitrate": 0}
    if not FFPROBE:
        return info
    try:
        p = _run_hidden([
            FFPROBE,
            "-v", "error",
            "-show_entries", "stream=codec_type,width,height,avg_frame_rate,bit_rate",
            "-of", "json",
            str(video_path),
        ], capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=35)
        data = json.loads(p.stdout or "{}")
        for stream in data.get("streams") or []:
            if not isinstance(stream, dict):
                continue
            if stream.get("codec_type") == "video":
                info["width"] = int(stream.get("width") or 0)
                info["height"] = int(stream.get("height") or 0)
                info["video_bitrate"] = int(stream.get("bit_rate") or 0)
                rate = str(stream.get("avg_frame_rate") or "")
                if "/" in rate:
                    a, b = rate.split("/", 1)
                    info["fps"] = round(float(a) / max(float(b), 0.0001), 3)
                elif rate:
                    info["fps"] = round(float(rate), 3)
            elif stream.get("codec_type") == "audio":
                info["audio_bitrate"] = int(stream.get("bit_rate") or 0)
    except Exception:
        pass
    return info


def _reference_text_density_profile(cuts: list[float], duration: float, motion_density: float) -> dict[str, Any]:
    # Sem OCR pesado: inferimos densidade de elementos/textos por ritmo, bursts e motion.
    bursts = sum(1 for a, b in zip(cuts, cuts[1:]) if b - a <= 1.15)
    cut_density = len(cuts) / max(duration / 60.0, 0.001) if duration else 0.0
    estimated = min(1.0, max(0.05, motion_density * 0.42 + min(1.0, cut_density / 24.0) * 0.36 + min(1.0, bursts / max(1, len(cuts))) * 0.22))
    return {
        "presence": "estimated",
        "density": round(estimated, 3),
        "recommended_positions": ["left_callout", "right_callout", "lower_center", "upper_right", "data_card"],
        "avoid_repetition": True,
        "method": "ritmo_de_corte_motion_proxy_sem_ocr_pesado",
    }


def _reference_event_style(cuts_per_minute: float, motion_density: float, audio: dict[str, Any]) -> dict[str, Any]:
    peak = _safe_float(audio.get("max_volume_db"), -1.0)
    mean = _safe_float(audio.get("mean_volume_db"), -23.0)
    intensity = "high" if cuts_per_minute >= 20 or motion_density >= 0.65 else ("low" if cuts_per_minute <= 8 and motion_density <= 0.28 else "balanced")
    return {
        "intensity": intensity,
        "transition_fx_density": 0.46 if intensity == "high" else (0.28 if intensity == "low" else 0.38),
        "subtitle_fx_density": 1.0,
        "image_event_fx_density": 0.62 if intensity == "high" else 0.46,
        "arrow_highlight_density": 0.34 if intensity == "high" else 0.22,
        "audio_loudness_hint": {
            "mean_db": mean,
            "peak_db": peak,
            "fx_headroom": round(max(0.8, min(4.0, abs(peak))), 2),
        },
    }


def analyze_reference_style_video(project_id: str, video_path: Path, display_name: str) -> dict[str, Any]:
    source_signature = _reference_video_signature(video_path)
    existing_path = _reference_style_dna_path(project_id)
    if existing_path.exists():
        try:
            existing = json.loads(existing_path.read_text(encoding="utf-8"))
            if (
                isinstance(existing, dict)
                and existing.get("dnaVersion") == "2.1"
                and (existing.get("sourceSignature") or {}).get("signature") == source_signature.get("signature")
            ):
                existing["cache_reused"] = True
                existing["cache_reused_reason"] = "assinatura do video referencia sem alteracoes"
                return existing
        except Exception:
            pass
    duration = safe_probe_duration(video_path)
    cuts = _parse_reference_scene_cuts(video_path, duration)
    audio = _parse_reference_audio(video_path)
    stream_info = _probe_reference_video_info(video_path)
    cuts_per_minute = (len(cuts) / max(duration / 60.0, 0.001)) if duration else 0.0
    avg_shot = duration / max(len(cuts) + 1, 1) if duration else 0.0
    intervals = [b - a for a, b in zip([0.0] + cuts, cuts + ([duration] if duration else [])) if b > a]
    sorted_intervals = sorted(intervals)
    median_shot = sorted_intervals[len(sorted_intervals) // 2] if sorted_intervals else avg_shot
    silences = audio.get("silences") if isinstance(audio.get("silences"), list) else []
    silence_cut_matches = 0
    for silence in silences:
        end = float(silence.get("end") or 0.0)
        if any(abs(cut - end) <= 0.35 for cut in cuts):
            silence_cut_matches += 1
    burst_cuts = sum(1 for a, b in zip(cuts, cuts[1:]) if (b - a) <= 1.15)
    motion_density = min(1.0, (cuts_per_minute / 28.0) * 0.72 + (burst_cuts / max(len(cuts), 1)) * 0.28)
    recommended_package = "modern_explainer"
    if cuts_per_minute >= 22:
        recommended_package = "tech_cyber"
    elif cuts_per_minute <= 8:
        recommended_package = "dark_doc"
    elif silence_cut_matches >= 3:
        recommended_package = "dramatic_history"
    text_profile = _reference_text_density_profile(cuts, duration, motion_density)
    event_style = _reference_event_style(cuts_per_minute, motion_density, audio)
    thirds = [
        ("inicio", 0.0, duration / 3.0),
        ("meio", duration / 3.0, duration * 2.0 / 3.0),
        ("final", duration * 2.0 / 3.0, duration),
    ] if duration else []
    energy_curve = []
    for label, start, end in thirds:
        span = max(0.001, end - start)
        local_cuts = [cut for cut in cuts if start <= cut < end]
        local_silences = [
            item for item in silences
            if start <= float(item.get("start") or 0.0) < end
        ]
        cpm = len(local_cuts) / max(span / 60.0, 0.001)
        silence_ratio = sum(float(item.get("duration") or 0.0) for item in local_silences) / span
        energy = max(0.05, min(1.0, (cpm / 26.0) * 0.72 + (1.0 - min(1.0, silence_ratio)) * 0.28))
        energy_curve.append({
            "part": label,
            "start": round(start, 3),
            "end": round(end, 3),
            "cuts_per_minute": round(cpm, 2),
            "silence_ratio": round(silence_ratio, 3),
            "energy": round(energy, 3),
        })
    storytelling_pattern = "impacto_inicial" if energy_curve and energy_curve[0]["energy"] >= max(item["energy"] for item in energy_curve) else (
        "crescimento_progressivo" if energy_curve and energy_curve[-1]["energy"] >= energy_curve[0]["energy"] + 0.12 else "equilibrado"
    )
    dna = {
        "kind": "glide_reference_style_dna",
        "version": APP_VERSION,
        "dnaVersion": "2.1",
        "projectId": project_id,
        "sourceVideo": display_name,
        "analysisPolicy": {
            "mode": "style_language_only",
            "noCopy": True,
            "description": "O video referencia e usado somente para ritmo, linguagem audiovisual e padroes editoriais; nenhum frame, cena ou conteudo visual e reutilizado.",
        },
        "sourceSignature": source_signature,
        "analyzedAt": _now_iso(),
        "duration": round(duration, 3),
        "fps": stream_info.get("fps"),
        "resolution": {
            "width": stream_info.get("width"),
            "height": stream_info.get("height"),
        },
        "bitrate": {
            "video": stream_info.get("video_bitrate"),
            "audio": stream_info.get("audio_bitrate"),
        },
        "scene": {
            "cut_count": len(cuts),
            "cuts_per_minute": round(cuts_per_minute, 2),
            "average_shot_seconds": round(avg_shot, 2),
            "median_shot_seconds": round(median_shot, 2),
            "cut_times": cuts[:240],
            "transition_clusters": burst_cuts,
        },
        "shot_profile": {
            "average_seconds": round(avg_shot, 2),
            "median_seconds": round(median_shot, 2),
            "short_shots": sum(1 for value in intervals if value <= 2.0),
            "long_shots": sum(1 for value in intervals if value >= 6.0),
            "rhythm": "fast" if cuts_per_minute >= 20 else ("slow" if cuts_per_minute <= 8 else "balanced"),
        },
        "audio": {
            **audio,
            "silence_count": len(silences),
            "silence_cut_matches": silence_cut_matches,
        },
        "audio_profile": {
            "mean_volume_db": audio.get("mean_volume_db"),
            "max_volume_db": audio.get("max_volume_db"),
            "silence_count": len(silences),
            "silence_cut_matches": silence_cut_matches,
            "cut_on_silence_ratio": round(silence_cut_matches / max(1, len(silences)), 3),
        },
        "motion": {
            "density": round(motion_density, 3),
            "method": "scene_change_proxy",
        },
        "motion_profile": {
            "density": round(motion_density, 3),
            "burst_cut_count": burst_cuts,
            "recommended_image_motion": "parallax_scan" if motion_density >= 0.45 else "clean_documentary_motion",
        },
        "transition_profile": {
            "cut_density": round(cuts_per_minute, 2),
            "burst_cut_count": burst_cuts,
            "style": "energetic" if cuts_per_minute >= 20 else ("cinematic_sparse" if cuts_per_minute <= 8 else "balanced_documentary"),
        },
        "music_profile": {
            "tone": "intense" if event_style["intensity"] == "high" else ("subtle" if event_style["intensity"] == "low" else "balanced"),
            "mean_volume_db": audio.get("mean_volume_db"),
            "max_volume_db": audio.get("max_volume_db"),
            "pause_impact_matches": silence_cut_matches,
        },
        "storytelling": {
            "pattern": storytelling_pattern,
            "visual_energy_by_part": energy_curve,
            "guidance": "Adaptar estrutura e energia ao novo conteudo sem copiar composicao visual.",
        },
        "energy_curve": energy_curve,
        "text": text_profile,
        "text_profile": text_profile,
        "event_style": event_style,
        "language_visual_hints": {
            "text_positions": text_profile["recommended_positions"],
            "graphics": ["arrow_draw", "highlight_pulse", "focus_line", "data_card"],
            "sync_target_ms": 33,
        },
        "recommendations": {
            "visualLanguagePackage": recommended_package,
            "cutRhythm": "fast" if cuts_per_minute >= 20 else ("slow" if cuts_per_minute <= 8 else "balanced"),
            "motionIntensity": "high" if motion_density >= 0.65 else ("low" if motion_density <= 0.28 else "balanced"),
            "styleSource": "reference_dna",
            "fallbackPackage": recommended_package,
        },
    }
    ref_dir = _reference_style_dir(project_id)
    ref_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(_reference_style_dna_path(project_id), json.dumps(dna, ensure_ascii=False, indent=2))
    return dna


def _repair_false_missing_audio_queue_errors() -> None:
    changed = False
    for project in QUEUE_PROJECTS:
        error = str(project.get("error") or "").lower()
        if "nenhum audio de narracao valido foi encontrado" not in error:
            continue
        project_id = str(project.get("id") or "").strip()
        groups = project.get("media") if isinstance(project.get("media"), dict) else {}
        audio_rels = [str(item).replace("\\", "/") for item in (groups.get("audios") or [])]
        index = _load_project_media_index(project_id)
        has_persisted_audio = False
        for rel in audio_rels:
            record = index.get(rel)
            if not record:
                continue
            stored_file = Path(str(record.get("file") or "")).name
            candidate = _project_media_dir(project_id) / stored_file
            if candidate.exists() and candidate.is_file() and candidate.stat().st_size > 0:
                has_persisted_audio = True
                break
        if not has_persisted_audio:
            continue
        project["status"] = "ready"
        project["error"] = None
        project["jobId"] = None
        project["lastRenderSummary"] = None
        options = project.get("options") if isinstance(project.get("options"), dict) else {}
        options.pop("backgroundMusicAutoSelection", None)
        project["options"] = options
        project["updatedAt"] = _now_iso()
        changed = True
    if changed:
        _save_queue_projects(QUEUE_PROJECTS)


_repair_false_missing_audio_queue_errors()


def _project_export_manifest(project: dict[str, Any]) -> list[dict[str, Any]]:
    output_dir = str(project.get("outputDir") or "").strip()
    candidates: list[Path] = []
    if output_dir:
        candidates.append(Path(output_dir) / "manifest.json")
    job_id = str(project.get("jobId") or "").strip()
    if job_id and not any(path.exists() for path in candidates):
        candidates.extend(EXPORT_ROOT.glob(f"**/*{job_id}*/manifest.json"))
    for candidate in candidates:
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                return [item for item in payload if isinstance(item, dict)]
        except Exception:
            continue
    return []


def _duration_from_clip_name(name: str) -> float:
    match = re.search(r"_(\d{1,2})m(\d{2})s-(\d{1,2})m(\d{2})s", str(name or ""), re.IGNORECASE)
    if not match:
        return 0.0
    start = int(match.group(1)) * 60 + int(match.group(2))
    end = int(match.group(3)) * 60 + int(match.group(4))
    return max(0.0, float(end - start))


def _resolve_persisted_manifest_item(item: dict[str, Any]) -> Path | None:
    project_id = str(item.get("persistedProjectId") or "").strip()
    stored_file = Path(str(item.get("persistedStoredFile") or "")).name
    if project_id and stored_file:
        candidate = _project_media_dir(project_id) / stored_file
        if candidate.exists() and candidate.is_file():
            return candidate
    source_job_id = safe_folder_component(str(item.get("persistedJobId") or ""), "")
    try:
        source_index = int(item.get("persistedIndex"))
    except Exception:
        source_index = -1
    if source_job_id and source_index >= 0:
        source_dir = UPLOAD_ROOT / source_job_id
        matches = list(source_dir.glob(f"u{source_index:04d}.*"))
        if matches and matches[0].is_file():
            return matches[0]
    return None


def _clear_queue_project_storage(project: dict[str, Any]) -> dict[str, Any]:
    removed = 0
    recovered = 0
    errors: list[str] = []
    project_id = str(project.get("id") or "")
    job_id = str(project.get("jobId") or "")
    active_job = JOBS.get(job_id) if job_id else None
    if active_job and active_job.status in {"uploading", "ready", "running"}:
        raise HTTPException(status_code=409, detail="Este projeto esta renderizando e nao pode ser limpo agora")

    candidates = [_project_media_dir(project_id)]
    if job_id:
        candidates.append(UPLOAD_ROOT / safe_folder_component(job_id, ""))
    output_dir = str(project.get("outputDir") or "").strip()
    if output_dir:
        try:
            output_path = Path(output_dir).resolve()
            if output_path == EXPORT_ROOT or EXPORT_ROOT in output_path.parents:
                candidates.append(output_path)
        except Exception:
            pass
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            key = str(resolved).lower()
            if key in seen or not resolved.exists():
                continue
            seen.add(key)
            recovered += path_size(resolved)
            if resolved.is_dir():
                shutil.rmtree(resolved)
            else:
                resolved.unlink(missing_ok=True)
            removed += 1
        except Exception as exc:
            errors.append(f"{candidate.name}: {exc}")
    if job_id and active_job is None:
        JOBS.pop(job_id, None)
    return {"removed": removed, "bytes_recovered": recovered, "errors": errors}


def _reset_queue_project_runtime(project: dict[str, Any]) -> None:
    """Clear media/render state while preserving the project identity and presets."""
    project["media"] = {"videos": [], "audios": [], "background_music": [], "texts": [], "captions": [], "script_guides": []}
    project["subtitleInfo"] = None
    project["captionInfo"] = None
    project["scriptGuideInfo"] = None
    project["scriptGuidePlan"] = None
    project["status"] = "draft"
    project["jobId"] = None
    project["outputFile"] = None
    project["outputDir"] = None
    project["error"] = None
    project["estimatedSize"] = 0
    project["lastRenderSummary"] = None
    project["visualAnalysisDetails"] = None
    project["renderGraphRun"] = None
    project["confidenceSummary"] = None
    project["audioMasterSummary"] = None
    project["directorState"] = None
    project["timelineHistory"] = []
    project["retryCount"] = 0
    project["retryHistory"] = []
    project["updatedAt"] = _now_iso()


def _queue_project_missing_requirements(project: dict[str, Any]) -> list[str]:
    media = project.get("media") if isinstance(project.get("media"), dict) else {}
    options = project.get("options") if isinstance(project.get("options"), dict) else {}
    missing: list[str] = []
    project_id = str(project.get("id") or "")
    stable_index = _load_project_media_index(project_id) if project_id else {}
    has_real_visual = False
    for raw_rel in media.get("videos") or []:
        rel_key = str(raw_rel).replace("\\", "/")
        record = stable_index.get(rel_key) or {}
        kind = str(record.get("kind") or "").lower()
        suffix = Path(str(record.get("name") or rel_key)).suffix.lower()
        if kind in ("video", "image") or suffix in VIDEO_EXTS or suffix in IMAGE_EXTS:
            has_real_visual = True
            break
    if not has_real_visual:
        missing.append("videos")
    if not media.get("audios"):
        missing.append("narracao")
    if not (media.get("texts") or media.get("subtitles")):
        missing.append("Textos")
    if not (options.get("ctaLanguage") or options.get("selectedCta")):
        missing.append("CTA")
    return missing


def _project_media_paths_by_kind(project: dict[str, Any], kind: str, limit: int = 4) -> list[Path]:
    project_id = str(project.get("id") or "")
    media = project.get("media") if isinstance(project.get("media"), dict) else {}
    index = _load_project_media_index(project_id) if project_id else {}
    rels = media.get(kind) or []
    paths: list[Path] = []
    for raw_rel in rels:
        rel_key = str(raw_rel).replace("\\", "/")
        record = index.get(rel_key) or {}
        stored_file = Path(str(record.get("file") or "")).name
        candidate = _project_media_dir(project_id) / stored_file if project_id and stored_file else None
        if candidate and candidate.exists() and candidate.is_file():
            paths.append(candidate)
        if len(paths) >= limit:
            break
    return paths


def queue_project_technical_autotest(project: dict[str, Any]) -> dict[str, Any]:
    if not bool((project.get("options") if isinstance(project.get("options"), dict) else {}).get("queueAutoTest", True)):
        return {"enabled": False, "status": "skipped", "reason": "auto-teste desligado"}
    missing = _queue_project_missing_requirements(project)
    if missing:
        return {"enabled": True, "status": "skipped", "reason": f"faltam {', '.join(missing)}"}
    options = project.get("options") if isinstance(project.get("options"), dict) else {}
    videos = _project_media_paths_by_kind(project, "videos", limit=8)
    audios = _project_media_paths_by_kind(project, "audios", limit=2)
    subtitles = _project_media_paths_by_kind(project, "texts", limit=1)
    if not subtitles:
        subtitles = _project_media_paths_by_kind(project, "subtitles", limit=1)
    checks: dict[str, Any] = {
        "visual": bool(videos),
        "audio": bool(audios),
        "srt": bool(subtitles),
        "cta": bool(options.get("ctaLanguage") or options.get("selectedCta")),
        "mux": False,
    }
    if not videos or not audios:
        return {"enabled": True, "status": "failed", "reason": "midia essencial ausente no armazenamento persistido", "checks": checks}
    visual = next((path for path in videos if path.suffix.lower() in VIDEO_EXTS), videos[0])
    audio = audios[0]
    if visual.suffix.lower() in VIDEO_EXTS and safe_probe_duration(visual) <= 0.08:
        checks["visual"] = False
        return {"enabled": True, "status": "failed", "reason": f"video sem duracao legivel: {visual.name}", "checks": checks}
    if not probe_has_audio(audio):
        checks["audio"] = False
        return {"enabled": True, "status": "failed", "reason": f"narracao sem faixa de audio legivel: {audio.name}", "checks": checks}
    if subtitles:
        try:
            checks["srt_cues"] = len(parse_srt_file(subtitles[0])[:5])
            if checks["srt_cues"] <= 0:
                checks["srt"] = False
                return {"enabled": True, "status": "failed", "reason": f"Textos sem cues legiveis: {subtitles[0].name}", "checks": checks}
        except Exception as exc:
            checks["srt"] = False
            return {"enabled": True, "status": "failed", "reason": f"Arquivo de Textos invalido: {human_render_error(exc)}", "checks": checks}
    if not FFMPEG:
        return {"enabled": True, "status": "skipped", "reason": "FFmpeg indisponivel", "checks": checks}
    test_dir = UPLOAD_ROOT / "_queue_autotest"
    test_dir.mkdir(parents=True, exist_ok=True)
    output = test_dir / f"{safe_folder_component(str(project.get('id') or 'project'), 'project')}_{uuid.uuid4().hex[:8]}.mp4"
    width, height = render_size(str(options.get("mode") or "fast"), str(options.get("ratio") or "16:9"))
    width = min(width, 640)
    height = max(2, int(round(width * 9 / 16 / 2)) * 2) if str(options.get("ratio") or "16:9") == "16:9" else min(height, 640)
    codec = "libx264"
    if visual.suffix.lower() in IMAGE_EXTS:
        visual_args = ["-loop", "1", "-framerate", "30", "-t", "3.0", "-i", str(visual)]
    else:
        visual_args = ["-t", "3.0", "-i", str(visual)]
    cmd = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        *visual_args,
        "-t", "3.0", "-i", str(audio),
        "-map", "0:v:0", "-map", "1:a:0",
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,fps=30,format=yuv420p",
        "-c:v", codec, "-preset", "ultrafast", "-b:v", "900k",
        "-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart",
        str(output),
    ]
    try:
        result = _run_hidden(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=60)
        checks["mux"] = result.returncode == 0 and output.exists() and output.stat().st_size > 1024
        if not checks["mux"]:
            return {"enabled": True, "status": "failed", "reason": human_render_error((result.stderr or result.stdout or "mini-render técnico falhou")[:300]), "checks": checks}
        return {"enabled": True, "status": "passed", "reason": "codec, audio e mux testados em 3s", "checks": checks}
    except Exception as exc:
        return {"enabled": True, "status": "failed", "reason": human_render_error(exc), "checks": checks}
    finally:
        try:
            if output.exists():
                output.unlink(missing_ok=True)
        except Exception:
            pass


def _normalized_director_decision_mode(options: dict[str, Any] | None = None) -> str:
    # Kept for backup/API compatibility. The visual filter and Eagle mode now
    # own their decisions independently, avoiding two competing intensity knobs.
    return "balanced"


def _healthy_threshold(options: dict[str, Any] | None = None) -> int:
    try:
        value = int(float((options or {}).get("healthyRenderThreshold", 70)))
    except Exception:
        value = 70
    return max(40, min(95, value))


def _confidence_score(project: dict[str, Any], preflight_summary: dict[str, Any] | None = None) -> int:
    confidence = project.get("confidenceSummary") if isinstance(project.get("confidenceSummary"), dict) else {}
    raw = confidence.get("overall")
    if raw is None and isinstance(preflight_summary, dict):
        raw = ((preflight_summary.get("confidence") or {}) if isinstance(preflight_summary.get("confidence"), dict) else {}).get("overall")
    try:
        return int(round(float(raw)))
    except Exception:
        missing = _queue_project_missing_requirements(project)
        return 72 if not missing else max(20, 70 - len(missing) * 18)


def _decision_record(
    kind: str,
    action: str,
    reason: str,
    confidence: float | int,
    target: str = "",
    **extra: Any,
) -> dict[str, Any]:
    try:
        normalized = float(confidence)
        if normalized > 1:
            normalized = normalized / 100.0
    except Exception:
        normalized = 0.5
    return {
        "kind": kind,
        "target": target,
        "action": action,
        "reason": reason,
        "confidence": round(max(0.0, min(1.0, normalized)), 3),
        **{key: value for key, value in extra.items() if value is not None},
    }


def recommended_error_actions(error: str | None, project: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    text = str(error or "").lower()
    actions: list[dict[str, Any]] = []

    def add(action: str, label: str, reason: str, primary: bool = False):
        if not any(item.get("action") == action for item in actions):
            actions.append({"action": action, "label": label, "reason": reason, "primary": primary})

    if any(token in text for token in ("hevc", "h265", "nvenc", "encoder", "codec", "tag:v")):
        add("retry_h264_cpu", "Tentar H.264 CPU", "Falha parece relacionada ao codec/aceleracao.", True)
    if any(token in text for token in ("invalid", "sem frames", "no frame", "moov", "corrupt", "invalid data", "clipe")):
        add("retry_without_invalid", "Tentar sem clipes invalidos", "Ha indicios de midia quebrada ou sem frames.", not actions)
    if any(token in text for token in ("subtitle", "srt", "ass", "legenda", "font", "subtitles")):
        add("rebuild_subtitles", "Recriar legendas", "Falha pode estar no SRT/ASS ou estilo de legenda.", not actions)
    if any(token in text for token in ("cache", "render graph", "artifact", "manifest")):
        add("clear_project_cache", "Limpar cache deste projeto", "Artefato cacheado pode estar incompleto.", not actions)
    if "turbo" not in text:
        add("retry_turbo", "Tentar em Turbo", "Render rapido suspende automacoes caras e usa caminho mais simples.", not actions)
    if not actions:
        add("safe_render", "Render seguro", "Usa caminho conservador para entregar o video com menos automacoes.", True)
        add("retry_turbo", "Tentar em Turbo", "Pode contornar filtros ou etapas lentas.", False)
    return actions[:5]


def _project_queue_plan_entry(project: dict[str, Any], render_mode: str = "all") -> dict[str, Any]:
    options = project.get("options") if isinstance(project.get("options"), dict) else {}
    missing = _queue_project_missing_requirements(project)
    threshold = _healthy_threshold(options)
    confidence = _confidence_score(project)
    eligible = not missing
    healthy = eligible and confidence >= threshold
    if render_mode == "healthy":
        renderable = healthy
    else:
        renderable = eligible
    ignored_reasons: list[str] = []
    if missing:
        ignored_reasons.append(f"faltam {', '.join(missing)}")
    if eligible and render_mode == "healthy" and confidence < threshold:
        ignored_reasons.append(f"confianca {confidence}% abaixo de {threshold}%")
    auto_test = queue_project_technical_autotest(project) if eligible else {"enabled": True, "status": "skipped", "reason": "projeto incompleto"}
    if eligible and auto_test.get("status") == "failed":
        renderable = False
        healthy = False
        ignored_reasons.append(f"auto-teste falhou: {auto_test.get('reason')}")

    preflight = build_preflight_summary(_project_export_manifest(project), options)
    decisions = [
        _decision_record(
            "render_mode",
            "use_turbo" if render_priority(options) == "max" else "use_balanced",
            "Modo global congelado antes da fila.",
            0.92,
            str(project.get("name") or project.get("id") or ""),
        ),
        _decision_record(
            "director",
            smart_visual_director_effective(options, bool((project.get("media") or {}).get("subtitles")))[1],
            f"Diretor em modo {_normalized_director_decision_mode(options)}; Turbo suspende automaticamente.",
            0.86,
            "smartVisualDirector",
        ),
        _decision_record(
            "health",
            "render" if renderable else "skip",
            "; ".join(ignored_reasons) if ignored_reasons else "Projeto cumpre requisitos para render.",
            confidence / 100.0,
            str(project.get("id") or ""),
        ),
    ]
    if project.get("error"):
        decisions.append(_decision_record(
            "error",
            "recommend_action",
            str(project.get("error") or "")[:240],
            0.74,
            str(project.get("id") or ""),
            actions=recommended_error_actions(str(project.get("error") or ""), project),
        ))

    return {
        "id": project.get("id"),
        "name": project.get("name") or "Projeto",
        "status": project.get("status") or "draft",
        "renderable": renderable,
        "eligible": eligible,
        "healthy": healthy,
        "confidence": confidence,
        "threshold": threshold,
        "missing": missing,
        "ignoredReasons": ignored_reasons,
        "renderPriority": render_priority(options),
        "directorDecisionMode": _normalized_director_decision_mode(options),
        "safeRenderMode": bool(options.get("safeRenderMode")),
        "preflight": compact_preflight_summary(preflight),
        "autoTest": auto_test,
        "decisions": decisions,
    }


def build_queue_preflight_plan(project_ids: list[str] | None = None, mode: str = "all") -> dict[str, Any]:
    requested = {str(item).strip() for item in (project_ids or []) if str(item).strip()}
    with QUEUE_LOCK:
        scoped = [
            project for project in QUEUE_PROJECTS
            if not requested or str(project.get("id") or "") in requested
        ]
        entries = [_project_queue_plan_entry(project, mode) for project in scoped]
    renderable = [item for item in entries if item.get("renderable")]
    ignored = [item for item in entries if not item.get("renderable")]
    plan = {
        "kind": "glide_ultra_queue_preflight_plan",
        "version": APP_VERSION,
        "createdAt": _now_iso(),
        "mode": mode if mode in {"all", "healthy", "selected"} else "all",
        "summary": {
            "total": len(entries),
            "renderable": len(renderable),
            "ignored": len(ignored),
            "healthy": sum(1 for item in entries if item.get("healthy")),
            "averageConfidence": round(sum(float(item.get("confidence") or 0) for item in entries) / max(1, len(entries))),
        },
        "projects": entries,
        "decisions": [
            _decision_record(
                "queue",
                "start" if renderable else "skip",
                f"{len(renderable)} projeto(s) renderizavel(is), {len(ignored)} ignorado(s).",
                0.9 if renderable else 0.6,
                "queue",
            )
        ],
    }
    return plan


def _safe_old_log_files() -> list[Path]:
    files: list[Path] = []
    for root in (DATA_ROOT, SOURCE_ROOT):
        try:
            resolved_root = root.resolve()
        except Exception:
            continue
        for pattern in SAFE_STARTUP_LOG_PATTERNS:
            for path in resolved_root.glob(pattern):
                try:
                    resolved = path.resolve()
                except Exception:
                    continue
                if not resolved.is_file():
                    continue
                if resolved.parent != resolved_root:
                    continue
                files.append(resolved)
    unique: dict[str, Path] = {str(path).lower(): path for path in files}
    return list(unique.values())


def _space_report() -> dict[str, Any]:
    groups = {
        "render_cache": RENDER_GRAPH_CACHE_ROOT,
        "exports": EXPORT_ROOT,
        "temporary_uploads": UPLOAD_ROOT,
        "cta_preview_cache": CTA_CACHE_ROOT,
        "project_media": PROJECT_MEDIA_ROOT,
        "renders_legacy": DATA_ROOT / "renders",
    }
    items = []
    total = 0
    for key, path in groups.items():
        size = path_size(path) if path.exists() else 0
        total += size
        items.append({
            "key": key,
            "path": str(path),
            "exists": path.exists(),
            "bytes": size,
            "label": human_bytes(size),
            "safeActions": (
                ["clear_old_cache"] if key == "render_cache" else
                ["clear_temporaries"] if key in {"temporary_uploads", "cta_preview_cache"} else
                ["clear_old_exports"] if key == "exports" else
                []
            ),
        })
    log_files = _safe_old_log_files()
    log_size = sum(path.stat().st_size for path in log_files if path.exists())
    total += log_size
    items.append({
        "key": "old_logs",
        "path": str(DATA_ROOT),
        "exists": bool(log_files),
        "bytes": log_size,
        "label": human_bytes(log_size),
        "count": len(log_files),
        "safeActions": ["clear_old_logs"],
    })
    return {
        "kind": "glide_ultra_space_report",
        "version": APP_VERSION,
        "createdAt": _now_iso(),
        "totalBytes": total,
        "totalLabel": human_bytes(total),
        "items": items,
    }


def build_render_decisions(job: Job) -> dict[str, Any]:
    preflight = job.preflight_summary or {}
    visual = preflight.get("visual_clean_filter") if isinstance(preflight.get("visual_clean_filter"), dict) else {}
    director = preflight.get("smart_visual_director") if isinstance(preflight.get("smart_visual_director"), dict) else {}
    style_profile = preflight.get("style_profile") if isinstance(preflight.get("style_profile"), dict) else reference_style_profile(job.options)
    confidence = preflight.get("confidence") if isinstance(preflight.get("confidence"), dict) else job.confidence_summary
    decisions = list(((preflight.get("decision_summary") or {}).get("decisions") or []))
    effective_visual = effective_visual_options(job)
    cache_policy = {
        "render_graph": True,
        "reuse_segments": not bool(job.options.get("safeRenderMode")),
        "reuse_audio": True,
        "reuse_composition": True,
    }
    decisions.extend([
        _decision_record(
            "render_priority",
            render_priority(job),
            "Modo de render congelado no inicio do job.",
            0.94,
            "renderPriority",
        ),
        _decision_record(
            "director",
            str(director.get("state") or smart_visual_director_effective(job.options, True)[1]),
            f"Modo de decisao: {_normalized_director_decision_mode(job.options)}.",
            0.86,
            "Diretor Visual Inteligente",
        ),
        _decision_record(
            "visual_filter",
            "enabled" if visual.get("enabled") else "disabled",
            "Rejeicoes incertas viram suspeitas; rejeicao massiva usa guardrail.",
            0.82,
            "Filtro visual",
        ),
        _decision_record(
            "audio_master",
            str(job.options.get("platformMasterProfile") or "youtube_long"),
            "Perfil de masterização escolhido antes do render.",
            0.8,
            "Master",
        ),
        _decision_record(
            "style_source",
            str(style_profile.get("source") or "glide_package"),
            str(style_profile.get("fallbackReason") or "Reference Style DNA domina quando ativo; pacote Glide fica como fallback."),
            0.86,
            str(style_profile.get("referenceName") or (style_profile.get("package") or {}).get("label") or "Estilo"),
        ),
    ])
    if bool(job.options.get("safeRenderMode")):
        decisions.append(_decision_record(
            "safe_render",
            "enabled",
            "Render seguro suspende automacoes arriscadas apenas nesta execucao.",
            0.9,
            "Render seguro",
        ))
    return {
        "kind": "glide_ultra_render_decisions",
        "version": APP_VERSION,
        "jobId": job.id,
        "projectId": job.options.get("queueProjectId"),
        "projectName": job.options.get("queueProjectName"),
        "createdAt": _now_iso(),
        "renderPriority": render_priority(job),
        "safeRenderMode": bool(job.options.get("safeRenderMode")),
        "healthyThreshold": _healthy_threshold(job.options),
        "confidence": confidence if isinstance(confidence, dict) else {},
        "effectiveOptions": {
            "renderPriority": render_priority(job),
            "codec": "h264" if bool(job.options.get("safeRenderMode")) else str(job.options.get("codec") or "hevc"),
            "safeRenderMode": bool(job.options.get("safeRenderMode")),
            "director": {
                "requested": smart_visual_director_requested(job.options),
                "state": str(director.get("state") or smart_visual_director_effective(job.options, True)[1]),
                "decisionMode": _normalized_director_decision_mode(job.options),
            },
            "visual": effective_visual,
            "music": {
                "genre": preset_music_genre(job.options),
                "autoLibrary": bool(job.options.get("backgroundMusicUseLibrary", True)),
                "manualOverride": bool(job.options.get("backgroundMusicManualOverride")),
            },
            "cta": {
                "language": job.options.get("ctaLanguage") or job.options.get("selectedCta"),
                "required": bool(job.options.get("ctaRequired", True)),
                "maxOccurrences": clamp_int(job.options.get("ctaMaxOccurrences"), CTA_OCCURRENCES, 1, 2),
                "placement": "director_contextual_max_2",
            },
            "subtitles": {
                "style": (job.options.get("subtitleStyle") or {}).get("preset") if isinstance(job.options.get("subtitleStyle"), dict) else None,
                "animation": (job.options.get("subtitleStyle") or {}).get("animation") if isinstance(job.options.get("subtitleStyle"), dict) else None,
                "placement": "smart_safe_zones",
            },
            "fx": {
                "autoSoundFx": bool(job.options.get("autoSoundFx", True)),
                "gainDb": float(job.options.get("soundFxGainDb") or 0.0),
            },
            "style": style_profile,
            "cachePolicy": cache_policy,
        },
        "decisions": decisions,
        "risks": list((confidence or {}).get("risks") or []) if isinstance(confidence, dict) else [],
    }


def apply_render_decisions(job: Job) -> None:
    decisions = job.render_decisions if isinstance(job.render_decisions, dict) else {}
    effective = decisions.get("effectiveOptions") if isinstance(decisions.get("effectiveOptions"), dict) else {}
    if not effective:
        return
    job.options["_render_decisions_effective"] = effective
    job.options["_render_decisions_cache_policy"] = effective.get("cachePolicy") or {}
    if isinstance(effective.get("style"), dict):
        job.options["_style_profile_effective"] = effective["style"]
    if bool(effective.get("safeRenderMode")):
        job.options.update({
            "codec": "h264",
            "gpu": False,
            "transitions": "off",
            "zoom": "off",
            "qualityBoost": False,
            "smartVisualDirector": False,
            "autoDirector": False,
            "visualCleanFilter": True,
            "visualFilterLevel": "light",
            "adaptiveVisualFilter": False,
            "dynamicPauses": False,
            "strongMomentEnhance": False,
            "renderRecovery": True,
        })
    director = effective.get("director") if isinstance(effective.get("director"), dict) else {}
    if director:
        job.options["directorDecisionMode"] = _normalized_director_decision_mode({"directorDecisionMode": director.get("decisionMode")})


def _compact_feature_summary(summary: dict[str, Any] | None, limit: int = 8) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, value in dict(summary or {}).items():
        if isinstance(value, list):
            compact[key] = value[:limit]
            if len(value) > limit:
                compact[f"{key}_count"] = len(value)
        elif isinstance(value, dict):
            compact[key] = {
                sub_key: (sub_value[:limit] if isinstance(sub_value, list) else sub_value)
                for sub_key, sub_value in value.items()
            }
        else:
            compact[key] = value
    return compact


def build_editorial_intelligence_plan(job: Job, phase: str = "pre_render") -> dict[str, Any]:
    director = job.director_summary if isinstance(job.director_summary, dict) else {}
    energy = job.energy_summary if isinstance(job.energy_summary, dict) else {}
    anti_repeat = job.anti_repeat_summary if isinstance(job.anti_repeat_summary, dict) else {}
    continuity = job.continuity_summary if isinstance(job.continuity_summary, dict) else {}
    learning = job.learning_summary if isinstance(job.learning_summary, dict) else {}
    visual_index = director.get("visual_index") if isinstance(director.get("visual_index"), dict) else {}
    render_decisions = job.render_decisions if isinstance(job.render_decisions, dict) else {}
    style_profile = ((render_decisions.get("effectiveOptions") or {}).get("style") if isinstance(render_decisions.get("effectiveOptions"), dict) else None)
    if not isinstance(style_profile, dict):
        style_profile = reference_style_profile(job.options)
    scene_rhythm = scene_rhythm_profile_from_style(style_profile)
    decisions: list[dict[str, Any]] = list(render_decisions.get("decisions") or [])
    script_guide = job.options.get("scriptGuidePlan") if isinstance(job.options.get("scriptGuidePlan"), dict) else {}
    script_blocks = script_guide.get("blocks") if isinstance(script_guide.get("blocks"), list) else []
    for block in script_blocks[:24]:
        if not isinstance(block, dict):
            continue
        decisions.append(_decision_record(
            "script_guide_block",
            str(block.get("title") or f"Bloco {block.get('index', '')}").strip() or "Bloco de roteiro",
            str(block.get("reason") or "Roteiro orienta a escolha de cena e elementos no trecho."),
            float(block.get("confidence") or 0.68),
            str(block.get("type") or "roteiro"),
            keywords=block.get("keywords") or [],
            estimated_position=block.get("estimated_position"),
            target_time=block.get("target_time"),
        ))

    assignments = director.get("assignment_preview")
    if not isinstance(assignments, list):
        assignments = []
    for item in assignments[:24]:
        decisions.append(_decision_record(
            "director_clip",
            Path(str(item.get("path") or "")).name or "clipe",
            str(item.get("reason") or "Escolha do Diretor Visual por pontuacao narrativa."),
            float(item.get("confidence") or 0.65),
            str(item.get("role") or "bloco"),
            block=item.get("block"),
            matched_keywords=item.get("matched_keywords") or [],
            matched_categories=item.get("matched_categories") or [],
        ))

    for item in (job.strong_moments_summary or {}).get("moments", [])[:16]:
        if isinstance(item, dict):
            decisions.append(_decision_record(
                "strong_moment",
                str(item.get("action") or "realcar texto"),
                str(item.get("reason") or item.get("pattern") or "Momento forte detectado no SRT."),
                float(item.get("confidence") or 0.7),
                "SRT",
                time=item.get("time"),
                cue_index=item.get("cue_index"),
            ))

    for item in (job.dynamic_pause_summary or {}).get("pauses", [])[:12]:
        if isinstance(item, dict):
            decisions.append(_decision_record(
                "dynamic_pause",
                f"+{float(item.get('duration') or 0.0):.1f}s",
                str(item.get("reason") or "Micro-pausa dinamica aplicada em ponto narrativo forte."),
                float(item.get("confidence") or 0.72),
                "narracao",
                time=item.get("time"),
            ))

    block_map: dict[int, dict[str, Any]] = {}
    for block in director.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        try:
            index = int(block.get("index") or block.get("block") or len(block_map) + 1)
        except Exception:
            index = len(block_map) + 1
        block_map[index] = {
            "block": index,
            "role": block.get("role") or "bloco",
            "start": block.get("start"),
            "end": block.get("end"),
            "keywords": block.get("keywords") or [],
            "shot_duration": block.get("shot_duration"),
        }
    for coverage in director.get("coverage_by_block") or []:
        if not isinstance(coverage, dict):
            continue
        try:
            index = int(coverage.get("block") or 0)
        except Exception:
            index = 0
        if not index:
            continue
        block_map.setdefault(index, {"block": index, "role": coverage.get("role") or "bloco"})
        block_map[index].update({
            "coverage_score": coverage.get("coverage_score"),
            "selected_clips": coverage.get("selected_clips"),
            "matched_keywords": coverage.get("matched_keywords") or [],
            "matched_categories": coverage.get("matched_categories") or [],
        })
    for energy_block in energy.get("block_summary") or []:
        if not isinstance(energy_block, dict):
            continue
        try:
            index = int(energy_block.get("block") or energy_block.get("index") or 0)
        except Exception:
            index = 0
        if not index:
            continue
        block_map.setdefault(index, {"block": index, "role": energy_block.get("role") or "bloco"})
        block_map[index]["energy"] = _compact_feature_summary(energy_block, 4)

    smart_windows = (job.timeline_summary or {}).get("smart_sample_summary")
    if isinstance(smart_windows, dict):
        sample_windows = smart_windows.get("windows") or []
    else:
        sample_windows = job.options.get("_smart_sample_windows") or []
    visual_window_scores = (job.timeline_summary or {}).get("visual_window_scores")
    if not isinstance(visual_window_scores, dict):
        visual_window_scores = {}
    adaptive_quality = (job.timeline_summary or {}).get("adaptive_quality_boost")
    if not isinstance(adaptive_quality, dict):
        adaptive_quality = {}

    plan = {
        "kind": "glide_ultra_editorial_intelligence_plan",
        "version": APP_VERSION,
        "jobId": job.id,
        "projectId": job.options.get("queueProjectId"),
        "projectName": job.options.get("queueProjectName"),
        "createdAt": _now_iso(),
        "phase": phase,
        "renderPriority": render_priority(job),
        "turboSuspendsDirector": render_priority(job) == "max",
        "features": {
            "styleLanguage": _compact_feature_summary(style_profile, 8),
            "scriptGuide": {
                "enabled": bool(script_guide),
                "summary": _compact_feature_summary(script_guide.get("summary") if isinstance(script_guide.get("summary"), dict) else {}, 8),
                "warnings": list(script_guide.get("warnings") or [])[:8] if isinstance(script_guide, dict) else [],
            },
            "sceneRhythm": scene_rhythm,
            "smartVisualDirector": {
                "requested": smart_visual_director_requested(job.options),
                "effective": bool(director.get("enabled")),
                "state": director.get("state") or ("suspenso_turbo" if render_priority(job) == "max" else "pendente"),
                "decisionMode": _normalized_director_decision_mode(job.options),
                "reordered": bool(director.get("reordered")),
                "changedPositions": int(director.get("changed_positions") or 0),
                "sceneFit": _compact_feature_summary(director.get("scene_fit_plan") if isinstance(director.get("scene_fit_plan"), dict) else {}, 8),
            },
            "subtitlePlacement": _compact_feature_summary(job.subtitle_summary.get("smart_layout") if isinstance(job.subtitle_summary, dict) else {}, 8),
            "ctaPlacement": _compact_feature_summary(job.cta_summary, 8),
            "visualSearch": {
                "enabled": bool(job.options.get("semanticVisualIndex", True)),
                "summary": _compact_feature_summary(visual_index, 10),
            },
            "channelLearning": _compact_feature_summary(learning, 8),
            "voiceRhythm": _compact_feature_summary(energy, 8),
            "antiRepeat": _compact_feature_summary(anti_repeat, 8),
            "continuity": _compact_feature_summary(continuity, 8),
            "scoreVisualWindows": _compact_feature_summary(visual_window_scores, 8),
            "adaptiveQualityBoost": _compact_feature_summary(adaptive_quality, 8),
            "ducking": _compact_feature_summary(job.ducking_summary, 8),
            "dynamicPauses": _compact_feature_summary(job.dynamic_pause_summary, 8),
            "strongMoments": _compact_feature_summary(job.strong_moments_summary, 8),
            "music": _compact_feature_summary(job.background_music_summary, 8),
            "soundFx": _compact_feature_summary(job.sound_fx_summary, 8),
        },
        "advancedPolicies": {
            "semanticVisualSearch": "modelo local opcional quando instalado; fallback heuristico sempre ativo",
            "channelMemory": "pesos suaves por canal depois de tres correcoes manuais semelhantes",
            "visualScoreByWindow": "janelas internas cacheadas para usar trechos bons de clipes longos",
            "adaptiveContinuity": "continuidade e boost visual so aplicam filtros quando ha diferenca perceptivel",
            "graphGranularity": "cache separado para validacao, narrativa, indexacao, audio, ASS/SRT, segmentos, CTA alpha, composicao, master e mux",
        },
        "blocks": [block_map[key] for key in sorted(block_map)],
        "sceneRhythm": scene_rhythm,
        "timelineComparison": list(director.get("comparison") or [])[:80],
        "decisions": decisions[:120],
        "smartSample": {
            "enabled": bool(job.options.get("smartSampleBlocks")),
            "windows": sample_windows[:8] if isinstance(sample_windows, list) else [],
            "policy": "intro, meio, momento forte, CTA e final quando disponiveis",
        },
        "performancePolicy": {
            "visualIndexing": "background_low_priority_paused_during_render",
            "frontendPolling": "compact_status_details_on_demand",
            "reportDetails": "loaded_from_last_render_summary",
        },
    }
    return plan


def write_editorial_intelligence_plan(job: Job, phase: str = "pre_render") -> dict[str, Any]:
    plan = build_editorial_intelligence_plan(job, phase)
    job.editorial_intelligence_plan = plan
    job.options["_editorial_intelligence_plan"] = {
        "phase": plan.get("phase"),
        "renderPriority": plan.get("renderPriority"),
        "features": plan.get("features"),
    }
    if job.export_dir:
        atomic_write_text(
            job.export_dir / "editorial_intelligence_plan.json",
            json.dumps(plan, ensure_ascii=False, indent=2),
        )
        if isinstance(plan.get("sceneRhythm"), dict):
            atomic_write_text(
                job.export_dir / "scene_rhythm_plan.json",
                json.dumps({
                    "kind": "glide_scene_rhythm_plan",
                    "version": APP_VERSION,
                    "jobId": job.id,
                    "projectId": job.options.get("queueProjectId"),
                    "projectName": job.options.get("queueProjectName"),
                    "createdAt": plan.get("createdAt"),
                    **plan["sceneRhythm"],
                }, ensure_ascii=False, indent=2),
            )
    return plan


def _reorder_queue_projects(project_ids: list[str]) -> dict[str, Any]:
    current_by_id = {str(item.get("id")): item for item in QUEUE_PROJECTS if item.get("id")}
    seen: set[str] = set()
    ordered: list[dict[str, Any]] = []
    ignored: list[str] = []
    for raw_id in project_ids:
        project_id = str(raw_id or "").strip()
        if not project_id or project_id in seen:
            continue
        project = current_by_id.get(project_id)
        if not project:
            ignored.append(project_id)
            continue
        ordered.append(project)
        seen.add(project_id)
    if not ordered:
        raise HTTPException(status_code=400, detail="Nenhum projeto valido para reordenar")
    remaining = [item for item in QUEUE_PROJECTS if str(item.get("id")) not in seen]
    QUEUE_PROJECTS[:] = ordered + remaining
    _save_queue_projects(QUEUE_PROJECTS)
    return {
        "ok": True,
        "ignored": ignored,
        "projects": [_public_queue_project(item) for item in QUEUE_PROJECTS],
    }


def _sanitize_queue_project_backup(item: dict[str, Any], index: int = 0) -> dict[str, Any]:
    project = _default_queue_project(str(item.get("name") or f"Projeto {index + 1}"))
    raw_id = str(item.get("id") or "").strip()
    if raw_id:
        project["id"] = safe_folder_component(raw_id, project["id"])[:40] or project["id"]
    project["status"] = str(item.get("status") or "draft")
    if project["status"] not in {"draft", "ready", "queued", "rendering", "paused", "cancelled", "done", "recovered", "error"}:
        project["status"] = "draft"
    media = item.get("media") if isinstance(item.get("media"), dict) else {}
    project["media"] = {
        "videos": [str(path) for path in (media.get("videos") or []) if str(path).strip()],
        "audios": [str(path) for path in (media.get("audios") or []) if str(path).strip()],
        "background_music": [str(path) for path in (media.get("background_music") or []) if str(path).strip()],
        "texts": [str(path) for path in (media.get("texts") or media.get("subtitles") or []) if str(path).strip()],
        "captions": [str(path) for path in (media.get("captions") or []) if str(path).strip()],
        "script_guides": [str(path) for path in (media.get("script_guides") or media.get("scriptGuide") or []) if str(path).strip()],
    }
    if isinstance(item.get("options"), dict):
        project["options"] = item["options"]
    if isinstance(item.get("subtitleInfo"), dict):
        project["subtitleInfo"] = item["subtitleInfo"]
    if isinstance(item.get("captionInfo"), dict):
        project["captionInfo"] = item["captionInfo"]
    if isinstance(item.get("scriptGuideInfo"), dict):
        project["scriptGuideInfo"] = item["scriptGuideInfo"]
    if isinstance(item.get("scriptGuidePlan"), dict):
        project["scriptGuidePlan"] = item["scriptGuidePlan"]
    if str(item.get("musicGenre") or "").lower() in PRESET_MUSIC_GENRES:
        project["musicGenre"] = str(item["musicGenre"]).lower()
    for key in (
        "outputName", "outputFile", "outputDir", "jobId", "error", "estimatedSize",
        "lastRenderSummary", "directorState", "timelineHistory", "confidenceSummary",
        "audioMasterSummary", "renderGraphRun", "createdAt", "updatedAt",
        "retryCount", "retryHistory",
    ):
        if key in item:
            project[key] = item[key]
    if isinstance(item.get("referenceStyleVideo"), dict):
        project["referenceStyleVideo"] = item["referenceStyleVideo"]
        project.setdefault("options", {})["referenceStyleVideo"] = item["referenceStyleVideo"]
    project["updatedAt"] = _now_iso()
    return project


def _public_queue_project(project: dict[str, Any]) -> dict[str, Any]:
    media = project.get("media") if isinstance(project.get("media"), dict) else {}
    options = dict(project.get("options") if isinstance(project.get("options"), dict) else {})
    if isinstance(project.get("referenceStyleVideo"), dict):
        options["referenceStyleVideo"] = _public_reference_style(project.get("referenceStyleVideo"))
    return {
        "id": project.get("id"),
        "name": project.get("name") or "Projeto",
        "status": project.get("status") or "draft",
        "media": {
            "videos": list(media.get("videos") or []),
            "audios": list(media.get("audios") or []),
            "background_music": list(media.get("background_music") or []),
            "texts": list(media.get("texts") or media.get("subtitles") or []),
            "captions": list(media.get("captions") or []),
            "script_guides": list(media.get("script_guides") or []),
        },
        "referenceStyleVideo": _public_reference_style(project.get("referenceStyleVideo")),
        "options": options,
        "subtitleInfo": project.get("subtitleInfo") if isinstance(project.get("subtitleInfo"), dict) else None,
        "captionInfo": project.get("captionInfo") if isinstance(project.get("captionInfo"), dict) else None,
        "scriptGuideInfo": project.get("scriptGuideInfo") if isinstance(project.get("scriptGuideInfo"), dict) else None,
        "scriptGuidePlan": project.get("scriptGuidePlan") if isinstance(project.get("scriptGuidePlan"), dict) else None,
        "musicGenre": project.get("musicGenre") or "cinematic",
        "outputName": project.get("outputName") or "",
        "outputFile": project.get("outputFile"),
        "outputDir": project.get("outputDir"),
        "jobId": project.get("jobId"),
        "error": project.get("error"),
        "estimatedSize": project.get("estimatedSize"),
        "lastRenderSummary": project.get("lastRenderSummary") if isinstance(project.get("lastRenderSummary"), dict) else None,
        "directorState": project.get("directorState") if isinstance(project.get("directorState"), dict) else None,
        "timelineHistory": list(project.get("timelineHistory") or [])[-10:],
        "confidenceSummary": project.get("confidenceSummary") if isinstance(project.get("confidenceSummary"), dict) else None,
        "audioMasterSummary": project.get("audioMasterSummary") if isinstance(project.get("audioMasterSummary"), dict) else None,
        "renderGraphRun": project.get("renderGraphRun") if isinstance(project.get("renderGraphRun"), dict) else None,
        "retryCount": int(project.get("retryCount") or 0),
        "retryHistory": list(project.get("retryHistory") or [])[-12:],
        "createdAt": project.get("createdAt"),
        "updatedAt": project.get("updatedAt"),
    }


def build_auto_fix_plan(
    files_manifest: list[dict[str, Any]],
    options: dict[str, Any],
    counts: dict[str, int],
    warnings: list[str],
    errors: list[str],
    tone_summary: dict[str, Any],
) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []

    def add(action: str, label: str, severity: str, reason: str, value: Any | None = None):
        actions.append({
            "action": action,
            "label": label,
            "severity": severity,
            "reason": reason,
            "value": value,
        })

    if counts.get("video", 0) > 0:
        add("sort_videos", "Ordenar videos por numero", "safe", "Evita timeline embaralhada quando os clipes vem numerados.")
    if counts.get("audio", 0) > 0:
        add("sort_audio", "Ordenar narracao por numero", "safe", "Mantem partes da voz na sequencia correta.")
    if not bool(options.get("voiceNormalize", True)):
        add("enable_voice_normalize", "Ativar voz nivelada", "safe", "Reduz diferencas de volume entre partes da narracao.")
    if not bool(options.get("qualityBoost", True)):
        add("enable_quality_boost", "Ativar Quality Boost natural", "safe", "Ajuda clipes fracos sem mexer em CTA/legendas.")
    if not bool(options.get("renderRecovery", True)):
        add("enable_render_recovery", "Ativar recuperacao de render", "safe", "Tenta H.264/CPU ou pula clipe suspeito se o render falhar.")
    bitrate = clamp_float(options.get("videoBitrateKbps"), 2500.0, 500.0, 25000.0)
    mode = str(options.get("mode") or "standard")
    codec = str(options.get("codec") or "hevc")
    cap = 4200.0 if mode != "fast" else 2200.0
    if codec == "h264":
        cap += 1300.0
    if bitrate > cap:
        add("cap_bitrate", "Corrigir bitrate exagerado", "safe", f"{int(bitrate)} kbps pode gerar arquivo pesado; ajuste sugerido {int(cap)} kbps.", int(cap))
    cta_language = str(options.get("ctaLanguage") or "").strip().lower()
    if CTA_REQUIRED and cta_language not in CTA_LANGUAGES:
        lang = infer_language_hint(options, files_manifest)
        add("set_cta", "Escolher CTA compatível", "needed", f"CTA obrigatório ausente; idioma sugerido por nomes/metadados: {lang.upper()}.", lang)
    if counts.get("background_music", 0) <= 0 and bool(options.get("backgroundMusicUseLibrary", True)):
        add("refresh_auto_music", "Trocar musica automatica recente", "safe", f"Usar biblioteca {options.get('backgroundMusicGenre') or 'cinematic'} com tom {tone_summary.get('tone')}.")
    if warnings:
        add("review_warnings", "Registrar avisos no relatorio", "info", "O render continua, mas os avisos ficam documentados.")
    return {
        "available": bool(actions),
        "actions": actions,
        "safe_count": sum(1 for item in actions if item.get("severity") == "safe"),
        "needed_count": sum(1 for item in actions if item.get("severity") == "needed"),
    }


def estimate_output_bytes(options: dict[str, Any], duration_seconds: float) -> int:
    duration = max(0.0, float(duration_seconds or 0.0))
    bitrate = clamp_float(options.get("videoBitrateKbps"), 2500.0, 500.0, 25000.0)
    audio_kbps = 160.0
    return int(((bitrate + audio_kbps) * 1000 / 8) * duration * 1.04)


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


@app.get("/favicon.ico")
def favicon():
    return FileResponse(ASSETS / "glide_studio.ico", media_type="image/x-icon")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "version": APP_VERSION,
        "ffmpeg": FFMPEG or None,
        "ffprobe": FFPROBE or None,
        "root": str(SOURCE_ROOT),
        "resources": str(RESOURCE_ROOT),
        "data_root": str(DATA_ROOT),
        "exports": str(EXPORT_ROOT),
        "downloads": str(default_downloads_dir()),
        "desktop": bool(getattr(sys, "frozen", False) or os.environ.get("GLIDE_ULTRA_DESKTOP")),
        "safe_engine": "segmentado/baixo uso de memoria",
        "visual_face_detector": yunet_detector_status(),
        "startup_cleanup": STARTUP_CLEANUP_SUMMARY,
    }


@app.post("/api/maintenance/clean-safe")
def maintenance_clean_safe():
    global STARTUP_CLEANUP_SUMMARY
    STARTUP_CLEANUP_SUMMARY = safe_startup_cleanup()
    return {"ok": True, "cleanup": STARTUP_CLEANUP_SUMMARY}


@app.post("/api/maintenance/prepare-shutdown")
def maintenance_prepare_shutdown():
    return {"ok": True, "cleanup": safe_shutdown_cleanup()}


class DropzoneManager:
    def __init__(self, root: Path = DROPZONE_ROOT, poll_interval: float = 6.0):
        self.root = root
        self.poll_interval = poll_interval
        self.enabled = True
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._processed_folders: set[str] = set()

    def start(self):
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            DROPZONE_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="DropzoneWatcher", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def scan_now(self) -> dict[str, Any]:
        return self._scan_directory()

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                if self.enabled:
                    self._scan_directory()
            except Exception:
                pass
            self._stop_event.wait(self.poll_interval)

    def _scan_directory(self) -> dict[str, Any]:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        discovered = []
        ingested = []

        try:
            subdirs = [p for p in self.root.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))]
        except Exception:
            subdirs = []

        for folder in subdirs:
            folder_key = str(folder.resolve()).lower()
            if folder_key in self._processed_folders:
                continue

            try:
                files = [p for p in folder.rglob("*") if p.is_file() and not p.name.startswith(".")]
            except Exception:
                files = []

            if not files:
                continue

            now = time.time()
            mtimes = [p.stat().st_mtime for p in files if p.exists()]
            if not mtimes:
                continue
            latest_mtime = max(mtimes)
            if (now - latest_mtime) < 2.5:
                continue

            discovered.append(folder.name)
            project_id = self._ingest_folder(folder, files)
            if project_id:
                self._processed_folders.add(folder_key)
                ingested.append({"folder": folder.name, "project_id": project_id})

        return {
            "enabled": self.enabled,
            "dropzone_dir": str(self.root),
            "output_dir": str(DROPZONE_OUTPUT_ROOT),
            "discovered_folders": len(discovered),
            "ingested_projects": ingested,
        }

    def _ingest_folder(self, folder: Path, files: list[Path]) -> str | None:
        audio_exts = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
        srt_exts = {".srt"}
        video_exts = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
        img_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
        script_exts = SCRIPT_GUIDE_EXTS

        audio_files = []
        srt_files = []
        media_files = []
        script_files = []

        for p in files:
            ext = p.suffix.lower()
            if ext in audio_exts:
                audio_files.append(p)
            elif ext in srt_exts:
                srt_files.append(p)
            elif ext in video_exts or ext in img_exts:
                media_files.append(p)
            elif ext in script_exts:
                script_files.append(p)

        if not audio_files or not media_files:
            return None

        media_files.sort(key=lambda p: natural_key(p.name))
        voiceover = audio_files[0]
        srt_path = srt_files[0] if srt_files else None
        script_path = script_files[0] if script_files else None

        project_name = folder.name.replace("_", " ").title()
        project_id = f"p_drop_{uuid.uuid4().hex[:8]}"

        script_plan = None
        if script_path:
            try:
                cues = parse_srt_file(srt_path) if srt_path else []
                script_plan = analyze_script_guide(script_path, project_id=project_id, rel=script_path.name, srt_cues=cues)
            except Exception:
                script_plan = None

        payload = {
            "id": project_id,
            "name": project_name,
            "status": "ready",
            "createdAt": _now_iso(),
            "updatedAt": _now_iso(),
            "source_folder": str(folder.resolve()),
            "media": {
                "voiceover": str(voiceover.resolve()),
                "subtitles": str(srt_path.resolve()) if srt_path else None,
                "videos": [str(m.resolve()) for m in media_files],
                "script_guides": [str(script_path.resolve())] if script_path else [],
            },
            "options": {
                "aspectRatio": "16:9",
                "qualityBoost": True,
                "allowAudioTrim": True,
                "scoreVisualWindows": True,
                "autoHeal": True,
                "scriptGuidePlan": script_plan,
            },
        }

        with QUEUE_LOCK:
            if not any(p.get("source_folder") == str(folder.resolve()) for p in QUEUE_PROJECTS):
                QUEUE_PROJECTS.append(payload)
                _save_queue_projects(QUEUE_PROJECTS)
                return project_id
        return None


DROPZONE_MANAGER = DropzoneManager()


@app.on_event("startup")
def application_startup_init():
    DROPZONE_MANAGER.start()


@app.get("/api/dropzone/status")
def api_dropzone_status():
    return DROPZONE_MANAGER.scan_now()


@app.post("/api/dropzone/toggle")
def api_dropzone_toggle(payload: dict[str, Any] | None = Body(None)):
    data = payload or {}
    if "enabled" in data:
        DROPZONE_MANAGER.enabled = bool(data["enabled"])
    else:
        DROPZONE_MANAGER.enabled = not DROPZONE_MANAGER.enabled
    return {"ok": True, "enabled": DROPZONE_MANAGER.enabled}


@app.post("/api/dropzone/scan_now")
def api_dropzone_scan_now():
    return DROPZONE_MANAGER.scan_now()


@app.on_event("shutdown")
def application_shutdown_cleanup():
    DROPZONE_MANAGER.stop()
    safe_shutdown_cleanup()


def _read_render_performance() -> list[dict[str, Any]]:
    with RENDER_PERFORMANCE_LOCK:
        try:
            payload = json.loads(RENDER_PERFORMANCE_FILE.read_text(encoding="utf-8"))
            records = payload.get("records") if isinstance(payload, dict) else payload
            return [item for item in (records or []) if isinstance(item, dict)][-80:]
        except Exception:
            return []


def _positive_median(values: list[float]) -> float:
    clean = sorted(float(value) for value in values if float(value) > 0)
    if not clean:
        return 0.0
    middle = len(clean) // 2
    if len(clean) % 2:
        return clean[middle]
    return (clean[middle - 1] + clean[middle]) / 2.0


def render_mode_label(priority: str | None) -> str:
    normalized = str(priority or "").lower()
    if normalized == "max":
        return "Turbo Produção"
    if normalized == "quality":
        return "Qualidade Máxima"
    return "Eficiente Inteligente"


def render_budget_enabled(options: dict[str, Any] | None = None) -> bool:
    if isinstance(options, dict) and "renderBudgetEnabled" in options:
        return bool(options.get("renderBudgetEnabled"))
    return True


def render_budget_multiplier(priority: str | None, options: dict[str, Any] | None = None) -> float:
    if not render_budget_enabled(options):
        return 0.0
    normalized = str(priority or "").lower()
    if normalized == "max":
        return max(2.0, min(8.0, float((options or {}).get("renderBudgetTurboMultiplier") or 4.0)))
    if normalized == "quality":
        return max(5.0, min(16.0, float((options or {}).get("renderBudgetQualityMultiplier") or 8.0)))
    return max(3.5, min(10.0, float((options or {}).get("renderBudgetEfficientMultiplier") or 6.0)))


def render_budget_for_duration(duration_seconds: Any, priority: str | None, options: dict[str, Any] | None = None) -> float:
    if not render_budget_enabled(options):
        return 0.0
    try:
        duration = max(1.0, float(duration_seconds or 0.0))
    except Exception:
        duration = 1.0
    return duration * render_budget_multiplier(priority, options)


def render_hardware_signature(profile: dict[str, Any] | None = None) -> str:
    hw = profile or hardware_profile()
    return stable_hash({
        "cpu": int(hw.get("cpu_count") or 0),
        "ram": round(float(hw.get("ram_gb") or 0.0), 1),
        "gpu": str(hw.get("preferred_gpu") or ""),
        "acceleration": str(hw.get("acceleration") or ""),
        "encoders": sorted(key for key, enabled in (hw.get("encoders") or {}).items() if enabled),
    })[:16]


def render_budget_remaining(job: Job) -> float:
    if not job.render_deadline_at:
        return float("inf")
    return max(0.0, job.render_deadline_at - time.time())


def render_budget_elapsed(job: Job) -> float:
    return max(0.0, time.time() - float(job.started_at or time.time()))


def assert_render_budget(job: Job, stage: str) -> None:
    if not render_budget_enabled(job.options):
        return
    if job.render_deadline_at and time.time() >= job.render_deadline_at:
        grace_extension = max(120.0, float(job.render_budget_seconds or 300.0) * 0.5)
        job.render_budget_seconds += grace_extension
        job.render_deadline_at += grace_extension
        job.render_budget_state = "extended"
        if "budget_auto_extended" not in job.render_budget_fallbacks:
            job.render_budget_fallbacks.append("budget_auto_extended")
        _append_log(
            job,
            f"Proteção de tempo adaptativa: render em andamento durante {stage}. "
            f"Limite estendido automaticamente em +{round(grace_extension)}s para garantir a conclusão do vídeo."
        )


def budget_allows_optional(job: Job, predicted_seconds: float, reserve_ratio: float = 0.55) -> bool:
    if not job.render_budget_seconds or not job.started_at:
        return True
    mandatory_reserve = max(18.0, job.render_budget_seconds * max(0.25, min(0.80, reserve_ratio)))
    allowed = render_budget_remaining(job) - mandatory_reserve
    if allowed >= max(0.0, predicted_seconds):
        return True
    job.render_budget_state = "protecting"
    return False


def render_time_estimate(duration_seconds: Any, options: dict[str, Any], priority_override: str | None = None) -> dict[str, Any]:
    try:
        duration = max(1.0, float(duration_seconds or 0.0))
    except Exception:
        duration = 1.0
    priority = render_priority({**options, "renderPriority": priority_override or options.get("renderPriority")})
    mode = str(options.get("mode") or "standard").lower()
    codec = "h264" if str(options.get("codec") or "hevc").lower() == "h264" else "hevc"
    gpu_requested = bool(options.get("gpu", False))
    hw = hardware_profile()
    hardware_encoder = (
        hw.get("recommended_h264_encoder" if codec == "h264" else "recommended_hevc_encoder")
        if (gpu_requested or priority in {"balanced", "max", "quality"})
        else None
    )
    gpu_effective = bool(hardware_encoder)
    perf = str(hw.get("performance_class") or "medium")
    perf_factor = {"high": 0.82, "medium": 1.0, "low": 1.22}.get(perf, 1.0)
    cpu_count = max(1, int(hw.get("cpu_count") or os.cpu_count() or 1))

    # Forecast all full-duration stages. The previous model mostly estimated
    # clip encoding, then clamped the answer to the budget and hid CTA/SRT,
    # sound design, mastering and mux costs.
    nvidia_factor = 0.94 if gpu_effective and str(hw.get("acceleration") or "").startswith("NVIDIA") else 1.0
    encode_factor = perf_factor * nvidia_factor * (1.0 if gpu_effective else 1.72)
    if priority == "max":
        stage_forecast: dict[str, float] = {
            "audio": 10.0 + duration * 0.045 * perf_factor,
            "direction": 1.0,
            "subtitles_ass": 4.0 + duration * 0.008,
            "visual_analysis": 8.0 + duration * 0.025 * perf_factor,
            "segments": 12.0 + duration * 0.16 * encode_factor,
            "concat": 5.0 + duration * 0.018,
            "sound_fx": (10.0 + duration * 0.045 * perf_factor) if bool(options.get("autoSoundFx", True)) else 0.0,
            "composition": 8.0 + duration * 0.17 * encode_factor,
            "mastering": (6.0 + duration * 0.11 * perf_factor) if bool(options.get("audioMastering", True)) else 0.0,
            "mux": 4.0 + duration * 0.018,
            "delivery": 5.0,
        }
        fixed_seconds = 10.0
    elif priority == "quality":
        director_active = bool(options.get("smartVisualDirector", True))
        stage_forecast = {
            "audio": 14.0 + duration * 0.060 * perf_factor,
            "direction": (24.0 + duration * 0.15 * perf_factor) if director_active else 2.0,
            "subtitles_ass": 6.0 + duration * 0.012,
            "visual_analysis": 22.0 + duration * 0.105 * perf_factor,
            "segments": 20.0 + duration * 0.34 * encode_factor,
            "concat": 7.0 + duration * 0.026,
            "sound_fx": (14.0 + duration * 0.060 * perf_factor) if bool(options.get("autoSoundFx", True)) else 0.0,
            "composition": 13.0 + duration * 0.26 * encode_factor,
            "mastering": (9.0 + duration * 0.15 * perf_factor) if bool(options.get("audioMastering", True)) else 0.0,
            "mux": 6.0 + duration * 0.024,
            "delivery": 7.0,
        }
        if bool(options.get("qualityBoost", True)):
            stage_forecast["segments"] *= 1.12
        if bool(options.get("scoreVisualWindows", True)):
            stage_forecast["visual_analysis"] *= 1.14
        if str(options.get("zoom") or "off") != "off":
            stage_forecast["segments"] *= 1.06
        if str(options.get("transitions") or "off") != "off":
            stage_forecast["segments"] *= 1.06
        fixed_seconds = 18.0
    else:
        director_active = bool(options.get("smartVisualDirector", True))
        stage_forecast = {
            "audio": 12.0 + duration * 0.055 * perf_factor,
            "direction": (18.0 + duration * 0.11 * perf_factor) if director_active else 1.0,
            "subtitles_ass": 5.0 + duration * 0.010,
            "visual_analysis": 16.0 + duration * 0.075 * perf_factor,
            "segments": 16.0 + duration * 0.29 * encode_factor,
            "concat": 6.0 + duration * 0.024,
            "sound_fx": (12.0 + duration * 0.050 * perf_factor) if bool(options.get("autoSoundFx", True)) else 0.0,
            "composition": 10.0 + duration * 0.22 * encode_factor,
            "mastering": (7.0 + duration * 0.12 * perf_factor) if bool(options.get("audioMastering", True)) else 0.0,
            "mux": 5.0 + duration * 0.022,
            "delivery": 6.0,
        }
        if mode == "fast":
            stage_forecast["segments"] *= 0.84
            stage_forecast["composition"] *= 0.90
        if bool(options.get("qualityBoost", True)):
            stage_forecast["segments"] *= 1.08
        if str(options.get("zoom") or "off") != "off":
            stage_forecast["segments"] *= 1.05
        if str(options.get("transitions") or "off") != "off":
            stage_forecast["segments"] *= 1.04
        fixed_seconds = 14.0

    hardware_sig = render_hardware_signature(hw)
    matching: list[float] = []
    stage_samples: dict[str, list[float]] = {}
    for item in _read_render_performance():
        if str(item.get("pipeline") or "") != RENDER_PERFORMANCE_VERSION:
            continue
        if str(item.get("priority")) != priority or str(item.get("mode")) != mode:
            continue
        recorded_signature = str(item.get("hardware_signature") or "")
        if recorded_signature and recorded_signature != hardware_sig:
            continue
        if str(item.get("codec") or codec).lower() != codec:
            continue
        value = item.get("realtime_factor")
        try:
            if 0.05 <= float(value) <= 12.0:
                matching.append(float(value))
        except Exception:
            continue
        rendered = max(1.0, float(item.get("duration_seconds") or duration))
        for key, seconds_value in (item.get("breakdown") or {}).items():
            if key == "total":
                continue
            try:
                stage_samples.setdefault(str(key), []).append(float(seconds_value) / rendered)
            except Exception:
                continue
    historical_rtf = _positive_median(matching[-12:])
    confidence = "historical" if len(matching) >= 2 else "heuristic"
    for key, values in stage_samples.items():
        if not values:
            continue
        historical_stage = duration * _positive_median(values[-12:])
        if historical_stage > 0:
            stage_forecast[key] = historical_stage * 0.68 + float(stage_forecast.get(key) or 0.0) * 0.32
    heuristic_seconds = fixed_seconds + sum(max(0.0, value) for value in stage_forecast.values())
    historical_seconds = duration * historical_rtf if historical_rtf else 0.0
    seconds = (
        historical_seconds * 0.72 + heuristic_seconds * 0.28
        if historical_seconds > 0
        else heuristic_seconds
    )
    seconds = max(20.0, seconds)
    effective_rtf = seconds / duration
    spread = 0.22 if confidence == "historical" else 0.34
    budget_seconds = render_budget_for_duration(duration, priority, options)
    minimum_required_rtf = (
        0.52 if priority == "max" and gpu_effective
        else 0.82 if priority == "max"
        else 1.45 if priority == "quality" and gpu_effective
        else 2.25 if priority == "quality"
        else 1.12 if gpu_effective
        else 1.72
    )
    minimum_required = duration * minimum_required_rtf + (8.0 if priority == "max" else 20.0 if priority == "quality" else 14.0)
    budget_active = render_budget_enabled(options)
    feasible = True if not budget_active else minimum_required <= budget_seconds
    projected_seconds = seconds
    minimum_seconds = max(15.0, projected_seconds * (1.0 - spread))
    maximum_seconds = projected_seconds * (1.0 + spread)
    if budget_active and feasible and projected_seconds <= budget_seconds:
        maximum_seconds = min(budget_seconds, maximum_seconds)
    budget_risk = (
        "disabled" if not budget_active
        else
        "blocked" if not feasible
        else "high" if projected_seconds > budget_seconds
        else "attention" if projected_seconds > budget_seconds * 0.82
        else "low"
    )
    return {
        "priority": priority,
        "label": render_mode_label(priority),
        "seconds": round(projected_seconds),
        "minimum_seconds": round(minimum_seconds),
        "maximum_seconds": round(maximum_seconds),
        "realtime_factor": round(effective_rtf, 3),
        "confidence": confidence,
        "history_samples": len(matching),
        "stage_forecast": {
            key: round(value, 1)
            for key, value in stage_forecast.items()
            if value > 0
        },
        "budget_seconds": round(budget_seconds),
        "budget_multiplier": render_budget_multiplier(priority, options),
        "budget_enabled": budget_active,
        "budget_feasible": feasible,
        "minimum_required_seconds": round(minimum_required),
        "budget_risk": budget_risk,
        "hardware_signature": hardware_sig,
        "gpu_effective": gpu_effective,
        "hardware_encoder": hardware_encoder,
        "hardware_acceleration": hw.get("acceleration"),
        "hardware_class": perf,
        "hardware_label": hw.get("preferred_gpu") or hw.get("cpu_name") or hw.get("acceleration"),
        "cpu_count": cpu_count,
        "ram_gb": hw.get("ram_gb"),
        "mode": mode,
        "codec": codec,
    }


def record_render_performance(job: Job, rendered_duration: float) -> None:
    if not job.started_at or not job.finished_at or rendered_duration <= 0:
        return
    elapsed = max(0.1, job.finished_at - job.started_at)
    hw = hardware_profile()
    record = {
        "at": _now_iso(),
        "version": APP_VERSION,
        "pipeline": RENDER_PERFORMANCE_VERSION,
        "project_id": str(job.options.get("queueProjectId") or ""),
        "project_name": str(job.options.get("queueProjectName") or job.options.get("outputName") or ""),
        "priority": render_priority(job),
        "mode": str(job.options.get("mode") or "standard").lower(),
        "codec": str(job.timeline_summary.get("codec_effective") or job.options.get("codec") or "hevc").lower(),
        "gpu": (
            bool(job.turbo_summary.get("gpu_effective"))
            if turbo_enabled(job)
            else bool(job.timeline_summary.get("gpu_effective") or job.options.get("gpu", False))
        ),
        "duration_seconds": round(rendered_duration, 3),
        "elapsed_seconds": round(elapsed, 3),
        "realtime_factor": round(elapsed / rendered_duration, 4),
        "hardware_signature": render_hardware_signature(hw),
        "hardware_acceleration": hw.get("acceleration"),
        "breakdown": dict(job.performance_breakdown),
        "budget_seconds": round(float(job.render_budget_seconds or 0.0), 3),
        "budget_state": job.render_budget_state,
        "budget_met": bool(not job.render_budget_seconds or elapsed <= job.render_budget_seconds),
        "budget_fallbacks": list(job.render_budget_fallbacks),
        "safe_render": bool(job.options.get("safeRenderMode")),
        "render_graph": {
            "processed": int((job.render_graph_run.get("counts") or {}).get("processed") or 0) if isinstance(job.render_graph_run, dict) else 0,
            "reused": int((job.render_graph_run.get("counts") or {}).get("reused") or 0) if isinstance(job.render_graph_run, dict) else 0,
        },
    }
    with RENDER_PERFORMANCE_LOCK:
        records = _read_render_performance()
        records.append(record)
        try:
            atomic_write_text(
                RENDER_PERFORMANCE_FILE,
                json.dumps({"version": APP_VERSION, "records": records[-80:]}, ensure_ascii=False, indent=2),
            )
        except Exception:
            pass


def performance_history_for_project(project_id: str | None, limit: int = 12) -> list[dict[str, Any]]:
    project_id = str(project_id or "").strip()
    if not project_id:
        return []
    rows = [
        item for item in _read_render_performance()
        if str(item.get("project_id") or "") == project_id
    ]
    return rows[-max(1, int(limit)):]


@app.get("/api/config")
def app_config():
    bundle = load_config_bundle(ASSETS, APP_VERSION)
    bundle["cta_languages"] = [
        {"key": key, "label": value.get("label"), "source": value.get("source")}
        for key, value in CTA_LANGUAGES.items()
    ]
    bundle["music"] = {
        "default": "cinematic",
        "genres": list(PRESET_MUSIC_GENRES.keys()),
        "history_file": str(MUSIC_HISTORY_FILE),
    }
    bundle["output"] = {
        "defaultMode": "downloads",
        "downloadsFolder": str(default_downloads_dir()),
        "modes": ["downloads", "custom", "browser_download"],
    }
    bundle["settings"] = _load_app_settings()
    bundle["hardware"] = hardware_profile_quick()
    return bundle


@app.post("/api/render-estimate")
def render_estimate(payload: dict[str, Any] = Body(default={})):
    options = apply_render_execution_profile(payload.get("options") if isinstance(payload.get("options"), dict) else {})
    duration = payload.get("durationSeconds") or 0
    hw = hardware_profile()
    return {
        "duration_seconds": duration,
        "hardware": hw,
        "balanced": render_time_estimate(duration, options, "balanced"),
        "max": render_time_estimate(duration, options, "max"),
        "quality": render_time_estimate(duration, options, "quality"),
    }


@app.get("/api/hardware-profile")
def api_hardware_profile():
    return hardware_profile()


@app.get("/api/intelligence/model")
def intelligence_model_status():
    return semantic_model_status()


@app.post("/api/intelligence/model/install")
async def intelligence_model_install(file: UploadFile = File(...)):
    filename = str(file.filename or "mobileclip.zip")
    if Path(filename).suffix.lower() != ".zip":
        raise HTTPException(status_code=400, detail="Envie um pacote .zip do modelo local.")
    staging = MODEL_PACK_ROOT.parent / f".mobileclip-{uuid.uuid4().hex}.tmp"
    archive = MODEL_PACK_ROOT.parent / f".mobileclip-{uuid.uuid4().hex}.zip"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    try:
        with archive.open("wb") as handle:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
        with zipfile.ZipFile(archive) as bundle:
            allowed = {".onnx", ".json", ".txt"}
            for info in bundle.infolist():
                if info.is_dir():
                    continue
                source_name = Path(info.filename)
                if source_name.suffix.lower() not in allowed:
                    continue
                destination = staging / source_name.name
                destination.write_bytes(bundle.read(info))
        if not (staging / "model.onnx").exists() or not (staging / "labels.json").exists():
            raise HTTPException(
                status_code=400,
                detail="Pacote invalido: sao obrigatorios model.onnx e labels.json.",
            )
        old = MODEL_PACK_ROOT.parent / f".mobileclip-old-{uuid.uuid4().hex}"
        if MODEL_PACK_ROOT.exists():
            os.replace(MODEL_PACK_ROOT, old)
        os.replace(staging, MODEL_PACK_ROOT)
        shutil.rmtree(old, ignore_errors=True)
        return {"ok": True, "status": semantic_model_status()}
    finally:
        archive.unlink(missing_ok=True)
        shutil.rmtree(staging, ignore_errors=True)


@app.post("/api/intelligence/visual-index/{project_id}/background")
def intelligence_visual_index_background(project_id: str):
    with QUEUE_LOCK:
        project = _find_queue_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto da fila nao encontrado.")
    return schedule_project_visual_index(project_id)


@app.get("/api/intelligence/cache")
def intelligence_cache_status():
    stats = INTELLIGENCE_DB.render_cache_stats()
    return {
        **stats,
        "total_human": human_bytes(int(stats.get("total_bytes") or 0)),
        "limit_bytes": 20 * 1024 * 1024 * 1024,
        "limit_human": "20 GB",
        "retention_days": 14,
        "path": str(RENDER_GRAPH_CACHE_ROOT),
    }


@app.delete("/api/intelligence/cache")
def intelligence_cache_clear():
    if any(job.status == "running" for job in JOBS.values()):
        raise HTTPException(status_code=409, detail="Aguarde o render terminar antes de limpar o cache.")
    rows = INTELLIGENCE_DB.clear_render_nodes()
    reclaimed = 0
    for row in rows:
        folder = Path(str(row.get("artifact_dir") or ""))
        reclaimed += int(row.get("size_bytes") or 0)
        try:
            resolved = folder.resolve()
            if resolved == RENDER_GRAPH_CACHE_ROOT or RENDER_GRAPH_CACHE_ROOT in resolved.parents:
                shutil.rmtree(resolved, ignore_errors=True)
        except Exception:
            continue
    return {"ok": True, "nodes": len(rows), "reclaimed_bytes": reclaimed, "reclaimed": human_bytes(reclaimed)}


@app.get("/api/intelligence/render-graph/{job_id}")
def intelligence_render_graph(job_id: str):
    job = JOBS.get(job_id)
    if job:
        return job.render_graph_run or {"job_id": job_id, "status": job.status, "nodes": []}
    stored = INTELLIGENCE_DB.get_graph_run(job_id)
    if not stored:
        raise HTTPException(status_code=404, detail="Execucao do grafo nao encontrada.")
    return stored.get("run") or {}


@app.get("/api/intelligence/learning/{channel}")
def intelligence_learning(channel: str):
    return {"channel": channel, "preferences": INTELLIGENCE_DB.preferences(channel)}


@app.post("/api/intelligence/learning/{channel}/correction")
def intelligence_record_correction(channel: str, payload: dict[str, Any] = Body(default={})):
    if str(payload.get("source") or "user") != "user":
        return {"ignored": True, "reason": "Correcoes automaticas nao alimentam o aprendizado."}
    event_type = str(payload.get("eventType") or "").strip()
    if not event_type:
        raise HTTPException(status_code=400, detail="eventType obrigatorio.")
    return INTELLIGENCE_DB.record_correction(
        channel=channel,
        project_id=str(payload.get("projectId") or ""),
        event_type=event_type,
        payload=payload.get("value") if isinstance(payload.get("value"), dict) else {"value": payload.get("value")},
        source="user",
    )


@app.delete("/api/intelligence/learning/{channel}")
def intelligence_reset_learning(channel: str):
    INTELLIGENCE_DB.reset_preferences(channel)
    return {"ok": True, "channel": channel}


@app.get("/api/intelligence/confidence/{project_id}")
def intelligence_project_confidence(project_id: str):
    with QUEUE_LOCK:
        project = _find_queue_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto da fila nao encontrado.")
        stored = project.get("confidenceSummary")
        if isinstance(stored, dict) and stored:
            return {"source": "last_render", "confidence": stored}
        media = project.get("media") if isinstance(project.get("media"), dict) else {}
        manifest: list[dict[str, Any]] = []
        for key, kind in (
            ("videos", "video"),
            ("audios", "audio"),
            ("background_music", "background_music"),
            ("texts", "text_srt"),
            ("captions", "caption_srt"),
        ):
            manifest.extend(
                {"name": Path(str(value)).name, "rel": str(value), "kind": kind}
                for value in (media.get(key) or [])
            )
        preflight = build_preflight_summary(
            manifest,
            project.get("options") if isinstance(project.get("options"), dict) else {},
        )
        return {"source": "preflight", "confidence": preflight.get("confidence") or {}, "risks": preflight.get("errors") or []}


@app.post("/api/queue/projects/{project_id}/director/rerun")
def queue_director_rerun(project_id: str):
    with QUEUE_LOCK:
        project = _find_queue_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto da fila nao encontrado.")
        project["directorState"] = None
        project["updatedAt"] = _now_iso()
        _save_queue_projects(QUEUE_PROJECTS)
        return {
            "ok": True,
            "message": "A direcao sera recalculada no proximo preflight/render.",
            "project": _public_queue_project(project),
        }


@app.post("/api/queue/projects/{project_id}/director/undo")
def queue_director_undo(project_id: str):
    with QUEUE_LOCK:
        project = _find_queue_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto da fila nao encontrado.")
        history = list(project.get("timelineHistory") or [])
        if not history:
            raise HTTPException(status_code=409, detail="Nao existe montagem anterior para desfazer.")
        previous = history.pop()
        order = [str(item) for item in (previous.get("order") or []) if str(item).strip()]
        if not order:
            raise HTTPException(status_code=409, detail="Historico de montagem invalido.")
        media = project.get("media") if isinstance(project.get("media"), dict) else {}
        media["videos"] = order
        project["media"] = media
        options = project.get("options") if isinstance(project.get("options"), dict) else {}
        options["videoOrder"] = order
        project["options"] = options
        project["directorState"] = None
        project["timelineHistory"] = history
        project["updatedAt"] = _now_iso()
        _save_queue_projects(QUEUE_PROJECTS)
        return {"ok": True, "project": _public_queue_project(project)}


def build_preflight_summary(files_manifest: list[dict[str, Any]], options: dict[str, Any]) -> dict[str, Any]:
    options = apply_render_execution_profile(options)
    if bool(options.get("safeRenderMode")):
        options = {
            **options,
            "smartVisualDirector": False,
            "autoDirector": False,
            "visualCleanFilter": True,
            "visualFilterLevel": "light",
            "adaptiveVisualFilter": False,
            "qualityBoost": False,
            "zoom": "off",
            "transitions": "off",
            "dynamicPauses": False,
            "strongMomentEnhance": False,
            "_safe_render_effective": True,
        }
    counts = {"video": 0, "image": 0, "visual_media": 0, "audio": 0, "background_music": 0, "text": 0, "caption": 0, "subtitle": 0, "script_guide": 0}
    mp4_audio_containers = 0
    mp4_background_containers = 0
    for item in files_manifest:
        name = str(item.get("name") or item.get("rel") or "")
        ext = Path(name).suffix.lower()
        kind = str(item.get("kind") or "")
        if kind == "background_music":
            counts["background_music"] += 1
            if ext in VIDEO_EXTS:
                mp4_background_containers += 1
        elif kind == "caption_srt":
            counts["caption"] += 1
        elif kind in {"text_srt", "subtitle"} or ext in SRT_EXTS:
            counts["text"] += 1
            counts["subtitle"] += 1
        elif kind == "script_guide" or ext in SCRIPT_GUIDE_EXTS:
            counts["script_guide"] += 1
        elif kind == "audio" or ext in AUDIO_EXTS:
            counts["audio"] += 1
            if kind == "audio" and ext in VIDEO_EXTS:
                mp4_audio_containers += 1
        elif kind == "image" or ext in IMAGE_EXTS:
            counts["image"] += 1
            counts["visual_media"] += 1
        elif kind == "video" or ext in VIDEO_EXTS:
            counts["video"] += 1
            counts["visual_media"] += 1

    errors: list[str] = []
    warnings: list[str] = []
    cta_language = str(options.get("ctaLanguage") or "").strip().lower()
    intro = intro_mode(options)
    music_genre = preset_music_genre(options)
    preset_music_count = len(list_preset_music_files(music_genre)) if bool(options.get("backgroundMusicUseLibrary", True)) else 0

    if counts["visual_media"] <= 0:
        errors.append("Adicione pelo menos um vídeo ou imagem para a timeline.")
    if counts["audio"] <= 0:
        errors.append("Adicione a narracao principal.")
    if CTA_REQUIRED and cta_language not in CTA_LANGUAGES:
        errors.append("Escolha um CTA valido antes de renderizar.")
    if counts["text"] <= 0:
        errors.append("Adicione um SRT de Textos.")
    if counts["background_music"] <= 0 and preset_music_count <= 0:
        warnings.append(f"Nenhuma musica manual e biblioteca {music_genre} vazia; o render seguira sem musica.")
    tone_summary = infer_project_tone(options, files_manifest)
    auto_fix_plan = build_auto_fix_plan(files_manifest, options, counts, warnings, errors, tone_summary)
    priority = render_priority(options)
    turbo = turbo_profile(options)
    hw = hardware_profile()
    requested_codec = "h264" if str(options.get("codec") or "hevc").lower() == "h264" else "hevc"
    efficient_hardware = (
        hw.get("recommended_h264_encoder" if requested_codec == "h264" else "recommended_hevc_encoder")
        if priority == "balanced" and not bool(options.get("_force_cpu"))
        else None
    )
    estimated_duration = options.get("estimatedDurationSeconds") or 0
    estimates = {
        "balanced": render_time_estimate(estimated_duration, options, "balanced"),
        "max": render_time_estimate(estimated_duration, options, "max"),
    } if estimated_duration else {}
    initial_confidence = confidence_summary(
        media_total=max(1, counts["visual_media"] or counts["video"]),
        media_valid=max(0, counts["visual_media"] or counts["video"]),
        subtitle_count=counts["subtitle"],
        audio_ok=counts["audio"] > 0,
        coverage_ratio=1.0 if counts["visual_media"] > 0 else 0.0,
        technical_risk=0.08 if counts["visual_media"] > 0 else 1.0,
    )
    style_profile = reference_style_profile(options)

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": counts,
        "media_containers": {
            "audio_from_video_container": mp4_audio_containers,
            "background_from_video_container": mp4_background_containers,
        },
        "auto_fix_plan": auto_fix_plan,
        "emotion_summary": tone_summary,
        "cta": {
            "required": CTA_REQUIRED,
            "selected": cta_language,
            "valid": cta_language in CTA_LANGUAGES,
            "policy": "manual_position_fixed_start_end",
        },
        "intro_mode": intro,
        "music": {
            "genre": music_genre,
            "manual_tracks": counts["background_music"],
            "preset_tracks_available": preset_music_count,
            "manual_override": counts["background_music"] > 0,
        },
        "quality_boost": bool(options.get("qualityBoost", True)),
        "safe_render": {
            "enabled": bool(options.get("safeRenderMode", False)),
            "description": "Caminho conservador: videos em ordem, SRT simples, CTA, audio e musica leve.",
        },
        "smart_visual_director": {
            "requested": smart_visual_director_requested(options),
            "effective": smart_visual_director_effective(options, counts["subtitle"] > 0)[0],
            "state": smart_visual_director_effective(options, counts["subtitle"] > 0)[1],
            "description": "Ordena clipes por SRT, nomes, categorias e numeracao como pistas leves.",
        },
        "visual_clean_filter": {
            "enabled": True,
            "requested_level": normalized_visual_filter_level(options),
            "adaptive_requested": bool(options.get("adaptiveVisualFilter", False)),
            "adaptive_effective": adaptive_visual_filter_effective(options),
            "policy": "adaptive_visual_clean" if adaptive_visual_filter_effective(options) else "manual_full_timeline",
            "images_level": "strict",
            "face_detector": yunet_detector_status(),
            "description": "Analisa toda a midia e separa talking head de pessoas ligadas ao tema.",
        },
        "auto_sound_fx": bool(options.get("autoSoundFx", True)),
        "adaptive_ducking": True,
        "dynamic_pauses": False,
        "render_recovery": bool(options.get("renderRecovery", True)),
        "style_profile": style_profile,
        "render_priority": priority,
        "render_priority_label": render_mode_label(priority),
        "render_priority_requested": str(options.get("renderPriority") or "balanced"),
        "render_priority_effective": priority,
        "gpu_requested": bool(options.get("gpu", False)),
        "gpu_enabled": (
            bool(turbo.get("gpu_effective"))
            if turbo.get("enabled")
            else bool(efficient_hardware)
        ),
        "hardware_encoder": (
            turbo.get("encoder_effective")
            if turbo.get("enabled") and turbo.get("gpu_effective")
            else efficient_hardware
        ),
        "hardware_profile": {
            "acceleration": hw.get("acceleration"),
            "performance_class": hw.get("performance_class"),
            "preferred_gpu": hw.get("preferred_gpu"),
            "cpu_count": hw.get("cpu_count"),
            "ram_gb": hw.get("ram_gb"),
            "recommended_hevc_encoder": hw.get("recommended_hevc_encoder"),
            "recommended_h264_encoder": hw.get("recommended_h264_encoder"),
        },
        "turbo_summary": turbo,
        "render_time_estimates": estimates,
        "intelligence": {
            "auto_director": smart_visual_director_requested(options),
            "smart_visual_director": smart_visual_director_requested(options),
            "smart_visual_director_effective": smart_visual_director_effective(options, counts["subtitle"] > 0)[1],
            "semantic_visual_index": bool(options.get("semanticVisualIndex", True)),
            "channel_learning": bool(options.get("channelLearning", True)),
            "energy_editing": bool(options.get("energyEditing", True)),
            "anti_repeat": bool(options.get("antiRepeat", True)),
            "continuity_match": False,
            "continuity_outliers_only": bool(options.get("continuityOutliersOnly", True)),
            "audio_mastering": bool(options.get("audioMastering", True)),
            "platform_master_profile": str(options.get("platformMasterProfile") or "youtube_long"),
            "model": semantic_model_status(),
        },
        "confidence": initial_confidence,
        "decision_summary": {
            "healthy_threshold": _healthy_threshold(options),
            "decisions": [
                _decision_record("cta", "use" if cta_language in CTA_LANGUAGES else "missing", "CTA obrigatorio no render.", 0.95 if cta_language in CTA_LANGUAGES else 0.35, cta_language or "cta"),
                _decision_record("director", smart_visual_director_effective(options, counts["subtitle"] > 0)[1], "Diretor respeita modo de decisao e suspensao no Turbo.", 0.86, "smartVisualDirector"),
                _decision_record("visual_filter", normalized_visual_filter_level(options), "Filtro temporal/contextual com proteção de 25% no início e 30% no restante.", 0.88, "visualFilterLevel"),
                _decision_record(
                    "style",
                    style_profile.get("referenceModeEffective") or style_profile.get("source") or "glide_package",
                    style_profile.get("fallbackReason") or "Linguagem audiovisual resolvida como guia de edição, sem copiar frames ou conteúdo da referência.",
                    0.88 if style_profile.get("source") == "reference_dna" else 0.84,
                    style_profile.get("referenceName") or style_profile.get("package", {}).get("label") or "estilo",
                ),
            ],
        },
    }


@app.post("/api/preflight")
async def preflight(manifest: str = Form("[]"), options: str = Form("{}")):
    try:
        files_manifest = json.loads(manifest)
        options_obj = json.loads(options)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Manifest/options invalidos: {exc}")
    if not isinstance(files_manifest, list) or not isinstance(options_obj, dict):
        raise HTTPException(status_code=400, detail="Manifest/options precisam ser JSON validos.")
    options_obj = apply_render_execution_profile(options_obj)
    return build_preflight_summary(files_manifest, options_obj)


def _compact_cmd_for_log(cmd: list[str]) -> str:
    text = " ".join(str(x) for x in cmd)
    if len(text) > 2200:
        return text[:2200] + " ... [comando encurtado no log]"
    return text


def _append_log(job: Job, line: str):
    line = str(clean_ui_text(line))
    if len(line) > 1800:
        line = line[:1800] + " ..."
    job.log.append(line)
    if len(job.log) > 260:
        del job.log[:80]


def _windows_startupinfo():
    if os.name != "nt":
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return startupinfo


def _windows_priority_flag(priority: str | None = None) -> int:
    if os.name != "nt":
        return 0
    value = str(priority or "balanced").strip().lower()
    if value in {"light", "leve", "idle"}:
        return getattr(subprocess, "IDLE_PRIORITY_CLASS", 0x00000040)
    return getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x00004000)


def render_priority(job: Job | dict[str, Any] | None = None) -> str:
    return "max"


def turbo_enabled(job: Job | dict[str, Any] | None = None) -> bool:
    return True


def render_execution_profile(options: dict[str, Any] | None = None) -> str:
    return "unified_ultra_performance"


def render_mode_label(priority: str = "max") -> str:
    return "1080p Ultra Performance"


def apply_render_execution_profile(options: dict[str, Any] | None) -> dict[str, Any]:
    """Motor unificado: 1080p Full HD com aceleracao por hardware GPU, keyframes a cada 2s e ordenacao sequencial pura."""
    normalized = dict(options or {})
    normalized["renderPriority"] = "max"
    normalized["renderExecutionProfile"] = "unified_ultra_performance"
    normalized["turboPolicy"] = "production_max"
    # Desativa reorganizacao semantica de clipes (garante 100% a ordem sequencial dos videos arrastados)
    normalized["smartVisualDirector"] = False
    normalized["autoDirector"] = False
    normalized["semanticVisualIndex"] = False
    normalized["scoreVisualWindows"] = False
    normalized["continuityMatch"] = False
    normalized["adaptiveVisualFilter"] = False
    normalized["dynamicPauses"] = False
    normalized["strongMomentEnhance"] = False
    normalized["premiumFeelScore"] = False
    normalized["postRenderCorrections"] = False
    normalized["queueAutoTest"] = False
    # Recursos essenciais de alta qualidade mantidos
    normalized.setdefault("audioMastering", True)
    normalized.setdefault("qualityBoost", True)
    normalized.setdefault("visualFilterLevel", "light")
    return normalized


def smart_visual_director_requested(options: dict[str, Any]) -> bool:
    return False


def smart_visual_director_effective(options: dict[str, Any], has_subtitles: bool = True) -> tuple[bool, str]:
    if bool(options.get("safeRenderMode")):
        return False, "suspenso_render_seguro"
    if not smart_visual_director_requested(options):
        return False, "desativado"
    if render_priority(options) == "max":
        return False, "suspenso_turbo"
    if not has_subtitles:
        return False, "sem_srt_valido"
    return True, "ativo"


_KEEP_AWAKE_LOCK = threading.RLock()
_KEEP_AWAKE_ENABLED = False


def set_system_keep_awake(enabled: bool, reason: str = "") -> None:
    """Best-effort: keep Windows awake while FFmpeg is rendering."""
    global _KEEP_AWAKE_ENABLED
    if os.name != "nt":
        return
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_DISPLAY_REQUIRED = 0x00000002
    with _KEEP_AWAKE_LOCK:
        if enabled == _KEEP_AWAKE_ENABLED:
            return
        flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED if enabled else 0)
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(flags)
            _KEEP_AWAKE_ENABLED = enabled
        except Exception:
            _KEEP_AWAKE_ENABLED = False


def turbo_policy(options: dict[str, Any]) -> str:
    if render_priority(options) != "max":
        return "disabled"
    return str(options.get("turboPolicy") or "production_max").strip().lower()


def turbo_profile(options: dict[str, Any]) -> dict[str, Any]:
    enabled = turbo_enabled(options)
    mode = str(options.get("mode") or "standard")
    ratio = str(options.get("ratio") or "16:9")
    requested_codec = "h264" if str(options.get("codec") or "hevc").lower() == "h264" else "hevc"
    width, height = render_size(mode, ratio)
    requested_rate = export_bitrate_settings(mode, requested_codec, options)
    if not enabled:
        return {
            "enabled": False,
            "policy": "disabled",
            "resolution": f"{width}x{height}",
            "width": width,
            "height": height,
            "bitrate_kbps": requested_rate["target"],
            "codec_requested": requested_codec,
            "codec_effective": requested_codec,
            "gpu_requested": bool(options.get("gpu", False)),
            "gpu_effective": bool(options.get("gpu", False)),
            "encoder_effective": None,
            "suspended_features": [],
            "visual_passes_target": 3,
            "visual_passes_avoided": 0,
            "unified_composition": False,
            "fallback_used": False,
        }

    hardware_encoder = best_hardware_encoder(requested_codec)
    hardware_available = bool(hardware_encoder)
    codec_effective = requested_codec if hardware_available else "h264"
    encoder_effective = hardware_encoder if hardware_available else "libx264"
    return {
        "enabled": True,
        "policy": turbo_policy(options),
        "resolution": f"{width}x{height}",
        "width": width,
        "height": height,
        "bitrate_kbps": requested_rate["target"],
        "codec_requested": requested_codec,
        "codec_effective": codec_effective,
        "gpu_requested": bool(options.get("gpu", False)),
        "gpu_effective": hardware_available,
        "nvenc_available": bool(hardware_encoder and hardware_encoder.endswith("_nvenc")),
        "hardware_encoder": hardware_encoder,
        "encoder_effective": encoder_effective,
        "encoder_preset": "speed" if hardware_available else "ultrafast",
        "suspended_features": [
            "zoom_in_out",
            "quality_boost",
            "visual_transitions",
            "dynamic_pauses",
            "strong_moment_enhance",
        ],
        "preserved_features": [
            "resolution",
            "bitrate",
            "voiceover",
            "background_music",
            "adaptive_ducking",
            "subtitle_animation",
            "subtitle_sound_fx",
            "cta",
            "intro",
            "render_recovery",
        ],
        "visual_passes_target": 2,
        "visual_passes_avoided": 1,
        "unified_composition": False,
        "fallback_used": False,
        "codec_fallback": requested_codec != codec_effective,
    }


def ensure_turbo_summary(job: Job) -> dict[str, Any]:
    if not job.turbo_summary:
        job.turbo_summary = turbo_profile(job.options)
    return job.turbo_summary


def effective_visual_options(job: Job) -> dict[str, Any]:
    if bool(job.options.get("safeRenderMode")):
        return {
            "quality_boost": False,
            "zoom": "off",
            "transitions": "off",
            "dynamic_pauses": False,
            "strong_moment_enhance": False,
            "strong_moments": False,
            "continuity_match": False,
            "safe_render": True,
        }
    priority = render_priority(job)
    if priority != "max":
        return {
            "zoom": str(job.options.get("zoom") or "off"),
            "transitions": str(job.options.get("transitions") or "off"),
            "quality_boost": bool(job.options.get("qualityBoost", True)),
            "dynamic_pauses": bool(job.options.get("dynamicPauses", False)) if priority == "quality" else False,
            "strong_moment_enhance": False,
            "strong_moments": False,
            "continuity_match": bool(job.options.get("continuityMatch", False)) if priority == "quality" else False,
            "continuity_outliers_only": True,
            "quality_max": priority == "quality",
            "motion_graphics_premium": bool(job.options.get("motionGraphicsPremium", False)) if priority == "quality" else False,
        }
    return {
        "zoom": "off",
        "transitions": "off",
        "quality_boost": False,
        "dynamic_pauses": False,
        "strong_moments": False,
    }


def command_for_render_priority(cmd: list[str], priority: str | None = None) -> list[str]:
    normalized = str(priority or "balanced").strip().lower()
    if normalized not in {"max", "maximum", "speed", "fast"}:
        if normalized == "balanced":
            optimized = list(cmd)
            logical_cpus = max(2, int(os.cpu_count() or 4))
            hw = hardware_profile()
            high_profile = bool(hw.get("performance_class") == "high")
            filter_cap = 12 if high_profile else 8
            complex_cap = 6 if high_profile else 4
            filter_budget = max(4, min(filter_cap, int(logical_cpus * (0.68 if high_profile else 0.55))))
            complex_budget = max(2, min(complex_cap, int(logical_cpus * (0.42 if high_profile else 0.30))))
            for flag, budget in (
                ("-filter_threads", filter_budget),
                ("-filter_complex_threads", complex_budget),
            ):
                try:
                    index = optimized.index(flag)
                    if index + 1 < len(optimized):
                        optimized[index + 1] = str(budget)
                except ValueError:
                    pass
            return optimized
        return cmd
    optimized: list[str] = []
    skip_next = False
    clean_next_x265_params = False
    for item in cmd:
        if skip_next:
            if clean_next_x265_params:
                params = [part for part in str(item).split(":") if not part.startswith(("pools=", "frame-threads="))]
                if params:
                    optimized.append(":".join(params))
                clean_next_x265_params = False
            skip_next = False
            continue
        if item in {"-filter_threads", "-filter_complex_threads", "-threads"}:
            skip_next = True
            continue
        if item == "-x265-params":
            optimized.append(item)
            skip_next = True
            clean_next_x265_params = True
            continue
        optimized.append(item)
    return optimized


def render_performance_budget(job: Job, gpu: bool = False, segment_count: int = 0) -> dict[str, Any]:
    priority = render_priority(job)
    logical_cpus = max(2, int(os.cpu_count() or 4))
    hw = hardware_profile()
    ram_gb = float(hw.get("ram_gb") or 0.0)
    force_cpu = bool(job.options.get("_force_cpu"))
    hardware_encoder = None if force_cpu else best_hardware_encoder("h264")
    hardware_active = bool(hardware_encoder) and (bool(gpu) or priority in {"balanced", "max", "quality"})

    # Orçamento dinâmico de alta performance com auto-calibração de hardware
    if priority == "max":
        if hardware_active and logical_cpus >= 16 and ram_gb >= 16:
            workers = 5
        elif hardware_active and logical_cpus >= 12 and ram_gb >= 12:
            workers = 4
        elif hardware_active and logical_cpus >= 8:
            workers = 3
        else:
            workers = 2
        cpu_thread_budget = max(4, min(logical_cpus - 1, int(logical_cpus * 0.85)))
        filter_threads = max(1, min(4, cpu_thread_budget // max(1, workers)))
        complex_threads = max(1, min(4, cpu_thread_budget // max(1, workers)))
    elif priority == "quality":
        workers = 3 if (hardware_active and logical_cpus >= 12 and ram_gb >= 12) else (2 if logical_cpus >= 8 else 1)
        cpu_thread_budget = max(3, min(logical_cpus - 1, int(logical_cpus * 0.70)))
        filter_threads = max(1, min(3, cpu_thread_budget // max(1, workers)))
        complex_threads = max(1, min(3, cpu_thread_budget // max(1, workers)))
    else:  # balanced
        workers = 4 if (hardware_active and logical_cpus >= 16 and ram_gb >= 16) else (3 if (hardware_active and logical_cpus >= 12 and ram_gb >= 12) else (2 if logical_cpus >= 6 else 1))
        cpu_thread_budget = max(3, min(logical_cpus - 1, int(logical_cpus * 0.75)))
        filter_threads = max(1, min(3, cpu_thread_budget // max(1, workers)))
        complex_threads = max(1, min(3, cpu_thread_budget // max(1, workers)))

    if segment_count > 0:
        workers = max(1, min(workers, segment_count))

    segment_thread_limit = max(1, min(4, cpu_thread_budget // max(1, workers)))

    return {
        "priority": priority,
        "segment_workers": workers,
        "cpu_thread_budget": cpu_thread_budget,
        "segment_threads": segment_thread_limit,
        "segment_filter_threads": filter_threads,
        "segment_complex_threads": complex_threads,
        "hardware_encoder": hardware_encoder,
        "hardware_active": hardware_active,
        "logical_cpus": logical_cpus,
        "ram_gb": ram_gb,
        "hardware_class": hw.get("performance_class"),
        "mode_label": render_mode_label(priority),
    }


def _hidden_subprocess_kwargs(cwd: Path | None = None, priority: str | None = None) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if cwd:
        kwargs["cwd"] = str(cwd)
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0) | _windows_priority_flag(priority)
        kwargs["startupinfo"] = _windows_startupinfo()
    return kwargs


def _run_hidden(cmd: list[str], cwd: Path | None = None, priority: str | None = None, **kwargs):
    options = _hidden_subprocess_kwargs(cwd, priority=priority)
    options.update(kwargs)
    return subprocess.run(cmd, **options)


def _popen_hidden(cmd: list[str], cwd: Path | None = None, priority: str | None = None, **kwargs):
    options = _hidden_subprocess_kwargs(cwd, priority=priority)
    options.update(kwargs)
    return subprocess.Popen(cmd, **options)


def _terminate_process(proc: subprocess.Popen[Any] | None) -> None:
    if not proc or proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=2.5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _register_process(job: Job, proc: subprocess.Popen[Any]) -> None:
    with job.process_lock:
        job.current_process = proc
        job.current_processes.append(proc)


def _unregister_process(job: Job, proc: subprocess.Popen[Any]) -> None:
    with job.process_lock:
        job.current_processes = [item for item in job.current_processes if item is not proc]
        job.current_process = job.current_processes[-1] if job.current_processes else None


def _terminate_job_processes(job: Job) -> None:
    with job.process_lock:
        processes = list(job.current_processes)
        if job.current_process and job.current_process not in processes:
            processes.append(job.current_process)
    for proc in processes:
        _terminate_process(proc)


def performance_start(job: Job, key: str) -> None:
    job.performance_marks[key] = time.perf_counter()


def performance_stop(job: Job, key: str) -> float:
    started = job.performance_marks.pop(key, None)
    if started is None:
        return 0.0
    elapsed = max(0.0, time.perf_counter() - started)
    job.performance_breakdown[key] = round(
        float(job.performance_breakdown.get(key) or 0.0) + elapsed,
        3,
    )
    return elapsed


def set_stage(job: Job, stage: str, label: str, message: str | None = None, percent: float | None = None):
    job.stage = stage
    job.stage_label = str(clean_ui_text(label))
    if message is not None:
        job.message = str(clean_ui_text(message))
    if percent is not None:
        job.percent = percent


def _open_path(path: Path):
    target = path.resolve()
    if os.name == "nt":
        if target.is_file():
            _popen_hidden(["explorer", f"/select,{target}"])
        else:
            _popen_hidden(["explorer", str(target)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(target)])
    else:
        subprocess.Popen(["xdg-open", str(target)])


def encoder_available(encoder: str) -> bool:
    global _ENCODER_LIST_CACHE, _ENCODER_LIST_CACHE_AT
    hardware_encoder = encoder.endswith(("_nvenc", "_qsv", "_amf"))
    with _ENCODER_CACHE_LOCK:
        if encoder in _ENCODER_CACHE:
            cached = bool(_ENCODER_CACHE[encoder])
            age = max(0.0, time.monotonic() - float(_ENCODER_CACHE_AT.get(encoder) or 0.0))
            if cached or not hardware_encoder or age < 12.0:
                return cached
    if not FFMPEG:
        with _ENCODER_CACHE_LOCK:
            _ENCODER_CACHE[encoder] = False
            _ENCODER_CACHE_AT[encoder] = time.monotonic()
        return False
    try:
        with _ENCODER_CACHE_LOCK:
            list_age = max(0.0, time.monotonic() - _ENCODER_LIST_CACHE_AT)
            encoder_list = _ENCODER_LIST_CACHE if _ENCODER_LIST_CACHE and list_age < 300.0 else ""
        if not encoder_list:
            p = _run_hidden(
                [FFMPEG, "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=15,
            )
            encoder_list = (p.stdout or "") if p.returncode == 0 else ""
            with _ENCODER_CACHE_LOCK:
                _ENCODER_LIST_CACHE = encoder_list
                _ENCODER_LIST_CACHE_AT = time.monotonic()
        ok = bool(encoder_list) and encoder in encoder_list
        if ok and hardware_encoder:
            runtime_probe = _run_hidden(
                [
                    FFMPEG,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=black:s=256x256:d=0.04",
                    "-frames:v",
                    "1",
                    "-an",
                    "-c:v",
                    encoder,
                    "-f",
                    "null",
                    os.devnull,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=20,
            )
            ok = runtime_probe.returncode == 0
    except Exception:
        ok = False
    with _ENCODER_CACHE_LOCK:
        _ENCODER_CACHE[encoder] = ok
        _ENCODER_CACHE_AT[encoder] = time.monotonic()
    return ok


def best_hardware_encoder(codec: str) -> str | None:
    prefix = "h264" if str(codec or "").lower() == "h264" else "hevc"
    for suffix in ("nvenc", "qsv", "amf"):
        encoder = f"{prefix}_{suffix}"
        if encoder_available(encoder):
            return encoder
    return None


_HARDWARE_PROFILE_CACHE: dict[str, Any] = {}
_HARDWARE_PROFILE_AT = 0.0
_HARDWARE_PROFILE_LOCK = threading.Lock()
_HARDWARE_PROFILE_WARMING = False


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _system_ram_gb() -> float:
    if sys.platform.startswith("win"):
        try:
            status = _MemoryStatusEx()
            status.dwLength = ctypes.sizeof(_MemoryStatusEx)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return round(float(status.ullTotalPhys) / (1024 ** 3), 1)
        except Exception:
            pass
    try:
        if hasattr(os, "sysconf"):
            pages = float(os.sysconf("SC_PHYS_PAGES"))
            page_size = float(os.sysconf("SC_PAGE_SIZE"))
            return round((pages * page_size) / (1024 ** 3), 1)
    except Exception:
        pass
    return 0.0


def _detect_windows_gpus() -> list[dict[str, Any]]:
    if not sys.platform.startswith("win"):
        return []
    gpus: list[dict[str, Any]] = []
    try:
        probe = _run_hidden(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_VideoController | "
                "Select-Object Name,AdapterRAM | ConvertTo-Json -Compress",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=4,
        )
        if probe.returncode == 0 and (probe.stdout or "").strip():
            raw = json.loads(probe.stdout)
            rows = raw if isinstance(raw, list) else [raw]
            for row in rows:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("Name") or "").strip()
                if not name:
                    continue
                try:
                    ram_gb = round(float(row.get("AdapterRAM") or 0) / (1024 ** 3), 1)
                except Exception:
                    ram_gb = 0.0
                lname = name.lower()
                gpus.append({
                    "name": name,
                    "adapter_ram_gb": ram_gb,
                    "vendor": (
                        "nvidia" if "nvidia" in lname
                        else "intel" if "intel" in lname
                        else "amd" if ("amd" in lname or "radeon" in lname)
                        else "unknown"
                    ),
                    "dedicated": any(token in lname for token in ("nvidia", "rtx", "gtx", "quadro", "radeon", "rx ")),
                })
    except Exception:
        pass
    if not any(item.get("vendor") == "nvidia" for item in gpus):
        try:
            probe = _run_hidden(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=4,
            )
            if probe.returncode == 0:
                for line in (probe.stdout or "").splitlines():
                    name, _, memory_mb = line.partition(",")
                    clean_name = name.strip()
                    if not clean_name:
                        continue
                    try:
                        ram_gb = round(float(memory_mb.strip()) / 1024.0, 1)
                    except Exception:
                        ram_gb = 0.0
                    gpus.append({
                        "name": clean_name,
                        "adapter_ram_gb": ram_gb,
                        "vendor": "nvidia",
                        "dedicated": True,
                    })
        except Exception:
            pass
    return gpus


def hardware_profile(force_refresh: bool = False) -> dict[str, Any]:
    global _HARDWARE_PROFILE_CACHE, _HARDWARE_PROFILE_AT, _HARDWARE_PROFILE_WARMING
    now = time.monotonic()
    with _HARDWARE_PROFILE_LOCK:
        if (
            not force_refresh
            and _HARDWARE_PROFILE_CACHE
            and now - _HARDWARE_PROFILE_AT < 300.0
        ):
            return dict(_HARDWARE_PROFILE_CACHE)

    cpu_count = max(1, int(os.cpu_count() or 1))
    cpu_name = (platform.processor() or platform.machine() or "CPU").strip()
    ram_gb = _system_ram_gb()
    gpus = _detect_windows_gpus()
    # Runtime probes are authoritative and also reveal integrated encoders that
    # Windows may omit when hardware inventory access is restricted.
    check_nvenc = True
    check_qsv = True
    check_amf = True
    encoders = {
        "hevc_nvenc": encoder_available("hevc_nvenc") if check_nvenc else False,
        "h264_nvenc": encoder_available("h264_nvenc") if check_nvenc else False,
        "hevc_qsv": encoder_available("hevc_qsv") if check_qsv else False,
        "h264_qsv": encoder_available("h264_qsv") if check_qsv else False,
        "hevc_amf": encoder_available("hevc_amf") if check_amf else False,
        "h264_amf": encoder_available("h264_amf") if check_amf else False,
    }
    preferred_gpu = ""
    for vendor in ("nvidia", "amd", "intel"):
        match = next((gpu for gpu in gpus if gpu.get("vendor") == vendor), None)
        if match:
            preferred_gpu = str(match.get("name") or "")
            break
    has_nvenc = bool(encoders.get("hevc_nvenc") or encoders.get("h264_nvenc"))
    has_any_hw = bool(any(encoders.values()))
    if has_nvenc and cpu_count >= 8 and ram_gb >= 12:
        perf = "high"
    elif has_any_hw or cpu_count >= 8:
        perf = "medium"
    else:
        perf = "low"
    acceleration = (
        "NVIDIA NVENC" if has_nvenc
        else "Intel Quick Sync" if (encoders.get("hevc_qsv") or encoders.get("h264_qsv"))
        else "AMD AMF" if (encoders.get("hevc_amf") or encoders.get("h264_amf"))
        else "CPU"
    )
    def recommended(prefix: str) -> str | None:
        for suffix in ("nvenc", "qsv", "amf"):
            name = f"{prefix}_{suffix}"
            if encoders.get(name):
                return name
        return None

    usable_cpu_threads = max(1, int(cpu_count * (0.70 if perf == "high" else 0.60 if perf == "medium" else 0.50)))
    balanced_segment_workers = 2 if (has_any_hw and cpu_count >= 8 and ram_gb >= 10) else 1
    turbo_segment_workers = 3 if (has_nvenc and cpu_count >= 12 and ram_gb >= 16) else 2 if (has_any_hw and cpu_count >= 8) else 1
    turbo_cpu_threads = max(2, min(cpu_count, int(cpu_count * 0.88)))
    balanced_filter_threads = max(1, min(4, usable_cpu_threads // max(1, balanced_segment_workers)))
    turbo_filter_threads = max(2, min(8, turbo_cpu_threads // max(1, turbo_segment_workers)))
    profile = {
        "cpu_count": cpu_count,
        "cpu_name": cpu_name,
        "ram_gb": ram_gb,
        "gpus": gpus,
        "preferred_gpu": preferred_gpu,
        "encoders": encoders,
        "acceleration": acceleration,
        "performance_class": perf,
        "recommended_hevc_encoder": recommended("hevc"),
        "recommended_h264_encoder": recommended("h264"),
        "render_capacity": {
            "balanced_segment_workers": balanced_segment_workers,
            "turbo_segment_workers": turbo_segment_workers,
            "balanced_cpu_threads": usable_cpu_threads,
            "turbo_cpu_threads": turbo_cpu_threads,
            "balanced_filter_threads": balanced_filter_threads,
            "turbo_filter_threads": turbo_filter_threads,
            "background_analysis_workers": 1,
            "prefer_hardware_encoder": has_any_hw,
            "notes": (
                "GPU dedicada detectada; priorizar encoder por hardware e manter CPU respirando."
                if has_nvenc
                else "Aceleracao por hardware detectada; usar workers moderados."
                if has_any_hw
                else "Sem encoder GPU confirmado; priorizar estabilidade e threads de CPU controladas."
            ),
        },
    }
    with _HARDWARE_PROFILE_LOCK:
        _HARDWARE_PROFILE_CACHE = dict(profile)
        _HARDWARE_PROFILE_AT = now
        _HARDWARE_PROFILE_WARMING = False
    return profile


def hardware_profile_quick() -> dict[str, Any]:
    global _HARDWARE_PROFILE_WARMING
    now = time.monotonic()
    with _HARDWARE_PROFILE_LOCK:
        if _HARDWARE_PROFILE_CACHE and now - _HARDWARE_PROFILE_AT < 300.0:
            profile = dict(_HARDWARE_PROFILE_CACHE)
            profile["profile_ready"] = True
            return profile
        if not _HARDWARE_PROFILE_WARMING:
            _HARDWARE_PROFILE_WARMING = True
            threading.Thread(
                target=_warm_hardware_profile_worker,
                daemon=True,
                name="glide-hardware-profile",
            ).start()
    cpu_count = max(1, int(os.cpu_count() or 1))
    ram_gb = _system_ram_gb()
    perf = "high" if cpu_count >= 12 and ram_gb >= 16 else "medium" if cpu_count >= 6 else "low"
    usable_cpu_threads = max(1, int(cpu_count * (0.60 if perf != "low" else 0.50)))
    return {
        "cpu_count": cpu_count,
        "cpu_name": (platform.processor() or platform.machine() or "CPU").strip(),
        "ram_gb": ram_gb,
        "gpus": [],
        "preferred_gpu": "",
        "encoders": {},
        "acceleration": "Detectando",
        "performance_class": perf,
        "recommended_hevc_encoder": None,
        "recommended_h264_encoder": None,
        "profile_ready": False,
        "render_capacity": {
            "balanced_segment_workers": 1,
            "turbo_segment_workers": 1 if perf == "low" else 2,
            "balanced_cpu_threads": usable_cpu_threads,
            "turbo_cpu_threads": max(2, min(cpu_count, int(cpu_count * 0.82))),
            "balanced_filter_threads": max(1, min(3, usable_cpu_threads)),
            "turbo_filter_threads": max(2, min(6, cpu_count)),
            "background_analysis_workers": 1,
            "prefer_hardware_encoder": False,
            "notes": "Perfil rápido; detecção completa de GPU/encoders em segundo plano.",
        },
    }


def _warm_hardware_profile_worker() -> None:
    global _HARDWARE_PROFILE_WARMING
    try:
        hardware_profile(force_refresh=True)
    except Exception:
        with _HARDWARE_PROFILE_LOCK:
            _HARDWARE_PROFILE_WARMING = False


def run_cmd(
    job: Job,
    cmd: list[str],
    total_duration: float | None = None,
    base: float = 0.0,
    span: float = 100.0,
    cwd: Path | None = None,
    quiet_success: bool = False,
):
    priority = render_priority(job)
    if job.cancel_requested:
        raise RenderCancelled("Render cancelado pelo usuario.")
    original_cmd = list(cmd)
    cmd = command_for_render_priority(cmd, priority)
    if total_duration and cmd and Path(str(cmd[0])).name.lower().startswith("ffmpeg") and "-progress" not in cmd:
        cmd = [cmd[0], "-progress", "pipe:1", "-nostats", *cmd[1:]]
    job.stage_progress_seconds = 0.0
    job.stage_progress_total = max(0.0, float(total_duration or 0.0))
    if priority == "max" and cmd != original_cmd:
        _append_log(job, "Render Turbo: limites de filtros/threads removidos deste comando FFmpeg.")
    _append_log(job, "CMD: " + _compact_cmd_for_log(cmd))
    proc = _popen_hidden(
        cmd,
        cwd=cwd,
        priority=priority,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="ignore",
        bufsize=1,
    )
    assert proc.stdout is not None
    _register_process(job, proc)
    line_queue: queue.Queue[str | None] = queue.Queue()

    def reader() -> None:
        try:
            assert proc.stdout is not None
            for raw_line in proc.stdout:
                line_queue.put(raw_line)
        finally:
            line_queue.put(None)

    threading.Thread(target=reader, daemon=True).start()

    last_lines: list[str] = []
    reader_done = False

    def consume_line(raw_line: str) -> None:
        line = raw_line.strip()
        if not line:
            return
        last_lines.append(line)
        if len(last_lines) > 35:
            last_lines.pop(0)
        if not quiet_success:
            _append_log(job, line)
        if total_duration:
            if line.startswith("out_time_ms="):
                try:
                    seconds = float(line.split("=", 1)[1]) / 1_000_000.0
                    job.stage_progress_seconds = max(job.stage_progress_seconds, seconds)
                    job.percent = min(99.0, base + (seconds / total_duration) * span)
                except Exception:
                    pass
            elif line.startswith("out_time_us="):
                try:
                    seconds = float(line.split("=", 1)[1]) / 1_000_000.0
                    job.stage_progress_seconds = max(job.stage_progress_seconds, seconds)
                    job.percent = min(99.0, base + (seconds / total_duration) * span)
                except Exception:
                    pass
            elif line.startswith("progress=end"):
                job.percent = min(99.0, base + span)

    try:
        while True:
            if job.cancel_requested:
                _terminate_process(proc)
                raise RenderCancelled("Render cancelado pelo usuario.")
            if job.render_deadline_at and time.time() >= job.render_deadline_at:
                job.render_budget_state = "exceeded"
                _terminate_process(proc)
                raise RenderBudgetExceeded(
                    f"Orçamento de render excedido no modo {render_mode_label(priority)}. "
                    "O job foi interrompido antes de ultrapassar o limite definido."
                )
            try:
                item = line_queue.get(timeout=0.15)
            except queue.Empty:
                if proc.poll() is not None and reader_done:
                    break
                continue
            if item is None:
                reader_done = True
                if proc.poll() is not None:
                    break
                continue
            consume_line(item)
        ret = proc.wait()
        while not line_queue.empty():
            item = line_queue.get_nowait()
            if item:
                consume_line(item)
        if job.cancel_requested:
            raise RenderCancelled("Render cancelado pelo usuario.")
        if ret != 0:
            raise RuntimeError("FFmpeg falhou:\n" + "\n".join(last_lines[-18:]))
    finally:
        _unregister_process(job, proc)


def probe_duration(path: Path, cwd: Path | None = None) -> float:
    source = path if path.is_absolute() else ((cwd or DATA_ROOT) / path).resolve()
    if not FFPROBE:
        raise RuntimeError("ffprobe não encontrado. Instale FFmpeg ou coloque ffprobe.exe nesta pasta.")
    cmd = [
        FFPROBE,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(source),
    ]
    p = _run_hidden(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if p.returncode != 0:
        raise RuntimeError(f"Falha ao ler duração de {path}: {p.stderr[-700:]}")
    try:
        return max(float((p.stdout or "0").strip()), 0.0)
    except Exception as exc:
        raise RuntimeError(f"Duração inválida para {path}: {p.stdout!r}") from exc


def safe_probe_duration(path: Path, cwd: Path | None = None) -> float:
    try:
        return probe_duration(path, cwd=cwd)
    except Exception:
        return 0.0


def cached_probe_duration(path: Path, cwd: Path | None = None) -> float:
    if cwd is not None:
        return safe_probe_duration(path, cwd=cwd)
    try:
        key = str(path.resolve())
    except Exception:
        key = str(path)
    if key in SFX_DURATION_CACHE:
        return SFX_DURATION_CACHE[key]
    duration = safe_probe_duration(path)
    SFX_DURATION_CACHE[key] = duration
    return duration


def probe_has_audio(path: Path, cwd: Path | None = None) -> bool:
    source = path if path.is_absolute() else ((cwd or DATA_ROOT) / path).resolve()
    if not FFPROBE:
        return False
    cmd = [
        FFPROBE,
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=index",
        "-of", "csv=p=0",
        str(source),
    ]
    try:
        p = _run_hidden(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=12)
        return p.returncode == 0 and bool((p.stdout or "").strip())
    except Exception:
        return False


def probe_has_video(path: Path, cwd: Path | None = None) -> bool:
    source = path if path.is_absolute() else ((cwd or DATA_ROOT) / path).resolve()
    if not FFPROBE:
        return False
    cmd = [
        FFPROBE,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=index",
        "-of", "csv=p=0",
        str(source),
    ]
    try:
        p = _run_hidden(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=12)
        return p.returncode == 0 and bool((p.stdout or "").strip())
    except Exception:
        return False


def validate_final_output(job: Job, path: Path, expected_duration: float | None = None) -> dict[str, Any]:
    summary = dict(job.delivery_summary or {})
    checks: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "validated": False,
    }
    errors: list[str] = []
    if not path.exists():
        errors.append("arquivo final ausente")
    else:
        try:
            checks["size_bytes"] = path.stat().st_size
        except Exception:
            checks["size_bytes"] = 0
        if int(checks.get("size_bytes") or 0) < 128 * 1024:
            errors.append("arquivo final pequeno demais")
        checks["has_video"] = probe_has_video(path)
        checks["has_audio"] = probe_has_audio(path)
        if not checks["has_video"]:
            errors.append("stream de video ausente")
        if not checks["has_audio"]:
            errors.append("stream de audio ausente")
        duration = cached_probe_duration(path)
        checks["duration_seconds"] = round(duration, 3)
        try:
            expected = max(0.0, float(expected_duration or 0.0))
        except Exception:
            expected = 0.0
        checks["expected_duration_seconds"] = round(expected, 3)
        if expected >= 15.0 and duration < expected * 0.90:
            errors.append("duracao final menor que o esperado")
        elif 0.0 < expected < 15.0 and duration + 2.0 < expected:
            errors.append("duracao final incompleta")
        elif expected <= 0.0 and duration <= 0.5:
            errors.append("duracao final invalida")
    if errors:
        checks["errors"] = errors
        summary.update(checks)
        summary["ok"] = False
        job.delivery_summary = summary
        raise RuntimeError("Arquivo final não validado: " + "; ".join(errors))
    checks["validated"] = True
    checks["ok"] = True
    summary.update(checks)
    summary["ok"] = True
    summary["validated"] = True
    job.delivery_summary = summary
    return summary


def _resolved_media_path(path: Path, cwd: Path | None = None) -> Path:
    if path.is_absolute():
        return path
    return ((cwd or DATA_ROOT) / path).resolve()


def video_file_size_mb(path: Path, cwd: Path | None = None) -> float:
    try:
        return _resolved_media_path(path, cwd).stat().st_size / (1024 * 1024)
    except Exception:
        return 0.0


def video_health_cache_key(path: Path, cwd: Path | None = None) -> str:
    resolved = _resolved_media_path(path, cwd)
    try:
        stat = resolved.stat()
        return f"{resolved}:{stat.st_size}:{int(stat.st_mtime)}"
    except Exception:
        return str(resolved)


def parse_signalstats(text: str) -> dict[str, float] | None:
    values: dict[str, float] = {}
    for key in ("YAVG", "YMIN", "YMAX"):
        match = re.search(rf"lavfi\.signalstats\.{key}=(-?[0-9.]+)", text)
        if match:
            try:
                values[key.lower()] = float(match.group(1))
            except Exception:
                pass
    if {"yavg", "ymin", "ymax"}.issubset(values):
        values["yrange"] = values["ymax"] - values["ymin"]
        return values
    return None


def probe_visible_video_frame(path: Path, duration: float, cwd: Path | None = None) -> dict[str, Any]:
    if not FFMPEG or duration <= 0:
        return {"visible": False, "reason": "sem ffmpeg/duracao", "samples": []}
    sample_points = [0.12]
    if duration > 0.8:
        sample_points.append(min(max(duration * 0.35, 0.40), max(0.25, duration - 0.25)))
    if duration > 1.8:
        sample_points.append(min(max(duration * 0.72, 0.90), max(0.40, duration - 0.25)))
    samples: list[dict[str, Any]] = []
    first_visible_offset = 0.0
    for at in sample_points:
        cmd = [
            FFMPEG, "-hide_banner", "-v", "error",
            "-ss", f"{max(0.0, at):.3f}",
            "-i", str(path),
            "-frames:v", "1",
            "-vf", "scale=64:64,format=gray,signalstats,metadata=print:file=-",
            "-f", "null", "-",
        ]
        try:
            p = _run_hidden(cmd, cwd=cwd, priority="balanced", capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=12)
            stats = parse_signalstats((p.stdout or "") + "\n" + (p.stderr or ""))
        except Exception:
            stats = None
        if not stats:
            samples.append({"at": round(at, 3), "visible": False, "reason": "sem frame decodificavel"})
            continue
        yavg = float(stats["yavg"])
        yrange = float(stats["yrange"])
        ymax = float(stats["ymax"])
        # Detecta telas escuras ou títulos estáticos com fundo preto
        visible = not (yavg <= 22.0 and ymax <= 36.0 and yrange < 24.0)
        sample = {
            "at": round(at, 3),
            "visible": visible,
            "yavg": round(yavg, 2),
            "ymax": round(ymax, 2),
            "yrange": round(yrange, 2),
        }
        samples.append(sample)
        if visible and first_visible_offset == 0.0:
            first_visible_offset = at

    has_any_visible = any(s.get("visible") for s in samples)
    if has_any_visible:
        suggested_offset = first_visible_offset if (not samples[0].get("visible") and first_visible_offset > 0.3) else 0.0
        return {
            "visible": True,
            "suggested_offset": round(suggested_offset, 3),
            "reason": "frame visivel",
            "samples": samples,
        }
    return {"visible": False, "reason": "amostras pretas/sem conteudo visual", "samples": samples}


def probe_video_render_health(path: Path, duration: float, cwd: Path | None = None) -> dict[str, Any]:
    key = video_health_cache_key(path, cwd)
    if key in VIDEO_HEALTH_CACHE:
        return dict(VIDEO_HEALTH_CACHE[key])
    size_mb = video_file_size_mb(path, cwd)
    summary: dict[str, Any] = {
        "valid": True,
        "reason": "ok",
        "duration": round(duration, 3),
        "size_mb": round(size_mb, 3),
        "visual_checked": False,
        "visible_frame": None,
    }
    if duration <= 0.08:
        summary.update({"valid": False, "reason": "sem duracao legivel"})
    else:
        visual = probe_visible_video_frame(path, duration, cwd=cwd)
        summary.update({
            "visual_checked": True,
            "visible_frame": bool(visual.get("visible")),
            "suggested_offset": float(visual.get("suggested_offset") or 0.0),
            "visual_samples": visual.get("samples") or [],
        })
        if not visual.get("visible"):
            summary.update({
                "valid": False,
                "reason": f"arquivo com tela preta/sem frames visiveis ({size_mb:.2f} MB)",
            })
    VIDEO_HEALTH_CACHE[key] = dict(summary)
    return summary


def enforce_clean_opening_protocol(
    job: Job,
    valid_pairs: list[tuple[Path, float]],
    work: Path,
    max_opening_slots: int = 10,
) -> tuple[list[tuple[Path, float]], dict[str, Any]]:
    """Garante que os primeiros 10 clipes sejam estritamente B-roll limpos (sem telas escuras, sem legendas gravadas e sem avatar falante)."""
    if len(valid_pairs) <= 3:
        return valid_pairs, {"enforced": False, "swapped": 0}

    opening_count = min(len(valid_pairs), max_opening_slots)
    clean_pool_indices: list[int] = []
    polluted_indices_in_opening: list[int] = []

    for idx, (path, dur) in enumerate(valid_pairs):
        is_opening = idx < opening_count
        analysis = probe_visual_clean_health(path, dur, "normal", cwd=work)
        category = str(analysis.get("category") or "clean")
        action = str(analysis.get("action") or "keep")

        # Poluição visual: tela preta, apresentador/avatar ou texto/legenda gravada
        is_polluted = category in {"black_screen", "presenter", "text_dominant", "low_quality"} or action == "hard_reject"

        if is_opening and is_polluted:
            polluted_indices_in_opening.append(idx)
        elif not is_opening and not is_polluted:
            clean_pool_indices.append(idx)

    reordered = list(valid_pairs)
    swapped_count = 0
    swapped_details: list[dict[str, Any]] = []

    for bad_idx in polluted_indices_in_opening:
        if not clean_pool_indices:
            break
        good_idx = clean_pool_indices.pop(0)
        bad_item = reordered[bad_idx]
        good_item = reordered[good_idx]
        reordered[bad_idx] = good_item
        reordered[good_idx] = bad_item
        swapped_count += 1
        swapped_details.append({
            "polluted_file": bad_item[0].name,
            "replaced_by": good_item[0].name,
            "opening_slot": bad_idx + 1,
        })
        _append_log(
            job,
            f"Clean Opening Protocol: Slot #{bad_idx + 1} protegido. Clipes com poluição visual '{bad_item[0].name}' substituído por B-roll limpo '{good_item[0].name}'.",
        )

    summary = {
        "enforced": True,
        "opening_slots_checked": opening_count,
        "swapped": swapped_count,
        "swapped_details": swapped_details,
    }
    return reordered, summary


MEDIA_STOPWORDS = {
    "clip", "video", "img", "image", "photo", "shot", "take", "footage", "screen",
    "the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "for", "with", "from",
    "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas", "um", "uma", "uns", "umas",
    "el", "la", "los", "las", "un", "una", "unos", "unas", "en", "con", "por", "para",
    "1080p", "720p", "4k", "2k", "hd", "mp4", "jpg", "jpeg", "png", "webm",
}


def extract_media_tokens(path: Path) -> set[str]:
    """Extrai tokens significativos do nome do arquivo (ex: '01_north_west_island_00m19s.mp4' -> {'north', 'west', 'island'})."""
    stem = path.stem.lower()
    stem = re.sub(r"\b\d+m\d+s(?:-\d+m\d+s)?\b", " ", stem)
    stem = re.sub(r"^\d+[\s_-]+", " ", stem)
    tokens = re.findall(r"[a-z0-9áéíóúãõâêîôûçñ]{3,}", stem)
    cleaned = {t for t in tokens if t not in MEDIA_STOPWORDS and (not t.isdigit() or len(t) == 4)}
    return cleaned


def _token_stem_match(t: str, w: str) -> bool:
    if t == w:
        return True
    if len(t) >= 4 and len(w) >= 4:
        min_prefix = min(len(t), len(w), 4)
        if t[:min_prefix] == w[:min_prefix]:
            return True
    return False


def match_media_to_subtitles(
    job: Job,
    valid_pairs: list[tuple[Path, float]],
    cues: list[SubtitleCue],
    audio_total: float,
) -> tuple[list[tuple[Path, float]], dict[str, Any]]:
    """Alinha semanticamente clipes de midia com as falas correspondentes na legenda SRT."""
    if len(valid_pairs) <= 3 or not cues:
        return valid_pairs, {"enabled": False, "matched_count": 0}

    cued_tokens: list[tuple[float, float, set[str]]] = []
    for cue in cues:
        words = set(re.findall(r"[a-z0-9áéíóúãõâêîôûçñ]{3,}", cue.text.lower()))
        words = {w for w in words if w not in MEDIA_STOPWORDS}
        if words:
            cued_tokens.append((cue.start, cue.end, words))

    if not cued_tokens:
        return valid_pairs, {"enabled": True, "matched_count": 0, "reason": "sem tokens em cues"}

    media_tokens_list: list[tuple[Path, float, set[str]]] = []
    for path, dur in valid_pairs:
        tokens = extract_media_tokens(path)
        media_tokens_list.append((path, dur, tokens))

    matches: list[dict[str, Any]] = []
    used_media_indices: set[int] = set()

    # 1. Cenas Obrigatórias do Roteiro (Prioridade Editorial Absoluta)
    script_plan = job.options.get("scriptGuidePlan") if isinstance(job.options.get("scriptGuidePlan"), dict) else {}
    mandatory_scenes = script_plan.get("mandatory_scenes") or []
    for scene in mandatory_scenes:
        s_keywords = set(scene.get("keywords") or [])
        s_target = scene.get("target_time")
        if not s_keywords or s_target is None:
            continue
        best_score = 0
        best_idx = -1
        best_common = []
        for idx, (path, dur, tokens) in enumerate(media_tokens_list):
            if idx in used_media_indices or not tokens:
                continue
            common = [t for t in tokens if any(_token_stem_match(t, w) for w in s_keywords)]
            if common:
                score = len(common) * 25 + 50
                if score > best_score:
                    best_score = score
                    best_idx = idx
                    best_common = common
        if best_idx >= 0 and best_score >= 50:
            used_media_indices.add(best_idx)
            path, dur, tokens = media_tokens_list[best_idx]
            matches.append({
                "media_idx": best_idx,
                "path": path,
                "duration": dur,
                "target_time": s_target,
                "matched_words": best_common,
                "score": best_score,
                "is_mandatory_scene": True,
            })

    # 2. Casamento Semântico Contínuo com Subtitles
    for cue_start, cue_end, cue_words in cued_tokens:
        best_score = 0
        best_idx = -1
        best_common: list[str] = []
        for idx, (path, dur, tokens) in enumerate(media_tokens_list):
            if idx in used_media_indices or not tokens:
                continue
            common = [t for t in tokens if any(_token_stem_match(t, w) for w in cue_words)]
            if common:
                score = len(common) * 10
                if score > best_score:
                    best_score = score
                    best_idx = idx
                    best_common = common

        if best_idx >= 0 and best_score >= 10:
            used_media_indices.add(best_idx)
            path, dur, tokens = media_tokens_list[best_idx]
            matches.append({
                "media_idx": best_idx,
                "path": path,
                "duration": dur,
                "target_time": cue_start,
                "matched_words": best_common,
                "score": best_score,
            })

    if not matches:
        return valid_pairs, {"enabled": True, "matched_count": 0, "reason": "nenhum casamento tematico encontrado"}

    total_clips = len(valid_pairs)
    avg_clip_dur = max(2.5, audio_total / max(1, total_clips))
    reordered: list[tuple[Path, float] | None] = [None] * total_clips

    for m in sorted(matches, key=lambda x: x["target_time"]):
        ideal_slot = min(total_clips - 1, max(0, int(round(m["target_time"] / avg_clip_dur))))
        placed = False
        for offset in range(total_clips):
            pos_right = ideal_slot + offset
            if pos_right < total_clips and reordered[pos_right] is None:
                reordered[pos_right] = (m["path"], m["duration"])
                placed = True
                break
            pos_left = ideal_slot - offset
            if pos_left >= 0 and reordered[pos_left] is None:
                reordered[pos_left] = (m["path"], m["duration"])
                placed = True
                break

    unmatched_pool = [
        (path, dur)
        for idx, (path, dur, _) in enumerate(media_tokens_list)
        if idx not in used_media_indices
    ]

    for i in range(total_clips):
        if reordered[i] is None and unmatched_pool:
            reordered[i] = unmatched_pool.pop(0)

    final_pairs: list[tuple[Path, float]] = [item for item in reordered if item is not None]
    if unmatched_pool:
        final_pairs.extend(unmatched_pool)

    summary = {
        "enabled": True,
        "matched_count": len(matches),
        "matches": [
            {
                "file": m["path"].name,
                "target_second": round(m["target_time"], 2),
                "matched_words": m["matched_words"],
            }
            for m in matches[:15]
        ],
    }
    _append_log(job, f"Semantic B-Roll Matcher: {len(matches)} clipes casados com temas da narracao.")
    return final_pairs, summary


def visual_clean_enabled(options: dict[str, Any]) -> bool:
    return True


def normalized_visual_filter_level(options: dict[str, Any] | None = None) -> str:
    value = str((options or {}).get("visualFilterLevel") or "normal").strip().lower()
    aliases = {"balanced": "normal", "strict": "strict", "light": "light", "normal": "normal"}
    return aliases.get(value, "normal")


def adaptive_visual_filter_effective(options: dict[str, Any] | None = None) -> bool:
    source = options or {}
    return bool(
        source.get("adaptiveVisualFilter", False)
        and smart_visual_director_requested(source)
        and render_priority(source) != "max"
        and not bool(source.get("safeRenderMode"))
    )


def visual_clean_cache_key(path: Path, duration: float, cwd: Path | None = None, scope: str = "full") -> str:
    resolved = _resolved_media_path(path, cwd)
    try:
        stat = resolved.stat()
        return f"v{VISUAL_CLEAN_CACHE_VERSION}:{scope}:{resolved}:{stat.st_size}:{stat.st_mtime_ns}:{duration:.3f}"
    except Exception:
        return f"v{VISUAL_CLEAN_CACHE_VERSION}:{scope}:{resolved}:{duration:.3f}"


def visual_clean_sample_points(duration: float, level: str) -> list[float]:
    if duration <= 0:
        return []
    safe_end = max(0.05, duration - 0.10)
    return [
        min(max(duration * 0.16, 0.08), safe_end),
        min(max(duration * 0.50, 0.12), safe_end),
        min(max(duration * 0.82, 0.16), safe_end),
    ]


def _probe_visual_clean_frames(path: Path, duration: float, cwd: Path | None = None, start_offset: float = 0.0) -> list[bytes]:
    if not FFMPEG:
        return []
    if is_image_path(path):
        count = 1
    elif duration < 2.0:
        count = 3
    elif duration < 8.0:
        count = 6
    elif duration < 20.0:
        count = 10
    elif duration < 60.0:
        count = 14
    else:
        count = 18
    image_source = is_image_path(path)
    trim_start = 0.0 if image_source else (
        max(0.0, float(start_offset or 0.0)) + min(0.08, max(0.0, duration * 0.03))
    )
    window = 0.2 if image_source else max(0.12, duration - min(0.08, duration * 0.03))
    sample_rate = count / window
    vf = (
        f"scale={VISUAL_CLEAN_FRAME_W}:{VISUAL_CLEAN_FRAME_H}:force_original_aspect_ratio=decrease,"
        f"pad={VISUAL_CLEAN_FRAME_W}:{VISUAL_CLEAN_FRAME_H}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"fps={sample_rate:.8f}:round=up:start_time=0,format=rgb24"
    )
    if image_source:
        cmd = [
            FFMPEG, "-hide_banner", "-loglevel", "error",
            "-i", str(path),
            "-vf",
            (
                f"scale={VISUAL_CLEAN_FRAME_W}:{VISUAL_CLEAN_FRAME_H}:force_original_aspect_ratio=decrease,"
                f"pad={VISUAL_CLEAN_FRAME_W}:{VISUAL_CLEAN_FRAME_H}:(ow-iw)/2:(oh-ih)/2:color=black,"
                "format=rgb24"
            ),
            "-frames:v", "1",
            "-f", "rawvideo",
            "pipe:1",
        ]
    else:
        # Multiple input seeks preserve temporal coverage without decoding the
        # whole clip. The vertically stacked output still uses one FFmpeg
        # process, keeping startup overhead low even for long timelines.
        safe_window = max(0.12, float(duration or 0.0))
        sample_start = max(0.0, float(start_offset or 0.0))
        sample_end = sample_start + max(0.04, safe_window - min(0.08, safe_window * 0.03))
        positions = [
            min(sample_end, sample_start + max(0.04, (sample_end - sample_start) * (0.04 + 0.92 * index / max(1, count - 1))))
            for index in range(count)
        ]
        cmd = [FFMPEG, "-hide_banner", "-loglevel", "error"]
        for position in positions:
            cmd.extend(["-ss", f"{position:.3f}", "-i", str(path)])
        scale_filter = (
            f"scale={VISUAL_CLEAN_FRAME_W}:{VISUAL_CLEAN_FRAME_H}:force_original_aspect_ratio=decrease,"
            f"pad={VISUAL_CLEAN_FRAME_W}:{VISUAL_CLEAN_FRAME_H}:(ow-iw)/2:(oh-ih)/2:color=black,"
            "setsar=1,format=rgb24"
        )
        filters = [
            f"[{index}:v]{scale_filter}[visual{index}]"
            for index in range(count)
        ]
        stacked = "".join(f"[visual{index}]" for index in range(count))
        filters.append(f"{stacked}vstack=inputs={count}[out]")
        cmd.extend([
            "-filter_complex", ";".join(filters),
            "-map", "[out]",
            "-frames:v", "1",
            "-f", "rawvideo",
            "pipe:1",
        ])
    frame_size = VISUAL_CLEAN_FRAME_W * VISUAL_CLEAN_FRAME_H * 3
    try:
        p = _run_hidden(cmd, cwd=cwd, priority="balanced", capture_output=True, timeout=30)
        data = p.stdout or b""
        if p.returncode == 0 and len(data) >= frame_size:
            available = min(count, len(data) // frame_size)
            return [
                bytes(data[index * frame_size:(index + 1) * frame_size])
                for index in range(available)
            ]
    except Exception:
        pass

    # A amostragem multipla pode falhar temporariamente quando muitos FFmpeg
    # disputam o decoder. Um frame central e suficiente para provar que o
    # arquivo continua decodificavel; falha aqui ainda nao prova corrupcao.
    fallback_cmd = [
        FFMPEG, "-hide_banner", "-loglevel", "error",
            "-ss", f"{max(0.0, float(start_offset or 0.0) + min(duration * 0.5, max(0.0, duration - 0.12))):.3f}",
        "-i", str(path),
        "-map", "0:v:0",
        "-frames:v", "1",
        "-vf",
        (
            f"scale={VISUAL_CLEAN_FRAME_W}:{VISUAL_CLEAN_FRAME_H}:force_original_aspect_ratio=decrease,"
            f"pad={VISUAL_CLEAN_FRAME_W}:{VISUAL_CLEAN_FRAME_H}:(ow-iw)/2:(oh-ih)/2:color=black,"
            "format=rgb24"
        ),
        "-f", "rawvideo",
        "pipe:1",
    ]
    try:
        fallback = _run_hidden(
            fallback_cmd,
            cwd=cwd,
            priority="balanced",
            capture_output=True,
            timeout=20,
        )
        data = fallback.stdout or b""
        if fallback.returncode == 0 and len(data) >= frame_size:
            return [bytes(data[:frame_size])]
    except Exception:
        pass
    return []


def yunet_detector_status() -> dict[str, Any]:
    import importlib.util

    model_available = YUNET_MODEL_PATH.exists()
    try:
        model_size = int(YUNET_MODEL_PATH.stat().st_size) if model_available else 0
    except Exception:
        model_size = 0
    model_valid = model_available and model_size >= 100_000
    runtime_available = importlib.util.find_spec("cv2") is not None and importlib.util.find_spec("numpy") is not None
    return {
        "engine": "opencv_yunet",
        "model": YUNET_MODEL_PATH.name,
        "model_available": model_available,
        "model_valid": model_valid,
        "model_size": model_size,
        "runtime_available": runtime_available,
        "active": bool(model_valid and runtime_available),
        "runtime_error": YUNET_RUNTIME_ERROR,
        "policy": "heuristica primeiro; YuNet somente em midia ambigua",
    }


def _probe_yunet_frames(path: Path, duration: float, cwd: Path | None = None) -> list[bytes]:
    if not FFMPEG:
        return []
    image_source = is_image_path(path)
    if image_source:
        count = 1
    elif duration < 2.0:
        count = 3
    elif duration < 8.0:
        count = 5
    else:
        count = 6
    scale_filter = (
        f"scale={YUNET_FRAME_W}:{YUNET_FRAME_H}:force_original_aspect_ratio=decrease,"
        f"pad={YUNET_FRAME_W}:{YUNET_FRAME_H}:(ow-iw)/2:(oh-ih)/2:color=black,"
        "setsar=1,format=bgr24"
    )
    command = [FFMPEG, "-hide_banner", "-loglevel", "error"]
    if image_source:
        command.extend([
            "-i", str(path),
            "-vf", scale_filter,
            "-frames:v", "1",
            "-f", "rawvideo",
            "pipe:1",
        ])
    else:
        safe_duration = max(0.08, duration - 0.08)
        if count <= 1:
            positions = [min(0.04, safe_duration)]
        else:
            positions = [
                min(safe_duration, max(0.04, safe_duration * (0.04 + 0.92 * index / (count - 1))))
                for index in range(count)
            ]
        for position in positions:
            command.extend(["-ss", f"{position:.3f}", "-i", str(path)])
        filters = [
            f"[{index}:v]{scale_filter}[yunet{index}]"
            for index in range(count)
        ]
        stacked = "".join(f"[yunet{index}]" for index in range(count))
        filters.append(f"{stacked}vstack=inputs={count}[out]")
        command.extend([
            "-filter_complex", ";".join(filters),
            "-map", "[out]",
            "-frames:v", "1",
            "-f", "rawvideo",
            "pipe:1",
        ])
    frame_size = YUNET_FRAME_W * YUNET_FRAME_H * 3
    try:
        completed = _run_hidden(command, cwd=cwd, priority="balanced", capture_output=True, timeout=30)
        data = completed.stdout or b""
        if completed.returncode != 0 or len(data) < frame_size:
            return []
        available = min(count, len(data) // frame_size)
        return [
            bytes(data[index * frame_size:(index + 1) * frame_size])
            for index in range(available)
        ]
    except Exception:
        return []


def _normalized_jitter(values: list[float], scale: float) -> float:
    if len(values) < 2 or scale <= 0:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return min(1.0, math.sqrt(variance) / scale)


def _yunet_face_analysis(path: Path, duration: float, cwd: Path | None = None) -> dict[str, Any]:
    global YUNET_DETECTOR, YUNET_RUNTIME_ERROR

    status = yunet_detector_status()
    base: dict[str, Any] = {
        **status,
        "analyzed": False,
        "samples": 0,
        "face_frames": 0,
        "face_ratio": 0.0,
        "talking_head_score": 0.0,
    }
    if not status.get("active"):
        return base
    frames = _probe_yunet_frames(path, duration, cwd=cwd)
    if not frames:
        base["runtime_error"] = "FFmpeg nao forneceu frames para o YuNet."
        return base
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore

        with YUNET_LOCK:
            if YUNET_DETECTOR is None:
                YUNET_DETECTOR = cv2.FaceDetectorYN.create(
                    str(YUNET_MODEL_PATH),
                    "",
                    (YUNET_FRAME_W, YUNET_FRAME_H),
                    0.72,
                    0.30,
                    5000,
                )
            YUNET_DETECTOR.setInputSize((YUNET_FRAME_W, YUNET_FRAME_H))
            frame_results: list[dict[str, Any]] = []
            for raw in frames:
                image = np.frombuffer(raw, dtype=np.uint8).reshape(YUNET_FRAME_H, YUNET_FRAME_W, 3)
                _retval, faces = YUNET_DETECTOR.detect(image)
                candidates: list[dict[str, float]] = []
                if faces is not None:
                    for row in faces:
                        x, y, width, height = [float(value) for value in row[:4]]
                        confidence = float(row[-1])
                        area_ratio = max(0.0, width * height) / float(YUNET_FRAME_W * YUNET_FRAME_H)
                        center_x = (x + width * 0.5) / YUNET_FRAME_W
                        center_y = (y + height * 0.5) / YUNET_FRAME_H
                        distance = min(1.0, math.hypot(center_x - 0.5, center_y - 0.48) / 0.72)
                        candidates.append({
                            "confidence": confidence,
                            "area_ratio": area_ratio,
                            "center_x": center_x,
                            "center_y": center_y,
                            "centrality": 1.0 - distance,
                        })
                candidates.sort(key=lambda item: (item["area_ratio"], item["confidence"]), reverse=True)
                frame_results.append({
                    "count": len(candidates),
                    "dominant": candidates[0] if candidates else None,
                })
    except Exception as exc:
        YUNET_RUNTIME_ERROR = str(exc)
        base["runtime_error"] = YUNET_RUNTIME_ERROR
        return base

    dominant = [item["dominant"] for item in frame_results if item.get("dominant")]
    face_flags = [
        bool(
            item.get("dominant")
            and float(item["dominant"].get("confidence") or 0.0) >= 0.72
            and float(item["dominant"].get("area_ratio") or 0.0) >= 0.003
        )
        for item in frame_results
    ]
    face_frames = sum(face_flags)
    samples = len(frame_results)
    face_ratio = face_frames / max(1, samples)
    areas = [float(item.get("area_ratio") or 0.0) for item in dominant]
    centers_x = [float(item.get("center_x") or 0.5) for item in dominant]
    centers_y = [float(item.get("center_y") or 0.5) for item in dominant]
    centralities = [float(item.get("centrality") or 0.0) for item in dominant]
    confidences = [float(item.get("confidence") or 0.0) for item in dominant]
    median_area = _median(areas)
    median_centrality = _median(centralities)
    center_jitter = max(
        _normalized_jitter(centers_x, 0.24),
        _normalized_jitter(centers_y, 0.24),
    )
    size_jitter = _normalized_jitter(areas, max(0.025, median_area))
    stability = max(0.0, 1.0 - center_jitter * 0.62 - size_jitter * 0.38)
    consecutive = _max_consecutive_flags(face_flags)
    talking_head_score = 0.0 if face_frames <= 0 else min(1.0, (
        face_ratio * 0.34
        + median_centrality * 0.18
        + min(1.0, median_area / 0.12) * 0.22
        + stability * 0.18
        + (consecutive / max(1, samples)) * 0.08
    ))
    return {
        **status,
        "analyzed": True,
        "samples": samples,
        "face_frames": face_frames,
        "face_ratio": round(face_ratio, 4),
        "max_consecutive_faces": consecutive,
        "median_face_area_ratio": round(median_area, 4),
        "median_centrality": round(median_centrality, 4),
        "median_confidence": round(_median(confidences), 4),
        "max_faces": max((int(item.get("count") or 0) for item in frame_results), default=0),
        "center_jitter": round(center_jitter, 4),
        "size_jitter": round(size_jitter, 4),
        "stability": round(stability, 4),
        "talking_head_score": round(talking_head_score, 4),
    }


def _quick_visual_frame_features(frame: bytes) -> tuple[dict[str, float], bytes]:
    total = max(1, VISUAL_CLEAN_FRAME_W * VISUAL_CLEAN_FRAME_H)
    gray = bytearray(total)
    total_value = 0
    total_square = 0
    for idx in range(total):
        base = idx * 3
        value = (77 * frame[base] + 150 * frame[base + 1] + 29 * frame[base + 2]) >> 8
        gray[idx] = value
        total_value += value
        total_square += value * value
    mean = total_value / total
    variance = max(0.0, total_square / total - mean * mean)
    return {"mean": mean, "stdev": variance ** 0.5}, bytes(gray)


def _visual_frame_features(frame: bytes, gray_source: bytes | None = None) -> tuple[dict[str, float], bytes, bytes]:
    w = VISUAL_CLEAN_FRAME_W
    h = VISUAL_CLEAN_FRAME_H
    total = max(1, w * h)
    gray = bytearray(gray_source) if gray_source and len(gray_source) == total else bytearray(total)
    calculate_gray = not bool(gray_source and len(gray_source) == total)
    skin = bytearray(total)
    center_skin = 0
    head_skin = 0
    torso_skin = 0
    center_pixels = 0
    head_pixels = 0
    torso_pixels = 0
    red_total = 0
    green_total = 0
    blue_total = 0
    saturation_total = 0.0
    for idx in range(total):
        base = idx * 3
        r, g, b = frame[base], frame[base + 1], frame[base + 2]
        red_total += r
        green_total += g
        blue_total += b
        highest = max(r, g, b)
        lowest = min(r, g, b)
        saturation_total += (highest - lowest) / max(1, highest)
        if calculate_gray:
            gray[idx] = (77 * r + 150 * g + 29 * b) >> 8
        is_skin = (
            r >= 72 and g >= 38 and b >= 20
            and max(r, g, b) - min(r, g, b) >= 14
            and r >= g * 0.94 and r >= b * 1.08
        )
        x = idx % w
        y = idx // w
        if int(w * 0.24) <= x <= int(w * 0.76) and int(h * 0.08) <= y <= int(h * 0.90):
            center_pixels += 1
            if is_skin:
                center_skin += 1
        if int(w * 0.32) <= x <= int(w * 0.68) and int(h * 0.06) <= y <= int(h * 0.54):
            head_pixels += 1
            if is_skin:
                head_skin += 1
        if int(w * 0.24) <= x <= int(w * 0.76) and int(h * 0.34) <= y <= int(h * 0.92):
            torso_pixels += 1
            if is_skin:
                torso_skin += 1
        if is_skin:
            skin[idx] = 1
    values = gray
    mean = sum(values) / total
    variance = sum((px - mean) * (px - mean) for px in values) / total
    stdev = variance ** 0.5

    edge_threshold = 26
    edge_count = 0
    center_edges = 0
    top_edges = 0
    middle_edges = 0
    bottom_edges = 0
    rows = [0] * h
    cols = [0] * w
    edge_mask = bytearray(total)
    cell_w = 8
    cell_h = 6
    grid_w = max(1, w // cell_w)
    grid_h = max(1, h // cell_h)
    cells = [0] * (grid_w * grid_h)
    center_x0 = int(w * 0.30)
    center_x1 = int(w * 0.70)
    for y in range(1, h - 1):
        row_off = y * w
        for x in range(1, w - 1):
            idx = row_off + x
            gx = abs(values[idx] - values[idx - 1]) + abs(values[idx] - values[idx + 1])
            gy = abs(values[idx] - values[idx - w]) + abs(values[idx] - values[idx + w])
            if max(gx, gy) >= edge_threshold:
                edge_mask[idx] = 1
                edge_count += 1
                rows[y] += 1
                cols[x] += 1
                if y < h * 0.33:
                    top_edges += 1
                elif y < h * 0.67:
                    middle_edges += 1
                else:
                    bottom_edges += 1
                if center_x0 <= x <= center_x1:
                    center_edges += 1
                cx = min(grid_w - 1, x // cell_w)
                cy = min(grid_h - 1, y // cell_h)
                cells[cy * grid_w + cx] += 1

    edge_density = edge_count / total
    active_rows = sum(1 for value in rows if value >= w * 0.12) / h
    active_cols = sum(1 for value in cols if value >= h * 0.10) / w
    active_cells = sum(1 for value in cells if value >= cell_w * cell_h * 0.13) / max(1, len(cells))
    center_ratio = center_edges / max(1, edge_count)
    active_row_indexes = [index for index, value in enumerate(rows) if value >= w * 0.12]
    vertical_span = (
        (active_row_indexes[-1] - active_row_indexes[0] + 1) / h
        if active_row_indexes else 0.0
    )
    side_edges = max(0, edge_count - center_edges)
    side_density = side_edges / max(1, total - ((center_x1 - center_x0 + 1) * h))
    metrics = {
        "mean": round(mean, 3),
        "stdev": round(stdev, 3),
        "edge_density": round(edge_density, 5),
        "active_rows": round(active_rows, 5),
        "active_cols": round(active_cols, 5),
        "active_cells": round(active_cells, 5),
        "center_edge_ratio": round(center_ratio, 5),
        "side_edge_density": round(side_density, 5),
        "vertical_span": round(vertical_span, 5),
        "top_edge_share": round(top_edges / max(1, edge_count), 5),
        "middle_edge_share": round(middle_edges / max(1, edge_count), 5),
        "bottom_edge_share": round(bottom_edges / max(1, edge_count), 5),
        "center_skin_ratio": round(center_skin / max(1, center_pixels), 5),
        "head_skin_ratio": round(head_skin / max(1, head_pixels), 5),
        "torso_skin_ratio": round(torso_skin / max(1, torso_pixels), 5),
        "red_mean": round(red_total / total, 3),
        "green_mean": round(green_total / total, 3),
        "blue_mean": round(blue_total / total, 3),
        "saturation_mean": round(saturation_total / total, 5),
    }
    return metrics, bytes(gray), bytes(edge_mask)


def _classify_visual_analysis(
    result: dict[str, Any],
    level: str,
    context: dict[str, Any] | None = None,
    media_kind: str = "video",
) -> dict[str, Any]:
    classified = dict(result)
    classified["level"] = level
    classified["media_kind"] = media_kind
    if classified.get("category") == "invalid":
        return classified
    metrics = classified.get("metrics") if isinstance(classified.get("metrics"), dict) else {}
    temporal = metrics.get("temporal") if isinstance(metrics.get("temporal"), dict) else {}
    context = context or {}
    subject_relevance = max(0.0, min(1.0, float(context.get("subject_relevance") or 0.0)))
    contextual_person = bool(context.get("person_context_expected")) and subject_relevance >= 0.56
    documentary_context = bool(context.get("documentary_context"))
    med_mean = float(metrics.get("mean") or 0.0)
    med_stdev = float(metrics.get("stdev") or 0.0)
    med_edge = float(metrics.get("edge_density") or 0.0)
    med_diff = float(metrics.get("frame_diff") or 0.0)
    med_persistence = float(metrics.get("edge_persistence") or 0.0)
    med_span = float(metrics.get("vertical_span") or 0.0)
    med_rows = float(metrics.get("active_rows") or 0.0)
    med_cols = float(metrics.get("active_cols") or 0.0)
    med_bottom = float(metrics.get("bottom_edge_share") or 0.0)
    med_skin = float(metrics.get("center_skin_ratio") or 0.0)
    med_head_skin = float(metrics.get("head_skin_ratio") or 0.0)
    med_center = float(metrics.get("center_edge_ratio") or 0.0)
    text_score = float(metrics.get("text_score") or 0.0)
    presenter_score = float(metrics.get("presenter_score") or 0.0)
    text_ratio = float(temporal.get("text_ratio") or 0.0)
    presenter_ratio = float(temporal.get("presenter_ratio") or 0.0)
    max_text = float(temporal.get("max_text_score") or text_score)
    max_presenter = float(temporal.get("max_presenter_score") or presenter_score)
    consecutive_text = int(temporal.get("max_consecutive_text") or 0)
    consecutive_presenter = int(temporal.get("max_consecutive_presenter") or 0)
    scene_change_ratio = float(temporal.get("scene_change_ratio") or 0.0)
    pollution_ratio = float(temporal.get("pollution_ratio") or 0.0)
    sample_count = max(1, int(classified.get("samples") or 1))
    face_detector = metrics.get("face_detector") if isinstance(metrics.get("face_detector"), dict) else {}
    yunet_analyzed = bool(face_detector.get("analyzed"))
    yunet_face_ratio = float(face_detector.get("face_ratio") or 0.0)
    yunet_talking_score = float(face_detector.get("talking_head_score") or 0.0)
    yunet_consecutive = int(face_detector.get("max_consecutive_faces") or 0)
    heuristic_max_presenter = max_presenter
    if yunet_analyzed:
        presenter_ratio = yunet_face_ratio
        consecutive_presenter = yunet_consecutive
        max_presenter = max(yunet_talking_score, heuristic_max_presenter * 0.45)
    is_image = media_kind == "image"
    level = "strict" if is_image else (level if level in {"strict", "normal", "light"} else "normal")
    classified["level"] = level

    thresholds = {
        "light": {"ratio": 0.80, "text": 0.82, "presenter": 0.78},
        "normal": {"ratio": 0.45, "text": 0.72, "presenter": 0.69},
        "strict": {"ratio": 1.0 / sample_count, "text": 0.66, "presenter": 0.64},
    }[level]
    text_confirmed = (
        max_text >= thresholds["text"]
        and (
            text_ratio >= thresholds["ratio"]
            or (level == "normal" and consecutive_text >= 2)
            or (level == "strict" and text_ratio > 0.0)
        )
    )
    if yunet_analyzed:
        yunet_thresholds = {
            "light": {"score": 0.80, "ratio": 0.75},
            "normal": {"score": 0.69, "ratio": 0.45},
            "strict": {"score": 0.64, "ratio": 0.25},
        }[level]
        presenter_confirmed = bool(
            (
                yunet_talking_score >= yunet_thresholds["score"]
                and yunet_face_ratio >= yunet_thresholds["ratio"]
                and (level == "light" or yunet_consecutive >= 2)
            )
            or (
                context.get("presentation_hint")
                and yunet_face_ratio > 0.0
                and yunet_talking_score >= yunet_thresholds["score"] - 0.08
            )
            or (
                context.get("presentation_hint")
                and yunet_face_ratio == 0.0
                and heuristic_max_presenter >= 0.82
            )
        )
    elif level == "strict":
        presenter_confirmed = bool(
            context.get("presentation_hint")
            or (
                max_presenter >= max(0.80, thresholds["presenter"])
                and (consecutive_presenter >= 2 or presenter_ratio >= 0.25)
            )
        )
    else:
        presenter_confirmed = bool(
            max_presenter >= thresholds["presenter"]
            and (
                presenter_ratio >= thresholds["ratio"]
                or (level == "normal" and consecutive_presenter >= 2)
            )
        )
    # Real-world footage tends to have camera/scene variation. A relevant
    # subject in sport, archive, news or events must not become a talking head
    # merely because a face occupies the frame.
    contextual_override = contextual_person and (
        documentary_context or scene_change_ratio >= 0.12 or med_diff >= 8.5
    )
    image_quality_low = bool(
        is_image and (
            med_stdev < 8.0
            or float(metrics.get("quality_score") or 1.0) < 0.42
        )
    )

    classified.update({"category": "clean", "action": "keep", "reason": "clipe limpo", "confidence": 0.0})
    if med_mean <= VIDEO_BLACK_YAVG_MAX and med_stdev <= 4.0 and med_edge <= 0.004:
        classified.update({"category": "black_screen", "action": "hard_reject", "reason": "tela preta/sem conteudo visual", "confidence": 1.0})
    elif image_quality_low:
        classified.update({
            "category": "low_quality",
            "action": "hard_reject",
            "reason": "imagem com qualidade visual insuficiente",
            "confidence": 0.88,
        })
    elif text_confirmed:
        confidence = min(0.99, max(max_text, text_ratio + 0.15))
        classified.update({
            "category": "text_dominant",
            "action": "hard_reject",
            "reason": "texto, legenda ou marca visual persistente",
            "confidence": confidence,
        })
    elif presenter_confirmed and contextual_override:
        classified.update({
            "category": "person_contextual",
            "action": "keep",
            "reason": "pessoa ligada ao tema em cena documental, evento ou arquivo",
            "confidence": min(0.96, max(subject_relevance, max_presenter)),
        })
    elif presenter_confirmed:
        confidence = min(0.98, max(max_presenter, presenter_ratio + 0.15))
        classified.update({
            "category": "presenter",
            "action": "hard_reject",
            "reason": "apresentador, avatar ou talking head persistente",
            "confidence": confidence,
        })
    elif max_presenter >= thresholds["presenter"] - 0.10 or text_ratio > 0.0 or pollution_ratio >= 0.45:
        classified.update({
            "category": "suspect",
            "action": "soft_suspect",
            "reason": "evidencia visual ambigua; preservado para revisao/fallback",
            "confidence": min(0.79, max(max_presenter, max_text, pollution_ratio)),
        })
    classified["evidence"] = {
        "text_ratio": round(text_ratio, 3),
        "presenter_ratio": round(presenter_ratio, 3),
        "pollution_ratio": round(pollution_ratio, 3),
        "scene_change_ratio": round(scene_change_ratio, 3),
        "subject_relevance": round(subject_relevance, 3),
        "samples": sample_count,
        "text_windows": list(temporal.get("text_windows") or [])[:18],
        "presenter_windows": list(temporal.get("presenter_windows") or [])[:18],
        "presenter_heuristic_score": round(heuristic_max_presenter, 3),
        "face_detector": face_detector,
    }
    return classified


def _visual_window_score_from_frames(frames: list[bytes]) -> dict[str, Any]:
    if not frames:
        return {"score": 0.0, "label": "sem_frames", "reason": "sem frames para janela"}
    quick_features: list[dict[str, float]] = []
    grays: list[bytes] = []
    for frame in frames:
        quick, gray = _quick_visual_frame_features(frame)
        quick_features.append(quick)
        grays.append(gray)
    mean = _median([float(item.get("mean") or 0.0) for item in quick_features])
    stdev = _median([float(item.get("stdev") or 0.0) for item in quick_features])
    motion = _median([
        _mean_abs_frame_diff(grays[index], grays[index - 1])
        for index in range(1, len(grays))
    ]) if len(grays) > 1 else 0.0
    if mean < 7.0 and stdev < 6.5:
        return {
            "score": 0.03,
            "label": "preto",
            "reason": "janela quase preta",
            "mean": round(mean, 2),
            "stdev": round(stdev, 2),
            "motion": round(motion, 2),
        }
    if stdev >= 24.0 and motion >= 1.8:
        return {
            "score": 0.92,
            "label": "limpo",
            "reason": "janela com contraste e movimento saudaveis",
            "mean": round(mean, 2),
            "stdev": round(stdev, 2),
            "motion": round(motion, 2),
        }
    detailed: list[dict[str, Any]] = []
    for frame, gray in zip(frames, grays):
        metrics, _, _ = _visual_frame_features(frame, gray)
        detailed.append(metrics)
    edge_density = _median([float(item.get("edge_density") or 0.0) for item in detailed])
    active_rows = _median([float(item.get("active_rows") or 0.0) for item in detailed])
    active_cols = _median([float(item.get("active_cols") or 0.0) for item in detailed])
    center_skin = _median([float(item.get("center_skin_ratio") or 0.0) for item in detailed])
    head_skin = _median([float(item.get("head_skin_ratio") or 0.0) for item in detailed])
    saturation = _median([float(item.get("saturation_mean") or 0.0) for item in detailed])
    text_penalty = 0.0
    if edge_density > 0.11 and active_rows > 0.42 and active_cols > 0.34:
        text_penalty = 0.42
    elif edge_density > 0.08 and active_rows > 0.32:
        text_penalty = 0.20
    presenter_penalty = 0.0
    if center_skin > 0.10 and head_skin > 0.12 and motion < 3.0:
        presenter_penalty = 0.18
    base = 0.56 + min(0.22, stdev / 145.0) + min(0.18, motion / 24.0) + min(0.06, saturation / 6.0)
    score = max(0.04, min(0.96, base - text_penalty - presenter_penalty))
    label = "texto" if text_penalty >= 0.35 else ("apresentador" if presenter_penalty else "limpo")
    return {
        "score": round(score, 3),
        "label": label,
        "reason": "texto dominante" if text_penalty >= 0.35 else ("apresentador provavel" if presenter_penalty else "janela visualmente utilizavel"),
        "mean": round(mean, 2),
        "stdev": round(stdev, 2),
        "motion": round(motion, 2),
        "edge_density": round(edge_density, 4),
        "active_rows": round(active_rows, 4),
        "active_cols": round(active_cols, 4),
        "center_skin_ratio": round(center_skin, 4),
    }


def probe_visual_window_scores(path: Path, duration: float, cwd: Path | None = None) -> dict[str, Any]:
    if duration <= 1.2 or is_image_path(path):
        return {"enabled": False, "reason": "midia curta ou imagem", "windows": []}
    cache_key = visual_clean_cache_key(path, duration, cwd=cwd, scope="windows_v3_batch")
    cached = VISUAL_CLEAN_CACHE.get(cache_key)
    if isinstance(cached, dict):
        cached_result = dict(cached)
        cached_result["cache_hit"] = True
        return cached_result
    window_seconds = min(2.4, max(1.0, duration * 0.18))
    max_start = max(0.0, duration - window_seconds - 0.08)
    sample_count = 4 if duration < 8.0 else (6 if duration < 22.0 else 8)
    even_starts = [
        0.0 if sample_count <= 1 else max_start * (idx / max(1, sample_count - 1))
        for idx in range(sample_count)
    ]
    starts = sorted({
        round(min(max_start, max(0.0, value)), 3)
        for value in [*even_starts, duration * 0.18, duration * 0.50, duration * 0.82]
    })
    # Reuse one temporally distributed extraction for every window. The old
    # implementation launched up to eight FFmpeg processes per clip.
    all_frames = _probe_visual_clean_frames(path, duration, cwd=cwd)
    windows: list[dict[str, Any]] = []
    frame_total = len(all_frames)
    group_size = max(1, min(4, frame_total // max(1, sample_count)))
    for index, start in enumerate(starts[:sample_count]):
        if not frame_total:
            frames: list[bytes] = []
        else:
            center = round(index * (frame_total - 1) / max(1, sample_count - 1))
            left = max(0, center - group_size // 2)
            right = min(frame_total, left + group_size)
            left = max(0, right - group_size)
            frames = all_frames[left:right]
        scored = _visual_window_score_from_frames(frames)
        scored.update({"start": start, "duration": round(window_seconds, 3)})
        windows.append(scored)
    if not windows:
        result = {"enabled": True, "cache_hit": False, "best_offset": 0.0, "best_score": 0.0, "windows": []}
    else:
        best = max(windows, key=lambda item: float(item.get("score") or 0.0))
        result = {
            "enabled": True,
            "cache_hit": False,
            "window_seconds": round(window_seconds, 3),
            "best_offset": float(best.get("start") or 0.0),
            "best_score": round(float(best.get("score") or 0.0), 3),
            "best_label": best.get("label"),
            "best_reason": best.get("reason"),
            "sample_count": sample_count,
            "extraction_processes": 1,
            "policy": "uma extracao temporal compartilhada; usa o melhor trecho saudavel sem processos FFmpeg repetidos",
            "windows": windows,
        }
    VISUAL_CLEAN_CACHE[cache_key] = dict(result)
    return result


def _mean_abs_frame_diff(a: bytes, b: bytes) -> float:
    if not a or not b or len(a) != len(b):
        return 255.0
    return sum(abs(x - y) for x, y in zip(a, b)) / max(1, len(a))


def _edge_persistence(a: bytes, b: bytes) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    overlap = 0
    smaller = min(sum(a), sum(b))
    if smaller <= 0:
        return 0.0
    for left, right in zip(a, b):
        if left and right:
            overlap += 1
    return overlap / smaller


def _median(values: list[float], fallback: float = 0.0) -> float:
    if not values:
        return fallback
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2.0)


def _max_consecutive_flags(flags: list[bool]) -> int:
    best = current = 0
    for flag in flags:
        current = current + 1 if flag else 0
        best = max(best, current)
    return best


def probe_visual_clean_health(
    path: Path,
    duration: float,
    level: str,
    cwd: Path | None = None,
    context: dict[str, Any] | None = None,
    media_kind: str = "video",
) -> dict[str, Any]:
    level = {"balanced": "normal"}.get(level, level)
    level = level if level in {"strict", "normal", "light"} else "normal"
    key = visual_clean_cache_key(path, duration, cwd)
    with VISUAL_CLEAN_CACHE_LOCK:
        cached = VISUAL_CLEAN_CACHE.get(key)
    if cached:
        result = _classify_visual_analysis(dict(cached), level, context=context, media_kind=media_kind)
        result["cache_hit"] = True
        return result
    result: dict[str, Any] = {
        "category": "clean",
        "action": "keep",
        "reason": "clipe limpo",
        "confidence": 0.0,
        "level": level,
        "samples": 0,
        "duration": round(duration, 3),
        "metrics": {},
        "cache_hit": False,
    }
    frames = _probe_visual_clean_frames(path, duration, cwd=cwd)
    if not frames:
        has_video_stream = probe_has_video(_resolved_media_path(path, cwd))
        result.update({
            "category": "analysis_unavailable" if has_video_stream else "no_frames",
            "action": "soft_suspect" if has_video_stream else "hard_reject",
            "reason": (
                "analise visual temporariamente indisponivel; preservado como suspeito"
                if has_video_stream
                else "arquivo sem stream ou frames de video"
            ),
            "confidence": 0.35 if has_video_stream else 1.0,
        })
        # Nao persista falhas transitorias. Uma proxima analise podera tentar
        # novamente sem condenar permanentemente uma midia saudavel.
        return result

    quick_features = [_quick_visual_frame_features(frame) for frame in frames]
    quick_metrics = [item[0] for item in quick_features]
    quick_gray = [item[1] for item in quick_features]
    quick_diffs = [_mean_abs_frame_diff(quick_gray[i - 1], quick_gray[i]) for i in range(1, len(quick_gray))]
    quick_mean = _median([float(item["mean"]) for item in quick_metrics])
    quick_stdev = _median([float(item["stdev"]) for item in quick_metrics])
    quick_diff = _median(quick_diffs, 0.0 if len(frames) == 1 else 255.0)
    if quick_mean <= VIDEO_BLACK_YAVG_MAX and quick_stdev <= 3.5:
        result.update({
            "samples": len(frames),
            "metrics": {"mean": round(quick_mean, 2), "stdev": round(quick_stdev, 2), "frame_diff": round(quick_diff, 2)},
            "category": "black_screen",
            "action": "hard_reject",
            "reason": "tela preta/sem conteudo visual",
            "confidence": 1.0,
        })
        with VISUAL_CLEAN_CACHE_LOCK:
            VISUAL_CLEAN_CACHE[key] = dict(result)
        return result
    features = [
        _visual_frame_features(frame, quick_gray[index])
        for index, frame in enumerate(frames)
    ]
    metrics = [item[0] for item in features]
    gray_frames = [item[1] for item in features]
    edge_masks = [item[2] for item in features]
    diffs = [_mean_abs_frame_diff(gray_frames[i - 1], gray_frames[i]) for i in range(1, len(gray_frames))]
    persistence_values = [_edge_persistence(edge_masks[i - 1], edge_masks[i]) for i in range(1, len(edge_masks))]
    med_edge = _median([float(item["edge_density"]) for item in metrics])
    med_cells = _median([float(item["active_cells"]) for item in metrics])
    med_rows = _median([float(item["active_rows"]) for item in metrics])
    med_cols = _median([float(item["active_cols"]) for item in metrics])
    med_center = _median([float(item["center_edge_ratio"]) for item in metrics])
    med_side = _median([float(item["side_edge_density"]) for item in metrics])
    med_stdev = _median([float(item["stdev"]) for item in metrics])
    med_mean = _median([float(item["mean"]) for item in metrics])
    med_span = _median([float(item["vertical_span"]) for item in metrics])
    med_bottom = _median([float(item["bottom_edge_share"]) for item in metrics])
    med_skin = _median([float(item["center_skin_ratio"]) for item in metrics])
    med_head_skin = _median([float(item["head_skin_ratio"]) for item in metrics])
    med_torso_skin = _median([float(item["torso_skin_ratio"]) for item in metrics])
    med_red = _median([float(item.get("red_mean") or 0.0) for item in metrics])
    med_green = _median([float(item.get("green_mean") or 0.0) for item in metrics])
    med_blue = _median([float(item.get("blue_mean") or 0.0) for item in metrics])
    med_saturation = _median([float(item.get("saturation_mean") or 0.0) for item in metrics])
    med_diff = _median(diffs, 0.0 if len(frames) == 1 else 255.0)
    med_persistence = _median(persistence_values)
    lower_third = med_bottom >= 0.48 and med_cols >= 0.55
    column_dominance = max(0.0, med_cols - med_rows)
    text_score = min(1.0, (
        min(1.0, med_edge / 0.10) * 0.14
        + min(1.0, med_cells / 0.20) * 0.14
        + min(1.0, med_span / 0.55) * 0.10
        + med_persistence * 0.24
        + max(0.0, 1.0 - med_diff / 22.0) * 0.16
        + min(1.0, column_dominance / 0.35) * 0.22
    ) * (0.42 if lower_third else 1.0) * max(0.58, 1.0 - med_skin * 1.8))
    presenter_score = min(1.0, (
        min(1.0, med_head_skin / 0.11) * 0.34
        + min(1.0, med_torso_skin / 0.13) * 0.19
        + min(1.0, med_skin / 0.12) * 0.17
        + min(1.0, med_center / 0.58) * 0.12
        + max(0.0, 1.0 - med_diff / 38.0) * 0.12
        + med_persistence * 0.06
    ))
    sample_text_scores: list[float] = []
    sample_presenter_scores: list[float] = []
    sample_pollution_scores: list[float] = []
    for index, item in enumerate(metrics):
        local_motion_values = []
        if index > 0 and index - 1 < len(diffs):
            local_motion_values.append(float(diffs[index - 1]))
        if index < len(diffs):
            local_motion_values.append(float(diffs[index]))
        local_motion = sum(local_motion_values) / len(local_motion_values) if local_motion_values else med_diff
        edge = float(item.get("edge_density") or 0.0)
        rows = float(item.get("active_rows") or 0.0)
        cols = float(item.get("active_cols") or 0.0)
        cells = float(item.get("active_cells") or 0.0)
        span = float(item.get("vertical_span") or 0.0)
        skin = float(item.get("center_skin_ratio") or 0.0)
        head = float(item.get("head_skin_ratio") or 0.0)
        torso = float(item.get("torso_skin_ratio") or 0.0)
        center = float(item.get("center_edge_ratio") or 0.0)
        column_dominance = max(0.0, cols - rows)
        frame_text = min(1.0, (
            min(1.0, edge / 0.11) * 0.22
            + min(1.0, cells / 0.22) * 0.18
            + min(1.0, span / 0.58) * 0.13
            + min(1.0, cols / 0.72) * 0.12
            + min(1.0, column_dominance / 0.32) * 0.23
            + max(0.0, 1.0 - local_motion / 28.0) * 0.12
        ) * max(0.62, 1.0 - skin * 1.4))
        frame_presenter = min(1.0, (
            min(1.0, head / 0.105) * 0.34
            + min(1.0, torso / 0.14) * 0.18
            + min(1.0, skin / 0.115) * 0.16
            + min(1.0, center / 0.60) * 0.14
            + max(0.0, 1.0 - local_motion / 25.0) * 0.18
        ))
        pollution = min(1.0, edge / 0.19 + cells / 0.42 + max(0.0, cols - 0.72))
        sample_text_scores.append(round(frame_text, 4))
        sample_presenter_scores.append(round(frame_presenter, 4))
        sample_pollution_scores.append(round(pollution, 4))
    text_flags = [score >= 0.66 for score in sample_text_scores]
    presenter_flags = [score >= 0.64 for score in sample_presenter_scores]
    scene_change_flags = [float(value) >= 18.0 for value in diffs]
    pollution_flags = [score >= 0.72 for score in sample_pollution_scores]
    quality_score = min(1.0, (
        min(1.0, med_stdev / 30.0) * 0.52
        + min(1.0, med_edge / 0.08) * 0.28
        + min(1.0, med_saturation / 0.22) * 0.20
    ))
    temporal_metrics = {
        "sample_count": len(frames),
        "coverage_ratio": 1.0,
        "text_ratio": round(sum(text_flags) / max(1, len(text_flags)), 4),
        "presenter_ratio": round(sum(presenter_flags) / max(1, len(presenter_flags)), 4),
        "pollution_ratio": round(sum(pollution_flags) / max(1, len(pollution_flags)), 4),
        "scene_change_ratio": round(sum(scene_change_flags) / max(1, len(scene_change_flags)), 4),
        "max_text_score": max(sample_text_scores, default=0.0),
        "max_presenter_score": max(sample_presenter_scores, default=0.0),
        "max_consecutive_text": _max_consecutive_flags(text_flags),
        "max_consecutive_presenter": _max_consecutive_flags(presenter_flags),
        "text_windows": [index + 1 for index, flag in enumerate(text_flags) if flag],
        "presenter_windows": [index + 1 for index, flag in enumerate(presenter_flags) if flag],
        "text_scores": sample_text_scores,
        "presenter_scores": sample_presenter_scores,
    }
    summary_metrics = {
        "edge_density": round(med_edge, 4),
        "active_cells": round(med_cells, 4),
        "active_rows": round(med_rows, 4),
        "active_cols": round(med_cols, 4),
        "center_edge_ratio": round(med_center, 4),
        "side_edge_density": round(med_side, 4),
        "mean": round(med_mean, 2),
        "stdev": round(med_stdev, 2),
        "frame_diff": round(med_diff, 2),
        "edge_persistence": round(med_persistence, 3),
        "vertical_span": round(med_span, 3),
        "bottom_edge_share": round(med_bottom, 3),
        "lower_third": lower_third,
        "center_skin_ratio": round(med_skin, 3),
        "head_skin_ratio": round(med_head_skin, 3),
        "torso_skin_ratio": round(med_torso_skin, 3),
        "text_score": round(text_score, 3),
        "presenter_score": round(presenter_score, 3),
        "red_mean": round(med_red, 2),
        "green_mean": round(med_green, 2),
        "blue_mean": round(med_blue, 2),
        "saturation_mean": round(med_saturation, 4),
        "quality_score": round(quality_score, 4),
        "temporal": temporal_metrics,
        "fingerprint": fingerprint_from_bytes(gray_frames[len(gray_frames) // 2], VISUAL_CLEAN_FRAME_W, VISUAL_CLEAN_FRAME_H),
    }
    if media_kind == "image" or is_image_path(path):
        media_info = _probe_reference_video_info(_resolved_media_path(path, cwd))
        width = int(media_info.get("width") or 0)
        height = int(media_info.get("height") or 0)
        summary_metrics["width"] = width
        summary_metrics["height"] = height
        summary_metrics["resolution_ok"] = bool(width >= 640 and height >= 360)
        if not summary_metrics["resolution_ok"]:
            summary_metrics["quality_score"] = min(float(summary_metrics.get("quality_score") or 0.0), 0.35)
    clear_text_signal = bool(
        max(sample_text_scores, default=0.0) >= 0.78
        and sum(text_flags) / max(1, len(text_flags)) >= 0.50
    )
    face_ambiguous = bool(
        (context or {}).get("presentation_hint")
        or max(sample_presenter_scores, default=0.0) >= 0.54
        or presenter_score >= 0.56
        or med_head_skin >= 0.035
        or (media_kind == "image" and med_skin >= 0.025)
    )
    if face_ambiguous and not clear_text_signal:
        summary_metrics["face_detector"] = _yunet_face_analysis(path, duration, cwd=cwd)
    else:
        summary_metrics["face_detector"] = {
            **yunet_detector_status(),
            "analyzed": False,
            "reason": "YuNet dispensado: heuristica conclusiva sem ambiguidade facial",
        }
    result.update({"samples": len(frames), "metrics": summary_metrics})
    with VISUAL_CLEAN_CACHE_LOCK:
        VISUAL_CLEAN_CACHE[key] = dict(result)
    return _classify_visual_analysis(result, level, context=context, media_kind=media_kind)


def semantic_model_status() -> dict[str, Any]:
    model_file = MODEL_PACK_ROOT / "model.onnx"
    labels_file = MODEL_PACK_ROOT / "labels.json"
    embeddings_file = MODEL_PACK_ROOT / "text_embeddings.json"
    runtime_available = False
    runtime_error = ""
    try:
        import onnxruntime  # type: ignore  # noqa: F401
        runtime_available = True
    except Exception as exc:
        runtime_error = str(exc)
    installed = model_file.exists() and labels_file.exists()
    compatible = installed and embeddings_file.exists()
    return {
        "installed": installed,
        "compatible": compatible,
        "active": bool(compatible and runtime_available),
        "runtime_available": runtime_available,
        "mode": "mobileclip" if compatible and runtime_available else "heuristic_fallback",
        "path": str(MODEL_PACK_ROOT),
        "model_file": model_file.name if model_file.exists() else None,
        "labels_file": labels_file.name if labels_file.exists() else None,
        "embeddings_file": embeddings_file.name if embeddings_file.exists() else None,
        "runtime_error": runtime_error if not runtime_available else "",
        "note": (
            "Modelo local ativo."
            if compatible and runtime_available
            else (
                "Pacote detectado, mas text_embeddings.json ou runtime ainda nao esta disponivel; fallback local ativo."
                if installed
                else "Classificacao por frames e vocabulario local ativa; o pacote ONNX e opcional."
            )
        ),
    }


def semantic_model_categories(path: Path, duration: float = 0.0, cwd: Path | None = None) -> list[dict[str, Any]]:
    status = semantic_model_status()
    if not status.get("active") or not FFMPEG:
        return []
    try:
        import numpy as np  # type: ignore
        import onnxruntime as ort  # type: ignore
        global SEMANTIC_MODEL_SESSION, SEMANTIC_MODEL_EMBEDDINGS
        with SEMANTIC_MODEL_LOCK:
            if SEMANTIC_MODEL_SESSION is None:
                SEMANTIC_MODEL_SESSION = ort.InferenceSession(
                    str(MODEL_PACK_ROOT / "model.onnx"),
                    providers=["CPUExecutionProvider"],
                )
            if SEMANTIC_MODEL_EMBEDDINGS is None:
                raw = json.loads((MODEL_PACK_ROOT / "text_embeddings.json").read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    labels = [str(key) for key in raw]
                    matrix = np.asarray([raw[key] for key in raw], dtype=np.float32)
                else:
                    labels = [str(item.get("label") or item.get("name")) for item in raw]
                    matrix = np.asarray([item.get("embedding") or item.get("vector") for item in raw], dtype=np.float32)
                matrix /= np.maximum(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-8)
                SEMANTIC_MODEL_EMBEDDINGS = (labels, matrix)
            session = SEMANTIC_MODEL_SESSION
            labels, text_matrix = SEMANTIC_MODEL_EMBEDDINGS
        resolved = _resolved_media_path(path, cwd)
        seek = max(0.0, duration * 0.45)
        raw_frame = _run_hidden(
            [
                FFMPEG, "-hide_banner", "-loglevel", "error",
                "-ss", f"{seek:.3f}", "-i", str(resolved),
                "-frames:v", "1",
                "-vf", "scale=224:224:force_original_aspect_ratio=increase,crop=224:224",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
            ],
            cwd=cwd,
            capture_output=True,
            timeout=30,
        ).stdout
        if len(raw_frame or b"") != 224 * 224 * 3:
            return []
        image = np.frombuffer(raw_frame, dtype=np.uint8).reshape(224, 224, 3).astype(np.float32) / 255.0
        image = (image - np.asarray([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)) / np.asarray(
            [0.26862954, 0.26130258, 0.27577711],
            dtype=np.float32,
        )
        input_meta = session.get_inputs()[0]
        input_shape = list(input_meta.shape)
        tensor = image.transpose(2, 0, 1)[None, ...] if len(input_shape) == 4 and input_shape[1] in {3, "3"} else image[None, ...]
        output = session.run(None, {input_meta.name: tensor})[0]
        embedding = np.asarray(output, dtype=np.float32).reshape(-1)
        embedding /= max(float(np.linalg.norm(embedding)), 1e-8)
        scores = text_matrix @ embedding
        best = np.argsort(scores)[::-1][:4]
        return [
            {
                "name": labels[int(index)],
                "confidence": round(float(max(0.0, min(1.0, (scores[int(index)] + 1.0) / 2.0))), 4),
                "source": "mobileclip",
            }
            for index in best
        ]
    except Exception:
        return []


def semantic_categories_for_analysis(
    path: Path,
    analysis: dict[str, Any],
    duration: float = 0.0,
    cwd: Path | None = None,
) -> list[dict[str, Any]]:
    categories = semantic_model_categories(path, duration=duration, cwd=cwd) or categories_for_path(path)
    metrics = analysis.get("metrics") if isinstance(analysis.get("metrics"), dict) else {}
    category = str(analysis.get("category") or "")
    if category in {"text_dominant", "text_suspect"}:
        categories.insert(0, {"name": "text_dominant", "confidence": float(analysis.get("confidence") or 0.8), "source": "visual"})
    if category in {"presenter_suspect", "static_center_suspect"}:
        categories.insert(0, {"name": "people", "confidence": float(analysis.get("confidence") or 0.7), "source": "visual"})
    if float(metrics.get("center_skin_ratio") or 0.0) >= 0.04 and not any(item.get("name") == "people" for item in categories):
        categories.append({"name": "people", "confidence": 0.48, "source": "visual"})
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in categories:
        name = str(item.get("name") or "")
        if not name or name in seen:
            continue
        seen.add(name)
        unique.append(item)
    return unique[:6]


def index_media_file(path: Path, duration: float = 0.0, cwd: Path | None = None, detailed: bool = True) -> dict[str, Any]:
    resolved = _resolved_media_path(path, cwd)
    signature = media_signature(resolved)
    cached = INTELLIGENCE_DB.get_media_index(signature)
    cached_features = cached.get("features") if isinstance(cached, dict) and isinstance(cached.get("features"), dict) else {}
    cached_metrics = cached_features.get("metrics") if isinstance(cached_features.get("metrics"), dict) else {}
    false_invalid_cache = bool(
        cached
        and str(cached_features.get("category") or "") == "invalid"
        and not cached_metrics
        and not str(cached.get("fingerprint") or "")
    )
    if cached and not false_invalid_cache:
        cached["cache_hit"] = True
        return cached
    if duration <= 0:
        duration = safe_probe_duration(resolved, cwd=cwd)
    analysis = probe_visual_clean_health(resolved, duration, "balanced" if detailed else "light", cwd=cwd)
    metrics = dict(analysis.get("metrics") or {})
    categories = semantic_categories_for_analysis(resolved, analysis, duration=duration, cwd=cwd)
    try:
        stat = resolved.stat()
        size_bytes = stat.st_size
        modified_ns = stat.st_mtime_ns
    except Exception:
        size_bytes = 0
        modified_ns = 0
    fingerprint = str(metrics.get("fingerprint") or "")
    features = {
        "duration": round(duration, 3),
        "category": analysis.get("category"),
        "action": analysis.get("action"),
        "confidence": analysis.get("confidence"),
        "metrics": metrics,
    }
    INTELLIGENCE_DB.upsert_media_index(
        signature=signature,
        path=str(resolved),
        size_bytes=size_bytes,
        modified_ns=modified_ns,
        categories=categories,
        features=features,
        fingerprint=fingerprint,
        model_version=semantic_model_status().get("mode") or "heuristic_fallback",
    )
    return {
        "signature": signature,
        "path": str(resolved),
        "categories": categories,
        "features": features,
        "fingerprint": fingerprint,
        "model_version": semantic_model_status().get("mode"),
        "cache_hit": False,
    }


def index_media_background(path: Path, duration: float = 0.0) -> None:
    if any(job.status == "running" for job in JOBS.values()):
        return
    try:
        indexed = index_media_file(path, duration=duration, detailed=False)
        if indexed.get("full_hash"):
            return
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                if any(job.status == "running" for job in JOBS.values()):
                    return
                chunk = handle.read(4 * 1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        INTELLIGENCE_DB.update_media_full_hash(str(indexed.get("signature") or ""), digest.hexdigest())
    except Exception:
        pass


def schedule_project_visual_index(project_id: str, *, limit: int = 260) -> dict[str, Any]:
    items = _load_project_media_index(project_id)
    project_dir = _project_media_dir(project_id)
    scheduled = 0
    skipped = 0
    cache_hits = 0
    for rel_key, item in list(items.items())[:limit]:
        kind = str(item.get("kind") or "").lower()
        name = str(item.get("file") or "")
        ext = Path(str(item.get("name") or name)).suffix.lower()
        if kind not in {"video", "image"} and ext not in VIDEO_EXTS and ext not in IMAGE_EXTS:
            skipped += 1
            continue
        path = project_dir / name
        if not path.exists():
            skipped += 1
            continue
        try:
            if INTELLIGENCE_DB.get_media_index(media_signature(path)):
                cache_hits += 1
                continue
        except Exception:
            pass
        try:
            MEDIA_INDEX_EXECUTOR.submit(
                index_media_background,
                path,
                max(0.0, float(item.get("duration") or 0.0)),
            )
            scheduled += 1
        except Exception:
            skipped += 1
    return {
        "project_id": project_id,
        "scheduled": scheduled,
        "skipped": skipped,
        "cache_hits": cache_hits,
        "incremental": True,
        "paused_when_rendering": True,
        "low_priority": True,
    }


def visual_filter_project_context(job: Job) -> dict[str, Any]:
    project_text = " ".join(filter(None, [
        str(job.options.get("queueProjectName") or ""),
        str(job.options.get("projectName") or ""),
        str(job.options.get("outputName") or ""),
        " ".join(cue.text for cue in (job.subtitle_cues or [])[:240]),
    ]))
    terms = set(keyword_terms(project_text, limit=48))
    categories = set(categories_for_text(project_text))
    tone = str((job.emotion_summary or {}).get("tone") or job.options.get("projectTone") or "").lower()
    documentary_terms = {
        "arquivo", "archive", "historico", "historical", "documentario", "documentary",
        "jornal", "news", "reportagem", "interview", "entrevista", "evento", "event",
        "jogo", "match", "sport", "esporte", "performance", "competicao", "competition",
    }
    folded = fold_text(project_text)
    return {
        "terms": terms,
        "categories": categories,
        "documentary_context": tone in {"historical", "documentary"} or any(term in folded for term in documentary_terms),
    }


def visual_filter_source_context(job: Job, source: Path, project_context: dict[str, Any]) -> dict[str, Any]:
    project_terms = set(project_context.get("terms") or set())
    project_categories = set(project_context.get("categories") or set())
    source_text = source.stem.replace("_", " ").replace("-", " ")
    source_terms = set(keyword_terms(source_text, limit=24))
    source_categories = {item.get("name") for item in categories_for_path(source) if item.get("name")}
    try:
        cached = INTELLIGENCE_DB.get_media_index(media_signature(_resolved_media_path(source, job.work)))
    except Exception:
        cached = None
    semantic_names: set[str] = set()
    if isinstance(cached, dict):
        for item in cached.get("categories") or []:
            if isinstance(item, dict) and item.get("name"):
                semantic_names.add(str(item["name"]))
    source_categories.update(semantic_names)
    overlap = project_terms.intersection(source_terms)
    category_overlap = project_categories.intersection(source_categories)
    relevance = min(1.0, len(overlap) * 0.28 + len(category_overlap) * 0.32)
    if not project_terms and not project_categories:
        relevance = 0.35
    folded_source = fold_text(source_text)
    documentary_markers = (
        "archive", "arquivo", "histor", "news", "jornal", "report", "interview",
        "entrevista", "sport", "jogo", "match", "event", "evento", "award", "premi",
        "race", "corrida", "train", "treino", "performance",
    )
    documentary_context = bool(project_context.get("documentary_context")) or any(
        marker in folded_source for marker in documentary_markers
    )
    presentation_markers = (
        "presenter", "apresentador", "talking head", "vlog", "youtuber",
        "avatar", "host", "podcast", "webcam", "facecam", "reaction",
    )
    presentation_hint = any(marker in folded_source for marker in presentation_markers) or any(
        any(marker.replace(" ", "_") in fold_text(name).replace(" ", "_") for marker in presentation_markers)
        for name in semantic_names
    )
    person_context_expected = bool(
        relevance >= 0.56
        or ("people" in project_categories and "people" in source_categories)
        or (overlap and documentary_context)
    )
    return {
        "subject_relevance": round(relevance, 3),
        "person_context_expected": person_context_expected,
        "documentary_context": documentary_context,
        "presentation_hint": presentation_hint,
        "matched_terms": sorted(overlap)[:8],
        "matched_categories": sorted(category_overlap)[:6],
        "semantic_categories": sorted(semantic_names)[:6],
    }


def visual_clean_zone(options: dict[str, Any], position_ratio: float, media_kind: str = "video") -> tuple[str, str]:
    if media_kind == "image":
        return "strict", "imagem rigorosa"
    if adaptive_visual_filter_effective(options):
        if position_ratio < (1.0 / 3.0):
            return "strict", "adaptativo: inicio rigoroso"
        if position_ratio < (2.0 / 3.0):
            return "normal", "adaptativo: meio normal"
        return "light", "adaptativo: final leve"
    level = normalized_visual_filter_level(options)
    return level, f"manual: {level}"


def apply_visual_clean_filter(
    job: Job,
    valid_pairs: list[tuple[Path, float]],
    audio_total: float,
    work: Path,
    candidate_sources: set[str] | None = None,
    imported_count: int | None = None,
) -> tuple[list[tuple[Path, float]], dict[str, Any]]:
    enabled = visual_clean_enabled(job.options)
    priority = render_priority(job)
    summary: dict[str, Any] = {
        "enabled": enabled,
        "priority": priority,
        "requested_level": normalized_visual_filter_level(job.options),
        "adaptive_requested": bool(job.options.get("adaptiveVisualFilter", False)),
        "adaptive_effective": adaptive_visual_filter_effective(job.options),
        "policy": "adaptive_visual_clean" if adaptive_visual_filter_effective(job.options) else "manual_full_timeline",
        "imported_clips": int(imported_count if imported_count is not None else len(valid_pairs)),
        "original_valid_clips": len(valid_pairs),
        "planned_clips": len(candidate_sources or valid_pairs),
        "clean_clips": len(valid_pairs) if not enabled else 0,
        "approved": len(valid_pairs) if not enabled else 0,
        "hard_rejected": 0,
        "rejected_invalid": max(0, int(imported_count or len(valid_pairs)) - len(valid_pairs)),
        "rejected_text": 0,
        "rejected_black": 0,
        "presenter_suspects": 0,
        "presenter_rejected": 0,
        "contextual_people": 0,
        "images_analyzed": 0,
        "images_rejected": 0,
        "context_mismatches": 0,
        "soft_demoted": 0,
        "fallback_used": 0,
        "kept_late_suspects": 0,
        "analyzed_clips": 0,
        "cache_hits": 0,
        "analysis_unavailable": 0,
        "face_detector": yunet_detector_status(),
        "yunet_analyzed": 0,
        "yunet_face_positive": 0,
        "skipped_analysis": 0,
        "not_needed": 0,
        "used_in_final": 0,
        "items": [],
    }
    if not enabled or not valid_pairs:
        summary["status"] = "disabled" if not enabled else "empty"
        return valid_pairs, summary

    raw_total = max(0.001, sum(duration for _, duration in valid_pairs))
    clean_pairs: list[tuple[Path, float]] = []
    fallback_pairs: list[tuple[Path, float]] = []
    guarded_reject_pairs: list[tuple[Path, float, dict[str, Any], str]] = []
    zone_analyzed = {"first": 0, "rest": 0}
    project_context = visual_filter_project_context(job)
    cumulative = 0.0
    for source, duration in valid_pairs:
        position_ratio = cumulative / raw_total
        cumulative += duration
        source_key = str(source).replace("\\", "/")
        display = media_display_name(job, source)
        if candidate_sources is not None and source_key not in candidate_sources:
            clean_pairs.append((source, duration))
            summary["not_needed"] += 1
            continue
        media_kind = "image" if is_image_path(source) else "video"
        zone, zone_label = visual_clean_zone(job.options, position_ratio, media_kind)
        guard_zone = "first" if position_ratio < (1.0 / 3.0) else "rest"
        zone_analyzed[guard_zone] += 1
        source_context = visual_filter_source_context(job, source, project_context)
        cache_key = visual_clean_cache_key(source, duration, cwd=work)
        has_cached_analysis = isinstance(VISUAL_CLEAN_CACHE.get(cache_key), dict)
        if media_kind == "video" and not has_cached_analysis and priority == "max":
            clean_pairs.append((source, duration))
            summary["skipped_analysis"] += 1
            summary["items"].append({
                "name": display,
                "file": source.name,
                "zone": zone_label,
                "category": "budget_cache_miss",
                "action": "keep",
                "reason": "Turbo preservou o clipe e evitou análise pesada sem cache",
                "confidence": 0.35,
                "duration": round(duration, 3),
                "media_kind": media_kind,
                "decision": "kept_unverified",
            })
            if "visual_analysis_cache_only_turbo" not in job.render_budget_fallbacks:
                job.render_budget_fallbacks.append("visual_analysis_cache_only_turbo")
            continue
        if media_kind == "video" and not has_cached_analysis and not budget_allows_optional(job, 1.6, reserve_ratio=0.62):
            clean_pairs.append((source, duration))
            summary["skipped_analysis"] += 1
            if "visual_analysis_quota_exhausted" not in job.render_budget_fallbacks:
                job.render_budget_fallbacks.append("visual_analysis_quota_exhausted")
            continue
        analysis = probe_visual_clean_health(
            source,
            duration,
            zone,
            cwd=work,
            context=source_context,
            media_kind=media_kind,
        )
        summary["analyzed_clips"] += 1
        if media_kind == "image":
            summary["images_analyzed"] += 1
        if analysis.get("cache_hit"):
            summary["cache_hits"] += 1
        evidence = analysis.get("evidence") if isinstance(analysis.get("evidence"), dict) else {}
        face_detector = evidence.get("face_detector") if isinstance(evidence.get("face_detector"), dict) else {}
        if face_detector.get("analyzed"):
            summary["yunet_analyzed"] += 1
            if int(face_detector.get("face_frames") or 0) > 0:
                summary["yunet_face_positive"] += 1
        action = str(analysis.get("action") or "keep")
        category = str(analysis.get("category") or "clean")
        reason = str(analysis.get("reason") or "clipe limpo")
        item = {
            "name": display,
            "file": source.name,
            "zone": zone_label,
            "category": category,
            "action": action,
            "reason": reason,
            "confidence": round(float(analysis.get("confidence") or 0.0), 3),
            "duration": round(duration, 3),
            "media_kind": media_kind,
            "evidence": analysis.get("evidence") or {},
            "context": source_context,
        }
        if media_kind == "image" and action == "keep" and float(source_context.get("subject_relevance") or 0.0) < 0.12 and project_context.get("terms"):
            action = "soft_suspect"
            category = "context_mismatch"
            item.update({
                "action": action,
                "category": category,
                "reason": "imagem sem correspondencia contextual suficiente",
                "confidence": 0.66,
            })
            summary["context_mismatches"] += 1
        if action == "hard_reject":
            summary["hard_rejected"] += 1
            if category == "text_dominant":
                summary["rejected_text"] += 1
            elif category == "black_screen":
                summary["rejected_black"] += 1
            elif category == "presenter":
                summary["presenter_rejected"] += 1
            if media_kind == "image":
                summary["images_rejected"] += 1
            if category not in {"black_screen", "invalid", "no_frames", "analysis_unavailable"}:
                guarded_reject_pairs.append((source, duration, item, guard_zone))
            item["decision"] = "removed"
        elif action == "soft_suspect":
            if category in {"presenter_suspect", "static_center_suspect", "presenter", "suspect"}:
                summary["presenter_suspects"] += 1
            if zone == "light" and priority != "max":
                clean_pairs.append((source, duration))
                summary["kept_late_suspects"] += 1
                item["decision"] = "kept_late"
            else:
                fallback_pairs.append((source, duration))
                summary["soft_demoted"] += 1
                item["decision"] = "fallback_only"
        else:
            clean_pairs.append((source, duration))
            if category == "person_contextual":
                summary["contextual_people"] += 1
            if category == "analysis_unavailable":
                summary["analysis_unavailable"] += 1
                item["decision"] = "kept_unverified"
            else:
                item["decision"] = "kept"
        if item["decision"] != "kept" or category != "clean":
            summary["items"].append(item)

    guardrail_details: dict[str, Any] = {}
    recovered_count = 0
    for guard_zone, limit in (("first", 0.25), ("rest", 0.30)):
        candidates = [item for item in guarded_reject_pairs if item[3] == guard_zone]
        analyzed = max(0, zone_analyzed[guard_zone])
        allowed = 0 if analyzed <= 0 else max(1, int(analyzed * limit))
        overflow = max(0, len(candidates) - allowed)
        recovered_here = 0
        if overflow:
            # Lowest-confidence editorial decisions are recovered first.
            for source, duration, item, _ in sorted(candidates, key=lambda row: float(row[2].get("confidence") or 0.0))[:overflow]:
                fallback_pairs.append((source, duration))
                item["decision"] = "guardrail_fallback"
                item["action"] = "soft_suspect"
                item["reason"] = f"{item.get('reason')}; proteção {int(limit * 100)}% converteu a decisão em suspeito"
                recovered_here += 1
                if item.get("category") == "text_dominant":
                    summary["rejected_text"] = max(0, int(summary.get("rejected_text") or 0) - 1)
                elif item.get("category") == "presenter":
                    summary["presenter_rejected"] = max(0, int(summary.get("presenter_rejected") or 0) - 1)
                if item.get("media_kind") == "image":
                    summary["images_rejected"] = max(0, int(summary.get("images_rejected") or 0) - 1)
        recovered_count += recovered_here
        guardrail_details[guard_zone] = {
            "limit": limit,
            "analyzed": analyzed,
            "editorial_rejected": len(candidates),
            "allowed": allowed,
            "recovered_as_suspect": recovered_here,
        }
    if recovered_count:
        summary["guardrail_triggered"] = True
        summary["guardrail_recovered"] = recovered_count
        summary["soft_demoted"] += recovered_count
        summary["hard_rejected"] = max(0, int(summary.get("hard_rejected") or 0) - recovered_count)
        summary["status"] = "guardrail"
    summary["guardrail"] = guardrail_details

    min_speed = float(job.options.get("minSpeed") or MIN_VIDEO_SPEED)
    needed_raw = max(0.0, audio_total * min_speed)
    clean_raw = sum(duration for _, duration in clean_pairs)
    selected_pairs = list(clean_pairs)
    fallback_items_used: list[dict[str, Any]] = []
    if clean_raw < needed_raw and fallback_pairs:
        for source, duration in fallback_pairs:
            selected_pairs.append((source, duration))
            clean_raw += duration
            summary["fallback_used"] += 1
            fallback_items_used.append({"name": media_display_name(job, source), "file": source.name, "duration": round(duration, 3)})
            if clean_raw >= needed_raw:
                break
    summary["clean_clips"] = len(clean_pairs)
    summary["approved"] = len(clean_pairs)
    summary["selected_clips"] = len(selected_pairs)
    summary["fallback_used_items"] = fallback_items_used[:20]
    summary["raw_seconds_after_filter"] = round(sum(duration for _, duration in selected_pairs), 3)
    summary["needed_raw_seconds"] = round(needed_raw, 3)
    if not summary.get("status"):
        summary["status"] = "ok"
    _save_visual_clean_cache()
    return selected_pairs, summary


def log_visual_clean_filter(job: Job, summary: dict[str, Any]) -> None:
    if not summary or not summary.get("enabled"):
        return
    removed = int(summary.get("hard_rejected") or 0)
    demoted = int(summary.get("soft_demoted") or 0)
    fallback = int(summary.get("fallback_used") or 0)
    analyzed = int(summary.get("analyzed_clips") or 0)
    yunet_analyzed = int(summary.get("yunet_analyzed") or 0)
    yunet_positive = int(summary.get("yunet_face_positive") or 0)
    _append_log(
        job,
        "Filtro visual inteligente: "
        f"analisados={analyzed} | removidos={removed} | rebaixados={demoted} | fallback_usado={fallback} | "
        f"YuNet={yunet_analyzed} ambiguos/{yunet_positive} com rosto | politica={summary.get('policy')}.",
    )
    notable = [item for item in (summary.get("items") or []) if item.get("decision") in {"removed", "fallback_only", "kept_late"}]
    if notable:
        sample = ", ".join(f"{item.get('name')} ({item.get('reason')})" for item in notable[:5])
        more = "..." if len(notable) > 5 else ""
        _append_log(job, f"Filtro visual: {sample}{more}")


def compact_visual_clean_summary(summary: dict[str, Any] | None) -> dict[str, Any]:
    source = summary or {}
    keys = (
        "enabled", "priority", "policy", "status", "requested_level",
        "adaptive_requested", "adaptive_effective",
        "imported_clips", "original_valid_clips", "planned_clips",
        "analyzed_clips", "cache_hits", "approved", "not_needed",
        "hard_rejected", "rejected_invalid", "rejected_text", "rejected_black",
        "analysis_unavailable",
        "face_detector", "yunet_analyzed", "yunet_face_positive",
        "presenter_suspects", "presenter_rejected", "contextual_people",
        "images_analyzed", "images_rejected", "context_mismatches",
        "soft_demoted", "kept_late_suspects",
        "fallback_used", "used_as_fallback", "used_in_final", "selected_clips",
        "guardrail_triggered", "guardrail_recovered", "guardrail",
    )
    return {key: source.get(key) for key in keys if key in source}


def compact_timeline_summary(summary: dict[str, Any] | None) -> dict[str, Any]:
    source = summary or {}
    compact: dict[str, Any] = {}
    for key, value in source.items():
        if key == "visual_clean_summary":
            compact[key] = compact_visual_clean_summary(value if isinstance(value, dict) else {})
        elif key == "subtitle_timing_summary":
            timing = value if isinstance(value, dict) else {}
            compact[key] = {name: item for name, item in timing.items() if name != "items"}
        elif key == "visual_window_scores":
            windows = value if isinstance(value, dict) else {}
            compact[key] = {name: item for name, item in windows.items() if name != "items"}
        elif isinstance(value, list):
            if len(value) <= 8 and all(isinstance(item, (str, int, float, bool, type(None))) for item in value):
                compact[key] = value
            else:
                compact[f"{key}_count"] = len(value)
        else:
            compact[key] = value
    return compact


def compact_preflight_summary(summary: dict[str, Any] | None) -> dict[str, Any]:
    compact = dict(summary or {})
    if isinstance(compact.get("visual_clean_filter"), dict):
        compact["visual_clean_filter"] = compact_visual_clean_summary(compact["visual_clean_filter"])
    for key in ("invalid_video_details", "auto_fix_plan"):
        value = compact.get(key)
        if isinstance(value, list) and len(value) > 8:
            compact[f"{key}_count"] = len(value)
            compact.pop(key, None)
    return compact


def subtitle_animation_seed(job: Job) -> str:
    return str(
        job.options.get("queueProjectId")
        or job.options.get("projectName")
        or job.options.get("outputName")
        or job.id
    )


def subtitle_phrase_role(cue: SubtitleCue) -> str:
    raw = str(cue.text or "")
    text = fold_text(raw)
    if re.search(r"\d|%|€|\$", raw) or any(token in text for token in (
        "milhao", "bilhao", "dolar", "euro", "preco", "percent",
    )):
        return "data"
    if any(token in text for token in (
        "segredo", "problema", "ninguem", "surpreendente", "verdade",
        "revel", "mas ", "danger", "secret", "nobody", "however",
    )):
        return "impact"
    if raw.rstrip().endswith("?") or any(token in text for token in ("por que", "como ", "sera que", "why ", "how ")):
        return "question"
    if any(token in text for token in (
        "finalmente", "em conclusao", "por fim", "conclusion", "finally",
    )):
        return "conclusion"
    if any(token in text for token in (
        "onde", "aqui", "mapa", "cidade", "fabrica", "local", "region",
    )):
        return "location"
    return "standard"


def _director_blocks(job: Job) -> list[dict[str, Any]]:
    summary = job.director_summary if isinstance(job.director_summary, dict) else {}
    blocks = summary.get("blocks") if isinstance(summary.get("blocks"), list) else []
    return [block for block in blocks if isinstance(block, dict)]


def _director_assignments_by_block(job: Job) -> dict[int, list[dict[str, Any]]]:
    summary = job.director_summary if isinstance(job.director_summary, dict) else {}
    assignments = summary.get("assignments") if isinstance(summary.get("assignments"), list) else []
    grouped: dict[int, list[dict[str, Any]]] = {}
    for item in assignments:
        if not isinstance(item, dict):
            continue
        try:
            block_index = int(item.get("block") or 0)
        except Exception:
            block_index = 0
        grouped.setdefault(block_index, []).append(item)
    return grouped


def _director_block_for_time(job: Job, value: float) -> dict[str, Any] | None:
    blocks = _director_blocks(job)
    if not blocks:
        return None
    value = float(value or 0.0)
    for block in blocks:
        if float(block.get("start") or 0.0) <= value <= float(block.get("end") or 0.0) + 0.05:
            return block
    return min(blocks, key=lambda block: abs(float(block.get("start") or 0.0) - value))


def _assignment_context(assignments: list[dict[str, Any]]) -> dict[str, Any]:
    categories: set[str] = set()
    media_types: set[str] = set()
    visual_flags: set[str] = set()
    suspect_count = 0
    for item in assignments:
        for category in item.get("categories") or []:
            if str(category).strip():
                categories.add(str(category).strip())
        if str(item.get("media_type") or "").strip():
            media_types.add(str(item.get("media_type") or "").strip())
        if str(item.get("visual_category") or "").strip():
            visual_flags.add(str(item.get("visual_category") or "").strip())
        if item.get("suspect"):
            suspect_count += 1
    has_people = bool(categories & {"people", "person", "presenter"}) or any(
        "presenter" in flag or "people" in flag or "face" in flag
        for flag in visual_flags
    )
    has_text = bool(categories & {"text", "document"}) or any(
        "text" in flag or "watermark" in flag
        for flag in visual_flags
    )
    has_image = "image" in media_types
    return {
        "categories": sorted(categories),
        "visual_flags": sorted(visual_flags),
        "media_types": sorted(media_types),
        "has_people": has_people,
        "has_text": has_text,
        "has_image": has_image,
        "suspect_count": suspect_count,
    }


def build_director_scene_fit_plan(job: Job, total_duration: float) -> dict[str, Any]:
    blocks = _director_blocks(job)
    assignments_by_block = _director_assignments_by_block(job)
    scene_blocks: list[dict[str, Any]] = []
    for block in blocks:
        try:
            block_index = int(block.get("index") or 0)
        except Exception:
            block_index = 0
        context = _assignment_context(assignments_by_block.get(block_index, []))
        role = str(block.get("role") or "explanation")
        energy = _safe_float(block.get("energy"), 0.42)
        shot = _safe_float(block.get("shot_duration"), 4.0)
        cut_profile = "calmo"
        if role in {"conflict", "reveal"} or energy >= 0.62:
            cut_profile = "impacto"
        elif role in {"conclusion", "cta"} or energy <= 0.28:
            cut_profile = "respiro"
        safe_slots = ["lower_center", "left_callout", "right_callout", "upper_right"]
        if context["has_people"]:
            safe_slots = ["lower_center", "upper_left", "upper_right", "left_callout", "right_callout"]
        if context["has_text"]:
            safe_slots = ["upper_left", "upper_right", "left_callout", "right_callout"]
        if role in {"reveal", "conflict"} and not context["has_people"]:
            safe_slots = ["center_card", "upper_left", "upper_right", "lower_center"]
        if role == "cta":
            safe_slots = ["upper_left", "upper_right", "lower_center"]
        scene_blocks.append({
            "block": block_index,
            "role": role,
            "start": round(float(block.get("start") or 0.0), 3),
            "end": round(float(block.get("end") or 0.0), 3),
            "energy": round(energy, 3),
            "shot_duration": round(shot, 3),
            "cut_profile": cut_profile,
            "safe_subtitle_slots": safe_slots,
            "context": context,
            "reason": (
                "rostos/pessoas detectados: evitar centro" if context["has_people"]
                else ("texto/documentos detectados: evitar zona baixa" if context["has_text"] else "zona livre por contexto")
            ),
        })
    plan = {
        "kind": "director_scene_fit_plan",
        "version": APP_VERSION,
        "enabled": bool(blocks),
        "total_duration": round(float(total_duration or 0.0), 3),
        "blocks": scene_blocks,
        "policy": "encaixe_narrativo_visual_sem_analise_pesada_extra",
    }
    if job.export_dir:
        atomic_write_text(job.export_dir / "director_scene_fit_plan.json", json.dumps(plan, ensure_ascii=False, indent=2))
    return plan


def subtitle_safe_slot_for_cue(
    job: Job,
    cue: SubtitleCue,
    idx: int,
    requested_slot: str,
    layout_context: dict[str, Any],
) -> tuple[str, str]:
    return "lower_center", "slot central padrao fixo"


def build_subtitle_layout_context(job: Job) -> dict[str, Any]:
    scene_fit = job.director_summary.get("scene_fit_plan") if isinstance(job.director_summary, dict) else None
    blocks = scene_fit.get("blocks") if isinstance(scene_fit, dict) and isinstance(scene_fit.get("blocks"), list) else []
    return {
        "enabled": bool(blocks),
        "blocks_by_index": {
            int(block.get("block") or 0): block
            for block in blocks
            if isinstance(block, dict)
        },
        "policy": "legenda reposicionada para evitar rosto, texto, CTA e elementos centrais quando houver contexto",
    }


def _subtitle_pick_without_recent(
    candidates: list[str],
    seed: str,
    recent: list[str],
) -> str:
    if not candidates:
        return "fade"
    start = stable_index(seed, len(candidates))
    ordered = candidates[start:] + candidates[:start]
    return next((value for value in ordered if value not in recent[-3:]), ordered[0])


def subtitle_editorial_sequence(
    job: Job,
    cues: list[SubtitleCue],
    animation: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    safe_intros = ["fade", "rise", "slide_left", "slide_right", "zoom_soft", "pop_soft", "cinema_drop", "pulse_in", "typewriter", "glitch"]
    role_intros = {
        "data": ["typewriter", "pulse_in", "slide_right", "rise"],
        "impact": ["pop", "cinema_drop", "shake", "pulse_in"],
        "question": ["rise", "zoom_soft", "slide_left", "fade"],
        "conclusion": ["cinema_drop", "fade", "rise", "zoom_soft"],
        "location": ["slide_left", "slide_right", "rise", "fade"],
    }
    explicit_intros = {
        "fade": ["fade", "rise"],
        "pop": ["pop", "pop_soft", "pulse_in"],
        "slide": ["rise", "slide_left", "slide_right"],
        "zoom": ["zoom_in", "zoom_soft", "rise"],
        "cinematic": ["cinema_drop", "rise", "fade"],
        "pulse": ["pulse_in", "pop_soft", "fade"],
        "glitch": ["glitch", "typewriter", "pulse_in"],
        "typewriter": ["typewriter", "fade", "rise"],
        "shake": ["shake", "pop", "cinema_drop"],
        "documentary": ["cinema_drop", "rise", "typewriter"],
        "archive": ["typewriter", "slide_left", "rise"],
        "digital": ["glitch", "typewriter", "pulse_in"],
        "stamp": ["pop", "shake", "cinema_drop"],
        "money": ["typewriter", "pulse_in", "slide_right"],
        "warning": ["shake", "pop", "pulse_in"],
        "industrial": ["shake", "cinema_drop", "slide_left"],
        "luxury": ["cinema_drop", "fade", "rise"],
    }
    outro_pool = ["fade", "float_fade", "shrink", "soft_blur", "glow_fade", "quick_dim"]
    seed = subtitle_animation_seed(job)
    accent_budget = max(0, int(len(cues) * 0.30))
    accent_count = 0
    recent_intros: list[str] = []
    recent_outros: list[str] = []
    plan: list[dict[str, Any]] = []
    role_counts: dict[str, int] = {}
    intro_counts: dict[str, int] = {}
    slot_counts: dict[str, int] = {}
    for idx, cue in enumerate(cues):
        role = subtitle_phrase_role(cue)
        role_counts[role] = role_counts.get(role, 0) + 1
        accent = role != "standard" and accent_count < accent_budget
        if accent:
            accent_count += 1
        if animation == "none":
            intro_candidates = ["none"]
        elif animation in explicit_intros:
            intro_candidates = explicit_intros[animation]
        elif accent:
            intro_candidates = role_intros.get(role, safe_intros)
        else:
            intro_candidates = safe_intros
        intro = _subtitle_pick_without_recent(
            intro_candidates,
            f"{seed}:editorial:intro:{idx}:{cue.text}",
            recent_intros,
        )
        outro = "none" if animation == "none" else _subtitle_pick_without_recent(
            outro_pool,
            f"{seed}:editorial:outro:{idx}:{cue.text}",
            recent_outros,
        )
        slot = "lower_center"
        recent_intros.append(intro)
        recent_outros.append(outro)
        intro_counts[intro] = intro_counts.get(intro, 0) + 1
        slot_counts[slot] = slot_counts.get(slot, 0) + 1
        plan.append({
            "role": role,
            "accent": False,
            "intro": intro,
            "outro": outro,
            "slot": slot,
        })
    return plan, {
        "enabled": bool(job.options.get("subtitleEditorialGrammar", True)),
        "safe_cues": len(cues) - accent_count,
        "accent_cues": accent_count,
        "accent_ratio": round(accent_count / max(1, len(cues)), 3),
        "repeat_guard_cues": 3,
        "role_counts": role_counts,
        "animation_counts": intro_counts,
        "slot_counts": slot_counts,
    }


def subtitle_variant_impact_delay(variant: str, cue_duration: float) -> float:
    delay = {
        "fade": 0.06,
        "rise": 0.16,
        "slide_left": 0.18,
        "slide_right": 0.18,
        "pop": 0.26,
        "pop_soft": 0.14,
        "zoom_in": 0.16,
        "zoom_soft": 0.12,
        "cinema_drop": 0.18,
        "pulse_in": 0.12,
        "glitch": 0.03,
        "typewriter": 0.0,
        "shake": 0.08,
    }.get(variant, 0.10)
    return min(max(0.0, cue_duration * 0.25), delay)


def build_event_timeline(job: Job) -> dict[str, Any]:
    fps = 30.0
    events: list[dict[str, Any]] = []

    def frame(t: float) -> int:
        return max(0, int(round(float(t or 0.0) * fps)))

    def add_event(
        event_type: str,
        *,
        start: float,
        impact: float | None = None,
        end: float | None = None,
        group: str = "visual",
        reason: str = "",
        **meta: Any,
    ) -> None:
        impact_time = float(impact if impact is not None else start)
        end_time = float(end if end is not None else max(impact_time + 0.32, start + 0.32))
        sound_lead = {
            "subtitle_enter": 0.03,
            "text_highlight": 0.02,
            "arrow_draw": 0.015,
            "transition_cut": 0.02,
            "clip_cut": 0.02,
            "image_enter": 0.03,
            "image_motion_peak": 0.04,
            "fx_hit": 0.0,
            "cta_enter": 0.0,
            "music_rise": 0.0,
        }.get(event_type, 0.02)
        event = {
            "type": event_type,
            "group": group,
            "reason": reason,
            "visual_start_frame": frame(start),
            "impact_frame": frame(impact_time),
            "sound_start_frame": frame(max(0.0, impact_time - sound_lead)),
            "sound_peak_frame": frame(impact_time),
            "fade_out_frame": frame(end_time),
            "target_time": round(impact_time, 3),
            "sync_target_ms": 33,
        }
        event.update({key: value for key, value in meta.items() if value is not None})
        events.append(event)

    def graphic_event_for_cue(cue: SubtitleCue) -> str:
        text = fold_text(cue.text or "")
        if re.search(r"\d|%|milhao|milhão|bilhao|bilhão|dolar|dólar|euro|preco|preço", cue.text or "", flags=re.IGNORECASE):
            return "text_highlight"
        if any(token in text for token in ("onde", "aqui", "neste ponto", "mapa", "local", "cidade", "fabrica", "fábrica")):
            return "arrow_draw"
        if any(token in text for token in ("segredo", "problema", "revel", "surpreendente", "ningu", "verdade", "mas")):
            return "text_highlight"
        return ""

    subtitle_animation = str(
        (job.subtitle_summary or {}).get("animation")
        or subtitle_style_from_options(job.options).get("animation")
        or "mixed"
    )
    timeline_cues = list((job.subtitle_cues or [])[:600])
    editorial_plan, _editorial_summary = subtitle_editorial_sequence(job, timeline_cues, subtitle_animation)
    timing_items = (job.subtitle_timing_summary or {}).get("items") if isinstance(job.subtitle_timing_summary, dict) else []
    layout_by_index = {
        int(item.get("cue") or 0) - 1: item
        for item in (timing_items or [])
        if isinstance(item, dict)
    }
    for idx, cue in enumerate(timeline_cues):
        start = float(cue.start or 0.0)
        end = float(cue.end or start)
        variant = str(editorial_plan[idx].get("intro") or "fade")
        impact = start + subtitle_variant_impact_delay(variant, max(0.0, end - start))
        add_event(
            "subtitle_enter",
            start=start,
            impact=impact,
            end=end,
            group="text",
            reason="entrada_de_legenda",
            cue_index=idx,
            text=cue.text[:120],
            subtitle_animation=subtitle_animation,
            subtitle_variant=variant,
            subtitle_slot=(layout_by_index.get(idx) or {}).get("slot"),
            subtitle_slot_reason=(layout_by_index.get(idx) or {}).get("slot_reason"),
        )
        graphic_type = graphic_event_for_cue(cue)
        if graphic_type:
            add_event(
                graphic_type,
                start=start + 0.04,
                impact=impact + 0.08,
                end=min(end, impact + 0.88),
                group="motion_graphic",
                reason="seta_ou_destaque_por_frase",
                cue_index=idx,
                text=cue.text[:120],
            )
    for item in (job.strong_moments_summary or {}).get("moments", [])[:80]:
        if not isinstance(item, dict):
            continue
        t = float(item.get("time") or 0.0)
        add_event(
            "fx_hit",
            start=max(0.0, t - 0.12),
            impact=t,
            end=t + 0.55,
            group="impact",
            reason=item.get("reason") or item.get("pattern") or "momento_forte",
            cue_index=item.get("cue_index"),
            confidence=item.get("confidence"),
        )
        add_event(
            "music_rise",
            start=max(0.0, t - 0.9),
            impact=max(0.0, t - 0.08),
            end=t + 0.35,
            group="music",
            reason="rise_sutil_para_momento_forte",
            cue_index=item.get("cue_index"),
        )
    cta = job.cta_summary or {}
    if cta.get("enabled") or cta.get("selected"):
        cta_duration = float(cta.get("duration") or 5.0)
        raw_times = cta.get("times") if isinstance(cta.get("times"), list) else []
        times = [float(value) for value in raw_times[:2] if isinstance(value, (int, float))]
        if not times:
            times = [float(cta.get("start") or cta.get("start_seconds") or 0.0)]
        for start in times[:2]:
            end = float(cta.get("end") or cta.get("end_seconds") or max(start + cta_duration, start))
            add_event(
                "cta_enter",
                start=start,
                impact=start + 0.18,
                end=end,
                group="cta",
                reason="entrada_cta_contextual_max_2",
                position_preset=cta.get("position_preset"),
            )
    director = job.director_summary if isinstance(job.director_summary, dict) else {}
    blocks = director.get("blocks") if isinstance(director.get("blocks"), list) else []
    assignments = director.get("assignments") if isinstance(director.get("assignments"), list) else []
    assignments_by_block: dict[int, list[dict[str, Any]]] = {}
    for item in assignments:
        if not isinstance(item, dict):
            continue
        try:
            block_index = int(item.get("block") or 0)
        except Exception:
            block_index = 0
        assignments_by_block.setdefault(block_index, []).append(item)
    for block in blocks[:80]:
        if not isinstance(block, dict):
            continue
        try:
            block_index = int(block.get("index") or block.get("block") or 0)
        except Exception:
            block_index = 0
        start = float(block.get("start") or 0.0)
        end = float(block.get("end") or start)
        shot = max(1.2, float(block.get("shot_duration") or 4.0))
        if start > 0.05:
            add_event(
                "transition_cut",
                start=start,
                impact=start,
                end=start + 0.35,
                group="transition",
                reason="corte_entre_blocos_narrativos",
                block=block_index,
                role=block.get("role") or "bloco",
            )
        for order, item in enumerate(assignments_by_block.get(block_index, [])[:12]):
            item_start = min(end, start + order * shot)
            peak = min(end, item_start + shot * 0.52)
            media_type = str(item.get("media_type") or "video").lower()
            if media_type == "image":
                add_event(
                    "image_enter",
                    start=item_start,
                    impact=item_start + min(0.24, shot * 0.18),
                    end=min(end, item_start + shot),
                    group="image",
                    reason="entrada_de_imagem_com_motion",
                    block=block_index,
                    role=block.get("role") or "bloco",
                    path=item.get("path"),
                )
                add_event(
                    "image_motion_peak",
                    start=item_start,
                    impact=peak,
                    end=min(end, item_start + shot),
                    group="image",
                    reason="pico_de_motion_da_imagem",
                    block=block_index,
                    role=block.get("role") or "bloco",
                    path=item.get("path"),
                )
            else:
                add_event(
                    "clip_cut",
                    start=item_start,
                    impact=item_start,
                    end=min(end, item_start + 0.3),
                    group="video",
                    reason="corte_de_clipe_no_bloco",
                    block=block_index,
                    role=block.get("role") or "bloco",
                    path=item.get("path"),
                )
                if str(job.options.get("zoom") or job.options.get("zoomMode") or "off") not in {"", "off", "none"}:
                    add_event(
                        "camera_motion_peak",
                        start=item_start,
                        impact=peak,
                        end=min(end, item_start + shot),
                        group="camera",
                        reason="pico_de_zoom_ou_movimento_de_camera",
                        block=block_index,
                        role=block.get("role") or "bloco",
                        path=item.get("path"),
                    )
    events.sort(key=lambda item: int(item.get("visual_start_frame") or 0))
    conflicts = []
    for previous, current in zip(events, events[1:]):
        gap = int(current.get("sound_start_frame") or 0) - int(previous.get("sound_peak_frame") or 0)
        if gap < 5 and previous.get("type") != current.get("type"):
            conflicts.append({
                "from": previous.get("type"),
                "to": current.get("type"),
                "gap_frames": gap,
                "resolution": "suprimir FX secundario sem deslocar o impacto principal",
            })
            if current.get("group") in {"motion_graphic", "transition", "image"}:
                current["conflict_resolution"] = "fx_secundario_suprimido_por_proximidade"
                current["fx_policy"] = "suppress_secondary"
    payload = {
        "kind": "glide_event_timeline_v2",
        "version": APP_VERSION,
        "eventTimelineVersion": "2.0",
        "jobId": job.id,
        "fps": fps,
        "createdAt": _now_iso(),
        "style": job.options.get("_style_profile_effective") or reference_style_profile(job.options),
        "events": events[:900],
        "conflicts": conflicts[:80],
        "targetMaxDeviationMs": 33,
        "summary": {
            "subtitle_events": sum(1 for item in events if item.get("type") == "subtitle_enter"),
            "image_events": sum(1 for item in events if str(item.get("group")) == "image"),
            "video_cut_events": sum(1 for item in events if item.get("type") == "clip_cut"),
            "camera_motion_events": sum(1 for item in events if item.get("type") == "camera_motion_peak"),
            "motion_graphic_events": sum(1 for item in events if str(item.get("group")) == "motion_graphic"),
            "transition_events": sum(1 for item in events if item.get("type") == "transition_cut"),
            "fx_hit_events": sum(1 for item in events if item.get("type") == "fx_hit"),
        },
    }
    if job.export_dir:
        atomic_write_text(job.export_dir / "event_timeline.json", json.dumps(payload, ensure_ascii=False, indent=2))
        atomic_write_text(job.export_dir / "event_timeline_v2.json", json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def build_premium_feel_report(job: Job, event_timeline: dict[str, Any] | None = None) -> dict[str, Any]:
    visual = (job.timeline_summary or {}).get("visual_clean_summary") or {}
    timing = job.subtitle_timing_summary or {}
    fx = job.sound_fx_summary or {}
    music = job.background_music_summary or {}
    continuity = job.continuity_summary or {}
    anti_repeat = job.anti_repeat_summary or {}
    style = job.options.get("_style_profile_effective") or reference_style_profile(job.options)
    max_deviation = float(timing.get("max_abs_deviation_ms") or 0.0)
    sync_score = 100 if max_deviation <= 33 else max(35, 100 - (max_deviation - 33) * 1.6)
    used = float(visual.get("effectively_used") or visual.get("used") or visual.get("approved") or 0)
    rejected = float(visual.get("rejected") or 0)
    visual_score = 82 if not used else max(45, min(100, 100 - (rejected / max(used + rejected, 1)) * 75))
    fx_score = 88 if fx.get("enabled", True) and int(fx.get("events") or fx.get("subtitle_events") or 0) else 62
    music_score = 86 if music.get("enabled", True) else 66
    continuity_score = 84 + min(10, int(continuity.get("adjusted") or continuity.get("applied") or 0))
    repetition_penalty = min(18, int(anti_repeat.get("repeated") or anti_repeat.get("demoted") or 0) * 2)
    event_score = 88 if (event_timeline or {}).get("events") else 68
    score = round(max(0, min(100, (
        sync_score * 0.22 + visual_score * 0.20 + fx_score * 0.16 + music_score * 0.15 +
        continuity_score * 0.12 + event_score * 0.15 - repetition_penalty
    ))))
    suggestions: list[str] = []
    if sync_score < 82:
        suggestions.append("Recriar legendas/FX com sincronizador frame-perfect.")
    if event_score < 82:
        suggestions.append("Recriar timeline invisivel de eventos para resolver conflitos entre CTA, texto, FX e musica.")
    if visual_score < 78:
        suggestions.append("Usar Render seguro ou reduzir rejeicoes visuais incertas.")
    if fx_score < 78:
        suggestions.append("Aumentar FX +2 dB ou refazer mapa de sound design.")
    if music_score < 78:
        suggestions.append("Trocar música ou refazer masterização com ducking vivo.")
    if repetition_penalty:
        suggestions.append("Ativar antirrepeticao mais forte ou usar mais imagens/clipes.")
    if style.get("source") == "glide_package" and style.get("referenceAvailable"):
        suggestions.append("Analisar a referencia para ativar o Style DNA completo.")
    payload = {
        "kind": "glide_premium_feel_report",
        "version": APP_VERSION,
        "jobId": job.id,
        "createdAt": _now_iso(),
        "score": score,
        "components": {
            "sync": round(sync_score),
            "visualVariety": round(visual_score),
            "soundFx": round(fx_score),
            "music": round(music_score),
            "continuity": round(continuity_score),
            "eventTimeline": round(event_score),
            "repetitionPenalty": repetition_penalty,
        },
        "style": style,
        "suggestions": suggestions[:8],
    }
    if job.export_dir:
        atomic_write_text(job.export_dir / "premium_feel_report.json", json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def build_post_render_corrections(job: Job, premium: dict[str, Any]) -> dict[str, Any]:
    suggestions = list(premium.get("suggestions") or [])
    actions: list[dict[str, Any]] = []
    for text in suggestions:
        action = "review"
        scope = "report_only"
        if "FX" in text:
            action = "boost_fx"
            scope = "audio_fx_mix"
        elif "musica" in text.lower() or "master" in text.lower():
            action = "remaster_audio"
            scope = "audio_mix_master"
        elif "legendas" in text.lower():
            action = "rebuild_subtitles"
            scope = "ass_srt_composition"
        elif "antirrepeticao" in text.lower():
            action = "rerun_director"
            scope = "director_timeline"
        actions.append({"action": action, "label": text, "renderGraphScope": scope})
    components = premium.get("components") if isinstance(premium.get("components"), dict) else {}
    if float(components.get("visualVariety") or 100) < 82 and not any(item.get("action") == "more_motion" for item in actions):
        actions.append({
            "action": "more_motion",
            "label": "Adicionar mais motion graphics nas imagens e trechos estaticos.",
            "renderGraphScope": "image_segments_composition",
        })
    if float(components.get("eventTimeline") or 100) < 82 and not any(item.get("action") == "rebuild_event_timeline" for item in actions):
        actions.append({
            "action": "rebuild_event_timeline",
            "label": "Recriar timeline invisivel de eventos para reduzir conflitos de CTA, texto, FX e musica.",
            "renderGraphScope": "event_timeline_fx",
        })
    payload = {
        "kind": "glide_post_render_corrections",
        "version": APP_VERSION,
        "jobId": job.id,
        "createdAt": _now_iso(),
        "available": bool(actions),
        "actions": actions[:10],
        "note": "Correcoes usam Render Graph quando os artefatos necessarios estiverem cacheados.",
    }
    if job.export_dir:
        atomic_write_text(job.export_dir / "post_render_corrections.json", json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def job_last_render_summary(job: Job) -> dict[str, Any]:
    visual = (job.timeline_summary or {}).get("visual_clean_summary") or {}
    project_id = str(job.options.get("queueProjectId") or "")
    event_timeline = build_event_timeline(job)
    return clean_ui_text({
        "jobId": job.id,
        "status": job.status,
        "renderPriority": render_priority(job),
        "visualClean": compact_visual_clean_summary(visual),
        "visualCleanDetails": {
            "items": list(visual.get("items") or [])[:160],
            "fallbackUsedItems": list(visual.get("fallback_used_items") or [])[:80],
        },
        "performance": dict(job.performance_breakdown),
        "subtitleTiming": {
            key: value
            for key, value in (job.subtitle_timing_summary or {}).items()
            if key != "items"
        },
        "soundFx": dict(job.sound_fx_summary),
        "backgroundMusic": dict(job.background_music_summary),
        "cta": dict(job.cta_summary),
        "subtitles": dict(job.subtitle_summary),
        "intro": dict(job.intro_summary),
        "recovery": dict(job.recovery_summary),
        "director": dict(job.director_summary),
        "energy": dict(job.energy_summary),
        "confidence": dict(job.confidence_summary),
        "continuity": dict(job.continuity_summary),
        "antiRepeat": dict(job.anti_repeat_summary),
        "audioMaster": dict(job.audio_master_summary),
        "learning": dict(job.learning_summary),
        "styleProfile": job.options.get("_style_profile_effective") or reference_style_profile(job.options),
        "sceneRhythm": scene_rhythm_profile_from_style(job.options.get("_style_profile_effective") or reference_style_profile(job.options)),
        "eventTimeline": {
            "events": len(event_timeline.get("events") or []),
            "conflicts": len(event_timeline.get("conflicts") or []),
            "targetMaxDeviationMs": event_timeline.get("targetMaxDeviationMs"),
            "version": event_timeline.get("eventTimelineVersion") or "2.0",
            "summary": event_timeline.get("summary") or {},
        },
        "renderGraph": dict(job.render_graph_run),
        "renderDecisions": dict(job.render_decisions),
        "editorialIntelligence": dict(job.editorial_intelligence_plan),
        "performanceHistory": performance_history_for_project(project_id),
        "errorActions": recommended_error_actions(job.error, job) if job.error else [],
        "outputName": Path(job.output).name if job.output else None,
        "outputDir": job.output_dir,
        "finishedAt": _now_iso(),
    })


def persist_job_summary_to_queue(job: Job) -> None:
    project_id = str(job.options.get("queueProjectId") or "").strip()
    if not project_id:
        return
    with QUEUE_LOCK:
        project = _find_queue_project(project_id)
        if not project:
            return
        project["lastRenderSummary"] = job_last_render_summary(job)
        project["directorState"] = dict(job.director_summary) if job.director_summary else project.get("directorState")
        project["confidenceSummary"] = dict(job.confidence_summary) if job.confidence_summary else None
        project["audioMasterSummary"] = dict(job.audio_master_summary) if job.audio_master_summary else None
        project["renderGraphRun"] = dict(job.render_graph_run) if job.render_graph_run else None
        if job.status in {"done", "cancelled", "error"}:
            project["status"] = (
                "recovered"
                if job.status == "done" and bool(job.recovery_summary.get("recovered"))
                else job.status
            )
        project["error"] = job.error
        project["jobId"] = job.id
        project["outputFile"] = Path(job.output).name if job.output else project.get("outputFile")
        project["outputDir"] = job.output_dir or project.get("outputDir")
        project["updatedAt"] = _now_iso()
        _save_queue_projects(QUEUE_PROJECTS)


def media_display_name(job: Job, path: Path | str) -> str:
    name = Path(path).name
    key = str(path).replace("\\", "/")
    return job.upload_names.get(key) or job.upload_names.get(name) or name


def ffmpeg_decode_hint(error: Exception | str) -> str:
    text = str(error).lower()
    if "invalid nal unit" in text or "missing picture" in text or "error splitting the input into nal" in text:
        return "H.264 corrompido ou incompleto"
    if "invalid data found" in text or "decode error" in text:
        return "frames invalidos no arquivo"
    if "no frame" in text or "could not find codec" in text:
        return "sem frames decodificaveis"
    return "FFmpeg nao conseguiu decodificar"


def voice_processing_filter(options: dict[str, Any]) -> str:
    base = "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"
    if bool(options.get("voiceNormalize", True)):
        return base + ",dynaudnorm=f=250:g=7:p=0.95,alimiter=limit=0.95"
    return base


def make_concat_audio(job: Job, audio_files: list[Path], work: Path) -> tuple[Path, float]:
    if not audio_files:
        raise RuntimeError("Nenhum áudio encontrado. Envie pelo menos uma narração/áudio.")
    audio_files = sorted(audio_files, key=lambda p: natural_key(p.name))
    audio_pairs: list[tuple[Path, float]] = []
    invalid_audio: list[str] = []
    video_container_audio: list[str] = []
    for p in audio_files:
        if p.suffix.lower() in VIDEO_EXTS:
            display = media_display_name(job, p)
            if not probe_has_audio(p, cwd=work):
                invalid_audio.append(f"{display} (MP4/MOV importado como audio sem faixa de audio legivel)")
                continue
            video_container_audio.append(display)
        dur = safe_probe_duration(p, cwd=work)
        if dur > 0.08:
            audio_pairs.append((p, dur))
        else:
            invalid_audio.append(media_display_name(job, p))
    if invalid_audio:
        _append_log(job, f"Pré-checagem: {len(invalid_audio)} áudio(s) sem duração válida foram ignorados.")
    if not audio_pairs:
        detail = f" Detalhe: {invalid_audio[0]}" if invalid_audio else ""
        raise RuntimeError(f"Nenhum audio de narracao valido foi encontrado.{detail}")
    audio_files = [item[0] for item in audio_pairs]
    durations = [item[1] for item in audio_pairs]
    job.preflight_summary.update({
        "audios_valid": len(audio_files),
        "audios_invalid": len(invalid_audio),
        "invalid_audio_names": invalid_audio[:20],
        "audio_video_containers": len(video_container_audio),
        "audio_video_container_names": video_container_audio[:20],
    })
    if video_container_audio:
        _append_log(job, f"Narracao em container de video: {len(video_container_audio)} arquivo(s) MP4/MOV usados somente como audio (-vn).")
    total = sum(durations)
    audio_filter = voice_processing_filter(job.options)
    job.preflight_summary["voice_normalize"] = bool(job.options.get("voiceNormalize", True))
    out = Path("glide_audio_concat.wav")
    if len(audio_files) == 1:
        job.message = "Preparando áudio"
        cmd = [
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-filter_threads", "1",
            "-i", str(audio_files[0]),
            "-vn", "-af", audio_filter, "-ac", "2", "-ar", "48000", str(out),
        ]
        run_cmd(job, cmd, total_duration=durations[0] or None, base=10, span=5, cwd=work)
    else:
        job.message = "Juntando áudios em ordem numérica"
        cmd: list[str] = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-filter_threads", "1", "-filter_complex_threads", "1"]
        for f in audio_files:
            cmd += ["-i", str(f)]
        filters = []
        labels = []
        for i in range(len(audio_files)):
            filters.append(f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]")
            labels.append(f"[a{i}]")
        filters.append("".join(labels) + f"concat=n={len(audio_files)}:v=0:a=1[acat]")
        filters.append(f"[acat]{audio_filter}[aout]")
        script = work / "audio_filter_complex.txt"
        script.write_text(";".join(filters), encoding="utf-8")
        cmd += ["-filter_complex_script", script.name, "-map", "[aout]", "-ac", "2", "-ar", "48000", str(out)]
        run_cmd(job, cmd, total_duration=total or None, base=10, span=5, cwd=work)
    return out, total


def clamp_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = default
    return max(minimum, min(maximum, parsed))


def background_volume_db(options: dict[str, Any]) -> float:
    preset = str(options.get("backgroundMusicPreset") or "immersive")
    if preset == "silent":
        return -32.0
    if preset == "custom":
        return clamp_float(options.get("backgroundMusicVolumeDb"), -26.0, -45.0, -14.0)
    return -26.0


def background_pause_ceiling_db(options: dict[str, Any]) -> float:
    base = background_volume_db(options)
    preset = str(options.get("backgroundMusicPreset") or "immersive")
    if preset == "silent":
        return -30.0
    return min(-18.0, base + 6.0)


def intro_mode(options: dict[str, Any]) -> str:
    mode = str(options.get("introMode") or "standard").strip().lower()
    return "cinematic" if mode == "cinematic" else "standard"


def intro_duration(options: dict[str, Any]) -> float:
    if intro_mode(options) != "cinematic":
        return 0.0
    return clamp_float(options.get("introDuration"), INTRO_DURATION_DEFAULT, 3.0, 5.0)


def intro_music_db(options: dict[str, Any]) -> float:
    return clamp_float(options.get("backgroundIntroVolumeDb"), -18.0, -32.0, -14.0)


def dynamic_pauses_enabled(options: dict[str, Any]) -> bool:
    return False


def pause_duration_for_moment(index: int, moment: dict[str, Any], intensity: str) -> float:
    strong = float(moment.get("weight") or 0.0) >= 0.95
    if intensity == "dramatic":
        cycle = (0.7, 1.2, 0.7, 0.4)
    elif intensity == "light":
        cycle = (0.4, 0.4, 0.7)
    else:
        cycle = (0.4, 0.7, 0.4, 1.2)
    value = cycle[index % len(cycle)]
    if strong and value < 0.7:
        value = 0.7
    return value


def build_dynamic_pause_plan(job: Job, cues: list[SubtitleCue], audio_total: float) -> list[dict[str, Any]]:
    if not dynamic_pauses_enabled(job.options) or not cues:
        job.dynamic_pause_summary = {"enabled": False, "reason": "desativado"}
        return []
    intensity = str(job.options.get("dynamicPauseIntensity") or "conservative").lower()
    moments = detect_strong_moments(cues, audio_total, limit=14)
    max_total = max(0.0, audio_total * DYNAMIC_PAUSE_MAX_RATIO)
    max_count = min(DYNAMIC_PAUSE_MAX_COUNT, 8)
    pauses: list[dict[str, Any]] = []
    total = 0.0
    last_at = -99.0
    for idx, moment in enumerate(moments):
        confidence = float(moment.get("confidence") or moment.get("weight") or 0.0)
        if confidence < 0.78:
            continue
        cue_idx = int(moment.get("index") or 0)
        if cue_idx >= len(cues):
            continue
        at = float(cues[cue_idx].end)
        if at < 1.0 or at > audio_total - 2.0 or at - last_at < 10.0:
            continue
        dur = pause_duration_for_moment(len(pauses), moment, intensity)
        if total + dur > max_total + 0.001:
            break
        pauses.append({
            "at": round(at, 3),
            "duration": round(dur, 3),
            "reason": moment.get("reason") or "momento forte",
            "confidence": round(confidence, 3),
            "action": moment.get("action") or "micro_respiro",
            "text": str(moment.get("text") or "")[:140],
        })
        total += dur
        last_at = at
        if len(pauses) >= max_count:
            break
    job.dynamic_pause_summary = {
        "enabled": bool(pauses),
        "requested": True,
        "intensity": intensity,
        "pauses": pauses,
        "count": len(pauses),
        "added_duration": round(total, 3),
        "limit_seconds": round(max_total, 3),
        "policy": "somente momentos fortes com confianca alta",
    }
    if not pauses:
        job.dynamic_pause_summary["reason"] = "Nenhum ponto forte seguro para inserir pausa."
    return pauses


def insert_dynamic_pauses(job: Job, audio_file: Path, audio_total: float, pauses: list[dict[str, Any]], work: Path) -> tuple[Path, float]:
    if not pauses:
        return audio_file, audio_total
    out = Path("glide_voiceover_dynamic_pauses.wav")
    filters: list[str] = []
    labels: list[str] = []
    cursor = 0.0
    part_no = 0
    for idx, pause in enumerate(pauses):
        at = max(cursor, min(float(pause.get("at") or cursor), audio_total))
        if at - cursor > 0.035:
            label = f"a{part_no}"
            filters.append(f"[0:a]atrim=start={cursor:.4f}:end={at:.4f},asetpts=PTS-STARTPTS[{label}]")
            labels.append(f"[{label}]")
            part_no += 1
        silence = max(0.05, float(pause.get("duration") or 0.0))
        slabel = f"s{idx}"
        filters.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{silence:.4f},asetpts=PTS-STARTPTS[{slabel}]")
        labels.append(f"[{slabel}]")
        cursor = at
    if audio_total - cursor > 0.035:
        label = f"a{part_no}"
        filters.append(f"[0:a]atrim=start={cursor:.4f}:end={audio_total:.4f},asetpts=PTS-STARTPTS[{label}]")
        labels.append(f"[{label}]")
    if len(labels) < 2:
        return audio_file, audio_total
    filters.append("".join(labels) + f"concat=n={len(labels)}:v=0:a=1,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[aout]")
    script = work / "dynamic_pauses_filter.txt"
    script.write_text(";".join(filters), encoding="utf-8")
    cmd = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-filter_threads", "1",
        "-i", str(audio_file),
        "-filter_complex_script", script.name,
        "-map", "[aout]",
        "-ac", "2", "-ar", "48000",
        out.name,
    ]
    set_stage(job, "audio", "Inserindo pausas dinâmicas", "Criando micro-respiros narrativos em pontos fortes")
    target = audio_total + sum(float(item.get("duration") or 0.0) for item in pauses)
    run_cmd(job, cmd, total_duration=target or None, base=12, span=2, cwd=work, quiet_success=True)
    actual = safe_probe_duration(work / out) or target
    job.options["_timing_adjustments"] = pauses
    job.dynamic_pause_summary["actual_duration"] = round(actual, 3)
    _append_log(job, f"Pausas dinâmicas: {len(pauses)} pausa(s), +{actual - audio_total:.2f}s, intensidade={job.dynamic_pause_summary.get('intensity')}.")
    return out, actual


def analyze_audio_health(job: Job, audio_file: Path, duration: float, work: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "status": "unknown",
        "duration": round(max(0.0, duration), 3),
        "silence_total": 0.0,
        "silence_ratio": 0.0,
        "longest_silence": 0.0,
        "silence_count": 0,
        "possible_clipping": False,
        "message": "Analise de audio indisponivel.",
    }
    if not FFMPEG or duration <= 0:
        job.audio_health_summary = summary
        return summary
    cmd = [
        FFMPEG, "-hide_banner", "-nostats", "-i", str(audio_file),
        "-af", "silencedetect=n=-45dB:d=1.2,volumedetect",
        "-f", "null", "-",
    ]
    try:
        p = _run_hidden(cmd, cwd=work, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=90)
        text = (p.stderr or "") + "\n" + (p.stdout or "")
    except Exception as exc:
        summary["message"] = f"Nao foi possivel analisar lacunas do audio: {exc}"
        job.audio_health_summary = summary
        return summary

    starts: list[float] = []
    silences: list[tuple[float, float]] = []
    for line in text.splitlines():
        start_match = re.search(r"silence_start:\s*([0-9.]+)", line)
        if start_match:
            starts.append(float(start_match.group(1)))
            continue
        end_match = re.search(r"silence_end:\s*([0-9.]+).*silence_duration:\s*([0-9.]+)", line)
        if end_match:
            end = float(end_match.group(1))
            length = float(end_match.group(2))
            start = starts.pop(0) if starts else max(0.0, end - length)
            silences.append((start, end))
    for start in starts:
        if duration > start:
            silences.append((start, duration))

    silence_total = sum(max(0.0, end - start) for start, end in silences)
    longest = max((max(0.0, end - start) for start, end in silences), default=0.0)
    mean_match = re.search(r"mean_volume:\s*(-?[0-9.]+)\s*dB", text)
    max_match = re.search(r"max_volume:\s*(-?[0-9.]+)\s*dB", text)
    mean_volume = float(mean_match.group(1)) if mean_match else None
    max_volume = float(max_match.group(1)) if max_match else None
    possible_clipping = bool(max_volume is not None and max_volume >= -0.2)
    ratio = silence_total / max(duration, 0.001)
    if possible_clipping or longest >= 4.0 or ratio >= 0.22:
        status = "problem"
        message = "Audio com lacunas longas, muito silencio ou pico muito alto."
    elif longest >= 1.2 or ratio >= 0.08:
        status = "warn"
        message = "Audio utilizavel, mas contem pausas/silencios perceptiveis."
    else:
        status = "ok"
        message = "Audio saudavel para render."
    summary.update({
        "status": status,
        "silence_total": round(silence_total, 3),
        "silence_ratio": round(ratio, 4),
        "longest_silence": round(longest, 3),
        "silence_count": len(silences),
        "silences": [[round(start, 3), round(end, 3)] for start, end in silences[:80]],
        "mean_volume_db": round(mean_volume, 2) if mean_volume is not None else None,
        "max_volume_db": round(max_volume, 2) if max_volume is not None else None,
        "possible_clipping": possible_clipping,
        "message": message,
    })
    job.audio_health_summary = summary
    _append_log(job, (
        f"Saude do audio: {status} | silencio={silence_total:.2f}s "
        f"({ratio * 100:.1f}%) | maior lacuna={longest:.2f}s | pico={max_volume if max_volume is not None else 'n/a'} dB."
    ))
    return summary


def preset_music_genre(options: dict[str, Any]) -> str:
    genre = str(options.get("backgroundMusicGenre") or "cinematic").strip().lower()
    return genre if genre in PRESET_MUSIC_GENRES else "cinematic"


def list_preset_music_files(genre: str) -> list[Path]:
    info = PRESET_MUSIC_GENRES.get(genre) or PRESET_MUSIC_GENRES["cinematic"]
    files: list[Path] = []
    seen: set[str] = set()
    for folder in info["dirs"]:
        try:
            if not folder.exists():
                continue
            for path in folder.iterdir():
                if not path.is_file() or path.suffix.lower() not in MUSIC_EXTS:
                    continue
                key = str(path.resolve()).lower()
                if key in seen:
                    continue
                seen.add(key)
                files.append(path)
        except Exception:
            continue
    for path in info.get("files", ()):
        try:
            if not path.is_file() or path.suffix.lower() not in MUSIC_EXTS:
                continue
            key = str(path.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            files.append(path)
        except Exception:
            continue
    return sorted(files, key=lambda p: natural_key(p.name))


def preset_music_roots(genre: str) -> list[dict[str, Any]]:
    info = PRESET_MUSIC_GENRES.get(genre) or PRESET_MUSIC_GENRES["cinematic"]
    roots: list[dict[str, Any]] = []
    seen: set[str] = set()
    for folder in info["dirs"]:
        try:
            resolved = folder.resolve()
            key = str(resolved).lower()
            if key in seen:
                continue
            seen.add(key)
            count = 0
            if resolved.exists():
                count = sum(1 for path in resolved.iterdir() if path.is_file() and path.suffix.lower() in MUSIC_EXTS)
            roots.append({
                "path": str(resolved),
                "exists": resolved.exists(),
                "count": count,
                "kind": "app" if APP_DIR in (resolved, *resolved.parents) else "user",
            })
        except Exception:
            roots.append({"path": str(folder), "exists": False, "count": 0, "kind": "user"})
    explicit_files = []
    for path in info.get("files", ()):
        try:
            if path.is_file() and path.suffix.lower() in MUSIC_EXTS:
                explicit_files.append(path)
        except Exception:
            continue
    if explicit_files:
        roots.append({
            "path": str(Path.home() / "Music" / "Yt music *.MP3"),
            "exists": True,
            "count": len(explicit_files),
            "kind": "user",
        })
    return roots


def choose_preset_music_files(
    genre: str,
    seed: str,
    limit: int = PRESET_MUSIC_MAX_FILES,
    tone: str | None = None,
    channel: str | None = None,
) -> tuple[list[Path], int]:
    files = avoid_recent_music(list_preset_music_files(genre), MUSIC_HISTORY_FILE, genre)
    channel_scores = channel_music_scores(MUSIC_HISTORY_FILE, channel or "", genre)
    shuffled = sorted(
        files,
        key=lambda path: (
            -channel_scores.get(path.name, 0.0),
            hashlib.sha256(f"{seed}:{genre}:{tone or 'neutral'}:{path.name}:{path.stat().st_size if path.exists() else 0}".encode("utf-8", errors="ignore")).hexdigest(),
        ),
    )
    if tone and tone in TONE_KEYWORDS:
        scored = sorted(
            files,
            key=lambda path: (
                -channel_scores.get(path.name, 0.0),
                -tone_music_score(path, tone),
                hashlib.sha256(f"{seed}:{tone}:{path.name}".encode("utf-8", errors="ignore")).hexdigest(),
            ),
        )
        preferred = [path for path in scored if tone_music_score(path, tone) > 0][: max(8, limit // 3)]
        if preferred:
            seen = {str(path.resolve()).lower() for path in preferred}
            shuffled = preferred + [path for path in shuffled if str(path.resolve()).lower() not in seen]
    return shuffled[:max(1, limit)], len(files)


@app.get("/api/preset-music")
def preset_music_status():
    genres = []
    for key, info in PRESET_MUSIC_GENRES.items():
        files = list_preset_music_files(key)
        size = 0
        exts: set[str] = set()
        for path in files:
            try:
                size += path.stat().st_size
                exts.add(path.suffix.lower().lstrip("."))
            except Exception:
                pass
        genres.append({
            "key": key,
            "label": info["label"],
            "count": len(files),
            "size": size,
            "default": key == "cinematic",
            "roots": preset_music_roots(key),
            "extensions": sorted(exts),
            "samples": [path.name for path in files[:PRESET_MUSIC_SAMPLE_LIMIT]],
            "manualOverride": True,
            "policy": "manual_tracks_disable_library",
            "splitAfterSeconds": PRESET_MUSIC_SPLIT_AFTER,
            "partSeconds": PRESET_MUSIC_PART_SECONDS,
        })
    return {
        "default": "cinematic",
        "genres": genres,
        "history": load_music_history(MUSIC_HISTORY_FILE).get("renders", [])[-8:],
        "manualOverride": "Quando voce importa musicas de fundo, a biblioteca automatica fica pausada neste render.",
        "rules": {
            "neverMixGenres": True,
            "splitLongerThanSeconds": PRESET_MUSIC_SPLIT_AFTER,
            "partSeconds": PRESET_MUSIC_PART_SECONDS,
        },
    }


@app.get("/api/music-history")
def music_history():
    return load_music_history(MUSIC_HISTORY_FILE)


def stable_shuffle_music(items: list[dict[str, Any]], seed: str) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: hashlib.sha256(f"{seed}:{item.get('id')}:{Path(item.get('path')).name}".encode("utf-8", errors="ignore")).hexdigest(),
    )


def build_background_music_plan(
    job: Job,
    music_files: list[Path],
    audio_total: float,
    work: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    library_mode = bool(job.options.get("backgroundMusicAutoLibrary"))
    genre = preset_music_genre(job.options)
    source_infos: list[dict[str, Any]] = []
    long_track_slices = 0
    invalid_video_containers: list[str] = []
    for idx, src in enumerate(music_files, start=1):
        if src.suffix.lower() in VIDEO_EXTS and not probe_has_audio(src, cwd=work):
            invalid_video_containers.append(src.name)
            continue
        dur = safe_probe_duration(src, cwd=work)
        if dur <= 0.08:
            continue
        if dur > PRESET_MUSIC_SPLIT_AFTER:
            offset = 0.0
            part = 1
            while offset < dur - 20.0:
                piece = min(PRESET_MUSIC_PART_SECONDS, dur - offset)
                if piece >= 20.0:
                    source_infos.append({
                        "id": f"{idx}:{part}",
                        "source_index": idx,
                        "path": src,
                        "source_duration": dur,
                        "duration": piece,
                        "offset": offset,
                        "part": part,
                        "name": src.name,
                    })
                    long_track_slices += 1
                offset += PRESET_MUSIC_PART_SECONDS
                part += 1
        else:
            source_infos.append({
                "id": f"{idx}:1",
                "source_index": idx,
                "path": src,
                "source_duration": dur,
                "duration": dur,
                "offset": 0.0,
                "part": 1,
                "name": src.name,
            })
    if not source_infos:
        return [], {
            "enabled": False,
            "reason": "Nenhuma musica de fundo valida.",
            "original_tracks": len(music_files),
            "valid_tracks": 0,
            "invalid_video_containers": invalid_video_containers[:20],
        }

    remaining = audio_total
    cycle = 0
    plans: list[dict[str, Any]] = []
    raw_total = sum(float(item["duration"]) for item in source_infos)
    max_cycles = max(2, int(audio_total / max(raw_total, 0.1)) + 4)

    while remaining > 0.05 and cycle <= max_cycles:
        order = stable_shuffle_music(source_infos, f"{job.id}:music:{genre}:{cycle}") if (library_mode or cycle > 0) else source_infos
        made_progress = False
        for item in order:
            if remaining <= 0.05:
                break
            target = min(float(item["duration"]), remaining)
            if target <= 0.05:
                continue
            plan = dict(item)
            plan.update({"cycle": cycle, "target": target})
            plans.append(plan)
            remaining -= target
            made_progress = True
        if not made_progress:
            break
        cycle += 1

    used_first_cycle = {int(item["source_index"]) for item in plans if int(item["cycle"]) == 0}
    trimmed = sum(1 for item in plans if float(item["target"]) + 0.05 < float(item["duration"]))
    summary = {
        "enabled": bool(plans),
        "original_tracks": len(music_files),
        "valid_tracks": len(source_infos),
        "used_segments": len(plans),
        "reused_segments": sum(1 for item in plans if int(item["cycle"]) > 0),
        "dropped_tracks": max(0, len(source_infos) - len(used_first_cycle)),
        "trimmed_segments": trimmed,
        "target_duration": round(audio_total, 3),
        "planned_duration": round(sum(float(item["target"]) for item in plans), 3),
        "policy": "fit_voiceover_random_reuse",
        "source": "preset_library" if library_mode else "timeline",
        "genre": genre,
        "tone": (job.emotion_summary or {}).get("tone"),
        "long_track_slices": long_track_slices,
        "sample_tracks": [str(Path(item["path"]).name) for item in plans[:6]],
        "invalid_video_containers": invalid_video_containers[:20],
    }
    return plans, summary


def make_background_music(
    job: Job,
    music_files: list[Path],
    audio_total: float,
    work: Path,
    render_volume_override: float | None = None,
) -> Path | None:
    if not music_files:
        return None
    volume_db = background_volume_db(job.options)
    ducking = True
    adaptive = True
    render_volume_db = (
        float(render_volume_override)
        if render_volume_override is not None
        else (background_pause_ceiling_db(job.options) if ducking and adaptive else volume_db)
    )
    plans, summary = build_background_music_plan(job, music_files, audio_total, work)
    summary["volume_db"] = volume_db
    summary["ducking"] = ducking
    summary["adaptive_ducking"] = adaptive and ducking
    summary["pause_ceiling_db"] = render_volume_db
    if render_volume_override is not None:
        summary["intro_render_volume_db"] = render_volume_db
    job.background_music_summary = summary
    if summary.get("invalid_video_containers"):
        _append_log(job, f"Musica de fundo: {len(summary.get('invalid_video_containers') or [])} MP4/MOV importado(s) como musica nao tinham audio legivel e foram ignorados.")
    if not plans:
        _append_log(job, f"Musica de fundo ignorada: {summary.get('reason', 'sem trechos validos')}")
        return None

    bg_dir = work / "background_music"
    bg_dir.mkdir(exist_ok=True)
    segment_paths: list[Path] = []
    fade_base = 1.0
    _append_log(job, (
        f"Musica de fundo: {summary['original_tracks']} arquivo(s), volume={volume_db:.0f} dB, "
        f"pausas ate {render_volume_db:.0f} dB, ducking={'on' if ducking else 'off'}, "
        f"segmentos={summary['used_segments']}, reutilizados={summary['reused_segments']}, "
        f"cortados={summary['trimmed_segments']}."
    ))

    for idx, plan in enumerate(plans, start=1):
        src = Path(plan["path"])
        target = float(plan["target"])
        offset = float(plan.get("offset") or 0.0)
        out = bg_dir / f"music_{idx:04d}.wav"
        fade = min(fade_base, max(0.08, target / 3.0))
        fade_out_at = max(0.0, target - fade)
        af = (
            "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"volume={render_volume_db:.2f}dB,"
            f"afade=t=in:st=0:d={fade:.3f},"
            f"afade=t=out:st={fade_out_at:.3f}:d={fade:.3f}"
        )
        cmd = [
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-filter_threads", "1",
        ]
        if offset > 0:
            cmd += ["-ss", f"{offset:.4f}"]
        cmd += [
            "-i", str(src),
            "-vn", "-t", f"{target:.4f}",
            "-af", af,
            "-ac", "2", "-ar", "48000",
            str(out),
        ]
        run_cmd(job, cmd, cwd=work, quiet_success=True)
        if out.exists() and out.stat().st_size > 0:
            segment_paths.append(out)

    if not segment_paths:
        job.background_music_summary["enabled"] = False
        _append_log(job, "Musica de fundo ignorada: nenhum segmento foi gerado.")
        return None

    out = Path("glide_background_music.wav")
    if len(segment_paths) == 1:
        cmd = [
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-filter_threads", "1",
            "-i", str(segment_paths[0]),
            "-vn", "-t", f"{audio_total:.4f}", "-ac", "2", "-ar", "48000",
            str(out),
        ]
        run_cmd(job, cmd, cwd=work, quiet_success=True)
    else:
        cmd: list[str] = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-filter_threads", "1", "-filter_complex_threads", "1"]
        for path in segment_paths:
            cmd += ["-i", str(path)]
        filters = []
        labels = []
        for i in range(len(segment_paths)):
            filters.append(f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[m{i}]")
            labels.append(f"[m{i}]")
        filters.append("".join(labels) + f"concat=n={len(segment_paths)}:v=0:a=1[music]")
        script = work / "background_music_filter.txt"
        script.write_text(";".join(filters), encoding="utf-8")
        cmd += ["-filter_complex_script", script.name, "-map", "[music]", "-t", f"{audio_total:.4f}", "-ac", "2", "-ar", "48000", str(out)]
        run_cmd(job, cmd, cwd=work, quiet_success=True)

    final_duration = safe_probe_duration(work / out)
    job.background_music_summary["actual_duration"] = round(final_duration, 3)
    _append_log(job, f"Musica de fundo pronta: duracao={final_duration:.2f}s, base={volume_db:.0f} dB, pausas={render_volume_db:.0f} dB.")
    return out


def delay_voiceover_for_intro(job: Job, voiceover_file: Path, timeline_total: float, work: Path, intro_seconds: float) -> Path:
    if intro_seconds <= 0:
        return voiceover_file
    out = Path("glide_voiceover_delayed.wav")
    delay_ms = max(0, int(round(intro_seconds * 1000)))
    fade = clamp_float(job.options.get("voiceIntroFade"), 0.45, 0.12, 1.2)
    af = (
        "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
        f"adelay={delay_ms}|{delay_ms},"
        f"afade=t=in:st={intro_seconds:.3f}:d={fade:.3f},"
        f"apad=whole_dur={timeline_total:.4f}"
    )
    cmd = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-filter_threads", "1",
        "-i", str(voiceover_file),
        "-vn", "-af", af,
        "-t", f"{timeline_total:.4f}",
        "-ac", "2", "-ar", "48000",
        str(out),
    ]
    set_stage(job, "audio", "Criando abertura", "Atrasando narracao para intro Cinematic")
    run_cmd(job, cmd, total_duration=timeline_total or None, base=12, span=2, cwd=work, quiet_success=True)
    return out


def mix_voiceover_with_background(
    job: Job,
    voiceover_file: Path,
    background_file: Path | None,
    audio_total: float,
    work: Path,
    intro_seconds: float = 0.0,
) -> Path:
    if not background_file:
        job.ducking_summary = {"enabled": False, "reason": "sem musica de fundo"}
        return voiceover_file
    out = Path("glide_audio_final_mix.wav")
    ducking = True
    adaptive = True
    base_db = background_volume_db(job.options)
    pause_ceiling = background_pause_ceiling_db(job.options)
    act1_end = min(12.0, max(3.0, audio_total * 0.10))
    act3_start = max(act1_end + 5.0, audio_total * 0.85)
    act_curve = f",volume=volume='if(lt(t\\,{act1_end:.1f})\\,1.20\\,if(gt(t\\,{act3_start:.1f})\\,1.18\\,1.0))':eval=frame"

    if intro_seconds > 0:
        intro_db = intro_music_db(job.options)
        target_db = background_volume_db(job.options)
        main_gain = target_db - intro_db
        intro_fade = clamp_float(job.options.get("introMusicFade"), 0.65, 0.2, 1.5)
        intro_out = max(0.0, intro_seconds - intro_fade)
        music_shape = (
            f"[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume={intro_db:.1f}dB{act_curve}[music_raw];"
            "[music_raw]asplit=2[mintro_src][mmain_src];"
            f"[mintro_src]atrim=0:{intro_seconds:.3f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={intro_fade:.3f},"
            f"afade=t=out:st={intro_out:.3f}:d={intro_fade:.3f}[music_intro];"
            f"[mmain_src]atrim=start={intro_seconds:.3f},asetpts=PTS-STARTPTS,"
            f"volume={main_gain:.2f}dB,adelay={int(round(intro_seconds * 1000))}|{int(round(intro_seconds * 1000))}[music_main];"
            "[music_intro][music_main]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[music_raw2];"
        )
        if ducking:
            mix_filter = (
                "[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[voice];"
                + music_shape +
                "[music_raw2][voice]sidechaincompress=threshold=0.032:ratio=4.0:attack=45:release=650:makeup=1.0,alimiter=limit=0.92[music];"
                "[voice][music]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
            )
        else:
            mix_filter = (
                "[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[voice];"
                + music_shape +
                "[voice][music_raw2]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
            )
        mix_message = "Mixando intro Cinematic: música abre e baixa suavemente com curva de 3 atos"
    elif ducking:
        mix_filter = (
            f"[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[voice];"
            f"[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume={base_db:.1f}dB{act_curve}[music_raw];"
            f"[music_raw][voice]sidechaincompress=threshold=0.032:ratio=4.0:attack=45:release=650:makeup=1.0,alimiter=limit=0.92[music];"
            f"[voice][music]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
        )
        mix_message = "Mixando narração com música dinâmica, curva de 3 atos e respiro suave em pausas"
    else:
        mix_filter = (
            f"[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[voice];"
            f"[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume={base_db:.1f}dB{act_curve}[music];"
            f"[voice][music]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
        )
        mix_message = "Mixando narração com música de fundo e curva de 3 atos"
    cmd = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-filter_threads", "1", "-filter_complex_threads", "1",
        "-i", str(voiceover_file),
        "-i", str(background_file),
        "-filter_complex",
        mix_filter,
        "-map", "[aout]",
        "-t", f"{audio_total:.4f}",
        "-ac", "2", "-ar", "48000",
        str(out),
    ]
    set_stage(job, "audio", "Mixando narração + música", mix_message)
    run_cmd(job, cmd, total_duration=audio_total or None, base=12, span=3, cwd=work, quiet_success=True)
    silence_segments = list((job.audio_health_summary or {}).get("silences") or [])
    long_pauses = [item for item in silence_segments if len(item) >= 2 and float(item[1]) - float(item[0]) >= 2.0]
    job.ducking_summary = {
        "enabled": ducking,
        "adaptive": adaptive and ducking,
        "base_db": base_db,
        "pause_ceiling_db": pause_ceiling,
        "method": "balanced_sidechain_music_floor" if ducking else "fixed_low_mix",
        "audibility_boost_db": 1.6 if ducking else 0.0,
        "envelope_policy": {
            "active_voice": "music controlled by smooth sidechain",
            "short_pause": "music rises slightly without competing with narration",
            "long_pause": f"music may approach the safe ceiling of {pause_ceiling:.0f} dB",
            "smoothing_ms": {"attack": 45, "release": 780},
        },
        "detected_silences": len(silence_segments),
        "long_pauses": len(long_pauses),
        "intro_seconds": round(intro_seconds, 3),
    }
    _append_log(job, (
        f"Audio final mixado: narracao em 1.0 + musica baixa; ducking={'on' if ducking else 'off'}; "
        f"adaptativo={'on' if adaptive and ducking else 'off'}; base={base_db:.0f} dB; "
        f"pausas ate {pause_ceiling:.0f} dB; intro={intro_seconds:.2f}s."
    ))
    return out


def render_size(mode: str, ratio: str) -> tuple[int, int]:
    mode = (mode or "standard").lower()
    if ratio == "9:16":
        return ((720, 1280) if mode == "fast" else (1080, 1920))
    return ((1280, 720) if mode == "fast" else (1920, 1080))


def srt_time_to_seconds(value: str) -> float:
    match = re.match(r"\s*(\d+):(\d{2}):(\d{2})[,.](\d{1,3})\s*", value)
    if not match:
        raise ValueError(f"Tempo SRT invalido: {value!r}")
    hours, minutes, seconds, millis = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis.ljust(3, "0")) / 1000


def seconds_to_ass_time(value: float) -> str:
    value = max(0.0, value)
    centis = int(round(value * 100))
    hours = centis // 360000
    centis %= 360000
    minutes = centis // 6000
    centis %= 6000
    seconds = centis // 100
    centis %= 100
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centis:02d}"


def ass_escape(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("{", "(").replace("}", ")")
    text = re.sub(r"\s+", " ", text).strip()
    return text.replace("\\", "\\\\")


def ass_color(value: str | None, default: str, alpha: str = "00") -> str:
    raw = (value or default).strip()
    if raw.startswith("#"):
        raw = raw[1:]
    if len(raw) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", raw):
        raw = default.lstrip("#")
    rr, gg, bb = raw[0:2], raw[2:4], raw[4:6]
    return f"&H{alpha}{bb}{gg}{rr}"


def stable_index(seed: str, modulo: int) -> int:
    digest = hashlib.sha256(seed.encode("utf-8", errors="ignore")).hexdigest()
    return int(digest[:8], 16) % modulo


def heuristic_text(value: Any) -> str:
    raw = str(value or "").lower()
    raw = raw.replace("_", " ").replace("-", " ").replace("%20", " ")
    raw = re.sub(r"[^\w\sáàâãéêíóôõúüçñ]", " ", raw, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", raw).strip()


TONE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "suspense": (
        "suspense", "misterio", "mistério", "shadow", "shadows", "dark", "eclipse", "secret",
        "segredo", "forbidden", "crime", "problem", "problema", "thriller", "night", "midnight",
        "cave", "caves", "danger", "dangerous", "collapse",
    ),
    "emotional": (
        "emotional", "emocional", "serenity", "serenidade", "sad", "sadness", "triste",
        "whispers", "quiet", "calm", "peaceful", "stillness", "reflections", "baby",
        "family", "familia", "família", "memory", "memoria", "memória",
    ),
    "explanatory": (
        "explicativo", "how to", "tutorial", "recipe", "receita", "documentary", "documentario",
        "documentário", "facts", "curiosidades", "guide", "history", "historia", "história",
        "process", "como", "por que", "porque", "what is",
    ),
    "energetic": (
        "epic", "hero", "battle", "trailer", "action", "impact", "rise", "reveal", "awakening",
        "dawn", "power", "powerful", "motivacional", "motivational", "speed", "fast",
    ),
    "historical": (
        "historical", "historia", "história", "archive", "arquivo", "ancient", "old", "forgotten",
        "document", "classified", "factory", "industrial", "machine", "legacy", "tradicional",
    ),
    "tech": (
        "tech", "tecnologia", "digital", "cyber", "futuristic", "futurista", "data", "hud",
        "ai", "ia", "interface", "glitch", "cosmic", "stars", "odyssey",
    ),
}


STRONG_MOMENT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("o mais impressionante", "frase de impacto"),
    ("mais impressionante", "frase de impacto"),
    ("ninguem esperava", "virada narrativa"),
    ("ninguém esperava", "virada narrativa"),
    ("mas o problema", "conflito"),
    ("o problema comecou", "conflito"),
    ("o problema começou", "conflito"),
    ("o segredo", "revelacao"),
    ("the secret", "revelacao"),
    ("nobody expected", "virada narrativa"),
    ("the problem began", "conflito"),
    ("but the problem", "conflito"),
    ("the most impressive", "frase de impacto"),
    ("lo mas impresionante", "frase de impacto"),
    ("lo más impresionante", "frase de impacto"),
    ("nadie esperaba", "virada narrativa"),
    ("el secreto", "revelacao"),
    ("le plus impressionnant", "frase de impacto"),
    ("personne ne s attendait", "virada narrativa"),
    ("le secret", "revelacao"),
    ("finally", "marco narrativo"),
    ("por fim", "marco narrativo"),
    ("no entanto", "virada narrativa"),
    ("however", "virada narrativa"),
    ("de repente", "virada narrativa"),
)


def infer_language_hint(options: dict[str, Any], files_manifest: list[dict[str, Any]]) -> str:
    text = heuristic_text(" ".join([
        str(options.get("queueProjectName") or ""),
        str(options.get("outputName") or ""),
        " ".join(str(item.get("name") or item.get("rel") or "") for item in files_manifest[:80]),
    ]))
    checks = (
        ("en", (" english ", " ingles ", " inglês ", " en ", "_en", " usa ", " uk ")),
        ("es", (" spanish ", " espanhol ", " espanol ", " español ", " es ", "_es")),
        ("fr", (" french ", " frances ", " francês ", " francais ", " français ", " fr ", "_fr")),
        ("de", (" german ", " alemao ", " alemão ", " deutsch ", " de ", "_de")),
        ("it", (" italian ", " italiano ", " it ", "_it")),
        ("ru", (" russian ", " russo ", " Ñ€ÑƒÑÑÐºÐ¸Ð¹ ", " ru ", "_ru")),
        ("pl", (" polish ", " polaco ", " polski ", " pl ", "_pl")),
        ("pt", (" portuguese ", " portugues ", " português ", " brasil ", " brazil ", " pt ", "_pt")),
    )
    padded = f" {text} "
    for lang, tokens in checks:
        if any(token in padded for token in tokens):
            return lang
    return "pt"


def infer_project_tone(options: dict[str, Any], files_manifest: list[dict[str, Any]] | None = None, cues: list[SubtitleCue] | None = None) -> dict[str, Any]:
    requested = str(options.get("projectTone") or "auto").strip().lower()
    if requested in PROJECT_TONES and requested != "auto":
        return {"tone": requested, "mode": "manual", "evidence": [f"Selecionado manualmente: {requested}"], "scores": {}}
    identity_chunks: list[str] = [
        str(options.get("queueProjectName") or ""),
        str(options.get("outputName") or ""),
        str(options.get("workflowPreset") or ""),
        str(options.get("visualLanguagePackage") or ""),
    ]
    style_chunks: list[str] = [
        str(options.get("exportProfile") or ""),
        str(options.get("transitions") or ""),
        str(options.get("introMode") or ""),
    ]
    media_chunks = [str(item.get("name") or item.get("rel") or "") for item in (files_manifest or [])[:120]]
    cue_chunks = [str(cue.text or "") for cue in (cues or [])[:120]]
    weighted_sources = (
        ("identidade", heuristic_text(" ".join(identity_chunks)), 4),
        ("narracao", heuristic_text(" ".join(cue_chunks)), 3),
        ("midia", heuristic_text(" ".join(media_chunks)), 1),
        ("estilo", heuristic_text(" ".join(style_chunks)), 1),
    )
    scores = {tone: 0 for tone in TONE_KEYWORDS}
    evidence_by_tone: dict[str, list[str]] = {tone: [] for tone in TONE_KEYWORDS}
    for tone, words in TONE_KEYWORDS.items():
        for word in words:
            for source_name, source_text, weight in weighted_sources:
                if word in source_text:
                    scores[tone] += weight
                    if len(evidence_by_tone[tone]) < 8:
                        evidence_by_tone[tone].append(f"{source_name}: {word}")
    text = " ".join(source[1] for source in weighted_sources)
    if "cinematic" in text or "cinema" in text:
        scores["energetic"] += 1
    if "document" in text or "archive" in text:
        scores["historical"] += 1
    priority = ("explanatory", "historical", "emotional", "suspense", "tech", "energetic")
    tone = max(priority, key=lambda key: scores[key])
    if scores[tone] <= 0:
        tone = "explanatory"
        evidence = ["Fallback conservador: explicativo/documental"]
    else:
        evidence = evidence_by_tone[tone][:8]
    sorted_scores = sorted(scores.values(), reverse=True)
    lead = scores[tone] - (sorted_scores[1] if len(sorted_scores) > 1 else 0)
    confidence = max(0.45, min(0.96, 0.56 + scores[tone] * 0.018 + lead * 0.025))
    return {
        "tone": tone,
        "mode": "auto",
        "confidence": round(confidence, 3),
        "evidence": evidence,
        "scores": scores,
        "policy": "identidade_e_narracao_tem_prioridade_sobre_nomes_de_midia",
    }


def tone_music_score(path: Path, tone: str) -> int:
    name = heuristic_text(path.stem)
    score = 0
    for token in TONE_KEYWORDS.get(tone, ()):
        if token in name:
            score += 6
    soft_cross = {
        "historical": ("archive", "ancient", "documentary", "industrial", "legacy", "shadow"),
        "suspense": ("dark", "shadow", "eclipse", "thriller", "cave", "secret"),
        "emotional": ("serenity", "whisper", "peace", "quiet", "reflection", "stillness"),
        "energetic": ("epic", "battle", "hero", "dawn", "trailer", "reveal"),
        "tech": ("digital", "cosmic", "futuristic", "odyssey", "data"),
        "explanatory": ("documentary", "background", "calm", "journey", "horizon"),
    }
    for token in soft_cross.get(tone, ()):
        if token in name:
            score += 3
    return score


def detect_strong_moments(cues: list[SubtitleCue], total_duration: float, limit: int = 12) -> list[dict[str, Any]]:
    moments: list[dict[str, Any]] = []
    last_time = -99.0
    for idx, cue in enumerate(cues):
        text = heuristic_text(cue.text)
        reason = ""
        weight = 0.0
        for pattern, label in STRONG_MOMENT_PATTERNS:
            if pattern in text:
                reason = label
                weight = 1.0
                break
        if not reason:
            if len(cue.text) >= 95 and any(token in text for token in ("mas", "but", "however", "segredo", "secret", "nunca", "never")):
                reason = "frase longa com virada"
                weight = 0.72
        if not reason:
            continue
        if cue.start - last_time < 8.0:
            continue
        if cue.start < 0.8 or cue.start > total_duration - 2.0:
            continue
        moments.append({
            "index": idx,
            "cue_index": idx,
            "time": round(cue.start, 3),
            "end": round(cue.end, 3),
            "text": cue.text[:160],
            "reason": reason,
            "weight": round(weight, 2),
            "confidence": round(max(0.45, min(0.98, weight)), 3),
            "action": "reforco_textual_sutil" if weight < 0.9 else "impacto_textual",
        })
        last_time = cue.start
        if len(moments) >= limit:
            break
    return moments


def build_smart_sample_windows(cues: list[SubtitleCue], total_duration: float, target_seconds: float = 30.0) -> list[dict[str, Any]]:
    total_duration = max(0.1, float(total_duration or 0.1))
    target_seconds = clamp_float(target_seconds, 30.0, 12.0, 90.0)
    normalized, _ = normalize_subtitles(cues, total_duration, min_duration=0.35) if cues else ([], {})
    moments = detect_strong_moments(normalized, total_duration, limit=6) if normalized else []

    def around(center: float, duration: float) -> tuple[float, float]:
        duration = max(2.0, min(duration, total_duration))
        start = max(0.0, min(total_duration - duration, center - duration / 2.0))
        return round(start, 3), round(min(total_duration, start + duration), 3)

    chunk = max(3.0, min(6.0, target_seconds / 5.0))
    candidates: list[tuple[str, float, str]] = [
        ("intro", min(total_duration * 0.08, chunk / 2.0), "inicio da narrativa"),
        ("meio", total_duration * 0.50, "meio do video"),
        ("cta", max(chunk / 2.0, total_duration * 0.84), "trecho proximo do CTA"),
        ("final", max(chunk / 2.0, total_duration - chunk / 2.0), "fechamento"),
    ]
    if moments:
        candidates.insert(2, ("momento_forte", float(moments[0].get("time") or total_duration * 0.35), str(moments[0].get("reason") or "frase forte")))
    else:
        candidates.insert(2, ("momento_forte", total_duration * 0.35, "ponto narrativo intermediário"))

    windows: list[dict[str, Any]] = []
    used_ranges: list[tuple[float, float]] = []
    cursor = 0.0
    for role, center, reason in candidates:
        start, end = around(center, chunk)
        if any(abs(start - prev_start) < 1.0 or (start < prev_end and end > prev_start) for prev_start, prev_end in used_ranges):
            continue
        duration = max(0.2, end - start)
        windows.append({
            "role": role,
            "source_start": start,
            "source_end": end,
            "sample_start": round(cursor, 3),
            "sample_end": round(cursor + duration, 3),
            "duration": round(duration, 3),
            "reason": reason,
        })
        used_ranges.append((start, end))
        cursor += duration
        if cursor >= target_seconds - 0.2:
            break
    if not windows:
        end = min(total_duration, target_seconds)
        windows.append({
            "role": "intro",
            "source_start": 0.0,
            "source_end": round(end, 3),
            "sample_start": 0.0,
            "sample_end": round(end, 3),
            "duration": round(end, 3),
            "reason": "fallback da amostra",
        })
    return windows


def remap_cues_for_smart_sample(cues: list[SubtitleCue], windows: list[dict[str, Any]]) -> list[SubtitleCue]:
    remapped: list[SubtitleCue] = []
    for window in windows:
        source_start = float(window.get("source_start") or 0.0)
        source_end = float(window.get("source_end") or source_start)
        sample_start = float(window.get("sample_start") or 0.0)
        for cue in cues:
            overlap_start = max(cue.start, source_start)
            overlap_end = min(cue.end, source_end)
            if overlap_end - overlap_start < 0.08:
                continue
            new_start = sample_start + (overlap_start - source_start)
            new_end = sample_start + (overlap_end - source_start)
            remapped.append(SubtitleCue(round(new_start, 3), round(max(new_start + 0.15, new_end), 3), cue.text))
    remapped.sort(key=lambda cue: (cue.start, cue.end))
    return remapped


def compose_smart_sample_audio(job: Job, audio_file: Path, windows: list[dict[str, Any]], work: Path) -> tuple[Path, float]:
    if not windows:
        return audio_file, 0.0
    sample_audio = work / "smart_sample_audio.wav"
    filters: list[str] = []
    labels: list[str] = []
    total = 0.0
    for idx, window in enumerate(windows):
        start = max(0.0, float(window.get("source_start") or 0.0))
        end = max(start + 0.1, float(window.get("source_end") or start + 0.1))
        label = f"s{idx}"
        filters.append(f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[{label}]")
        labels.append(f"[{label}]")
        total += end - start
    filters.append(f"{''.join(labels)}concat=n={len(labels)}:v=0:a=1,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[aout]")
    run_cmd(
        job,
        [
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(audio_file),
            "-filter_complex", ";".join(filters),
            "-map", "[aout]",
            "-c:a", "pcm_s16le",
            str(sample_audio),
        ],
        cwd=work,
        quiet_success=True,
    )
    return sample_audio, max(0.1, total)


def timing_offset_at(value: float, adjustments: list[dict[str, Any]]) -> float:
    offset = 0.0
    for item in adjustments:
        if value >= float(item.get("at") or 0.0):
            offset += float(item.get("duration") or 0.0)
    return offset


def apply_timing_adjustments(cues: list[SubtitleCue], adjustments: list[dict[str, Any]]) -> list[SubtitleCue]:
    if not adjustments:
        return cues
    shifted: list[SubtitleCue] = []
    for cue in cues:
        start = cue.start + timing_offset_at(cue.start, adjustments)
        end = cue.end + timing_offset_at(cue.end, adjustments)
        shifted.append(SubtitleCue(start=start, end=max(start + 0.05, end), text=cue.text))
    return shifted


def split_cue_into_single_lines(cue: SubtitleCue, max_chars: int = 40) -> list[SubtitleCue]:
    """Divide blocos de legendas longos em frases elegantes de 1 linha sem quebrar contexto."""
    raw_text = re.sub(r"\s+", " ", cue.text).strip()
    if not raw_text:
        return []
    dur = max(0.1, cue.end - cue.start)
    if len(raw_text) <= max_chars and len(raw_text.split()) <= 7:
        return [SubtitleCue(cue.start, cue.end, raw_text)]

    def _find_best_split(text: str) -> tuple[str, str]:
        mid = len(text) // 2

        # 1. Ponto de corte por pontuação forte/média próxima ao meio
        punct_matches = list(re.finditer(r"[\.!\?;:,—–]\s+", text))
        if punct_matches:
            best_p = min(punct_matches, key=lambda m: abs(m.end() - mid))
            if 6 <= best_p.end() <= len(text) - 6:
                return text[:best_p.end()].strip(), text[best_p.end():].strip()

        # 2. Ponto de corte por conectivos gramaticais próximos ao meio
        conn_matches = list(re.finditer(
            r"\s+(?:porque|que|quando|onde|donde|pero|mas|como|para|com|sem|por|and|or|because|that|which|when|where|with|from|então|entonces|del|de la|de los|do|da|dos|das)\s+",
            text,
            re.IGNORECASE,
        ))
        if conn_matches:
            best_c = min(conn_matches, key=lambda m: abs(m.start() - mid))
            if 6 <= best_c.start() <= len(text) - 6:
                return text[:best_c.start()].strip(), text[best_c.start():].strip()

        # 3. Ponto de corte no espaço entre palavras mais central
        words = text.split()
        if len(words) > 1:
            mid_word = len(words) // 2
            left = " ".join(words[:mid_word]).strip()
            right = " ".join(words[mid_word:]).strip()
            return left, right

        return text, ""

    def _split_recursive(text: str, start: float, end: float) -> list[SubtitleCue]:
        text = text.strip()
        dur_segment = max(0.08, end - start)
        if len(text) <= max_chars and len(text.split()) <= 7:
            return [SubtitleCue(round(start, 3), round(end, 3), text)]

        left, right = _find_best_split(text)
        if not left or not right:
            return [SubtitleCue(round(start, 3), round(end, 3), text)]

        total_chars = len(left) + len(right)
        left_dur = max(0.12, dur_segment * (len(left) / max(1, total_chars)))
        mid_time = start + left_dur

        return _split_recursive(left, start, mid_time) + _split_recursive(right, mid_time, end)

    return _split_recursive(raw_text, cue.start, cue.end)


def parse_srt_file(path: Path) -> list[SubtitleCue]:
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        text = path.read_text(encoding="latin-1", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", text.strip())
    cues: list[SubtitleCue] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        time_idx = next((idx for idx, line in enumerate(lines) if "-->" in line), -1)
        if time_idx < 0:
            continue
        left, right = lines[time_idx].split("-->", 1)
        try:
            start = srt_time_to_seconds(left)
            end = srt_time_to_seconds(right.split()[0])
        except Exception:
            continue
        body = " ".join(lines[time_idx + 1:]).strip()
        if body:
            raw_cue = SubtitleCue(start=start, end=max(start, end), text=body)
            cues.extend(split_cue_into_single_lines(raw_cue, max_chars=40))
    return cues


def normalize_subtitles(cues: list[SubtitleCue], total_duration: float, min_duration: float = MIN_SUBTITLE_SECONDS) -> tuple[list[SubtitleCue], dict[str, Any]]:
    # Garante que todas as cues passem pela divisão semântica de 1 linha
    expanded_cues: list[SubtitleCue] = []
    for cue in cues:
        expanded_cues.extend(split_cue_into_single_lines(cue, max_chars=40))

    adjusted: list[SubtitleCue] = []
    removed_outside = 0
    removed_short_tail = 0
    for cue in expanded_cues:
        if cue.start < 0:
            cue = SubtitleCue(0.0, cue.end, cue.text)
        if cue.start >= total_duration or not cue.text.strip():
            removed_outside += 1
            continue
        end = min(total_duration, max(cue.end, cue.start + min_duration))
        if end - cue.start < min_duration - 0.02:
            removed_short_tail += 1
            continue
        adjusted.append(SubtitleCue(cue.start, end, cue.text.strip()))

    adjusted.sort(key=lambda cue: (cue.start, cue.end))
    clusters: list[list[SubtitleCue]] = []
    current: list[SubtitleCue] = []
    current_end = -1.0
    for cue in adjusted:
        if not current or cue.start < current_end - 0.02:
            current.append(cue)
            current_end = max(current_end, cue.end)
        else:
            clusters.append(current)
            current = [cue]
            current_end = cue.end
    if current:
        clusters.append(current)

    kept: list[SubtitleCue] = []
    removed_overlap = 0
    for cluster in clusters:
        winner = max(cluster, key=lambda cue: (len(re.sub(r"\s+", "", cue.text)), cue.end - cue.start))
        kept.append(winner)
        removed_overlap += len(cluster) - 1
    kept.sort(key=lambda cue: cue.start)
    summary = {
        "original": len(cues),
        "valid": len(kept),
        "removed_outside": removed_outside,
        "removed_short_tail": removed_short_tail,
        "removed_overlap": removed_overlap,
        "min_duration": min_duration,
    }
    return kept, summary


def subtitle_style_from_options(options: dict[str, Any]) -> dict[str, Any]:
    style = dict(options.get("textStyle") or options.get("subtitleStyle") or {})
    preset = style.get("preset") or "bold_white"
    font_presets = {
        "arial": "Arial",
        "arial_black": "Arial Black",
        "bahnschrift": "Bahnschrift",
        "segoe": "Segoe UI Semibold",
        "impact": "Impact",
        "georgia": "Georgia",
        "trebuchet": "Trebuchet MS",
        "verdana": "Verdana",
    }
    presets = {
        "bold_white": {"font": "Arial Black", "size": 48, "primary": "#FFFFFF", "outline": "#0A0A0A", "back": "#000000", "bold": True, "box": False, "animation": "spring", "outline_size": 1.8, "shadow": 1.2},
        "bold_yellow": {"font": "Arial Black", "size": 48, "primary": "#FFE600", "outline": "#0C0C0C", "back": "#000000", "bold": True, "box": False, "animation": "spring", "outline_size": 1.8, "shadow": 1.2},
        "dark_box": {"font": "Segoe UI Semibold", "size": 42, "primary": "#FFFFFF", "outline": "#000000", "back": "#121519", "bold": True, "box": True, "animation": "slide", "outline_size": 0.8, "shadow": 0.0},
        "cinema_white": {"font": "Georgia", "size": 44, "primary": "#FBF6EE", "outline": "#080808", "back": "#000000", "bold": False, "box": False, "animation": "cinematic", "outline_size": 1.4, "shadow": 1.2},
        "green_neon": {"font": "Arial Black", "size": 46, "primary": "#65FF90", "outline": "#031E0C", "back": "#000000", "bold": True, "box": False, "animation": "pulse", "outline_size": 1.8, "shadow": 1.0},
        "minimal": {"font": "Segoe UI Semibold", "size": 40, "primary": "#F5F5F7", "outline": "#18181A", "back": "#000000", "bold": False, "box": False, "animation": "fade", "outline_size": 1.0, "shadow": 0.6},
        "impact_gold": {"font": "Impact", "size": 50, "primary": "#FFDE59", "outline": "#140F03", "back": "#000000", "bold": True, "box": False, "animation": "spring", "outline_size": 2.2, "shadow": 1.2},
        "documentary": {"font": "Bahnschrift", "size": 43, "primary": "#F0F4F2", "outline": "#09120E", "back": "#000000", "bold": True, "box": False, "animation": "cinematic", "outline_size": 1.6, "shadow": 1.0},
        "blue_glow": {"font": "Arial Black", "size": 46, "primary": "#7FE5FF", "outline": "#041C2C", "back": "#000000", "bold": True, "box": False, "animation": "kinetic", "outline_size": 2.0, "shadow": 1.2},
        "red_punch": {"font": "Arial Black", "size": 48, "primary": "#FF594D", "outline": "#180403", "back": "#000000", "bold": True, "box": False, "animation": "spring", "outline_size": 2.0, "shadow": 1.0},
        "soft_pink": {"font": "Trebuchet MS", "size": 44, "primary": "#FFD4EB", "outline": "#220C19", "back": "#000000", "bold": True, "box": False, "animation": "fade", "outline_size": 1.4, "shadow": 0.8},
        "clean_box": {"font": "Verdana", "size": 40, "primary": "#FFFFFF", "outline": "#000000", "back": "#0A0D12", "bold": True, "box": True, "animation": "fade", "outline_size": 0.6, "shadow": 0.0},
    }
    base = presets.get(preset, presets["bold_white"]).copy()
    base["preset"] = preset
    font_key = str(style.get("fontPreset") or "").strip()
    if font_key in font_presets:
        base["font"] = font_presets[font_key]
    if style.get("font"):
        base["font"] = str(style["font"])
    for key in ("primary", "outline", "back"):
        if style.get(key):
            base[key] = str(style[key])
    if style.get("size"):
        try:
            base["size"] = max(28, min(120, int(style["size"])))
        except Exception:
            pass
    try:
        base["position"] = max(8, min(34, int(style.get("position", 16))))
    except Exception:
        base["position"] = 16
    if "box" in style:
        base["box"] = bool(style["box"])
    animation = str(style.get("animation") or base.get("animation") or "mixed")
    if animation not in SUBTITLE_ANIMATIONS:
        animation = "mixed"
    base["animation"] = animation
    try:
        base["outline_size"] = max(0.0, min(5.0, float(style.get("outlineSize", base.get("outline_size", 2.0)))))
    except Exception:
        base["outline_size"] = 2.0
    try:
        base["shadow"] = max(0.0, min(3.0, float(style.get("shadow", base.get("shadow", 1.0)))))
    except Exception:
        base["shadow"] = 1.0
    return base


def intro_subtitle_style_from_options(options: dict[str, Any]) -> dict[str, Any]:
    raw = dict(options.get("introSubtitleStyle") or {})
    presets = {
        "cinema_gold": {"font": "Georgia", "size": 76, "primary": "#FFD36A", "outline": "#090909", "bold": True, "box": False, "position": 44, "outline_size": 2.2, "shadow": 1.2},
        "white_title": {"font": "Arial Black", "size": 72, "primary": "#FFFFFF", "outline": "#101010", "bold": True, "box": False, "position": 44, "outline_size": 2.4, "shadow": 1.0},
        "dark_card": {"font": "Segoe UI Semibold", "size": 62, "primary": "#FFFFFF", "outline": "#000000", "bold": True, "box": True, "position": 46, "outline_size": 0.8, "shadow": 0.0},
        "green_premiere": {"font": "Bahnschrift", "size": 68, "primary": "#98FFB0", "outline": "#062412", "bold": True, "box": False, "position": 44, "outline_size": 2.0, "shadow": 1.1},
    }
    preset = str(raw.get("preset") or "cinema_gold")
    base = presets.get(preset, presets["cinema_gold"]).copy()
    base["preset"] = preset
    font_presets = {
        "arial_black": "Arial Black",
        "bahnschrift": "Bahnschrift",
        "segoe": "Segoe UI Semibold",
        "georgia": "Georgia",
        "impact": "Impact",
    }
    font_key = str(raw.get("fontPreset") or "").strip()
    if font_key in font_presets:
        base["font"] = font_presets[font_key]
    for key in ("primary", "outline"):
        if raw.get(key):
            base[key] = str(raw[key])
    try:
        base["size"] = max(42, min(132, int(raw.get("size", base["size"]))))
    except Exception:
        pass
    try:
        base["position"] = max(25, min(68, int(raw.get("position", base["position"]))))
    except Exception:
        pass
    try:
        base["outline_size"] = max(0.0, min(5.0, float(raw.get("outlineSize", base["outline_size"]))))
    except Exception:
        pass
    if "box" in raw:
        base["box"] = bool(raw["box"])
    return base


def intro_subtitle_tags(
    x: int,
    y: int,
    duration_ms: int,
    outline_size: float,
    tone: str = "explanatory",
) -> list[str]:
    out_start = max(900, duration_ms - 440)
    tone = str(tone or "explanatory").lower()
    if tone in {"tech", "energetic"}:
        return [
            "\\an5",
            f"\\pos({x},{y})",
            "\\alpha&H40&\\fscx88\\fscy116",
            "\\t(0,140,\\alpha&H00&\\fscx106\\fscy94)",
            "\\t(140,260,\\fscx98\\fscy102)",
            "\\t(260,360,\\fscx100\\fscy100)",
            f"\\t({out_start},{duration_ms},\\alpha&H80&\\blur1.5)",
            "\\fad(120,240)",
        ]
    if tone in {"emotional", "suspense"}:
        return [
            "\\an5",
            f"\\move({x},{y + 10},{x},{y},0,420)",
            "\\alpha&H45&\\blur3.5",
            "\\t(0,340,\\alpha&H00&\\blur0)",
            f"\\t({out_start},{duration_ms},\\alpha&H80&\\blur2.5)",
            "\\fad(240,360)",
        ]
    return [
        "\\an5",
        f"\\pos({x},{y})",
        "\\alpha&H35&\\fscx92\\fscy110\\blur2",
        "\\t(0,180,\\alpha&H00&\\fscx104\\fscy97\\blur0)",
        "\\t(180,320,\\fscx100\\fscy100)",
        f"\\t({out_start},{duration_ms},\\alpha&H75&\\blur2)",
        "\\fad(180,300)",
    ]


def subtitle_animation_tags(
    job_id: str,
    idx: int,
    cue: SubtitleCue,
    animation: str,
    x: int,
    y: int,
    duration_ms: int,
    outline_size: float,
    forced_intro: str | None = None,
    forced_outro: str | None = None,
) -> list[str]:
    intro_map = {
        "fade": ["fade", "blur_rise"],
        "pop": ["spring", "pop_soft"],
        "spring": ["spring", "pop_soft"],
        "kinetic": ["kinetic", "slide_left", "slide_right"],
        "blur_rise": ["blur_rise", "rise"],
        "slide": ["rise", "slide_left", "slide_right"],
        "zoom": ["zoom_in", "zoom_soft"],
        "cinematic": ["blur_rise", "cinema_drop"],
        "pulse": ["pulse_in", "spring"],
        "glitch": ["glitch"],
        "typewriter": ["typewriter"],
        "shake": ["shake"],
        "none": ["none"],
        "random_text": ["spring", "blur_rise", "kinetic", "zoom_in", "slide_left", "slide_right", "cinema_drop", "glitch"],
        "documentary": ["blur_rise", "cinema_drop", "typewriter"],
        "archive": ["typewriter", "slide_left", "blur_rise"],
        "digital": ["glitch", "typewriter", "kinetic"],
        "stamp": ["spring", "shake"],
        "money": ["spring", "kinetic"],
        "warning": ["shake", "spring"],
        "industrial": ["shake", "cinema_drop"],
        "luxury": ["blur_rise", "fade", "cinema_drop"],
        "mixed": ["spring", "blur_rise", "kinetic", "zoom_soft", "slide_left", "slide_right", "cinema_drop"],
    }
    outro_map = {
        "fade": ["fade"],
        "pop": ["shrink", "glow_fade"],
        "spring": ["shrink", "soft_blur"],
        "kinetic": ["quick_dim", "float_fade"],
        "blur_rise": ["soft_blur", "float_fade"],
        "slide": ["float_fade", "shrink"],
        "zoom": ["shrink", "fade"],
        "cinematic": ["soft_blur", "float_fade"],
        "pulse": ["glow_fade", "shrink"],
        "glitch": ["quick_dim"],
        "typewriter": ["fade"],
        "shake": ["shrink"],
        "none": ["none"],
        "random_text": ["fade", "float_fade", "shrink", "soft_blur", "glow_fade", "quick_dim"],
        "documentary": ["soft_blur", "float_fade"],
        "archive": ["float_fade", "quick_dim"],
        "digital": ["quick_dim", "fade"],
        "stamp": ["shrink", "quick_dim"],
        "money": ["glow_fade", "fade"],
        "warning": ["quick_dim", "shrink"],
        "industrial": ["shrink", "quick_dim"],
        "luxury": ["soft_blur", "glow_fade"],
        "mixed": ["fade", "float_fade", "shrink", "soft_blur", "glow_fade", "quick_dim"],
    }
    intros = intro_map.get(animation, intro_map["mixed"])
    outros = outro_map.get(animation, outro_map["mixed"])
    intro = forced_intro or intros[stable_index(f"{job_id}:intro:{idx}:{cue.text}", len(intros))]
    outro = forced_outro or outros[stable_index(f"{job_id}:outro:{idx}:{cue.text}", len(outros))]
    tags = ["\\an2"]
    fade_in = 140
    fade_out = 220

    if intro == "none":
        tags.append(f"\\pos({x},{y})")
    elif intro in {"spring", "pop"}:
        tags.append(f"\\pos({x},{y})")
        # Efeito elastico moderno em 3 estagios (squash & stretch elastico)
        tags.extend([
            "\\fscx90\\fscy114\\alpha&H25&",
            "\\t(0,130,\\fscx108\\fscy94\\alpha&H00&)",
            "\\t(130,240,\\fscx98\\fscy102)",
            "\\t(240,320,\\fscx100\\fscy100)",
        ])
    elif intro == "pop_soft":
        tags.append(f"\\pos({x},{y})")
        tags.extend(["\\fscx94\\fscy94\\alpha&H20&", "\\t(0,220,\\fscx104\\fscy104\\alpha&H00&)", "\\t(220,320,\\fscx100\\fscy100)"])
    elif intro in {"blur_rise", "rise"}:
        # Subida suave com blur optico estilo documentario
        tags.append(f"\\move({x},{y + 12},{x},{y},0,280)")
        tags.extend(["\\blur3.5\\alpha&H35&", "\\t(0,240,\\blur0\\alpha&H00&)"])
    elif intro == "kinetic":
        tags.append(f"\\move({x - 35},{y},{x},{y},0,160)")
        tags.extend(["\\alpha&H40&", "\\t(0,120,\\alpha&H00&)"])
    elif intro == "slide_left":
        tags.append(f"\\move({x - 45},{y},{x},{y},0,240)")
        tags.extend(["\\alpha&H30&", "\\t(0,180,\\alpha&H00&)"])
    elif intro == "slide_right":
        tags.append(f"\\move({x + 45},{y},{x},{y},0,240)")
        tags.extend(["\\alpha&H30&", "\\t(0,180,\\alpha&H00&)"])
    elif intro == "zoom_in":
        tags.append(f"\\pos({x},{y})")
        tags.extend(["\\fscx108\\fscy108\\blur2\\alpha&H35&", "\\t(0,280,\\fscx100\\fscy100\\blur0\\alpha&H00&)"])
    elif intro == "zoom_soft":
        tags.append(f"\\pos({x},{y})")
        tags.extend(["\\fscx104\\fscy104\\alpha&H20&", "\\t(0,260,\\fscx100\\fscy100\\alpha&H00&)"])
    elif intro == "cinema_drop":
        tags.append(f"\\move({x},{y - 12},{x},{y},0,280)")
        tags.extend(["\\blur2.5\\alpha&H30&", "\\t(0,240,\\blur0\\alpha&H00&)"])
    elif intro == "pulse_in":
        tags.append(f"\\pos({x},{y})")
        tags.extend([f"\\bord{outline_size + 0.8:.1f}", f"\\t(0,240,\\bord{outline_size:.1f})"])
    elif intro == "glitch":
        tags.append(f"\\pos({x},{y})")
        tags.extend(["\\alpha&H45&", "\\t(0,60,\\alpha&H00&)", "\\t(60,120,\\fscx104\\fscy96)", "\\t(120,180,\\fscx98\\fscy102)", "\\t(180,260,\\fscx100\\fscy100)"])
    elif intro == "typewriter":
        tags.append(f"\\pos({x},{y})")
        tags.extend(["\\alpha&H25&", "\\t(0,240,\\alpha&H00&)"])
    elif intro == "shake":
        tags.append(f"\\pos({x},{y})")
        tags.extend(["\\fscx103\\fscy103", "\\t(0,60,\\fscx97\\fscy103)", "\\t(60,120,\\fscx103\\fscy97)", "\\t(120,220,\\fscx100\\fscy100)"])
    else:
        tags.append(f"\\pos({x},{y})")

    if intro != "none" and outro != "none":
        tags.append(f"\\fad({fade_in},{fade_out})")

    out_start = max(0, duration_ms - 420)
    if outro == "float_fade":
        tags.append(f"\\t({out_start},{duration_ms},\\alpha&H85&)")
    elif outro == "shrink":
        tags.append(f"\\t({out_start},{duration_ms},\\fscx95\\fscy95\\alpha&H70&)")
    elif outro == "soft_blur":
        tags.append(f"\\t({out_start},{duration_ms},\\blur2.5\\alpha&H80&)")
    elif outro == "glow_fade":
        tags.append(f"\\t({out_start},{duration_ms},\\bord{outline_size + 1.2:.1f}\\alpha&H70&)")
    elif outro == "quick_dim":
        tags.append(f"\\t({max(0, duration_ms - 220)},{duration_ms},\\alpha&H75&)")
    return tags


def subtitle_visual_slot(
    job: Job,
    idx: int,
    cue: SubtitleCue,
    w: int,
    h: int,
    default_x: int,
    default_y: int,
    forced_slot: str | None = None,
) -> tuple[int, int, int, str]:
    y_low = max(48, min(h - 44, default_y))
    return default_x, y_low, 2, "lower_center"


def subtitle_accent_dialogue(
    cue: SubtitleCue,
    role: str,
    render_start: float,
    cue_x: int,
    cue_y: int,
    w: int,
    h: int,
) -> str:
    return ""


def caption_style_from_options(options: dict[str, Any]) -> dict[str, Any]:
    style = dict(options.get("captionStyle") or {})
    presets = {
        "clean_two_lines": {"font": "Arial", "size": 38, "primary": "#FFFFFF", "outline": "#111111", "outline_size": 2.0, "box": False},
        "soft_box": {"font": "Segoe UI Semibold", "size": 36, "primary": "#FFFFFF", "outline": "#000000", "outline_size": 1.0, "box": True},
        "documentary": {"font": "Georgia", "size": 36, "primary": "#F7F1E8", "outline": "#111111", "outline_size": 1.8, "box": False},
    }
    merged = {**presets.get(str(style.get("preset") or "clean_two_lines"), presets["clean_two_lines"]), **style}
    merged["position"] = clamp_float(merged.get("position"), 10.0, 5.0, 40.0)
    merged["size"] = clamp_int(merged.get("size"), 38, 24, 72)
    merged["alignment"] = str(merged.get("alignment") or "center")
    if merged["alignment"] not in {"left", "center", "right"}:
        merged["alignment"] = "center"
    return merged


def wrap_caption_text(text: str, max_chars: int = 44) -> str:
    words = re.sub(r"\s+", " ", str(text or "")).strip().split()
    if not words:
        return ""
    lines = ["", ""]
    line = 0
    for word in words:
        candidate = f"{lines[line]} {word}".strip()
        if lines[line] and len(candidate) > max_chars and line == 0:
            line = 1
            candidate = word
        lines[line] = candidate
    return "\\N".join(item for item in lines if item)


def split_caption_cues(cues: list[SubtitleCue], max_chars: int = 44) -> list[SubtitleCue]:
    """Split long captions into timed two-line blocks without dropping words."""
    result: list[SubtitleCue] = []
    for cue in cues:
        words = re.sub(r"\s+", " ", str(cue.text or "")).strip().split()
        if not words:
            continue
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if current and len(candidate) > max_chars:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        blocks = ["\\N".join(lines[index:index + 2]) for index in range(0, len(lines), 2)]
        if len(blocks) == 1:
            result.append(SubtitleCue(cue.start, cue.end, blocks[0]))
            continue
        duration = max(0.01, cue.end - cue.start)
        weights = [max(1, len(block.replace("\\N", " ").split())) for block in blocks]
        total_weight = max(1, sum(weights))
        cursor = cue.start
        for index, (block, weight) in enumerate(zip(blocks, weights)):
            end = cue.end if index == len(blocks) - 1 else cursor + duration * (weight / total_weight)
            result.append(SubtitleCue(cursor, min(cue.end, end), block))
            cursor = end
    return result


def build_ass_file(
    job: Job,
    srt_path: Path,
    total_duration: float,
    w: int,
    h: int,
    work: Path,
    caption_path: Path | None = None,
) -> Path | None:
    original_cues = parse_srt_file(srt_path)
    min_duration = float(job.options.get("subtitleMinDuration") or MIN_SUBTITLE_SECONDS)
    cinematic = intro_mode(job.options) == "cinematic"
    offset = intro_duration(job.options) if cinematic else 0.0
    narration_duration = max(0.1, total_duration - offset) if cinematic else total_duration
    smart_sample_windows = list(job.options.get("_smart_sample_windows") or [])
    if smart_sample_windows:
        original_cues = remap_cues_for_smart_sample(original_cues, smart_sample_windows)
        job.subtitle_summary["smart_sample_blocks"] = smart_sample_windows
    cues, summary = normalize_subtitles(original_cues, narration_duration, min_duration=min_duration)
    if smart_sample_windows:
        summary["smart_sample_blocks"] = smart_sample_windows
        summary["smart_sample_mode"] = "blocos_narrativos"
    caption_original = parse_srt_file(caption_path) if caption_path and caption_path.exists() else []
    caption_cues, caption_summary = normalize_subtitles(caption_original, narration_duration, min_duration=0.45)
    caption_cues = split_caption_cues(caption_cues)
    if cinematic:
        caption_cues = [SubtitleCue(cue.start + offset, min(total_duration, cue.end + offset), cue.text) for cue in caption_cues]
    job.options["_captions_active"] = bool(caption_cues)
    timing_adjustments = list(job.options.get("_timing_adjustments") or [])
    if timing_adjustments:
        cues = apply_timing_adjustments(cues, timing_adjustments)
        summary["dynamic_pause_shift_seconds"] = round(sum(float(item.get("duration") or 0.0) for item in timing_adjustments), 3)
    if cinematic:
        cues = [SubtitleCue(cue.start + offset, min(total_duration, cue.end + offset), cue.text) for cue in cues]
        summary["cinematic_offset"] = round(offset, 3)
    job.subtitle_cues = cues
    job.subtitle_summary = summary
    if not cues:
        _append_log(job, f"Textos ignorados: nenhum cue valido apos limpeza. Resumo={summary}")
        return None
    style = subtitle_style_from_options(job.options)
    caption_style = caption_style_from_options(job.options)
    summary["preset"] = style.get("preset")
    summary["animation"] = style.get("animation")
    margin_v = max(18, int(h * (style.get("position", 16) / 100)))
    font_size = int(style["size"] * (h / 720))
    font_size = max(28, min(150, font_size))
    border_style = 3 if style.get("box") else 1
    outline = float(style.get("outline_size", 2 if not style.get("box") else 1))
    shadow = float(style.get("shadow", 1 if not style.get("box") else 0))
    primary = ass_color(style.get("primary"), "#FFFFFF")
    secondary = ass_color(style.get("primary"), "#FFFFFF")
    outline_color = ass_color(style.get("outline"), "#111111")
    back_color = ass_color(style.get("back"), "#000000", alpha=("70" if style.get("box") else "AA"))
    bold = -1 if style.get("bold") else 0
    italic = -1 if style.get("italic") else 0
    spacing = float(style.get("spacing", 0))
    x = w // 2
    y = h - margin_v
    intro_style = intro_subtitle_style_from_options(job.options) if cinematic else None
    intro_font_size = int((intro_style or {}).get("size", 76) * (h / 720)) if intro_style else font_size
    intro_font_size = max(40, min(170, intro_font_size))
    intro_y = int(h * ((intro_style or {}).get("position", 44) / 100)) if intro_style else h // 2
    intro_outline = float((intro_style or {}).get("outline_size", 2.2)) if intro_style else outline
    intro_back = ass_color("#000000", "#000000", alpha=("68" if intro_style and intro_style.get("box") else "AA"))
    intro_border_style = 3 if intro_style and intro_style.get("box") else 1
    intro_bold = -1 if intro_style and intro_style.get("bold") else 0
    caption_font_size = max(22, min(96, int(caption_style["size"] * (h / 720))))
    caption_margin = max(18, int(h * (float(caption_style["position"]) / 100.0)))
    caption_alignment = {"left": 1, "center": 2, "right": 3}[caption_style["alignment"]]
    caption_back = ass_color("#000000", "#000000", alpha=("78" if caption_style.get("box") else "AA"))
    caption_border = 3 if caption_style.get("box") else 1

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style['font']},{font_size},{primary},{secondary},{outline_color},{back_color},{bold},{italic},0,0,100,100,{spacing},0,{border_style},{outline:.1f},{shadow:.1f},2,70,70,{margin_v},1
{f"Style: Intro,{intro_style['font']},{intro_font_size},{ass_color(intro_style.get('primary'), '#FFD36A')},{ass_color(intro_style.get('primary'), '#FFD36A')},{ass_color(intro_style.get('outline'), '#090909')},{intro_back},{intro_bold},0,0,0,100,100,0,0,{intro_border_style},{intro_outline:.1f},{float(intro_style.get('shadow', 1.0)):.1f},5,80,80,0,1" if intro_style else ""}
Style: Accent,Arial,20,&H0067E6C2&,&H0067E6C2&,&H00000000&,&H00000000&,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Caption,{caption_style['font']},{caption_font_size},{ass_color(caption_style.get('primary'), '#FFFFFF')},{ass_color(caption_style.get('primary'), '#FFFFFF')},{ass_color(caption_style.get('outline'), '#111111')},{caption_back},0,0,0,0,100,100,0,0,{caption_border},{float(caption_style.get('outline_size', 2.0)):.1f},0,{caption_alignment},70,70,{caption_margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    opening_policy = str(job.options.get("cinematicOpeningPolicy") or "auto_contextual")
    first_role = subtitle_phrase_role(cues[0]) if cues else "standard"
    use_intro_text = bool(
        cinematic and intro_style and cues and opening_policy == "auto_contextual"
        and max(0.0, cues[0].start - offset) <= 1.2 and first_role in {"impact", "question", "data"}
    )
    if use_intro_text:
        intro_text = ass_escape(cues[0].text)
        intro_start = 0.55
        intro_end = min(max(2.55, offset - 0.08), total_duration)
        intro_ms = max(1, int((intro_end - intro_start) * 1000))
        intro_tone = str((job.emotion_summary or {}).get("tone") or job.options.get("projectTone") or "explanatory")
        tags = intro_subtitle_tags(w // 2, intro_y, intro_ms, intro_outline, intro_tone)
        lines.append(
            f"Dialogue: 1,{seconds_to_ass_time(intro_start)},{seconds_to_ass_time(intro_end)},Intro,,0,0,0,,{{{''.join(tags)}}}{intro_text}\n"
        )
        summary["intro_text"] = cues[0].text[:120]
        summary["intro_style"] = intro_style.get("preset")
        summary["intro_consumed_first_text"] = True
    elif cinematic:
        summary["intro_mode_effective"] = "fade_only"
    timing_items: list[dict[str, Any]] = []
    turbo_lead = (1.0 / 30.0) if turbo_enabled(job) else 0.0
    editorial_plan, editorial_summary = subtitle_editorial_sequence(
        job,
        cues,
        str(style.get("animation") or "mixed"),
    )
    layout_context = build_subtitle_layout_context(job)
    summary["editorial_grammar"] = editorial_summary
    summary["smart_layout"] = {
        "enabled": bool(layout_context.get("enabled")),
        "policy": layout_context.get("policy"),
        "repositioned": 0,
        "slot_reasons": {},
    }
    for idx, cue in enumerate(cues):
        if use_intro_text and idx == 0:
            continue
        render_start = max(0.0, cue.start - turbo_lead)
        duration_ms = max(1, int((cue.end - render_start) * 1000))
        subtitle_seed = str(
            job.options.get("queueProjectId")
            or job.options.get("projectName")
            or job.options.get("outputName")
            or job.id
        )
        cue_plan = editorial_plan[idx]
        requested_slot = str(cue_plan.get("slot") or "lower_center")
        safe_slot, safe_reason = subtitle_safe_slot_for_cue(job, cue, idx, requested_slot, layout_context)
        if safe_slot != requested_slot:
            summary["smart_layout"]["repositioned"] += 1
        summary["smart_layout"]["slot_reasons"][safe_slot] = int(summary["smart_layout"]["slot_reasons"].get(safe_slot, 0)) + 1
        cue_x, cue_y, cue_alignment, cue_slot = subtitle_visual_slot(
            job,
            idx,
            cue,
            w,
            h,
            x,
            y,
            forced_slot=safe_slot,
        )
        cue_plan["slot"] = safe_slot
        cue_plan["slot_reason"] = safe_reason
        tags = subtitle_animation_tags(
            subtitle_seed,
            idx,
            cue,
            str(style.get("animation") or "mixed"),
            cue_x,
            cue_y,
            duration_ms,
            outline,
            forced_intro=str(cue_plan.get("intro") or "fade"),
            forced_outro=str(cue_plan.get("outro") or "fade"),
        )
        if cue_alignment != 2:
            tags[0] = f"\\an{cue_alignment}"
        summary.setdefault("layout_slots", {})
        summary["layout_slots"][cue_slot] = int(summary["layout_slots"].get(cue_slot, 0)) + 1
        text = ass_escape(cue.text)
        ass_start = round(render_start + 1e-9, 2)
        first_frame = max(0.0, int((ass_start * 30.0) + 0.999999) / 30.0)
        deviation_ms = (first_frame - cue.start) * 1000.0
        if len(timing_items) < 24:
            timing_items.append({
                "cue": idx + 1,
                "target_time": round(cue.start, 4),
                "ass_start": round(ass_start, 4),
                "first_visible_frame": round(first_frame, 4),
                "deviation_ms": round(deviation_ms, 2),
                "within_one_frame": abs(deviation_ms) <= 33.5,
                "slot": cue_slot,
                "slot_reason": safe_reason,
            })
        if bool(cue_plan.get("accent")):
            accent_line = subtitle_accent_dialogue(
                cue,
                str(cue_plan.get("role") or "standard"),
                render_start,
                cue_x,
                cue_y,
                w,
                h,
            )
            if accent_line:
                lines.append(accent_line)
        lines.append(
            f"Dialogue: 2,{seconds_to_ass_time(render_start)},{seconds_to_ass_time(cue.end)},Default,,0,0,0,,{{{''.join(tags)}}}{text}\n"
        )

    for cue in caption_cues:
        wrapped = ass_escape(cue.text if "\\N" in cue.text else wrap_caption_text(cue.text))
        wrapped = wrapped.replace("\\\\N", "\\N")
        lines.append(
            f"Dialogue: 3,{seconds_to_ass_time(cue.start)},{seconds_to_ass_time(cue.end)},Caption,,0,0,0,,"
            f"{{\\fad(90,120)}}{wrapped}\n"
        )

    out = work / "combined_layers.ass"
    out.write_text("".join(lines), encoding="utf-8")
    max_abs_deviation = max((abs(float(item["deviation_ms"])) for item in timing_items), default=0.0)
    job.subtitle_timing_summary = {
        "clock": "timeline_zero_cfr_30",
        "fps": 30,
        "turbo_compensation_ms": round(turbo_lead * 1000.0, 2),
        "checked_cues": len(timing_items),
        "max_abs_deviation_ms": round(max_abs_deviation, 2),
        "within_one_frame": max_abs_deviation <= 33.5,
        "items": timing_items,
    }
    job.caption_summary = {
        **caption_summary,
        "enabled": bool(caption_cues),
        "preset": caption_style.get("preset"),
        "alignment": caption_style.get("alignment"),
        "position": caption_style.get("position"),
        "max_lines": 2,
        "sound_fx": False,
    }
    job.layer_collision_summary = {
        "captions_reserved_zone": bool(caption_cues),
        "caption_position": caption_style.get("position"),
        "texts_repositioned": int(summary.get("smart_layout", {}).get("repositioned") or 0),
        "policy": "legendas_priorizam_leitura; textos_e_cta_usam_zonas_livres",
    }
    _append_log(job, f"Camadas ASS: {summary['valid']} texto(s) editorial(is) e {len(caption_cues)} legenda(s), em uma unica composicao.")
    return out


def cta_source_path(key: str) -> Path:
    info = CTA_LANGUAGES[key]
    return CTA_SOURCE_DIR / str(info["source"])


def cta_default_duration(key: str) -> float:
    return 8.5


def cta_public_info(key: str) -> dict[str, Any]:
    info = CTA_LANGUAGES[key]
    source = cta_source_path(key)
    exists = source.exists()
    duration = safe_probe_duration(source) if exists else cta_default_duration(key)
    return {
        "key": key,
        "label": info["label"],
        "available": bool(exists),
        "has_audio": probe_has_audio(source) if exists else False,
        "duration": round(duration, 3),
        "status": "pronto" if exists else "indisponivel",
        "preview": f"/api/cta-preview/{key}",
        "text": info.get("text") or "",
    }


@app.get("/api/cta-assets")
def cta_assets():
    return {"required": CTA_REQUIRED, "occurrences": CTA_OCCURRENCES, "items": [cta_public_info(key) for key in CTA_LANGUAGES]}


def cta_cache_path(key: str, suffix: str, source: Path | None = None) -> Path:
    info = CTA_LANGUAGES[key]
    seed = f"{APP_VERSION}:{key}:{info.get('kind')}:{info.get('text')}"
    if source and source.exists():
        stat = source.stat()
        seed += f":{stat.st_size}:{stat.st_mtime_ns}"
    digest = hashlib.sha256(seed.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return CTA_CACHE_ROOT / f"cta_{key}_{digest}{suffix}"


def cta_preview_path(key: str, source: Path | None = None) -> Path:
    info = CTA_LANGUAGES[key]
    seed = f"preview:{APP_VERSION}:{key}:{info.get('kind')}:{info.get('text')}"
    if source and source.exists():
        stat = source.stat()
        seed += f":{stat.st_size}:{stat.st_mtime_ns}"
    digest = hashlib.sha256(seed.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return CTA_CACHE_ROOT / f"cta_preview_{key}_{digest}.webm"


def sfx_preview_cache_path(effect: str, spec: dict[str, Any]) -> Path:
    digest = hashlib.sha256(f"{APP_VERSION}:{effect}:{spec}".encode("utf-8", errors="ignore")).hexdigest()[:10]
    return CTA_CACHE_ROOT / f"sfx_preview_{effect}_{digest}.wav"


def prune_generated_media_cache() -> dict[str, Any]:
    if any(job.status in {"uploading", "ready", "running"} for job in JOBS.values()):
        return {"skipped": True, "reason": "render ativo", "removed": 0, "freed_bytes": 0}
    if not CACHE_MAINTENANCE_LOCK.acquire(blocking=False):
        return {"skipped": True, "reason": "limpeza em andamento", "removed": 0, "freed_bytes": 0}
    try:
        expected: set[Path] = set()
        for key in CTA_LANGUAGES:
            source = cta_source_path(key)
            source_ref = source if source.exists() else None
            expected.add(cta_cache_path(key, ".mov", source_ref).resolve())
            expected.add(cta_preview_path(key, source_ref).resolve())
        for effect, spec in (globals().get("SFX_PREVIEW_EFFECTS") or {}).items():
            expected.add(sfx_preview_cache_path(str(effect), spec).resolve())

        removed = 0
        freed_bytes = 0
        for path in CTA_CACHE_ROOT.iterdir():
            if not path.is_file():
                continue
            if not (path.name.startswith("cta_") or path.name.startswith("sfx_preview_")):
                continue
            try:
                resolved = path.resolve()
                if resolved in expected and path.stat().st_size > 0:
                    continue
                size = path.stat().st_size
                path.unlink(missing_ok=True)
                removed += 1
                freed_bytes += size
            except Exception:
                continue
        return {
            "skipped": False,
            "removed": removed,
            "freed_bytes": freed_bytes,
            "freed_mb": round(freed_bytes / (1024 * 1024), 2),
            "kept": len(expected),
        }
    finally:
        CACHE_MAINTENANCE_LOCK.release()


def run_hidden_checked(cmd: list[str], cwd: Path | None = None):
    if not FFMPEG:
        raise RuntimeError("FFmpeg nao encontrado.")
    p = _run_hidden(cmd, cwd=cwd, priority="balanced", capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "FFmpeg falhou")[-1200:])
    return p


def cta_chroma_filter(key: str, width: int, height: int, alpha_format: str) -> str:
    info = CTA_LANGUAGES.get(key, {})
    cleanup = ""
    remove_top = float(info.get("remove_top_text") or 0.0)
    if remove_top > 0:
        # The German source contains a white promotional line above the actual CTA.
        # Paint that band key-green before keying so only the CTA card remains.
        cleanup = f"drawbox=x=0:y=0:w=iw:h=ih*{min(remove_top, 0.6):.3f}:color=0x00ff00@1:t=fill,"
    return (
        f"fps=30,scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x00ff00,"
        f"{cleanup}"
        "format=rgba,colorkey=0x00ff00:0.30:0.08,despill=type=green,"
        f"format={alpha_format}"
    )


def prepare_cta_preview_asset(key: str) -> Path:
    if key not in CTA_LANGUAGES:
        raise RuntimeError("CTA invalido.")
    source = cta_source_path(key)
    out = cta_preview_path(key, source if source.exists() else None)
    if out.exists() and out.stat().st_size > 4096:
        return out
    out.unlink(missing_ok=True)
    if not source.exists():
        raise RuntimeError("CTA indisponivel.")
    has_audio = probe_has_audio(source)
    vf = cta_chroma_filter(key, 640, 360, "yuva420p")
    cmd = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-filter_threads", "1",
        "-i", str(source),
        "-vf", vf,
        "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0",
        "-deadline", "realtime", "-cpu-used", "8", "-row-mt", "1", "-b:v", "850k",
    ]
    if has_audio:
        cmd += ["-c:a", "libopus", "-b:a", "96k", "-shortest"]
    else:
        cmd += ["-an"]
    cmd.append(str(out))
    run_hidden_checked(cmd)
    return out


@app.get("/api/cta-preview/{key}")
def cta_preview(key: str):
    key = key.strip().lower()
    try:
        preview = prepare_cta_preview_asset(key)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Preview CTA indisponivel: {exc}")
    return FileResponse(preview, media_type="video/webm")


def warm_cache_worker():
    CACHE_WARM_STATUS.update({"running": True, "items": 0, "errors": [], "cleanup": {}})
    errors: list[str] = []
    items = 0
    cleanup = prune_generated_media_cache()
    for key in CTA_LANGUAGES:
        try:
            prepare_cta_preview_asset(key)
            items += 1
        except Exception as exc:
            errors.append(f"cta:{key}: {exc}")
    CACHE_WARM_STATUS.update({
        "running": False,
        "items": items,
        "errors": errors[:8],
        "cleanup": cleanup,
        "finished_at": time.time(),
    })


@app.post("/api/warm-cache")
def warm_cache():
    with CACHE_WARM_LOCK:
        if CACHE_WARM_STATUS.get("running"):
            return {"ok": True, "already_running": True, **CACHE_WARM_STATUS}
        CACHE_WARM_STATUS.update({"running": True, "items": 0, "errors": [], "cleanup": {}})
        threading.Thread(target=warm_cache_worker, daemon=True).start()
        return {"ok": True, "started": True}


@app.get("/api/warm-cache")
def warm_cache_status():
    return {"ok": True, **CACHE_WARM_STATUS}


def prepare_cta_asset(job: Job, key: str) -> dict[str, Any]:
    if key not in CTA_LANGUAGES:
        raise RuntimeError("CTA invalido. Escolha um idioma de CTA antes de renderizar.")
    info = CTA_LANGUAGES[key]
    source = cta_source_path(key)
    if not source.exists():
        raise RuntimeError(f"CTA {info['label']} indisponivel. O arquivo base nao foi encontrado em assets/cta/source.")

    out = cta_cache_path(key, ".mov", source)
    if not out.exists():
        set_stage(job, "cta", "Preparando CTA", f"Removendo fundo verde do CTA {info['label']}")
        vf = cta_chroma_filter(key, 1280, 720, "argb")
        cmd = [
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-filter_threads", "1",
            "-i", str(source),
            "-vf", vf,
            "-an", "-c:v", "qtrle", "-pix_fmt", "argb",
            str(out),
        ]
        run_cmd(job, cmd, cwd=None, quiet_success=True)
    duration = safe_probe_duration(out) or safe_probe_duration(source) or cta_default_duration(key)
    return {
        "key": key,
        "label": info["label"],
        "video": out,
        "audio_source": source if probe_has_audio(source) else None,
        "duration": duration,
        "has_audio": probe_has_audio(source),
    }


def choose_cta_times(job: Job, audio_total: float, cta_duration: float) -> list[float]:
    duration = max(0.5, min(float(cta_duration or 0.5), max(0.5, audio_total)))
    if audio_total < duration + 0.8:
        raise RuntimeError("Video curto demais para inserir CTA sem sobreposicao.")
    requested_max = clamp_int(job.options.get("ctaMaxOccurrences"), CTA_OCCURRENCES, 1, 2)
    target_count = requested_max if audio_total >= 95.0 else 1
    if audio_total >= 210.0:
        target_count = requested_max
    min_start = 4.0 if audio_total < 60.0 else max(8.0, min(22.0, audio_total * 0.10))
    max_start = max(min_start + 0.1, audio_total - duration - (2.0 if audio_total < 60.0 else 6.0))
    strong_times = [
        float(item.get("time") or 0.0)
        for item in (job.strong_moments_summary or {}).get("moments", [])
        if isinstance(item, dict)
    ]
    candidates: list[dict[str, Any]] = []

    def add_candidate(start: float, score: float, reason: str, position_hint: str = "") -> None:
        start = max(min_start, min(max_start, float(start)))
        if start + duration > audio_total:
            start = max(min_start, audio_total - duration - 0.3)
        if any(abs(start - value) < 3.2 for value in strong_times):
            score -= 0.9
            reason += "; afastado de momento forte"
        if start < audio_total * 0.18:
            score -= 0.45
        if start > audio_total * 0.92:
            score -= 0.25
        candidates.append({
            "start": round(start, 3),
            "score": round(score, 3),
            "reason": reason,
            "position_hint": position_hint,
        })

    blocks = _director_blocks(job)
    for block in blocks:
        role = str(block.get("role") or "")
        start = float(block.get("start") or 0.0)
        end = float(block.get("end") or start)
        length = max(0.1, end - start)
        if role == "cta":
            add_candidate(max(start + 0.2, end - duration - 0.2), 4.0, "bloco narrativo CTA", "top_right")
        elif role == "conclusion":
            add_candidate(max(start + length * 0.22, end - duration - 0.4), 3.4, "conclusao com respiro", "bottom_right")
        elif role == "reveal" and audio_total >= 130.0:
            add_candidate(min(end + 0.6, start + length * 0.72), 2.45, "apos revelacao", "top_right")

    script_plan = job.options.get("scriptGuidePlan") if isinstance(job.options.get("scriptGuidePlan"), dict) else {}
    cta_target_time = script_plan.get("cta_target_time")
    if cta_target_time is not None and float(cta_target_time) > 0:
        add_candidate(float(cta_target_time), 5.5, "ponto exato do CTA definido no roteiro", "top_right")
    cues = list(job.subtitle_cues or [])
    for idx, cue in enumerate(cues[:-1]):
        next_cue = cues[idx + 1]
        gap = max(0.0, float(next_cue.start) - float(cue.end))
        if gap < 0.45:
            continue
        position = float(cue.end) / max(audio_total, 0.1)
        if 0.22 <= position <= 0.90:
            add_candidate(
                float(cue.end) + min(0.25, gap * 0.35),
                2.0 + min(1.2, gap * 0.65),
                f"pausa natural no SRT ({gap:.2f}s)",
                "top_right" if position < 0.62 else "bottom_right",
            )
    add_candidate(audio_total * (0.62 if target_count == 1 else 0.52), 1.45, "fallback editorial no meio-final", "top_right")
    if target_count >= 2:
        add_candidate(audio_total * 0.84, 1.75, "fallback editorial perto do encerramento", "bottom_right")

    candidates.sort(key=lambda item: (float(item.get("score") or 0.0), -abs(float(item.get("start") or 0.0) - audio_total * 0.72)), reverse=True)
    chosen: list[dict[str, Any]] = []
    min_gap = max(duration + 12.0, 20.0 if target_count >= 2 else duration + 2.0)
    for candidate in candidates:
        start = float(candidate.get("start") or 0.0)
        if any(abs(start - float(item.get("start") or 0.0)) < min_gap for item in chosen):
            continue
        chosen.append(candidate)
        if len(chosen) >= target_count:
            break
    if not chosen:
        chosen = [{
            "start": round(max(min_start, min(max_start, audio_total * 0.72)), 3),
            "score": 1.0,
            "reason": "fallback unico seguro",
            "position_hint": "top_right",
        }]
    chosen.sort(key=lambda item: float(item.get("start") or 0.0))
    preferred_position = next((str(item.get("position_hint") or "") for item in chosen if item.get("position_hint")), "")
    if preferred_position:
        job.cta_summary["smart_position_preset"] = preferred_position
    job.cta_summary.update({
        "timing_policy": "director_contextual_max_2",
        "max_occurrences": 2,
        "requested_occurrences": requested_max,
        "target_occurrences": target_count,
        "candidate_count": len(candidates),
        "selection_reason": "CTA posicionada por blocos narrativos, pausas de SRT e distancia de momentos fortes.",
        "selected_windows": chosen,
        "avoids_strong_moments": True,
    })
    return [round(float(item.get("start") or 0.0), 3) for item in chosen[:2]]


def cta_scale_width(job: Job, frame_w: int) -> int:
    ratio = str(job.options.get("ratio") or "16:9")
    scale = 0.68 if ratio == "9:16" else 0.42
    return max(180, int(round(frame_w * scale)))


def cta_position_expr(job: Job) -> tuple[str, str, str]:
    preset = str(
        (job.cta_summary or {}).get("smart_position_preset")
        or (job.cta_summary or {}).get("position_preset")
        or job.options.get("ctaPositionPreset")
        or "top_right"
    )
    if preset not in CTA_POSITION_PRESETS:
        preset = "top_right"
    offset_x = clamp_float(job.options.get("ctaOffsetX"), 0.0, -35.0, 35.0)
    offset_y = clamp_float(job.options.get("ctaOffsetY"), 0.0, -35.0, 35.0)
    base = CTA_POSITION_PRESETS[preset]
    x = f"{base['x']}+W*{offset_x / 100:.5f}"
    y = f"{base['y']}+H*{offset_y / 100:.5f}"
    return preset, x, y


def overlay_cta_on_video(job: Job, video_source: Path, cta: dict[str, Any], times: list[float], work: Path) -> Path:
    set_stage(job, "cta", "Aplicando CTA", "Sobrepondo CTA de inscricao")
    w, _ = render_size(job.options.get("mode", "standard"), job.options.get("ratio", "16:9"))
    target_w = cta_scale_width(job, w)
    preset, x_expr, y_expr = cta_position_expr(job)
    out = work / "video_cta.mp4"
    filter_args = ["-threads", "4", "-filter_threads", "2", "-filter_complex_threads", "2"]
    cmd: list[str] = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        *filter_args,
        "-reinit_filter", "0",
        "-i", str(video_source),
    ]
    is_still = Path(str(cta["video"])).suffix.lower() in {".png", ".webp", ".jpg", ".jpeg"}
    for _ in times:
        if is_still:
            cmd += ["-loop", "1", "-i", str(cta["video"])]
        else:
            cmd += ["-i", str(cta["video"])]
    chains: list[str] = []
    current = "[0:v]"
    for idx, start in enumerate(times):
        input_idx = idx + 1
        cta_duration = max(
            0.5,
            float(cta.get("duration") or cta_default_duration(str(cta.get("key") or "pt"))),
        )
        end = start + cta_duration
        if is_still:
            chains.append(
                f"[{input_idx}:v]settb=AVTB,format=rgba,scale={target_w}:-1,"
                f"trim=duration={cta_duration:.4f},setpts=PTS-STARTPTS+{start:.4f}/TB[cta{idx}]"
            )
        else:
            chains.append(
                f"[{input_idx}:v]fps=30,settb=AVTB,format=rgba,scale={target_w}:-1,"
                f"trim=duration={cta_duration:.4f},setpts=PTS-STARTPTS+{start:.4f}/TB[cta{idx}]"
            )
        out_label = f"[vcta{idx}]"
        chains.append(
            f"{current}[cta{idx}]overlay=x='{x_expr}':y='{y_expr}':"
            f"enable='between(t,{start:.4f},{end:.4f})':"
            f"eof_action=pass:repeatlast=0:shortest=0{out_label}"
        )
        current = out_label
    encoder_args = choose_video_args(job.options.get("mode", "standard"), job.options.get("codec", "hevc"), bool(job.options.get("gpu", False)), job)
    cmd += [
        "-filter_complex", ";".join(chains),
        "-map", current,
        "-an",
        *encoder_args,
        "-pix_fmt", "yuv420p",
        str(out),
    ]
    run_cmd(job, cmd, cwd=work, quiet_success=True)
    job.cta_summary.update({
        "position_preset": preset,
        "offset_x": clamp_float(job.options.get("ctaOffsetX"), 0.0, -35.0, 35.0),
        "offset_y": clamp_float(job.options.get("ctaOffsetY"), 0.0, -35.0, 35.0),
        "scale_width_px": target_w,
    })
    return out


def compose_final_visuals(
    job: Job,
    video_source: Path,
    cta: dict[str, Any],
    times: list[float],
    subtitle_ass: Path | None,
    work: Path,
    target_duration: float,
) -> Path:
    label = "Composicao Turbo" if turbo_enabled(job) else "Composicao final otimizada"
    set_stage(job, "cta", label, "Aplicando CTA, Textos e Legendas em uma unica passagem")
    target_duration = max(0.1, float(target_duration or 0.1))
    w, _ = render_size(job.options.get("mode", "standard"), job.options.get("ratio", "16:9"))
    target_w = cta_scale_width(job, w)
    preset, x_expr, y_expr = cta_position_expr(job)
    out = work / ("video_turbo_composed.mp4" if turbo_enabled(job) else "video_final_composed.mp4")
    logical_cpus = max(2, int(os.cpu_count() or 4))
    comp_threads = max(4, min(16, int(logical_cpus * 0.85)))
    comp_filter_threads = max(2, min(8, logical_cpus // 2))
    filter_args = [
        "-threads", str(comp_threads),
        "-filter_threads", str(comp_filter_threads),
        "-filter_complex_threads", str(comp_filter_threads),
    ]
    cmd: list[str] = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        *filter_args,
        "-fflags", "+genpts",
        "-reinit_filter", "0",
        "-t", f"{target_duration:.4f}",
        "-i", str(video_source),
    ]
    is_still = Path(str(cta["video"])).suffix.lower() in {".png", ".webp", ".jpg", ".jpeg"}
    for _ in times:
        if is_still:
            cmd += ["-loop", "1", "-i", str(cta["video"])]
        else:
            cmd += ["-i", str(cta["video"])]

    # Complete a short concat inside the composition pass itself. Previously a
    # second full-video encode was triggered after CTA/SRT for a gap of only a
    # few seconds.
    base_filters = (
        "fps=30,settb=AVTB,setpts=PTS-STARTPTS,"
        f"tpad=stop_mode=clone:stop_duration={target_duration:.4f}"
    )
    if not turbo_enabled(job) and bool(job.options.get("qualityBoost", True)):
        job.timeline_summary["quality_boost_stage"] = "parallel_segment_pass"
    chains: list[str] = [
        f"[0:v]{base_filters},"
        f"trim=duration={target_duration:.4f},setpts=PTS-STARTPTS[vbase]"
    ]
    current = "[vbase]"
    for idx, start in enumerate(times):
        input_idx = idx + 1
        cta_duration = max(
            0.5,
            float(cta.get("duration") or cta_default_duration(str(cta.get("key") or "pt"))),
        )
        end = min(target_duration, start + cta_duration)
        if is_still:
            chains.append(
                f"[{input_idx}:v]settb=AVTB,format=rgba,scale={target_w}:-1,"
                f"trim=duration={cta_duration:.4f},setpts=PTS-STARTPTS+{start:.4f}/TB[cta{idx}]"
            )
        else:
            chains.append(
                f"[{input_idx}:v]fps=30,settb=AVTB,format=rgba,scale={target_w}:-1,"
                f"trim=duration={cta_duration:.4f},setpts=PTS-STARTPTS+{start:.4f}/TB[cta{idx}]"
            )
        out_label = f"[vcta{idx}]"
        chains.append(
            f"{current}[cta{idx}]overlay=x='{x_expr}':y='{y_expr}':"
            f"enable='between(t,{start:.4f},{end:.4f})':"
            f"eof_action=pass:repeatlast=0:shortest=0{out_label}"
        )
        current = out_label

    if subtitle_ass and subtitle_ass.exists():
        subtitle_label = "[vfinal]"
        chains.append(f"{current}ass={subtitle_ass.name}{subtitle_label}")
        current = subtitle_label

    encoder_args = choose_video_args(
        job.options.get("mode", "standard"),
        job.options.get("codec", "hevc"),
        bool(job.options.get("gpu", False)),
        job,
    )
    cmd += [
        "-filter_complex", ";".join(chains),
        "-map", current,
        "-an",
        *encoder_args,
        "-t", f"{target_duration:.4f}",
        "-fps_mode", "cfr",
        "-avoid_negative_ts", "make_zero",
        "-pix_fmt", "yuv420p",
        str(out),
    ]
    run_cmd(
        job,
        cmd,
        total_duration=target_duration,
        base=94.0,
        span=1.5,
        cwd=work,
        quiet_success=True,
    )
    composed_duration = safe_probe_duration(out)
    job.timeline_summary["composed_visual_duration"] = round(composed_duration, 3)
    if composed_duration < target_duration - 0.35:
        _append_log(
            job,
            f"Composicao visual terminou em {composed_duration:.2f}s para "
            f"{target_duration:.2f}s de audio; a protecao de duracao completara "
            "somente a diferenca necessaria.",
        )
    else:
        job.timeline_summary["duration_repair_avoided"] = True
        _append_log(job, "Composicao final cobriu toda a narracao; passagem extra de reparo evitada.")
    job.cta_summary.update({
        "position_preset": preset,
        "offset_x": clamp_float(job.options.get("ctaOffsetX"), 0.0, -35.0, 35.0),
        "offset_y": clamp_float(job.options.get("ctaOffsetY"), 0.0, -35.0, 35.0),
        "scale_width_px": target_w,
    })
    job.timeline_summary.update({
        "unified_final_composition": True,
        "visual_passes_effective": 2,
        "visual_passes_avoided": 1,
    })
    if turbo_enabled(job):
        turbo = ensure_turbo_summary(job)
        turbo.update({
            "unified_composition": True,
            "fallback_used": False,
            "visual_passes_effective": 2,
            "visual_passes_avoided": 1,
        })
        _append_log(job, "Turbo Produção: CTA + Textos + Legendas compostos em uma única passagem visual.")
    else:
        _append_log(job, "Modo Eficiente otimizado: CTA + Textos + Legendas compostos em uma unica passagem final, preservando todos os efeitos.")
    return out


def ensure_video_duration(job: Job, video_source: Path, target_duration: float, work: Path) -> Path:
    """Pad a short visual stream with its last valid frame instead of failing the render."""
    target_duration = max(0.1, float(target_duration or 0.1))
    current_duration = safe_probe_duration(video_source)
    if current_duration >= target_duration - 0.35:
        return video_source
    if current_duration <= 0.05:
        raise RuntimeError("Video final sem frames validos antes do mux.")

    missing = max(0.1, target_duration - current_duration + 0.12)
    repaired = work / "video_duration_repaired.mp4"
    encoder_args = choose_video_args(
        job.options.get("mode", "standard"),
        job.options.get("codec", "hevc"),
        bool(job.options.get("gpu", False)),
        job,
    )
    _append_log(
        job,
        f"Protecao de duracao: prolongando o ultimo frame por {missing:.2f}s "
        f"(video={current_duration:.2f}s, audio={target_duration:.2f}s).",
    )
    cmd = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-fflags", "+genpts",
        "-i", str(video_source),
        "-vf",
        (
            f"fps=30,settb=AVTB,setpts=PTS-STARTPTS,"
            f"tpad=stop_mode=clone:stop_duration={missing:.4f},"
            f"trim=duration={target_duration:.4f},setpts=PTS-STARTPTS"
        ),
        "-an",
        *encoder_args,
        "-t", f"{target_duration:.4f}",
        "-fps_mode", "cfr",
        "-avoid_negative_ts", "make_zero",
        "-pix_fmt", "yuv420p",
        str(repaired),
    ]
    run_cmd(
        job,
        cmd,
        total_duration=target_duration,
        base=95.0,
        span=0.7,
        cwd=work,
        quiet_success=True,
    )
    repaired_duration = safe_probe_duration(repaired)
    if repaired_duration < target_duration - 0.35:
        raise RuntimeError(
            f"Nao foi possivel reparar a duracao visual: video={repaired_duration:.2f}s, "
            f"audio={target_duration:.2f}s."
        )
    job.timeline_summary["duration_repaired"] = True
    job.timeline_summary["duration_repair_seconds"] = round(missing, 3)
    return repaired


def burn_subtitles_on_video(
    job: Job,
    video_source: Path,
    subtitle_ass: Path,
    work: Path,
    output_name: str = "video_subtitled.mp4",
    target_duration: float | None = None,
) -> Path:
    set_stage(job, "subtitles", "Aplicando legendas", "Aplicando legendas animadas")
    job.percent = 95
    subtitle_video = work / output_name
    encoder_args = choose_video_args(
        job.options.get("mode", "standard"),
        job.options.get("codec", "hevc"),
        bool(job.options.get("gpu", False)),
        job,
    )
    duration = max(0.0, float(target_duration or 0.0))
    duration_filter = (
        f",tpad=stop_mode=clone:stop_duration={duration:.4f},trim=duration={duration:.4f}"
        if duration > 0
        else ""
    )
    cmd_subtitles = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-filter_threads", "1", "-filter_complex_threads", "1",
        "-fflags", "+genpts",
        "-i", video_source.name,
        "-vf",
        f"fps=30,settb=AVTB,setpts=PTS-STARTPTS{duration_filter},ass={subtitle_ass.name}",
        *encoder_args,
        *(["-t", f"{duration:.4f}"] if duration > 0 else []),
        "-fps_mode", "cfr",
        "-avoid_negative_ts", "make_zero",
        "-pix_fmt", "yuv420p",
        str(subtitle_video.name),
    ]
    run_cmd(
        job,
        cmd_subtitles,
        total_duration=duration or None,
        base=94.0,
        span=1.5,
        cwd=work,
        quiet_success=True,
    )
    return subtitle_video


def mix_cta_audio(job: Job, base_audio: Path, cta: dict[str, Any], times: list[float], audio_total: float, work: Path) -> Path:
    audio_source = cta.get("audio_source")
    if not audio_source or not cta.get("has_audio"):
        return base_audio
    out = Path("glide_audio_with_cta.wav")
    cmd: list[str] = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-filter_threads", "1", "-filter_complex_threads", "1", "-i", str(base_audio)]
    for _ in times:
        cmd += ["-i", str(audio_source)]
    filters = ["[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[base]"]
    labels = ["[base]"]
    cta_duration = max(0.5, min(float(cta.get("duration") or 0.0), audio_total))
    for idx, start in enumerate(times):
        delay = max(0, int(round(start * 1000)))
        filters.append(
            f"[{idx + 1}:a]atrim=0:{cta_duration:.3f},asetpts=PTS-STARTPTS,"
            f"adelay={delay}|{delay},aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[cta_a{idx}]"
        )
        labels.append(f"[cta_a{idx}]")
    filters.append("".join(labels) + f"amix=inputs={len(labels)}:duration=first:dropout_transition=0:normalize=0[aout]")
    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "[aout]",
        "-t", f"{audio_total:.4f}",
        "-ac", "2", "-ar", "48000",
        str(out),
    ]
    set_stage(job, "cta", "Mixando audio CTA", "Mantendo som do CTA junto da narracao")
    run_cmd(job, cmd, total_duration=audio_total or None, base=91, span=2, cwd=work, quiet_success=True)
    return out


def auto_sound_fx_enabled(options: dict[str, Any]) -> bool:
    return bool(options.get("autoSoundFx", True))


def stable_float(seed: str) -> float:
    return stable_index(seed, 10_000) / 9999.0


def clamp_sfx_db(value: float) -> float:
    return max(AUTO_SFX_MIN_DB, min(AUTO_SFX_MAX_DB, value))


def sfx_volume_db(job: Job, kind: str, emphasis: float = 0.0) -> float:
    spec = SFX_EFFECT_SPECS.get(kind, {})
    base = float(spec.get("volume_db", AUTO_SFX_DEFAULT_DB))
    try:
        base += float(job.options.get("soundFxGainDb", 2.0) or 0.0)
    except Exception:
        base += 2.0
    lowered = kind.lower()
    if job.background_music_summary.get("enabled"):
        base -= 0.35
    if job.audio_health_summary.get("status") == "problem":
        base -= 0.45
    if kind in {"intro_hit", "cta_click"} or any(token in lowered for token in ("hit", "bass", "stamp", "slam", "title")):
        base += 0.70
    if kind in {"cta_whoosh", "subtitle_whoosh", "subtitle_swipe"} or any(token in lowered for token in ("whoosh", "sweep", "swipe", "slide", "cymbal")):
        base += 0.10
    if any(token in lowered for token in ("glitch", "camera", "flash", "mechanical", "industrial", "metal")):
        base += 0.25
    if kind in {"intro_ambience", "subtitle_air"} or any(token in lowered for token in ("air", "ambience", "luxury", "documentary")):
        base -= 0.35
    return round(clamp_sfx_db(base + emphasis), 2)


def subtitle_intro_variant_for_sfx(job_id: str, idx: int, cue: SubtitleCue, animation: str) -> str:
    intro_map = {
        "fade": ["fade"],
        "pop": ["pop", "pop_soft"],
        "slide": ["rise", "slide_left", "slide_right"],
        "zoom": ["zoom_in", "zoom_soft"],
        "cinematic": ["cinema_drop", "rise"],
        "pulse": ["pulse_in", "pop_soft"],
        "glitch": ["glitch"],
        "typewriter": ["typewriter"],
        "shake": ["shake"],
        "none": ["none"],
        "random_text": ["fade", "rise", "pop", "zoom_in", "slide_left", "slide_right", "cinema_drop", "pulse_in", "glitch", "typewriter"],
        "documentary": ["cinema_drop", "rise", "typewriter"],
        "archive": ["typewriter", "slide_left", "rise"],
        "digital": ["glitch", "typewriter", "pulse_in"],
        "stamp": ["pop", "shake"],
        "money": ["typewriter", "pulse_in"],
        "warning": ["shake", "pop"],
        "industrial": ["shake", "cinema_drop"],
        "luxury": ["cinema_drop", "fade", "rise"],
        "mixed": ["fade", "rise", "pop", "zoom_in", "slide_left", "slide_right", "cinema_drop", "pulse_in"],
    }
    intros = intro_map.get(animation, intro_map["mixed"])
    return intros[stable_index(f"{job_id}:intro:{idx}:{cue.text}", len(intros))]


def sfx_effect_layers_for_subtitle(
    job: Job,
    idx: int,
    cue: SubtitleCue,
    animation: str,
    forced_variant: str | None = None,
) -> list[tuple[str, float, float]]:
    if animation == "none":
        return []
    seed = subtitle_animation_seed(job)
    intro = forced_variant or subtitle_intro_variant_for_sfx(seed, idx, cue, animation)
    if animation in {"archive", "documentary", "digital", "money", "stamp", "warning", "industrial", "luxury"}:
        preferred = {
            "archive": "subtitle_archive_caption",
            "documentary": "subtitle_luxury_doc",
            "digital": "subtitle_digital_typing" if intro == "typewriter" else "subtitle_glitch_reveal",
            "money": "subtitle_money_counter",
            "stamp": "subtitle_stamp",
            "warning": "subtitle_warning_alert",
            "industrial": "subtitle_industrial_metal",
            "luxury": "subtitle_luxury_doc",
        }[animation]
        spec = SFX_EFFECT_SPECS.get(preferred, {})
        offset = 0.0 if str(spec.get("anchor")) == "pico" else -0.008
        return [(preferred, offset, 0.18)]

    variant = SUBTITLE_VARIANT_SFX.get(intro)
    if variant:
        effect, offset, emphasis, _anchor = variant
        return [(effect, offset, emphasis)]

    choices = SUBTITLE_SFX_POOLS.get(animation, SUBTITLE_SFX_POOLS["mixed"])
    if not choices:
        return []
    selected = choices[stable_index(f"{seed}:sfx:subtitle:{animation}:{idx}:{cue.text}", len(choices))]
    return [(selected, 0.0, 0.08)]


def sfx_effect_for_subtitle(job: Job, idx: int, cue: SubtitleCue, animation: str) -> str:
    layers = sfx_effect_layers_for_subtitle(job, idx, cue, animation)
    return layers[0][0] if layers else ""


def sfx_duration(effect: str, event_duration: float = 0.0) -> float:
    spec = SFX_EFFECT_SPECS.get(effect, {})
    defaults = {
        "intro_ambience": 2.3,
        "intro_rise": 2.15,
        "intro_hit": 0.72,
        "subtitle_air": 0.42,
        "subtitle_shimmer": 0.48,
        "subtitle_swipe": 0.34,
        "subtitle_whoosh": 0.36,
        "subtitle_zoom": 0.42,
        "subtitle_hit": 0.26,
        "subtitle_click": 0.14,
        "subtitle_pulse": 0.34,
        "subtitle_glitch": 0.32,
        "subtitle_type": 0.40,
        "subtitle_shake": 0.28,
        "subtitle_type_classic": 0.42,
        "subtitle_digital_typing": 0.36,
        "subtitle_money_counter": 0.42,
        "subtitle_title_slam": 0.30,
        "subtitle_glitch_reveal": 0.32,
        "subtitle_neon_flicker": 0.34,
        "subtitle_stamp": 0.28,
        "subtitle_archive_caption": 0.44,
        "subtitle_warning_alert": 0.30,
        "subtitle_industrial_metal": 0.36,
        "subtitle_luxury_doc": 0.48,
        "subtitle_bullet_pop": 0.22,
        "subtitle_data_scan": 0.36,
        "subtitle_date_reveal": 0.42,
        "image_soft_in": 0.34,
        "image_parallax_peak": 0.38,
        "graphic_arrow_draw": 0.26,
        "graphic_highlight_pulse": 0.22,
        "data_counter_tick": 0.30,
    }
    if event_duration > 0:
        return round(max(0.12, min(2.8, event_duration)), 3)
    return float(spec.get("duration", defaults.get(effect, 0.45)))


def sfx_effect_anchor(effect: str) -> str:
    return str(SFX_EFFECT_SPECS.get(effect, {}).get("anchor") or "inicio")


def tone_allows_suspense_fx(job: Job) -> bool:
    tone = str((job.emotion_summary or {}).get("tone") or job.options.get("projectTone") or "").lower()
    template = str(job.options.get("workflowPreset") or job.options.get("template") or "").lower()
    transition = str(job.options.get("transitions") or "").lower()
    haystack = " ".join([
        tone,
        template,
        transition,
        str(job.options.get("projectName") or job.options.get("queueProjectName") or job.options.get("outputName") or "").lower(),
        str(job.options.get("identity") or "").lower(),
        " ".join(str(item.get("reason") or "").lower() for item in (job.strong_moments_summary or {}).get("moments", [])[:6] if isinstance(item, dict)),
    ])
    tokens = {
        "suspense", "terror", "horror", "dark", "sombrio", "shadow", "misterio", "mystery",
        "industrial", "glitch", "classified", "archive", "forbidden", "historical",
    }
    return any(token in haystack for token in tokens)


def transition_sfx_pool_for_job(job: Job, mode: str, idx: int = 0) -> list[str]:
    mode = str(mode or "off")
    if mode in {"", "off", "none"}:
        return []
    pool = list(TRANSITION_SFX_POOLS.get(mode) or TRANSITION_SFX_POOLS.get("random") or [])
    if mode.startswith("random"):
        tone = str((job.emotion_summary or {}).get("tone") or job.options.get("projectTone") or "auto").lower()
        tone_extra = {
            "suspense": ["transition_suspense", "transition_digital_glitch", "transition_industrial"],
            "historical": ["transition_archive", "transition_documentary"],
            "tech": ["transition_futuristic", "transition_digital_glitch"],
            "energetic": ["transition_swipe", "transition_flash", "transition_bass_hit"],
            "emotional": ["transition_air", "transition_whoosh"],
            "explanatory": ["transition_swipe", "transition_map", "transition_air"],
        }.get(tone, [])
        pool = pool + tone_extra
    if tone_allows_suspense_fx(job) and mode in {"random_glitch", "random_industrial", "digital_glitch", "industrial", "bass_hit", "whoosh", "random_cinematic", "random"}:
        pool.append("transition_suspense")
    if not tone_allows_suspense_fx(job):
        pool = [effect for effect in pool if not SFX_EFFECT_SPECS.get(effect, {}).get("suspense_only")]
    cleaned: list[str] = []
    for effect in pool:
        if effect and effect not in cleaned:
            cleaned.append(effect)
    if not mode.startswith("random"):
        return cleaned
    if len(cleaned) <= 1:
        return cleaned
    start = stable_index(f"{job.id}:transition_pool:{mode}:{idx}", len(cleaned))
    return cleaned[start:] + cleaned[:start]


def transition_boundary_times(segments: list[Path], audio_total: float, work: Path) -> list[tuple[int, float]]:
    boundaries: list[tuple[int, float]] = []
    elapsed = 0.0
    for idx, segment in enumerate(segments):
        try:
            duration = cached_probe_duration(segment, cwd=work if not segment.is_absolute() else None)
        except Exception:
            duration = 0.0
        if idx > 0 and 0.15 <= elapsed < audio_total - 0.15:
            boundaries.append((idx, round(elapsed, 3)))
        elapsed += max(0.0, float(duration or 0.0))
        if elapsed >= audio_total + 2.0:
            break
    return boundaries


def build_auto_sfx_events(job: Job, audio_total: float, segments: list[Path], work: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    def add(
        target_time: float,
        effect: str,
        reason: str,
        duration: float = 0.0,
        db: float | None = None,
        seed: str | None = None,
        anchor: str | None = None,
        offset: float = 0.0,
        meta: dict[str, Any] | None = None,
    ):
        if not effect:
            return
        dur = sfx_duration(effect, duration)
        anchor = anchor or sfx_effect_anchor(effect)
        target = max(0.0, float(target_time))
        if anchor == "pico":
            start = target - min(0.12, dur * 0.42)
        elif anchor == "cauda":
            start = target - dur + min(0.05, dur * 0.08)
        else:
            start = target
        start = max(0.0, start + float(offset or 0.0))
        if start >= audio_total - 0.05:
            return
        dur = min(max(0.08, float(dur)), max(0.08, audio_total - start))
        event = {
            "time": round(start, 3),
            "actual_start": round(start, 3),
            "target_time": round(target, 3),
            "effect": effect,
            "reason": reason,
            "anchor": anchor,
            "offset": round(float(offset or 0.0), 3),
            "duration": round(dur, 3),
            "volume_db": sfx_volume_db(job, effect) if db is None else clamp_sfx_db(float(db)),
            "seed": seed or f"{job.id}:{reason}:{effect}:{start:.3f}",
        }
        if meta:
            event.update(meta)
        events.append(event)

    if job.intro_summary.get("mode") == "cinematic":
        if job.subtitle_summary.get("intro_text"):
            intro_tone = str((job.emotion_summary or {}).get("tone") or "explanatory")
            intro_effect = {
                "tech": "subtitle_glitch_reveal",
                "energetic": "subtitle_title_slam",
                "historical": "subtitle_archive_caption",
                "suspense": "subtitle_luxury_doc",
                "emotional": "subtitle_shimmer",
                "explanatory": "subtitle_air",
            }.get(intro_tone, "subtitle_luxury_doc")
            add(
                0.72,
                intro_effect,
                "intro_text",
                sfx_duration(intro_effect),
                sfx_volume_db(job, intro_effect, -0.05),
                anchor=sfx_effect_anchor(intro_effect),
                meta={"tone": intro_tone},
            )

    style = subtitle_style_from_options(job.options)
    animation = str(job.subtitle_summary.get("animation") or style.get("animation") or "mixed")
    cues = list(job.subtitle_cues or [])
    style_profile = job.options.get("_style_profile_effective") or reference_style_profile(job.options)
    dna_profile = style_profile.get("dna") if isinstance(style_profile.get("dna"), dict) else {}
    try:
        timeline_for_fx = build_event_timeline(job)
    except Exception:
        timeline_for_fx = {}
    timeline_events = list(timeline_for_fx.get("events") or [])
    subtitle_timeline = {
        int(item.get("cue_index")): item
        for item in timeline_events
        if item.get("type") == "subtitle_enter" and item.get("cue_index") is not None
    }

    def event_anchor_time(item: dict[str, Any] | None, anchor_name: str, fallback: float) -> float:
        if not item:
            return fallback
        frame_key = {
            "inicio": "visual_start_frame",
            "pico": "impact_frame",
            "cauda": "fade_out_frame",
        }.get(anchor_name, "impact_frame")
        try:
            return max(0.0, float(item.get(frame_key) or 0) / 30.0)
        except Exception:
            return fallback

    last_subtitle_fx = -99.0
    last_subtitle_effect = ""
    for idx, cue in enumerate(cues):
        if cue.start < 0.20 or cue.start >= audio_total - 0.2:
            continue
        timeline_item = subtitle_timeline.get(idx)
        layers = sfx_effect_layers_for_subtitle(
            job,
            idx,
            cue,
            animation,
            forced_variant=str((timeline_item or {}).get("subtitle_variant") or "") or None,
        )
        if layers:
            effect, offset, emphasis = layers[0]
            # Anti-Fatigue SFX Throttle: espacamento minimo de 1.35s entre efeitos sonoros de texto,
            # permitindo maior frequencia apenas em frases enfaticas (!, ?, :, —)
            is_emphatic = any(p in cue.text for p in ["!", "?", ":", "—", "..."])
            spacing = cue.start - last_subtitle_fx
            if spacing < (0.90 if is_emphatic else 1.35):
                continue

            if effect == last_subtitle_effect:
                pool = SUBTITLE_SFX_POOLS.get(animation, SUBTITLE_SFX_POOLS["mixed"])
                alternates = [item for item in pool if item != effect]
                if alternates:
                    effect = alternates[stable_index(f"{job.id}:subtitle_alt:{idx}:{cue.text}", len(alternates))]

            # Sincronizacao exata no frame 0 da cue (zero latency)
            target_time = round(cue.start, 3)
            add(
                target_time,
                effect,
                "subtitle",
                0.0,
                sfx_volume_db(job, effect, emphasis),
                f"{job.id}:subtitle:{idx}:{animation}:{cue.text}",
                anchor="inicio",
                offset=0.0,
                meta={
                    "subtitle_index": idx,
                    "subtitle_animation": animation,
                    "subtitle_variant": (timeline_item or {}).get("subtitle_variant"),
                    "is_emphatic": is_emphatic,
                },
            )
            last_subtitle_fx = cue.start
            last_subtitle_effect = effect
    if cues and animation != "none" and not any(item["reason"] == "subtitle" for item in events):
        cue = next((item for item in cues if 0.20 <= item.start < audio_total - 0.2), cues[0])
        timeline_item = subtitle_timeline.get(0)
        layers = sfx_effect_layers_for_subtitle(
            job,
            0,
            cue,
            animation,
            forced_variant=str((timeline_item or {}).get("subtitle_variant") or "") or None,
        )
        if layers:
            effect, offset, emphasis = layers[0]
            add(
                round(cue.start, 3),
                effect,
                "subtitle",
                0.0,
                sfx_volume_db(job, effect, emphasis),
                f"{job.id}:subtitle:fallback:{animation}",
                anchor="inicio",
                offset=0.0,
                meta={
                    "subtitle_index": 0,
                    "subtitle_animation": animation,
                    "subtitle_variant": (timeline_item or {}).get("subtitle_variant"),
                },
            )

    transition_mode = str(job.options.get("transitions") or "off")
    boundaries = transition_boundary_times(segments, audio_total, work)
    if transition_mode not in {"", "off", "none"} and boundaries:
        last_transition_fx = -99.0
        last_transition_effect = ""
        selected_transition_count = 0
        for boundary_idx, boundary_time in boundaries:
            if boundary_time - last_transition_fx < 7.0:
                continue
            draw = stable_index(f"{job.id}:transition_draw:{transition_mode}:{boundary_idx}:{boundary_time:.2f}", 100)
            force_first = selected_transition_count == 0 and (
                boundary_idx == boundaries[-1][0] or (len(boundaries) >= 3 and boundary_idx == boundaries[min(2, len(boundaries) - 1)][0])
            )
            transition_density = max(0.18, min(0.68, _safe_float(dna_profile.get("transitionFxDensity"), 0.38)))
            if draw >= int(round(transition_density * 100.0)) and not force_first:
                continue
            pool = transition_sfx_pool_for_job(job, transition_mode, boundary_idx)
            if not pool:
                continue
            effect = pool[stable_index(f"{job.id}:transition_effect:{transition_mode}:{boundary_idx}", len(pool))]
            if effect == last_transition_effect and len(pool) > 1:
                effect = pool[(pool.index(effect) + 1) % len(pool)]
            emphasis = -0.85 if effect != "transition_suspense" else -1.05
            add(
                boundary_time,
                effect,
                "transition",
                0.0,
                sfx_volume_db(job, effect, emphasis),
                f"{job.id}:transition:{boundary_idx}:{transition_mode}:{effect}",
                anchor=sfx_effect_anchor(effect),
                offset=0.0,
                meta={"transition_index": boundary_idx, "transition_mode": transition_mode},
            )
            last_transition_fx = boundary_time
            last_transition_effect = effect
            selected_transition_count += 1

    image_fx_density = _safe_float(dna_profile.get("imageEventFxDensity"), 0.48)
    graphic_fx_density = _safe_float(dna_profile.get("arrowHighlightDensity"), 0.24)
    last_graphic_fx = -99.0
    last_image_fx = -99.0
    last_cut_fx = -99.0
    last_camera_fx = -99.0
    graphic_effects = {
        "arrow_draw": "graphic_arrow_draw",
        "text_highlight": "graphic_highlight_pulse",
    }
    for idx, item in enumerate((timeline_for_fx.get("events") or [])[:220]):
        if item.get("fx_policy") == "suppress_secondary":
            continue
        event_type = str(item.get("type") or "")
        target = float(item.get("target_time") or (float(item.get("impact_frame") or 0) / 30.0))
        if target < 0.25 or target >= audio_total - 0.2:
            continue
        if event_type == "image_enter":
            if target - last_image_fx < 5.5:
                continue
            draw = stable_float(f"{job.id}:image_fx:{idx}:{target:.2f}")
            if draw > max(0.18, min(0.82, image_fx_density)):
                continue
            effect = "image_soft_in"
            anchor_name = sfx_effect_anchor(effect)
            target = event_anchor_time(item, anchor_name, target)
            add(
                target,
                effect,
                "image_event",
                0.0,
                sfx_volume_db(job, effect, -0.35),
                f"{job.id}:image_event:{idx}:{target:.2f}",
                anchor=anchor_name,
                meta={
                    "event_timeline_type": event_type,
                    "block": item.get("block"),
                    "visual_start_frame": item.get("visual_start_frame"),
                    "impact_frame": item.get("impact_frame"),
                },
            )
            last_image_fx = target
        elif event_type == "image_motion_peak":
            if target - last_image_fx < 4.5:
                continue
            draw = stable_float(f"{job.id}:image_peak_fx:{idx}:{target:.2f}")
            if draw > max(0.12, min(0.68, image_fx_density * 0.72)):
                continue
            effect = "image_parallax_peak"
            anchor_name = sfx_effect_anchor(effect)
            target = event_anchor_time(item, anchor_name, target)
            add(
                target,
                effect,
                "image_motion",
                0.0,
                sfx_volume_db(job, effect, -0.55),
                f"{job.id}:image_motion:{idx}:{target:.2f}",
                anchor=anchor_name,
                meta={
                    "event_timeline_type": event_type,
                    "block": item.get("block"),
                    "visual_start_frame": item.get("visual_start_frame"),
                    "impact_frame": item.get("impact_frame"),
                },
            )
            last_image_fx = target
        elif event_type in graphic_effects:
            if target - last_graphic_fx < 2.2:
                continue
            draw = stable_float(f"{job.id}:graphic_fx:{event_type}:{idx}:{target:.2f}")
            if draw > max(0.10, min(0.72, graphic_fx_density + 0.18)):
                continue
            effect = graphic_effects[event_type]
            if re.search(r"\d|%|milh|bilh|dolar|euro|preco", str(item.get("text") or ""), flags=re.IGNORECASE):
                effect = "data_counter_tick"
            anchor_name = sfx_effect_anchor(effect)
            target = event_anchor_time(item, anchor_name, target)
            add(
                target,
                effect,
                "motion_graphic",
                0.0,
                sfx_volume_db(job, effect, -0.15),
                f"{job.id}:graphic:{event_type}:{idx}:{target:.2f}",
                anchor=anchor_name,
                meta={
                    "event_timeline_type": event_type,
                    "cue_index": item.get("cue_index"),
                    "visual_start_frame": item.get("visual_start_frame"),
                    "impact_frame": item.get("impact_frame"),
                },
            )
            last_graphic_fx = target
        elif event_type == "clip_cut":
            if target - last_cut_fx < 8.0:
                continue
            if stable_float(f"{job.id}:cut_fx:{idx}:{target:.2f}") > 0.20:
                continue
            effect = "cut_soft_tick"
            anchor_name = sfx_effect_anchor(effect)
            target = event_anchor_time(item, anchor_name, target)
            add(
                target,
                effect,
                "cut_event",
                0.0,
                sfx_volume_db(job, effect, -0.45),
                f"{job.id}:cut_event:{idx}:{target:.2f}",
                anchor=anchor_name,
                meta={"event_timeline_type": event_type, "block": item.get("block")},
            )
            last_cut_fx = target
        elif event_type == "camera_motion_peak":
            if target - last_camera_fx < 7.0:
                continue
            if stable_float(f"{job.id}:camera_fx:{idx}:{target:.2f}") > 0.24:
                continue
            effect = "camera_zoom_breath"
            anchor_name = sfx_effect_anchor(effect)
            target = event_anchor_time(item, anchor_name, target)
            add(
                target,
                effect,
                "camera_motion",
                0.0,
                sfx_volume_db(job, effect, -0.40),
                f"{job.id}:camera_motion:{idx}:{target:.2f}",
                anchor=anchor_name,
                meta={"event_timeline_type": event_type, "block": item.get("block")},
            )
            last_camera_fx = target

    if effective_visual_options(job)["strong_moments"]:
        strong_moments = list((job.strong_moments_summary or {}).get("moments") or [])
        last_strong_fx = -99.0
        tone = str((job.emotion_summary or {}).get("tone") or "explanatory")
        tone_effect = {
            "suspense": "subtitle_luxury_doc",
            "emotional": "subtitle_shimmer",
            "explanatory": "subtitle_bullet_pop",
            "energetic": "subtitle_title_slam",
            "historical": "subtitle_archive_caption",
            "tech": "subtitle_data_scan",
        }.get(tone, "subtitle_title_slam")
        for idx, moment in enumerate(strong_moments[:8]):
            start = float(moment.get("time") or 0.0)
            if start - last_strong_fx < 9.0:
                continue
            if start >= audio_total - 0.6:
                continue
            add(
                start,
                tone_effect,
                "strong_moment",
                0.0,
                sfx_volume_db(job, tone_effect, 0.45),
                f"{job.id}:strong:{idx}:{tone}:{moment.get('reason')}",
                anchor=sfx_effect_anchor(tone_effect),
                offset=-0.08,
                meta={"strong_moment_index": idx},
            )
            if tone in {"suspense", "energetic", "historical"}:
                layer_effect = "subtitle_hit" if tone != "historical" else "subtitle_archive_caption"
                add(
                    start + 0.16,
                    layer_effect,
                    "strong_moment",
                    0.0,
                    sfx_volume_db(job, layer_effect, -0.28),
                    f"{job.id}:strong_layer:{idx}:{tone}",
                    anchor=sfx_effect_anchor(layer_effect),
                    meta={"strong_moment_index": idx, "layer": True},
                )
            last_strong_fx = start

    events.sort(key=lambda item: (item["time"], item["reason"]))
    if len(events) > 240:
        priority = {"intro_text": 0, "subtitle": 1, "strong_moment": 2, "transition": 3}
        selected = sorted(events, key=lambda item: (priority.get(item["reason"], 9), item["time"]))[:240]
        events = sorted(selected, key=lambda item: (item["time"], item["reason"]))
    return events


def sfx_asset_tokens(effect: str) -> list[str]:
    if effect == "cut_soft_tick":
        return ["slide-click", "fast_bullet", "click", "tap", "text"]
    if effect == "camera_zoom_breath":
        return ["speed_blur_slide", "push_slide", "whoosh", "swipe", "sweep"]
    groups = {
        "whoosh": ["whoosh", "swipe", "sweep", "air", "sword", "cut", "11l-whoosh"],
        "swipe": ["horizontal_swipe", "speed_blur_slide", "push_slide", "swipe", "whoosh", "sword", "cut"],
        "zoom": ["whoosh", "swipe", "sweep", "speed_blur_slide", "push_slide"],
        "slide": ["push_slide", "slide"],
        "push": ["push_slide", "slide"],
        "blur": ["speed_blur_slide", "blur", "swipe"],
        "sweep": ["sweep", "whoosh", "air", "cinematic", "reverse_cymbal"],
        "air": ["air", "whoosh", "sweep", "ambience", "calm"],
        "hit": ["powerful_title", "stamp_text", "fast_bullet", "hit", "impact", "boom", "punch", "bang", "blockbuster", "logo", "percussion"],
        "bell": ["bell", "chime", "ding"],
        "click": ["click", "tap", "type", "text"],
        "type": ["type", "typing", "writing", "pen", "text"],
        "glitch": ["glitch", "digital"],
        "rise": ["rise", "riser", "build", "trailer", "cinematic"],
        "shimmer": ["shimmer", "sparkle", "shine", "text"],
        "ambience": ["ambience", "ambient", "air", "sadness", "cinematic"],
        "pulse": ["pulse", "hit", "impact"],
        "shake": ["stamp_text", "powerful_title", "shake", "hit", "impact", "bang"],
        "dark": ["dark_documentary", "documentary", "tension", "sadness", "shadow"],
        "documentary": ["dark_documentary", "luxury_documentary", "documentary", "tension"],
        "archive": ["ancient_archive", "archive_capt", "paper_archive", "archive", "paper"],
        "paper": ["paper_archive", "archive", "paper"],
        "vhs": ["retro_vhs", "vhs", "tape"],
        "digital": ["digital_glitch", "futuristic_interface", "digital", "glitch"],
        "camera": ["camera_flash", "flash"],
        "flash": ["camera_flash", "flash"],
        "mechanical": ["mechanical_gear", "gear", "mechanical"],
        "gear": ["mechanical_gear", "gear"],
        "money": ["money_cash", "money_number", "cashier", "cash", "ka-ching"],
        "counter": ["money_number_counter", "money_number", "number_counter", "counter"],
        "image": ["whoosh", "swipe", "air", "slide", "cinematic"],
        "arrow": ["swipe", "whoosh", "slide", "text", "click"],
        "highlight": ["click", "tap", "pulse", "hit", "text"],
        "cash": ["money_cash", "cashier", "cash"],
        "map": ["map_travel", "travel", "map"],
        "travel": ["map_travel", "travel", "map"],
        "futuristic": ["futuristic_interface", "ui", "interface", "digital"],
        "industrial": ["industrial_text", "industrial", "factory", "mechanical"],
        "metal": ["industrial_text", "mechanical_gear", "metal", "steel"],
        "bass": ["sub_bass_pulse", "bass-dropmp3", "sub_bass", "bass-drop", "bass", "boom"],
        "reverse": ["reverse_cymbal", "cymbal", "reverse"],
        "cymbal": ["reverse_cymbal", "cymbal"],
        "glass": ["footstep on cracked glass", "cracked glass", "windshield", "glass"],
        "stamp": ["stamp_text", "stamp"],
        "bullet": ["fast_bullet", "bullet", "pop"],
        "title": ["powerful_title", "blockbuster", "title", "logo"],
        "luxury": ["luxury_documentary", "documentary", "shimmer"],
        "warning": ["warning", "bang", "impact", "alert"],
        "data": ["futuristic_interface", "data", "scan", "digital"],
        "suspense": ["suspense", "horror", "tension", "nightmare", "creepy", "evil", "riser", "hells-horns", "monster", "mysterious"],
        "terror": ["horror", "terror", "creepy", "nightmare", "evil", "monster", "hells-horns"],
        "cauda": ["riser", "reverse_cymbal", "tension", "suspense"],
    }
    lowered = effect.lower()
    tokens = [lowered]
    for key, values in groups.items():
        if key == "title":
            matched = bool(re.search(r"(^|_)title($|_)", lowered))
        else:
            matched = key in lowered
        if matched:
            tokens.extend(values)
    return sorted(set(tokens), key=len, reverse=True)


def indexed_sfx_assets() -> list[Path]:
    global SFX_ASSET_CACHE
    with SFX_INDEX_LOCK:
        if SFX_ASSET_CACHE is not None:
            return SFX_ASSET_CACHE
        candidates: list[Path] = []
        seen: set[str] = set()
        for folder in SFX_SOURCE_DIRS:
            if not folder.exists():
                continue
            try:
                iterator = folder.rglob("*")
                for path in iterator:
                    if not path.is_file() or path.suffix.lower() not in SFX_EXTS:
                        continue
                    try:
                        key = str(path.resolve())
                    except Exception:
                        key = str(path)
                    if key in seen:
                        continue
                    candidates.append(path)
                    seen.add(key)
            except Exception:
                continue
        SFX_ASSET_CACHE = sorted(candidates, key=lambda p: natural_key(p.name))
        return SFX_ASSET_CACHE


def find_matching_sfx_asset(effect: str, seed: str | None = None) -> Path | None:
    tokens = sfx_asset_tokens(effect)
    ranked: list[tuple[int, Path]] = []
    for path in indexed_sfx_assets():
        stem = path.stem.lower()
        score = 0
        for token in tokens:
            if token and token in stem:
                score += max(1, min(24, len(token)))
        if score > 0:
            ranked.append((score, path))
    if not ranked:
        return None
    best_score = max(score for score, _ in ranked)
    best = sorted([path for score, path in ranked if score == best_score], key=lambda p: natural_key(p.name))
    return best[stable_index(seed or effect, len(best))]


def procedural_sfx_source(effect: str) -> tuple[str, str]:
    if "hit" in effect or "boom" in effect:
        return (
            "sine=frequency=82:sample_rate=48000",
            "lowpass=f=420,afade=t=in:st=0:d=0.008",
        )
    if "bell" in effect or "shimmer" in effect or "pulse" in effect:
        return (
            "sine=frequency=880:sample_rate=48000",
            "highpass=f=450,lowpass=f=5400,aecho=0.55:0.45:70:0.26,afade=t=in:st=0:d=0.018",
        )
    if "click" in effect or "type" in effect:
        return (
            "sine=frequency=1450:sample_rate=48000",
            "highpass=f=700,lowpass=f=4200,afade=t=in:st=0:d=0.002",
        )
    if "glitch" in effect:
        return (
            "anoisesrc=color=white:amplitude=0.32:sample_rate=48000",
            "highpass=f=900,lowpass=f=5200,acrusher=level_in=1:level_out=0.55:bits=7:mode=log,afade=t=in:st=0:d=0.01",
        )
    if "rise" in effect:
        return (
            "anoisesrc=color=pink:amplitude=0.25:sample_rate=48000",
            "highpass=f=220,lowpass=f=6200,afade=t=in:st=0:d=0.24",
        )
    if "ambience" in effect or "air" in effect:
        return (
            "anoisesrc=color=pink:amplitude=0.18:sample_rate=48000",
            "highpass=f=260,lowpass=f=3600,afade=t=in:st=0:d=0.18",
        )
    if "swipe" in effect or "slide" in effect:
        return (
            "anoisesrc=color=pink:amplitude=0.10:sample_rate=48000",
            "highpass=f=350,lowpass=f=2800,afade=t=in:st=0:d=0.08",
        )
    return (
        "anoisesrc=color=pink:amplitude=0.28:sample_rate=48000",
        "highpass=f=360,lowpass=f=6400,afade=t=in:st=0:d=0.025",
    )


def run_ffmpeg_quiet(cmd: list[str], cwd: Path | None = None, priority: str | None = "balanced"):
    p = _run_hidden(cmd, cwd=cwd, priority=priority, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=30)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "FFmpeg falhou")[-1000:])


def sfx_asset_timing_profile(asset: Path) -> dict[str, float]:
    try:
        stat = asset.stat()
        key = f"{asset.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"
    except Exception:
        key = str(asset)
    cached = SFX_TIMING_CACHE.get(key)
    if cached:
        return cached
    fallback = {
        "onset_seconds": 0.0,
        "peak_seconds": 0.08,
        "peak_after_trim_seconds": 0.08,
        "peak_normalized": 0.5,
        "normalization_db": 0.0,
    }
    try:
        cmd = [
            FFMPEG, "-hide_banner", "-loglevel", "error",
            "-i", str(asset), "-vn", "-t", "8",
            "-ac", "1", "-ar", "8000", "-f", "s16le", "pipe:1",
        ]
        result = _run_hidden(cmd, priority="balanced", capture_output=True, timeout=20)
        if result.returncode != 0 or not result.stdout:
            return fallback
        samples = array("h")
        samples.frombytes(result.stdout)
        if sys.byteorder != "little":
            samples.byteswap()
        if not samples:
            return fallback
        window_samples = 40  # 5 ms at 8 kHz.
        envelope: list[float] = []
        for offset in range(0, len(samples), window_samples):
            chunk = samples[offset:offset + window_samples]
            if chunk:
                envelope.append(sum(abs(value) for value in chunk) / len(chunk))
        if not envelope:
            return fallback
        peak_value = max(envelope)
        peak_window = envelope.index(peak_value)
        onset_threshold = max(260.0, peak_value * 0.075)
        onset_window = 0
        for index, value in enumerate(envelope):
            next_value = envelope[index + 1] if index + 1 < len(envelope) else value
            if value >= onset_threshold and next_value >= onset_threshold * 0.82:
                onset_window = index
                break
        onset_seconds = onset_window * window_samples / 8000.0
        peak_seconds = peak_window * window_samples / 8000.0
        peak_normalized = max(0.001, min(1.0, peak_value / 32768.0))
        target_peak = 10 ** (-5.5 / 20.0)
        normalization_db = max(-5.0, min(9.0, 20.0 * math.log10(target_peak / peak_normalized)))
        profile = {
            "onset_seconds": round(onset_seconds, 4),
            "peak_seconds": round(peak_seconds, 4),
            "peak_after_trim_seconds": round(max(0.0, peak_seconds - onset_seconds), 4),
            "peak_normalized": round(peak_normalized, 5),
            "normalization_db": round(normalization_db, 2),
        }
        SFX_TIMING_CACHE[key] = profile
        return profile
    except Exception:
        return fallback


def align_sfx_event_to_asset(event: dict[str, Any], profile: dict[str, float]) -> None:
    anchor = str(event.get("anchor") or sfx_effect_anchor(str(event.get("effect") or "")))
    target = max(0.0, float(event.get("target_time") or 0.0))
    offset = float(event.get("offset") or 0.0)
    duration = max(0.08, float(event.get("duration") or 0.45))
    peak_after_trim = max(0.0, float(profile.get("peak_after_trim_seconds") or 0.0))
    if anchor == "pico":
        start = target - peak_after_trim + offset
        actual_anchor = start + peak_after_trim
    elif anchor == "cauda":
        start = target - duration + offset
        actual_anchor = start + duration
    else:
        start = target + offset
        actual_anchor = start
    start = max(0.0, start)
    if anchor == "pico":
        actual_anchor = start + peak_after_trim
    elif anchor == "cauda":
        actual_anchor = start + duration
    else:
        actual_anchor = start
    event["time"] = round(start, 4)
    event["actual_start"] = round(start, 4)
    event["actual_peak"] = round(start + peak_after_trim, 4)
    event["measured_onset_ms"] = round(float(profile.get("onset_seconds") or 0.0) * 1000.0, 1)
    event["measured_peak_ms"] = round(float(profile.get("peak_seconds") or 0.0) * 1000.0, 1)
    event["sync_deviation_ms"] = round((actual_anchor - (target + offset)) * 1000.0, 1)
    event["timing_source"] = "measured_asset_peak"


def make_sfx_clip(event: dict[str, Any], out: Path, work: Path) -> tuple[Path, str]:
    effect = str(event["effect"])
    duration = max(0.08, min(3.5, float(event.get("duration") or 0.45)))
    db = clamp_sfx_db(float(event.get("volume_db", AUTO_SFX_DEFAULT_DB)))
    fade_out = min(0.34, max(0.035, duration * 0.34))
    fade_start = max(0.0, duration - fade_out)
    seed = str(event.get("seed") or f"{effect}:{out.name}")
    asset = find_matching_sfx_asset(effect, seed)
    out_arg = str(out.relative_to(work)) if out.is_absolute() and out.is_relative_to(work) else str(out)
    if asset:
        event["variant_file"] = asset.name
        event["source"] = "asset"
        timing_profile = sfx_asset_timing_profile(asset)
        seek_args: list[str] = []
        asset_seek = 0.0
        try:
            asset_duration = cached_probe_duration(asset)
            anchor_name = str(event.get("anchor") or sfx_effect_anchor(effect))
            if anchor_name == "cauda" and asset_duration > duration + 0.55:
                seek = max(0.0, asset_duration - duration - 0.08)
                asset_seek = seek
                seek_args = ["-ss", f"{seek:.3f}"]
                event["asset_seek_seconds"] = round(seek, 3)
            elif anchor_name == "pico" and float(timing_profile.get("peak_after_trim_seconds") or 0.0) > duration - 0.03:
                pre_peak = min(0.12, duration * 0.36)
                seek = max(0.0, float(timing_profile.get("peak_seconds") or 0.0) - pre_peak)
                asset_seek = seek
                seek_args = ["-ss", f"{seek:.3f}"]
                event["asset_seek_seconds"] = round(seek, 3)
                timing_profile = dict(timing_profile)
                timing_profile["onset_seconds"] = 0.0
                timing_profile["peak_seconds"] = pre_peak
                timing_profile["peak_after_trim_seconds"] = pre_peak
        except Exception:
            seek_args = []
        align_sfx_event_to_asset(event, timing_profile)
        trim_silence = "" if any(token in effect.lower() for token in ("ambience", "air")) else "silenceremove=start_periods=1:start_duration=0.012:start_threshold=-50dB,"
        normalization_db = float(timing_profile.get("normalization_db") or 0.0)
        af = (
            f"{trim_silence}asetpts=N/SR/TB,apad=pad_dur={duration:.3f},atrim=0:{duration:.3f},"
            "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"volume={normalization_db:.2f}dB,"
            "acompressor=threshold=0.18:ratio=1.55:attack=1:release=42:makeup=1,"
            f"afade=t=out:st={fade_start:.3f}:d={fade_out:.3f},volume={db:.2f}dB,alimiter=limit=0.96"
        )
        cmd = [
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-filter_threads", "1",
            *seek_args,
            "-i", str(asset),
            "-vn", "-af", af,
            "-t", f"{duration:.3f}",
            "-ac", "2", "-ar", "48000",
            out_arg,
        ]
        run_ffmpeg_quiet(cmd, cwd=work)
        rendered_profile_key = (
            f"{asset.resolve()}:{asset_seek:.3f}:{duration:.3f}:"
            f"{normalization_db:.2f}:{db:.2f}:{effect}"
        )
        rendered_profile = SFX_RENDER_PROFILE_CACHE.get(rendered_profile_key)
        if rendered_profile is None:
            rendered_profile = sfx_asset_timing_profile(out)
            SFX_RENDER_PROFILE_CACHE[rendered_profile_key] = rendered_profile
        event["rendered_onset_ms"] = round(float(rendered_profile.get("onset_seconds") or 0.0) * 1000.0, 1)
        rendered_alignment_profile = dict(rendered_profile)
        rendered_alignment_profile["onset_seconds"] = 0.0
        rendered_alignment_profile["peak_after_trim_seconds"] = float(rendered_profile.get("peak_seconds") or 0.0)
        align_sfx_event_to_asset(event, rendered_alignment_profile)
        event["timing_source"] = "measured_rendered_peak"
        return out, "asset"
    event["variant_file"] = ""
    event["source"] = "procedural"
    align_sfx_event_to_asset(event, {
        "onset_seconds": 0.0,
        "peak_seconds": 0.0 if event.get("anchor") == "inicio" else min(0.08, duration * 0.3),
        "peak_after_trim_seconds": 0.0 if event.get("anchor") == "inicio" else min(0.08, duration * 0.3),
    })
    source, chain = procedural_sfx_source(effect)
    af = (
        f"{chain},"
        f"afade=t=out:st={fade_start:.3f}:d={fade_out:.3f},"
        f"volume={db:.2f}dB,alimiter=limit=0.96"
    )
    cmd = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-filter_threads", "1",
        "-f", "lavfi", "-i", source,
        "-t", f"{duration:.3f}",
        "-af", af,
        "-ac", "2", "-ar", "48000",
        out_arg,
    ]
    run_ffmpeg_quiet(cmd, cwd=work)
    return out, "procedural"


def build_pcm_sfx_event_bed(
    prepared: list[tuple[dict[str, Any], Path]],
    audio_total: float,
    work: Path,
) -> Path:
    """Mix short PCM effects into one sample-accurate bed without a huge FFmpeg graph."""
    sample_rate = 48000
    channels = 2
    sample_width = 2
    frame_bytes = channels * sample_width
    total_frames = max(1, int(math.ceil(max(0.1, audio_total) * sample_rate)))
    data_size = total_frames * frame_bytes
    if data_size >= 0xFFFFFFFF - 44:
        raise RuntimeError("Faixa de efeitos excede o limite WAV PCM.")

    bed = work / "glide_sfx_event_bed.wav"
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        channels,
        sample_rate,
        sample_rate * frame_bytes,
        frame_bytes,
        sample_width * 8,
        b"data",
        data_size,
    )
    with bed.open("wb") as target:
        target.write(header)
        target.seek(44 + data_size - 1)
        target.write(b"\0")

    chunk_frames = 8192
    with bed.open("r+b", buffering=0) as target:
        for event, clip in prepared:
            start_frame = max(0, int(round(float(event.get("time") or 0.0) * sample_rate)))
            if start_frame >= total_frames:
                continue
            with wave.open(str(clip), "rb") as source:
                if (
                    source.getnchannels() != channels
                    or source.getsampwidth() != sample_width
                    or source.getframerate() != sample_rate
                    or source.getcomptype() != "NONE"
                ):
                    raise RuntimeError(f"FX fora do formato PCM esperado: {clip.name}")
                written_frames = 0
                remaining_frames = min(source.getnframes(), total_frames - start_frame)
                while written_frames < remaining_frames:
                    take = min(chunk_frames, remaining_frames - written_frames)
                    incoming_raw = source.readframes(take)
                    if not incoming_raw:
                        break
                    incoming = array("h")
                    incoming.frombytes(incoming_raw)
                    if sys.byteorder != "little":
                        incoming.byteswap()
                    byte_offset = 44 + (start_frame + written_frames) * frame_bytes
                    target.seek(byte_offset)
                    existing_raw = target.read(len(incoming_raw))
                    if len(existing_raw) < len(incoming_raw):
                        existing_raw += b"\0" * (len(incoming_raw) - len(existing_raw))
                    existing = array("h")
                    existing.frombytes(existing_raw)
                    if sys.byteorder != "little":
                        existing.byteswap()
                    for index, sample in enumerate(incoming):
                        mixed = int(existing[index]) + int(sample)
                        existing[index] = max(-32768, min(32767, mixed))
                    if sys.byteorder != "little":
                        existing.byteswap()
                    target.seek(byte_offset)
                    target.write(existing.tobytes())
                    written_frames += len(incoming) // channels
    return bed


SFX_PREVIEW_EFFECTS: dict[str, dict[str, Any]] = {
    "subtitle_shimmer": {"label": "SRT fade/cinema", "duration": 0.48, "volume_db": -16.0},
    "subtitle_air": {"label": "SRT air cinematic", "duration": 0.42, "volume_db": -16.8},
    "subtitle_swipe": {"label": "SRT slide/swipe", "duration": 0.34, "volume_db": -16.2},
    "subtitle_whoosh": {"label": "SRT whoosh suave", "duration": 0.36, "volume_db": -16.4},
    "subtitle_zoom": {"label": "SRT zoom", "duration": 0.42, "volume_db": -16.0},
    "subtitle_hit": {"label": "SRT pop/punch", "duration": 0.26, "volume_db": -15.4},
    "subtitle_click": {"label": "SRT click leve", "duration": 0.14, "volume_db": -16.2},
    "subtitle_type": {"label": "SRT typewriter", "duration": 0.40, "volume_db": -17.0},
    "subtitle_glitch": {"label": "SRT glitch", "duration": 0.32, "volume_db": -15.8},
    "subtitle_pulse": {"label": "SRT pulse", "duration": 0.34, "volume_db": -15.8},
    "subtitle_shake": {"label": "SRT shake", "duration": 0.28, "volume_db": -15.2},
    "subtitle_type_classic": {"label": "Texto - classic typewriter", "duration": 0.42, "volume_db": -16.8},
    "subtitle_digital_typing": {"label": "Texto - digital typing", "duration": 0.36, "volume_db": -16.0},
    "subtitle_money_counter": {"label": "Texto - money counter", "duration": 0.42, "volume_db": -15.8},
    "subtitle_title_slam": {"label": "Texto - big title slam", "duration": 0.30, "volume_db": -14.8},
    "subtitle_glitch_reveal": {"label": "Texto - glitch reveal", "duration": 0.32, "volume_db": -15.6},
    "subtitle_stamp": {"label": "Texto - stamp impact", "duration": 0.28, "volume_db": -15.2},
    "subtitle_archive_caption": {"label": "Texto - archive caption", "duration": 0.44, "volume_db": -16.2},
    "subtitle_warning_alert": {"label": "Texto - warning alert", "duration": 0.30, "volume_db": -15.0},
    "subtitle_industrial_metal": {"label": "Texto - industrial metal", "duration": 0.36, "volume_db": -15.4},
    "subtitle_luxury_doc": {"label": "Texto - luxury documentary", "duration": 0.48, "volume_db": -16.4},
    "subtitle_bullet_pop": {"label": "Texto - bullet pop", "duration": 0.22, "volume_db": -15.6},
    "subtitle_data_scan": {"label": "Texto - data scan", "duration": 0.36, "volume_db": -16.0},
    "transition_air": {"label": "Transicao - air sweep", "duration": 0.34, "volume_db": -13.2},
    "transition_whoosh": {"label": "Transicao - cinematic whoosh", "duration": 0.46, "volume_db": -12.7},
    "transition_sweep": {"label": "Transicao - sweep", "duration": 0.50, "volume_db": -12.8},
    "transition_swipe": {"label": "Transicao - swipe", "duration": 0.34, "volume_db": -12.6},
    "transition_flash": {"label": "Transicao - camera flash", "duration": 0.24, "volume_db": -13.0},
    "transition_archive": {"label": "Transicao - paper archive", "duration": 0.34, "volume_db": -13.0},
    "transition_documentary": {"label": "Transicao - documentary sweep", "duration": 0.44, "volume_db": -13.3},
    "transition_vhs": {"label": "Transicao - VHS glitch", "duration": 0.30, "volume_db": -13.1},
    "transition_digital_glitch": {"label": "Transicao - digital glitch", "duration": 0.26, "volume_db": -12.8},
    "transition_mechanical": {"label": "Transicao - mechanical gear", "duration": 0.42, "volume_db": -12.6},
    "transition_industrial": {"label": "Transicao - industrial", "duration": 0.42, "volume_db": -12.5},
    "transition_money": {"label": "Transicao - money cash", "duration": 0.30, "volume_db": -12.9},
    "transition_map": {"label": "Transicao - map travel", "duration": 0.32, "volume_db": -13.2},
    "transition_futuristic": {"label": "Transicao - futuristic UI", "duration": 0.36, "volume_db": -12.9},
    "transition_bass_hit": {"label": "Transicao - deep bass hit", "duration": 0.36, "volume_db": -12.3},
    "transition_glass": {"label": "Transicao - glass swipe", "duration": 0.28, "volume_db": -13.0},
    "transition_suspense": {"label": "Transicao - suspense", "duration": 0.62, "volume_db": -13.3},
}

for _sfx_preview_effect, _sfx_preview_spec in SFX_PREVIEW_EFFECTS.items():
    _render_spec = SFX_EFFECT_SPECS.get(_sfx_preview_effect, {})
    _preview_db = float(_render_spec.get("volume_db", _sfx_preview_spec.get("volume_db", AUTO_SFX_DEFAULT_DB))) + 2.0
    if any(token in _sfx_preview_effect for token in ("hit", "bass", "stamp", "slam", "title")):
        _preview_db += 0.7
    elif any(token in _sfx_preview_effect for token in ("glitch", "flash", "mechanical", "industrial")):
        _preview_db += 0.25
    _sfx_preview_spec["volume_db"] = clamp_sfx_db(_preview_db)


@app.get("/api/sfx-preview-map")
def sfx_preview_map():
    subtitle_preview = {
        "mixed": ["subtitle_shimmer"],
        "pop": ["subtitle_title_slam"],
        "slide": ["subtitle_swipe"],
        "zoom": ["subtitle_zoom"],
        "fade": ["subtitle_shimmer"],
        "cinematic": ["subtitle_luxury_doc"],
        "pulse": ["subtitle_pulse"],
        "glitch": ["subtitle_glitch_reveal"],
        "typewriter": ["subtitle_type_classic"],
        "shake": ["subtitle_shake"],
        "random_text": ["subtitle_archive_caption"],
        "documentary": ["subtitle_luxury_doc"],
        "archive": ["subtitle_archive_caption"],
        "digital": ["subtitle_digital_typing"],
        "stamp": ["subtitle_stamp"],
        "money": ["subtitle_money_counter"],
        "warning": ["subtitle_warning_alert"],
        "industrial": ["subtitle_industrial_metal"],
        "luxury": ["subtitle_luxury_doc"],
        "none": "",
    }
    transition_preview: dict[str, Any] = {"off": ""}
    for mode, pool in TRANSITION_SFX_POOLS.items():
        transition_preview[mode] = [pool[0]] if pool else ""
    return {
        "items": [
            {"effect": key, **value}
            for key, value in sorted(SFX_PREVIEW_EFFECTS.items(), key=lambda item: item[0])
        ],
        "subtitle": subtitle_preview,
        "transition": transition_preview,
        "available_subtitle_animations": sorted(subtitle_preview.keys()),
        "available_transitions": sorted(transition_preview.keys()),
        "cta": [],
        "intro": {"standard": "", "cinematic": ["subtitle_luxury_doc"]},
    }


@app.get("/api/sfx-preview/{effect}")
def sfx_preview(effect: str):
    effect = re.sub(r"[^a-zA-Z0-9_\-]", "", effect or "").lower()
    spec = SFX_PREVIEW_EFFECTS.get(effect)
    if not spec:
        raise HTTPException(status_code=404, detail="Efeito sonoro indisponivel.")
    if not FFMPEG:
        raise HTTPException(status_code=503, detail="FFmpeg nao encontrado para gerar preview de audio.")
    out = sfx_preview_cache_path(effect, spec)
    if not out.exists():
        event = {
            "effect": effect,
            "duration": float(spec.get("duration") or 0.45),
            "volume_db": float(spec.get("volume_db") or AUTO_SFX_DEFAULT_DB),
        }
        try:
            make_sfx_clip(event, out, CTA_CACHE_ROOT)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Falha ao gerar preview de FX: {exc}") from exc
    return FileResponse(out, media_type="audio/wav", filename=out.name)


def _cleanup_automator_sessions() -> None:
    cutoff = time.time() - AUTOMATOR_SESSION_TTL_SECONDS
    stale_ids: list[str] = []
    with AUTOMATOR_SESSION_LOCK:
        for session_id, session in AUTOMATOR_SESSIONS.items():
            if float(session.get("created_at") or 0.0) < cutoff:
                stale_ids.append(session_id)
        for session_id in stale_ids:
            AUTOMATOR_SESSIONS.pop(session_id, None)
    for folder in AUTOMATOR_STAGING_ROOT.iterdir():
        try:
            if folder.is_dir() and folder.stat().st_mtime < cutoff:
                shutil.rmtree(folder, ignore_errors=True)
        except Exception:
            continue


def _automator_project_is_empty(project: dict[str, Any]) -> bool:
    media = project.get("media") if isinstance(project.get("media"), dict) else {}
    return not any(media.get(key) for key in ("videos", "audios", "texts", "subtitles"))


def _automator_kind_allowed(kind: str, suffix: str) -> bool:
    kind = str(kind or "").lower()
    suffix = str(suffix or "").lower()
    if kind in ("subtitle", "text", "text_srt"):
        return suffix in SRT_EXTS
    if kind == "audio":
        return suffix in AUDIO_EXTS or suffix in {".mp4", ".m4v", ".mov", ".webm"}
    if kind in ("script_guide", "script"):
        return suffix in SCRIPT_GUIDE_EXTS
    if kind in ("video", "image"):
        return suffix in VIDEO_EXTS or suffix in IMAGE_EXTS
    return False


@app.post("/api/queue/automator/sessions")
def create_automator_session(payload: dict[str, Any] = Body(default={})):
    _cleanup_automator_sessions()
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    files = payload.get("files") if isinstance(payload.get("files"), list) else []
    if not rows or not files:
        raise HTTPException(status_code=400, detail="Plano AUTO incompleto.")
    project_ids = [str(row.get("projectId") or "").strip() for row in rows]
    if not all(project_ids) or len(project_ids) != len(set(project_ids)):
        raise HTTPException(status_code=400, detail="Projetos AUTO inválidos ou repetidos.")
    with QUEUE_LOCK:
        projects = {str(item.get("id")): item for item in QUEUE_PROJECTS}
        missing = [project_id for project_id in project_ids if project_id not in projects]
        occupied = [
            projects[project_id].get("name") or project_id
            for project_id in project_ids
            if project_id in projects and not _automator_project_is_empty(projects[project_id])
        ]
    if missing:
        raise HTTPException(status_code=404, detail=f"Projetos não encontrados: {', '.join(missing)}")
    if occupied:
        raise HTTPException(
            status_code=409,
            detail="O AUTO aceita apenas projetos vazios. Ocupados: " + ", ".join(str(item) for item in occupied),
        )
    expected: dict[str, dict[str, Any]] = {}
    for raw in files:
        slot = re.sub(r"[^a-zA-Z0-9_-]", "", str(raw.get("slot") or ""))
        project_id = str(raw.get("projectId") or "").strip()
        kind = str(raw.get("kind") or "").lower()
        rel_key = str(raw.get("rel") or raw.get("name") or "").replace("\\", "/").strip("/")
        if not slot or slot in expected or project_id not in project_ids or not rel_key:
            raise HTTPException(status_code=400, detail="Slot de arquivo AUTO inválido.")
        if not _automator_kind_allowed(kind, Path(rel_key).suffix):
            raise HTTPException(status_code=400, detail=f"Tipo não suportado no AUTO: {rel_key} ({kind})")
        expected[slot] = {
            "slot": slot,
            "projectId": project_id,
            "kind": kind,
            "lane": str(raw.get("lane") or kind),
            "rel": rel_key,
            "name": Path(rel_key).name,
            "size": max(0, int(raw.get("size") or 0)),
            "duration": max(0.0, float(raw.get("duration") or 0.0)),
        }
    for project_id in project_ids:
        project_files = [item for item in expected.values() if item["projectId"] == project_id]
        subtitles = [item for item in project_files if item["kind"] == "subtitle"]
        audios = [item for item in project_files if item["kind"] == "audio"]
        videos = [item for item in project_files if item["kind"] == "video"]
        if len(subtitles) != 1 or len(audios) != 1 or not videos:
            raise HTTPException(
                status_code=400,
                detail=f"Projeto {project_id}: o AUTO exige uma narração, Textos em SRT e pelo menos um vídeo real.",
            )
    session_id = uuid.uuid4().hex
    folder = AUTOMATOR_STAGING_ROOT / session_id
    folder.mkdir(parents=True, exist_ok=False)
    session = {
        "id": session_id,
        "created_at": time.time(),
        "status": "uploading",
        "rows": json.loads(json.dumps(rows, ensure_ascii=False)),
        "expected": expected,
        "uploads": {},
        "folder": folder,
        "result": None,
    }
    atomic_write_text(folder / "session.json", json.dumps({
        "id": session_id,
        "created_at": _now_iso(),
        "rows": rows,
        "expected": expected,
    }, ensure_ascii=False, indent=2))
    with AUTOMATOR_SESSION_LOCK:
        AUTOMATOR_SESSIONS[session_id] = session
    return {
        "ok": True,
        "sessionId": session_id,
        "status": "uploading",
        "expectedFiles": len(expected),
        "projects": len(project_ids),
    }


@app.post("/api/queue/automator/sessions/{session_id}/file")
async def upload_automator_session_file(
    session_id: str,
    file: UploadFile = File(...),
    slot: str = Form(...),
):
    with AUTOMATOR_SESSION_LOCK:
        session = AUTOMATOR_SESSIONS.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Sessão AUTO expirada ou inexistente.")
        session_status = str(session.get("status") or "")
        if session_status == "committed":
            return {"ok": True, "alreadyCommitted": True}
        if session_status != "uploading":
            raise HTTPException(status_code=409, detail="A sessão AUTO não aceita novos uploads neste estado.")
    expected = (session.get("expected") or {}).get(slot)
    if not expected:
        raise HTTPException(status_code=400, detail="Arquivo não pertence ao plano AUTO.")
    suffix = Path(file.filename or expected.get("name") or "").suffix.lower()
    if not _automator_kind_allowed(str(expected.get("kind") or ""), suffix):
        raise HTTPException(status_code=400, detail=f"Extensão incompatível: {file.filename}")
    destination = Path(session["folder"]) / f"{slot}{suffix}"
    temporary = destination.with_suffix(destination.suffix + ".part")
    size = 0
    try:
        with temporary.open("wb") as handle:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                size += len(chunk)
        if size <= 0:
            raise HTTPException(status_code=400, detail=f"Arquivo vazio: {file.filename}")
        expected_size = int(expected.get("size") or 0)
        if expected_size > 0 and size != expected_size:
            raise HTTPException(
                status_code=400,
                detail=f"Upload incompleto: {file.filename} ({size}/{expected_size} bytes)",
            )
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    with AUTOMATOR_SESSION_LOCK:
        session["uploads"][slot] = {
            "path": destination,
            "size": size,
            "filename": file.filename or expected.get("name"),
        }
    return {
        "ok": True,
        "slot": slot,
        "uploadedFiles": len(session["uploads"]),
        "expectedFiles": len(session["expected"]),
        "size": size,
    }


@app.post("/api/queue/automator/sessions/{session_id}/commit")
def commit_automator_session(session_id: str):
    with AUTOMATOR_SESSION_LOCK:
        session = AUTOMATOR_SESSIONS.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Sessão AUTO expirada ou inexistente.")
        if session.get("status") == "committed":
            return session.get("result") or {"ok": True, "alreadyCommitted": True}
        if session.get("status") == "committing":
            raise HTTPException(status_code=409, detail="A sessão AUTO já está sendo confirmada.")
        expected = dict(session.get("expected") or {})
        uploads = dict(session.get("uploads") or {})
        missing_slots = [slot for slot in expected if slot not in uploads]
        if missing_slots:
            raise HTTPException(status_code=409, detail=f"Faltam {len(missing_slots)} arquivo(s) antes de confirmar.")
        session["status"] = "committing"

    created_paths: list[Path] = []
    index_backups: dict[str, dict[str, Any]] = {}
    project_results: dict[str, dict[str, Any]] = {}
    try:
        with QUEUE_LOCK:
            project_map = {str(item.get("id")): item for item in QUEUE_PROJECTS}
            project_backup = json.loads(json.dumps(QUEUE_PROJECTS, ensure_ascii=False))
            for row in session.get("rows") or []:
                project_id = str(row.get("projectId") or "")
                project = project_map.get(project_id)
                if not project or not _automator_project_is_empty(project):
                    raise RuntimeError(f"Projeto ocupado ou indisponível durante o commit: {project_id}")
                project_results[project_id] = {
                    "projectId": project_id,
                    "name": project.get("name") or project_id,
                    "videos": [],
                    "audios": [],
                    "background_music": [],
                    "texts": [],
                    "script_guides": [],
                }
                index_backups[project_id] = _load_project_media_index(project_id)

            for slot, spec in expected.items():
                upload = uploads[slot]
                source = Path(upload["path"])
                if not source.exists() or source.stat().st_size <= 0:
                    raise RuntimeError(f"Arquivo de staging ausente: {spec.get('name')}")
                project_id = str(spec["projectId"])
                kind = str(spec["kind"])
                rel_key = str(spec["rel"]).replace("\\", "/")
                folder = _project_media_dir(project_id)
                folder.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256(rel_key.lower().encode("utf-8", errors="ignore")).hexdigest()[:20]
                target = folder / f"{digest}_{session_id[:10]}{source.suffix.lower()}"
                temp_target = folder / f".{digest}.{uuid.uuid4().hex}.part"
                shutil.copy2(source, temp_target)
                os.replace(temp_target, target)
                created_paths.append(target)
                items = _load_project_media_index(project_id)
                items[rel_key] = {
                    "file": target.name,
                    "name": Path(rel_key).name,
                    "kind": kind,
                    "size": target.stat().st_size,
                    "duration": max(0.0, float(spec.get("duration") or 0.0)),
                    "updatedAt": _now_iso(),
                }
                _save_project_media_index(project_id, items)
                group = "videos" if kind in ("video", "image") else "audios" if kind == "audio" else "script_guides" if kind in ("script_guide", "script") else "texts"
                project_results[project_id][group].append(rel_key)

            for row in session.get("rows") or []:
                project_id = str(row.get("projectId") or "")
                project = project_map[project_id]
                result = project_results[project_id]
                media = project.get("media") if isinstance(project.get("media"), dict) else {}
                project["media"] = {
                    "videos": result["videos"],
                    "audios": result["audios"],
                    "background_music": result["background_music"] or list(media.get("background_music") or []),
                    "texts": result["texts"],
                    "captions": list(media.get("captions") or []),
                    "script_guides": result["script_guides"] or list(media.get("script_guides") or []),
                }
                options = project.get("options") if isinstance(project.get("options"), dict) else {}
                if result["script_guides"]:
                    try:
                        script_rel = result["script_guides"][0]
                        script_file_item = _load_project_media_index(project_id).get(script_rel)
                        if script_file_item:
                            script_disk_path = _project_media_dir(project_id) / script_file_item["file"]
                            if script_disk_path.exists():
                                srt_cues = []
                                if result["texts"]:
                                    srt_rel = result["texts"][0]
                                    srt_file_item = _load_project_media_index(project_id).get(srt_rel)
                                    if srt_file_item:
                                        srt_disk_path = _project_media_dir(project_id) / srt_file_item["file"]
                                        if srt_disk_path.exists():
                                            srt_cues = parse_srt_file(srt_disk_path)
                                plan = analyze_script_guide(script_disk_path, project_id=project_id, rel=script_rel, srt_cues=srt_cues)
                                _script_guide_dir(project_id).mkdir(parents=True, exist_ok=True)
                                atomic_write_text(_script_guide_plan_path(project_id), json.dumps(plan, ensure_ascii=False, indent=2))
                                options["scriptGuidePlan"] = plan
                    except Exception:
                        pass
                project["options"] = options
                project["status"] = "ready" if not _queue_project_missing_requirements(project) else "draft"
                project["error"] = None
                project["updatedAt"] = _now_iso()
            _save_queue_projects(QUEUE_PROJECTS)

        result_payload = {
            "ok": True,
            "sessionId": session_id,
            "status": "committed",
            "projects": [
                {
                    **project_results[str(row.get("projectId"))],
                    "counts": {
                        key: len(project_results[str(row.get("projectId"))][key])
                        for key in ("videos", "audios", "texts")
                    },
                }
                for row in session.get("rows") or []
            ],
            "uploadedFiles": len(uploads),
        }
        with AUTOMATOR_SESSION_LOCK:
            session["status"] = "committed"
            session["result"] = result_payload
        shutil.rmtree(Path(session["folder"]), ignore_errors=True)
        return result_payload
    except Exception as exc:
        with QUEUE_LOCK:
            if "project_backup" in locals():
                QUEUE_PROJECTS[:] = project_backup
                _save_queue_projects(QUEUE_PROJECTS)
        for project_id, backup in index_backups.items():
            try:
                _save_project_media_index(project_id, backup)
            except Exception:
                pass
        for path in reversed(created_paths):
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
        with AUTOMATOR_SESSION_LOCK:
            session["status"] = "uploading"
            session["last_error"] = str(exc)
        raise HTTPException(status_code=500, detail=f"AUTO não alterou nenhum projeto: {exc}") from exc


@app.delete("/api/queue/automator/sessions/{session_id}")
def cancel_automator_session(session_id: str):
    with AUTOMATOR_SESSION_LOCK:
        session = AUTOMATOR_SESSIONS.pop(session_id, None)
    if not session:
        return {"ok": True, "status": "missing"}
    if session.get("status") == "committed":
        return {"ok": True, "status": "committed"}
    shutil.rmtree(Path(session["folder"]), ignore_errors=True)
    return {"ok": True, "status": "cancelled"}


@app.get("/api/queue/projects")
def queue_projects():
    with QUEUE_LOCK:
        return {
            "projects": [_public_queue_project(item) for item in QUEUE_PROJECTS],
            "store": str(QUEUE_PROJECTS_FILE),
            "statuses": ["draft", "ready", "queued", "rendering", "paused", "cancelled", "done", "recovered", "error"],
        }


@app.get("/api/queue/projects/{project_id}/media")
def queue_project_media(project_id: str):
    with QUEUE_LOCK:
        project = _find_queue_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto da fila nao encontrado")
        project_copy = json.loads(json.dumps(project, ensure_ascii=False))

    stable_index = _load_project_media_index(project_id)
    stable_changed = False
    legacy_manifest = _project_export_manifest(project_copy)
    legacy_by_rel = {
        str(item.get("rel") or item.get("name") or "").replace("\\", "/"): (index, item)
        for index, item in enumerate(legacy_manifest)
    }
    source_job_id = str(project_copy.get("jobId") or "").strip()
    groups = project_copy.get("media") if isinstance(project_copy.get("media"), dict) else {}
    result: dict[str, list[dict[str, Any]]] = {
        "videos": [],
        "audios": [],
        "background_music": [],
        "texts": [],
        "captions": [],
        "script_guides": [],
    }
    missing: list[str] = []
    kind_map = {
        "videos": "video",
        "audios": "audio",
        "background_music": "background_music",
        "texts": "text_srt",
        "captions": "caption_srt",
        "script_guides": "script_guide",
    }
    mime_map = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".m4v": "video/x-m4v",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".srt": "application/x-subrip",
        ".txt": "text/plain",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pdf": "application/pdf",
        ".html": "text/html",
        ".htm": "text/html",
    }
    for group, kind in kind_map.items():
        for raw_rel in groups.get(group) or []:
            rel_key = str(raw_rel).replace("\\", "/")
            record = stable_index.get(rel_key)
            item_kind = str((record or {}).get("kind") or kind).lower()
            if group == "videos" and (item_kind == "image" or Path(rel_key).suffix.lower() in IMAGE_EXTS):
                item_kind = "image"
            elif group == "videos":
                item_kind = "video"
            path: Path | None = None
            persisted: dict[str, Any] = {}
            if record:
                stored_file = Path(str(record.get("file") or "")).name
                candidate = _project_media_dir(project_id) / stored_file
                if candidate.exists() and candidate.is_file():
                    path = candidate
                    persisted = {
                        "persistedProjectId": project_id,
                        "persistedStoredFile": stored_file,
                    }
            if path is None:
                legacy = legacy_by_rel.get(rel_key) or legacy_by_rel.get(Path(rel_key).name)
                if legacy and source_job_id:
                    index, manifest_item = legacy
                    ext = Path(str(manifest_item.get("name") or rel_key)).suffix.lower()
                    candidate = UPLOAD_ROOT / source_job_id / f"u{index:04d}{ext}"
                    if not candidate.exists():
                        alternatives = list((UPLOAD_ROOT / source_job_id).glob(f"u{index:04d}.*"))
                        candidate = alternatives[0] if alternatives else candidate
                    if candidate.exists() and candidate.is_file():
                        digest = hashlib.sha256(rel_key.lower().encode("utf-8", errors="ignore")).hexdigest()[:20]
                        stable_dir = _project_media_dir(project_id)
                        stable_dir.mkdir(parents=True, exist_ok=True)
                        stable_path = stable_dir / f"{digest}{candidate.suffix.lower()}"
                        try:
                            if not stable_path.exists():
                                os.link(candidate, stable_path)
                            path = stable_path
                            stable_index[rel_key] = {
                                "file": stable_path.name,
                                "name": Path(rel_key).name,
                                "kind": item_kind,
                                "size": stable_path.stat().st_size,
                                "duration": _duration_from_clip_name(rel_key),
                                "updatedAt": _now_iso(),
                            }
                            stable_changed = True
                            persisted = {
                                "persistedProjectId": project_id,
                                "persistedStoredFile": stable_path.name,
                            }
                        except Exception:
                            path = candidate
                            persisted = {
                                "persistedJobId": source_job_id,
                                "persistedIndex": index,
                            }
            if path is None:
                missing.append(rel_key)
                continue

            stat = path.stat()
            duration = float((record or {}).get("duration") or 0.0)
            if duration <= 0:
                duration = _duration_from_clip_name(rel_key)
            if duration <= 0 and item_kind == "image":
                duration = image_duration_default(project_copy.get("options") if isinstance(project_copy.get("options"), dict) else {})
            if duration <= 0 and item_kind in {"audio", "background_music"}:
                duration = safe_probe_duration(path)
            result[group].append({
                "name": Path(rel_key).name,
                "rel": rel_key,
                "kind": item_kind,
                "size": stat.st_size,
                "lastModified": int(stat.st_mtime * 1000),
                "type": mime_map.get(path.suffix.lower(), "application/octet-stream"),
                "duration": round(duration, 4),
                **persisted,
            })
    if stable_changed:
        _save_project_media_index(project_id, stable_index)
    return {
        "projectId": project_id,
        "media": result,
        "missing": missing,
        "available": sum(len(items) for items in result.values()),
    }


@app.get("/api/queue/projects/{project_id}/media-content")
def queue_project_media_content(project_id: str, rel: str):
    rel_key = str(rel or "").replace("\\", "/")
    with QUEUE_LOCK:
        project = _find_queue_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto da fila nao encontrado")
        project_copy = json.loads(json.dumps(project, ensure_ascii=False))
    stable = _load_project_media_index(project_id).get(rel_key)
    if stable:
        stored_file = Path(str(stable.get("file") or "")).name
        candidate = _project_media_dir(project_id) / stored_file
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate, filename=Path(rel_key).name)
    source_job_id = str(project_copy.get("jobId") or "").strip()
    manifest = _project_export_manifest(project_copy)
    for index, item in enumerate(manifest):
        item_rel = str(item.get("rel") or item.get("name") or "").replace("\\", "/")
        if item_rel != rel_key and Path(item_rel).name != Path(rel_key).name:
            continue
        if source_job_id:
            matches = list((UPLOAD_ROOT / source_job_id).glob(f"u{index:04d}.*"))
            if matches and matches[0].is_file():
                return FileResponse(matches[0], filename=Path(rel_key).name)
    raise HTTPException(status_code=404, detail="Midia persistida nao encontrada")


@app.post("/api/queue/projects/{project_id}/media-file")
async def queue_store_project_media(
    project_id: str,
    file: UploadFile = File(...),
    rel: str = Form(...),
    kind: str = Form("file"),
    duration: float = Form(0.0),
):
    with QUEUE_LOCK:
        if not _find_queue_project(project_id):
            raise HTTPException(status_code=404, detail="Projeto da fila nao encontrado")
    rel_key = str(rel or file.filename or "media").replace("\\", "/")
    extension = Path(safe_name(rel_key)).suffix.lower() or Path(file.filename or "").suffix.lower() or ".bin"
    digest = hashlib.sha256(rel_key.lower().encode("utf-8", errors="ignore")).hexdigest()[:20]
    folder = _project_media_dir(project_id)
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / f"{digest}{extension}"
    temporary = folder / f".{digest}.{uuid.uuid4().hex}.upload"
    try:
        with temporary.open("wb") as handle:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)

    items = _load_project_media_index(project_id)
    items[rel_key] = {
        "file": destination.name,
        "name": Path(rel_key).name,
        "kind": str(kind or "file"),
        "size": destination.stat().st_size,
        "duration": max(0.0, float(duration or 0.0)),
        "updatedAt": _now_iso(),
    }
    _save_project_media_index(project_id, items)
    if str(kind or "").lower() in {"video", "image"} or extension in VIDEO_EXTS or extension in IMAGE_EXTS:
        try:
            MEDIA_INDEX_EXECUTOR.submit(index_media_background, destination, max(0.0, float(duration or 0.0)))
        except Exception:
            pass
    return {
        "ok": True,
        "rel": rel_key,
        "name": Path(rel_key).name,
        "size": destination.stat().st_size,
        "persistedProjectId": project_id,
        "persistedStoredFile": destination.name,
    }


@app.post("/api/script-guide/analyze")
async def api_analyze_script_guide(file: UploadFile = File(...), rel: str = Form("")):
    suffix = Path(file.filename or rel or "").suffix.lower()
    if suffix not in SCRIPT_GUIDE_EXTS:
        raise HTTPException(status_code=400, detail="Formato de roteiro não suportado. Use TXT, DOCX, PDF ou HTML.")
    folder = UPLOAD_ROOT / "_script_guide_preview"
    folder.mkdir(parents=True, exist_ok=True)
    temp = folder / f"{uuid.uuid4().hex}{suffix}"
    try:
        with temp.open("wb") as handle:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
        plan = analyze_script_guide(temp, rel=rel or file.filename or temp.name)
        return {"ok": True, "plan": plan}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        temp.unlink(missing_ok=True)


@app.post("/api/queue/projects/{project_id}/script-guide/analyze")
def api_analyze_project_script_guide(project_id: str, payload: dict[str, Any] | None = Body(None)):
    data = payload or {}
    rel_key = str(data.get("rel") or "").replace("\\", "/")
    if not rel_key:
        raise HTTPException(status_code=400, detail="Roteiro não informado.")
    with QUEUE_LOCK:
        project = _find_queue_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto da fila nao encontrado")
        project_copy = json.loads(json.dumps(project, ensure_ascii=False))
    record = _load_project_media_index(project_id).get(rel_key)
    if not record:
        raise HTTPException(status_code=404, detail="Roteiro persistido não encontrado.")
    stored_file = Path(str(record.get("file") or "")).name
    candidate = _project_media_dir(project_id) / stored_file
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Arquivo de roteiro não está acessível.")
    try:
        subtitle_paths = _project_media_paths_by_kind(project_copy, "texts", limit=1)
        srt_cues = parse_srt_file(subtitle_paths[0]) if subtitle_paths else []
        plan = analyze_script_guide(candidate, project_id=project_id, rel=rel_key, srt_cues=srt_cues)
        _script_guide_dir(project_id).mkdir(parents=True, exist_ok=True)
        atomic_write_text(_script_guide_plan_path(project_id), json.dumps(plan, ensure_ascii=False, indent=2))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    info = {
        "name": Path(rel_key).name,
        "rel": rel_key,
        "format": candidate.suffix.lower().lstrip("."),
        "blocks": int(plan.get("summary", {}).get("blocks") or 0),
        "confidence": float(plan.get("summary", {}).get("avg_confidence") or 0.0),
        "warnings": list(plan.get("warnings") or []),
        "updatedAt": _now_iso(),
    }
    with QUEUE_LOCK:
        project = _find_queue_project(project_id)
        if project:
            media = project.get("media") if isinstance(project.get("media"), dict) else {}
            media["script_guides"] = [rel_key]
            project["media"] = media
            project["scriptGuideInfo"] = info
            project["scriptGuidePlan"] = plan
            project["updatedAt"] = _now_iso()
            _save_queue_projects(QUEUE_PROJECTS)
    return {"ok": True, "info": info, "plan": plan}


@app.get("/api/queue/backup")
def queue_backup():
    with QUEUE_LOCK:
        return {
            "kind": "glide_ultra_queue_backup",
            "version": APP_VERSION,
            "createdAt": _now_iso(),
            "store": str(QUEUE_PROJECTS_FILE),
            "mergePolicy": "same id updates, missing ids are added, existing projects are preserved",
            "projects": [_public_queue_project(item) for item in QUEUE_PROJECTS],
        }


@app.post("/api/queue/backup/import")
def queue_import_backup(payload: dict[str, Any] | None = Body(None)):
    data = payload or {}
    raw_projects = data.get("projects")
    if not isinstance(raw_projects, list):
        raise HTTPException(status_code=400, detail="Backup invalido: lista de projetos ausente")
    imported = 0
    updated = 0
    added = 0
    with QUEUE_LOCK:
        by_id = {str(item.get("id")): item for item in QUEUE_PROJECTS if item.get("id")}
        for index, raw in enumerate(raw_projects):
            if not isinstance(raw, dict):
                continue
            restored = _sanitize_queue_project_backup(raw, index)
            project_id = str(restored.get("id") or "")
            if not project_id:
                continue
            imported += 1
            existing = by_id.get(project_id)
            if existing:
                existing.clear()
                existing.update(restored)
                updated += 1
            else:
                QUEUE_PROJECTS.append(restored)
                by_id[project_id] = restored
                added += 1
        _save_queue_projects(QUEUE_PROJECTS)
        return {
            "ok": True,
            "imported": imported,
            "updated": updated,
            "added": added,
            "projects": [_public_queue_project(item) for item in QUEUE_PROJECTS],
        }


@app.get("/api/queue/status")
def queue_status():
    active_jobs = [job for job in JOBS.values() if job.status in {"uploading", "ready", "running"}]
    with QUEUE_LOCK:
        projects = [_public_queue_project(item) for item in QUEUE_PROJECTS]
    return {
        "projects": projects,
        "active_jobs": [
            {
                "id": job.id,
                "status": job.status,
                "percent": round(job.percent, 1),
                "output_dir": job.output_dir,
                "project_id": job.options.get("queueProjectId"),
                "batch_id": job.options.get("queueBatchId"),
            }
            for job in active_jobs
        ],
        "sequential": True,
    }


@app.post("/api/settings/save")
def api_save_settings(payload: dict[str, Any] | None = Body(None)):
    data = payload or {}
    project_id = str(data.get("projectId") or "").strip()
    saved_project = None
    global_settings = data.get("global") if isinstance(data.get("global"), dict) else None
    with QUEUE_LOCK:
        project = _find_queue_project(project_id) if project_id else None
        if project:
            if isinstance(data.get("name"), str) and data.get("name", "").strip():
                project["name"] = str(data["name"]).strip()[:80]
            if isinstance(data.get("options"), dict):
                options = project.get("options") if isinstance(project.get("options"), dict) else {}
                options.update(data["options"])
                options["directorDecisionMode"] = _normalized_director_decision_mode(options)
                options["healthyRenderThreshold"] = _healthy_threshold(options)
                options["platformMasterProfile"] = str(options.get("platformMasterProfile") or "youtube_long")
                project["options"] = options
            if str(data.get("musicGenre") or "").lower() in PRESET_MUSIC_GENRES:
                project["musicGenre"] = str(data["musicGenre"]).lower()
            if isinstance(data.get("subtitleInfo"), dict) or data.get("subtitleInfo") is None:
                project["subtitleInfo"] = data.get("subtitleInfo")
            if isinstance(data.get("captionInfo"), dict) or data.get("captionInfo") is None:
                project["captionInfo"] = data.get("captionInfo")
            if isinstance(data.get("scriptGuideInfo"), dict) or data.get("scriptGuideInfo") is None:
                project["scriptGuideInfo"] = data.get("scriptGuideInfo")
            if isinstance(data.get("scriptGuidePlan"), dict) or data.get("scriptGuidePlan") is None:
                project["scriptGuidePlan"] = data.get("scriptGuidePlan")
            project["updatedAt"] = _now_iso()
            _save_queue_projects(QUEUE_PROJECTS)
            saved_project = _public_queue_project(project)
    if global_settings is not None:
        existing = _load_app_settings()
        existing["global"] = {
            **(existing.get("global") if isinstance(existing.get("global"), dict) else {}),
            **global_settings,
        }
        _save_app_settings(existing)
    return {
        "ok": True,
        "savedAt": _now_iso(),
        "project": saved_project,
        "message": "Configurações salvas",
    }


@app.post("/api/queue/preflight-plan")
def queue_preflight_plan(payload: dict[str, Any] | None = Body(None)):
    data = payload or {}
    mode = str(data.get("mode") or "all").lower().strip()
    if mode not in {"all", "healthy", "selected"}:
        mode = "all"
    project_ids = [str(item) for item in (data.get("projectIds") or []) if str(item).strip()]
    plan = build_queue_preflight_plan(project_ids, mode)
    try:
        EXPORT_ROOT.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            EXPORT_ROOT / "queue_preflight_plan.json",
            json.dumps(plan, ensure_ascii=False, indent=2),
        )
    except Exception:
        pass
    return {"ok": True, "plan": plan}


@app.post("/api/queue/projects/prepare-healthy")
def queue_prepare_healthy_projects(payload: dict[str, Any] | None = Body(None)):
    data = payload or {}
    project_ids = [str(item) for item in (data.get("projectIds") or []) if str(item).strip()]
    plan = build_queue_preflight_plan(project_ids, "healthy")
    retryable = [str(item.get("id")) for item in plan.get("projects", []) if item.get("renderable")]
    skipped = [
        {"id": item.get("id"), "reason": "; ".join(item.get("ignoredReasons") or []) or "nao saudavel"}
        for item in plan.get("projects", [])
        if not item.get("renderable")
    ]
    with QUEUE_LOCK:
        retry_set = set(retryable)
        for project in QUEUE_PROJECTS:
            if str(project.get("id") or "") not in retry_set:
                continue
            if str(project.get("status") or "") in {"done", "recovered", "error", "cancelled", "paused"}:
                project["status"] = "ready"
                project["error"] = None
                project["jobId"] = None
                project["updatedAt"] = _now_iso()
        if retryable:
            _save_queue_projects(QUEUE_PROJECTS)
        return {
            "ok": True,
            "retryable": retryable,
            "skipped": skipped,
            "plan": plan,
            "projects": [_public_queue_project(item) for item in QUEUE_PROJECTS],
        }


@app.get("/api/storage/space-report")
def api_space_report():
    report = _space_report()
    try:
        EXPORT_ROOT.mkdir(parents=True, exist_ok=True)
        atomic_write_text(EXPORT_ROOT / "space_report.json", json.dumps(report, ensure_ascii=False, indent=2))
    except Exception:
        pass
    return report


@app.post("/api/storage/clean")
def api_storage_clean(payload: dict[str, Any] | None = Body(None)):
    data = payload or {}
    action = str(data.get("action") or "temporaries").strip().lower()
    summary = {"action": action, "removed": 0, "bytes_recovered": 0, "errors": []}
    if any(job.status in {"ready", "running"} for job in JOBS.values()):
        raise HTTPException(
            status_code=409,
            detail="A limpeza de espaco fica bloqueada durante render ativo para proteger midias temporarias.",
        )

    def remove_inside(path: Path, bucket: str):
        nonlocal summary
        try:
            resolved = _maintenance_safe_child(path)
            if not resolved:
                summary["errors"].append(f"{bucket}: categoria protegida")
                return
            if not resolved.exists():
                return
            summary["bytes_recovered"] += path_size(resolved)
            if resolved.is_dir():
                shutil.rmtree(resolved)
            else:
                resolved.unlink(missing_ok=True)
            summary["removed"] += 1
        except Exception as exc:
            summary["errors"].append(f"{bucket}: {exc}")

    if action in {"temporaries", "clear_temporaries"}:
        for path in (UPLOAD_ROOT, CTA_CACHE_ROOT / "tmp"):
            remove_inside(path, path.name)
    elif action in {"old_cache", "clear_old_cache"}:
        cleanup = RenderGraph(RENDER_GRAPH_CACHE_ROOT, INTELLIGENCE_DB, APP_VERSION, "storage-clean").cleanup(force=False)
        summary["removed"] += int(cleanup.get("removed") or 0)
        summary["bytes_recovered"] += int(cleanup.get("reclaimed_bytes") or 0)
    elif action in {"old_exports", "clear_old_exports"}:
        cutoff = time.time() - 14 * 24 * 60 * 60
        for child in EXPORT_ROOT.iterdir() if EXPORT_ROOT.exists() else []:
            try:
                if child.stat().st_mtime < cutoff and child.name.lower().startswith(("batch_", "render_")):
                    remove_inside(child, child.name)
            except Exception as exc:
                summary["errors"].append(f"{child.name}: {exc}")
    elif action in {"old_logs", "clear_old_logs"}:
        for path in _safe_old_log_files():
            try:
                summary["bytes_recovered"] += path.stat().st_size
                path.unlink(missing_ok=True)
                summary["removed"] += 1
            except Exception as exc:
                summary["errors"].append(f"{path.name}: {exc}")
    else:
        raise HTTPException(status_code=400, detail="Acao de limpeza desconhecida")

    report = _space_report()
    return {
        "ok": True,
        "summary": {
            **summary,
            "space_recovered": human_bytes(int(summary.get("bytes_recovered") or 0)),
        },
        "space": report,
    }


@app.post("/api/queue/batch-report")
def queue_save_batch_report(payload: dict[str, Any] | None = Body(None)):
    data = payload or {}
    batch_id = safe_folder_component(str(data.get("batchId") or ""), f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    raw_projects = data.get("projects")
    projects = raw_projects if isinstance(raw_projects, list) else []
    report = {
        "kind": "glide_ultra_batch_report",
        "version": APP_VERSION,
        "batchId": batch_id,
        "createdAt": _now_iso(),
        "renderMode": str(data.get("renderMode") or "balanced"),
        "summary": data.get("summary") if isinstance(data.get("summary"), dict) else {},
        "projects": [item for item in projects if isinstance(item, dict)],
    }
    saved_paths: list[str] = []
    technical_dir = EXPORT_ROOT / batch_id
    technical_dir.mkdir(parents=True, exist_ok=True)
    technical_path = technical_dir / "batch_report.json"
    technical_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    saved_paths.append(str(technical_path))

    output_dirs = []
    for raw in data.get("outputDirs") or []:
        try:
            folder = Path(str(raw)).expanduser().resolve()
        except Exception:
            continue
        if folder.is_dir() and folder not in output_dirs:
            output_dirs.append(folder)
    if output_dirs:
        try:
            common_dir = Path(os.path.commonpath([str(folder) for folder in output_dirs]))
            if common_dir.is_dir():
                delivery_path = common_dir / f"{batch_id}_report.json"
                if delivery_path.resolve() != technical_path.resolve():
                    delivery_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                    saved_paths.append(str(delivery_path))
        except Exception:
            pass
    return {"ok": True, "report": report, "savedPaths": saved_paths}


@app.post("/api/queue/projects")
def queue_create_project(payload: dict[str, Any] | None = Body(None)):
    data = payload or {}
    with QUEUE_LOCK:
        project = _default_queue_project(str(data.get("name") or ""))
        if isinstance(data.get("options"), dict):
            project["options"] = data["options"]
        if isinstance(data.get("subtitleInfo"), dict) or data.get("subtitleInfo") is None:
            project["subtitleInfo"] = data.get("subtitleInfo")
        if isinstance(data.get("captionInfo"), dict) or data.get("captionInfo") is None:
            project["captionInfo"] = data.get("captionInfo")
        if str(data.get("musicGenre") or "").lower() in PRESET_MUSIC_GENRES:
            project["musicGenre"] = str(data["musicGenre"]).lower()
        QUEUE_PROJECTS.append(project)
        _save_queue_projects(QUEUE_PROJECTS)
        return {"project": _public_queue_project(project), "projects": [_public_queue_project(item) for item in QUEUE_PROJECTS]}


@app.post("/api/queue/projects/reorder")
def queue_reorder_projects(payload: dict[str, Any] | None = Body(None)):
    data = payload or {}
    raw_order = data.get("order")
    if not isinstance(raw_order, list):
        raise HTTPException(status_code=400, detail="Envie a lista 'order' com os IDs dos projetos")
    with QUEUE_LOCK:
        return _reorder_queue_projects([str(item) for item in raw_order])


@app.post("/api/queue/projects/retry-failed")
def queue_retry_failed_projects(payload: dict[str, Any] | None = Body(None)):
    data = payload or {}
    requested_ids = {
        str(item).strip()
        for item in (data.get("projectIds") or [])
        if str(item).strip()
    }
    retryable: list[str] = []
    skipped: list[dict[str, Any]] = []
    with QUEUE_LOCK:
        for project in QUEUE_PROJECTS:
            project_id = str(project.get("id") or "")
            if requested_ids and project_id not in requested_ids:
                continue
            if str(project.get("status") or "") != "error":
                continue
            job_id = str(project.get("jobId") or "")
            active_job = JOBS.get(job_id) if job_id else None
            if active_job and active_job.status in {"uploading", "ready", "running"}:
                skipped.append({"id": project_id, "reason": "render ainda ativo"})
                continue
            missing = _queue_project_missing_requirements(project)
            if missing:
                skipped.append({
                    "id": project_id,
                    "reason": f"faltam {', '.join(missing)}",
                })
                continue
            history = list(project.get("retryHistory") or [])
            history.append({
                "requestedAt": _now_iso(),
                "failedJobId": job_id or None,
                "error": str(project.get("error") or "")[:1200],
            })
            project["retryHistory"] = history[-12:]
            project["retryCount"] = int(project.get("retryCount") or 0) + 1
            project["status"] = "ready"
            project["error"] = None
            project["updatedAt"] = _now_iso()
            retryable.append(project_id)
        if retryable:
            _save_queue_projects(QUEUE_PROJECTS)
        return {
            "ok": True,
            "retryable": retryable,
            "skipped": skipped,
            "projects": [_public_queue_project(item) for item in QUEUE_PROJECTS],
        }


@app.post("/api/queue/projects/prepare-rerender")
def queue_prepare_rerender_projects(payload: dict[str, Any] | None = Body(None)):
    data = payload or {}
    mode = str(data.get("mode") or "all").lower().strip()
    if mode not in {"all", "selected"}:
        mode = "all"
    requested_ids = {
        str(item).strip()
        for item in (data.get("projectIds") or [])
        if str(item).strip()
    }
    retryable: list[str] = []
    skipped: list[dict[str, Any]] = []
    with QUEUE_LOCK:
        for project in QUEUE_PROJECTS:
            project_id = str(project.get("id") or "")
            if mode == "selected" and project_id not in requested_ids:
                continue
            job_id = str(project.get("jobId") or "")
            active_job = JOBS.get(job_id) if job_id else None
            if active_job and active_job.status in {"uploading", "ready", "running"}:
                skipped.append({"id": project_id, "reason": "render ainda ativo"})
                continue
            missing = _queue_project_missing_requirements(project)
            if missing:
                skipped.append({"id": project_id, "reason": f"faltam {', '.join(missing)}"})
                continue
            history = list(project.get("retryHistory") or [])
            history.append({
                "requestedAt": _now_iso(),
                "previousJobId": job_id or None,
                "previousStatus": str(project.get("status") or ""),
                "mode": mode,
            })
            project["retryHistory"] = history[-12:]
            project["retryCount"] = int(project.get("retryCount") or 0) + 1
            project["status"] = "ready"
            project["error"] = None
            project["jobId"] = None
            project["updatedAt"] = _now_iso()
            retryable.append(project_id)
        if retryable:
            _save_queue_projects(QUEUE_PROJECTS)
        return {
            "ok": True,
            "retryable": retryable,
            "skipped": skipped,
            "projects": [_public_queue_project(item) for item in QUEUE_PROJECTS],
        }


@app.post("/api/queue/projects/{project_id}/snapshot")
def queue_snapshot_project(project_id: str, payload: dict[str, Any] | None = Body(None)):
    data = payload or {}
    with QUEUE_LOCK:
        project = _find_queue_project(project_id)
        if not project:
            project = _default_queue_project(str(data.get("name") or "Projeto"))
            project["id"] = safe_folder_component(project_id, uuid.uuid4().hex[:10])[:40]
            QUEUE_PROJECTS.append(project)
        for key in (
            "name", "status", "outputName", "outputFile", "outputDir", "jobId",
            "error", "estimatedSize", "lastRenderSummary", "directorState",
            "timelineHistory", "confidenceSummary", "audioMasterSummary", "renderGraphRun",
            "retryCount", "retryHistory",
        ):
            if key in data:
                project[key] = data[key]
        if isinstance(data.get("media"), dict):
            media = data["media"]
            project["media"] = {
                "videos": list(media.get("videos") or []),
                "audios": list(media.get("audios") or []),
                "background_music": list(media.get("background_music") or []),
                "texts": list(media.get("texts") or media.get("subtitles") or []),
                "captions": list(media.get("captions") or []),
            }
        if isinstance(data.get("options"), dict):
            project["options"] = data["options"]
        if isinstance(project.get("referenceStyleVideo"), dict):
            project.setdefault("options", {})["referenceStyleVideo"] = project["referenceStyleVideo"]
        if str(data.get("musicGenre") or "").lower() in PRESET_MUSIC_GENRES:
            project["musicGenre"] = str(data["musicGenre"]).lower()
        if isinstance(data.get("subtitleInfo"), dict) or data.get("subtitleInfo") is None:
            project["subtitleInfo"] = data.get("subtitleInfo")
        if isinstance(data.get("captionInfo"), dict) or data.get("captionInfo") is None:
            project["captionInfo"] = data.get("captionInfo")
        project["updatedAt"] = _now_iso()
        _save_queue_projects(QUEUE_PROJECTS)
        return {"project": _public_queue_project(project)}


@app.post("/api/queue/projects/{project_id}/reference-style")
async def queue_upload_reference_style(project_id: str, file: UploadFile = File(...)):
    filename = safe_name(file.filename or "referencia.mp4")
    ext = Path(filename).suffix.lower()
    if ext not in VIDEO_EXTS:
        raise HTTPException(status_code=400, detail="Envie um video de referencia valido (.mp4, .mov, .mkv, .webm...).")
    with QUEUE_LOCK:
        project = _find_queue_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto da fila nao encontrado.")
    ref_dir = _reference_style_dir(project_id)
    ref_dir.mkdir(parents=True, exist_ok=True)
    for old in ref_dir.glob("reference.*"):
        try:
            old.unlink()
        except Exception:
            pass
    target = ref_dir / f"reference{ext}"
    tmp = ref_dir / f".reference-{uuid.uuid4().hex}{ext}.tmp"
    try:
        with tmp.open("wb") as handle:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
    meta = {
        "name": filename,
        "path": str(target),
        "size": target.stat().st_size if target.exists() else 0,
        "updatedAt": _now_iso(),
        "analyzedAt": None,
        "styleDna": None,
    }
    with QUEUE_LOCK:
        project = _find_queue_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto da fila nao encontrado.")
        options = project.get("options") if isinstance(project.get("options"), dict) else {}
        options.update({
            "referenceStyleVideo": meta,
            "referenceStyleEnabled": True,
            "styleSource": "reference_dna",
            "referenceStyleMode": normalized_reference_style_mode(options),
        })
        project["options"] = options
        project["referenceStyleVideo"] = meta
        project["updatedAt"] = _now_iso()
        _save_queue_projects(QUEUE_PROJECTS)
        return {"ok": True, "referenceStyleVideo": _public_reference_style(meta), "project": _public_queue_project(project)}


@app.post("/api/queue/projects/{project_id}/reference-style/analyze")
def queue_analyze_reference_style(project_id: str):
    with QUEUE_LOCK:
        project = _find_queue_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto da fila nao encontrado.")
        meta = project.get("referenceStyleVideo") if isinstance(project.get("referenceStyleVideo"), dict) else None
    if not meta:
        raise HTTPException(status_code=409, detail="Nenhum video referencia anexado neste projeto.")
    path = Path(str(meta.get("path") or ""))
    try:
        resolved = path.resolve()
        root = _reference_style_dir(project_id).resolve()
        if root not in resolved.parents or not resolved.exists():
            raise ValueError("referencia ausente")
    except Exception:
        raise HTTPException(status_code=404, detail="Arquivo de referencia nao encontrado. Substitua a referencia.")
    dna = analyze_reference_style_video(project_id, resolved, str(meta.get("name") or resolved.name))
    with QUEUE_LOCK:
        project = _find_queue_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto da fila nao encontrado.")
        meta = dict(project.get("referenceStyleVideo") or {})
        meta["styleDna"] = dna
        meta["analyzedAt"] = dna.get("analyzedAt")
        project["referenceStyleVideo"] = meta
        options = project.get("options") if isinstance(project.get("options"), dict) else {}
        options.update({
            "referenceStyleVideo": meta,
            "referenceStyleEnabled": True,
            "styleSource": "reference_dna",
            "referenceStyleMode": normalized_reference_style_mode(options),
        })
        if not options.get("visualLanguagePackage"):
            options["visualLanguagePackage"] = (dna.get("recommendations") or {}).get("visualLanguagePackage") or "dark_doc"
        project["options"] = options
        project["updatedAt"] = _now_iso()
        _save_queue_projects(QUEUE_PROJECTS)
        return {"ok": True, "styleDna": dna, "referenceStyleVideo": _public_reference_style(meta), "project": _public_queue_project(project)}


@app.delete("/api/queue/projects/{project_id}/reference-style")
def queue_delete_reference_style(project_id: str):
    with QUEUE_LOCK:
        project = _find_queue_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto da fila nao encontrado.")
        shutil.rmtree(_reference_style_dir(project_id), ignore_errors=True)
        project["referenceStyleVideo"] = None
        options = project.get("options") if isinstance(project.get("options"), dict) else {}
        options.update({
            "referenceStyleVideo": None,
            "referenceStyleEnabled": False,
            "styleSource": "glide_package",
            "referenceStyleMode": normalized_reference_style_mode(options),
        })
        project["options"] = options
        project["updatedAt"] = _now_iso()
        _save_queue_projects(QUEUE_PROJECTS)
        return {"ok": True, "project": _public_queue_project(project)}


@app.post("/api/queue/projects/{project_id}/post-render-correction")
def queue_apply_post_render_correction(project_id: str, payload: dict[str, Any] | None = Body(None)):
    raise HTTPException(
        status_code=410,
        detail="Correções pós-render baseadas em Premium Feel foram removidas no Glide Studio v1.28.",
    )


@app.post("/api/queue/projects/{project_id}/duplicate")
def queue_duplicate_project(project_id: str):
    with QUEUE_LOCK:
        source = _find_queue_project(project_id)
        if not source:
            raise HTTPException(status_code=404, detail="Projeto da fila nao encontrado")
        clone = json.loads(json.dumps(_public_queue_project(source), ensure_ascii=False))
        clone["id"] = uuid.uuid4().hex[:10]
        clone["name"] = f"{clone.get('name') or 'Projeto'} copia"[:80]
        clone["status"] = "draft"
        clone["jobId"] = None
        clone["outputFile"] = None
        clone["outputDir"] = None
        clone["error"] = None
        if isinstance(source.get("referenceStyleVideo"), dict):
            ref_meta = json.loads(json.dumps(source["referenceStyleVideo"], ensure_ascii=False))
            source_path = Path(str(ref_meta.get("path") or ""))
            if source_path.exists():
                clone_ref_dir = _reference_style_dir(str(clone["id"]))
                clone_ref_dir.mkdir(parents=True, exist_ok=True)
                clone_path = clone_ref_dir / source_path.name
                try:
                    shutil.copy2(source_path, clone_path)
                    ref_meta["path"] = str(clone_path)
                except Exception:
                    pass
            clone["referenceStyleVideo"] = ref_meta
            if isinstance(clone.get("options"), dict):
                clone["options"]["referenceStyleVideo"] = ref_meta
        clone["createdAt"] = _now_iso()
        clone["updatedAt"] = _now_iso()
        QUEUE_PROJECTS.append(clone)
        _save_queue_projects(QUEUE_PROJECTS)
        return {"project": _public_queue_project(clone), "projects": [_public_queue_project(item) for item in QUEUE_PROJECTS]}


@app.delete("/api/queue/projects/{project_id}")
def queue_delete_project(project_id: str):
    with QUEUE_LOCK:
        project = _find_queue_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto da fila nao encontrado")
        storage = _clear_queue_project_storage(project)
        before = len(QUEUE_PROJECTS)
        QUEUE_PROJECTS[:] = [item for item in QUEUE_PROJECTS if item.get("id") != project_id]
        if len(QUEUE_PROJECTS) == before:
            raise HTTPException(status_code=404, detail="Projeto da fila nao encontrado")
        _save_queue_projects(QUEUE_PROJECTS)
        return {"ok": True, "storage": storage, "projects": [_public_queue_project(item) for item in QUEUE_PROJECTS]}


@app.post("/api/queue/projects/{project_id}/clear-media")
def queue_clear_project_media(project_id: str):
    with QUEUE_LOCK:
        project = _find_queue_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto da fila nao encontrado")
        storage = _clear_queue_project_storage(project)
        _reset_queue_project_runtime(project)
        _save_queue_projects(QUEUE_PROJECTS)
        return {
            "ok": True,
            "storage": storage,
            "space_recovered": human_bytes(int(storage.get("bytes_recovered") or 0)),
            "project": _public_queue_project(project),
        }


@app.post("/api/queue/projects/clear-all-media")
def queue_clear_all_project_media():
    with QUEUE_LOCK:
        active = []
        for project in QUEUE_PROJECTS:
            job_id = str(project.get("jobId") or "")
            job = JOBS.get(job_id) if job_id else None
            if job and job.status in {"uploading", "ready", "running"}:
                active.append(str(project.get("name") or project.get("id") or "projeto"))
        if active:
            raise HTTPException(status_code=409, detail=f"Render ativo em: {', '.join(active[:3])}")
        total_removed = 0
        total_recovered = 0
        errors: list[str] = []
        for project in QUEUE_PROJECTS:
            try:
                storage = _clear_queue_project_storage(project)
                total_removed += int(storage.get("removed") or 0)
                total_recovered += int(storage.get("bytes_recovered") or 0)
                errors.extend(str(item) for item in (storage.get("errors") or []) if str(item).strip())
            finally:
                _reset_queue_project_runtime(project)
        _save_queue_projects(QUEUE_PROJECTS)
        return {
            "ok": True,
            "storage": {
                "removed": total_removed,
                "bytes_recovered": total_recovered,
                "errors": errors[-20:],
            },
            "space_recovered": human_bytes(total_recovered),
            "projects": [_public_queue_project(item) for item in QUEUE_PROJECTS],
        }


@app.get("/api/renders")
def render_gallery():
    renders: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_render(path: Path, batch: str | None = None):
        try:
            if not path.exists() or not path.is_file():
                return
            resolved = str(path.resolve())
            if resolved in seen:
                return
            seen.add(resolved)
            stat = path.stat()
            parent = path.parent
            report = parent / "relatorio_render.txt"
            renders.append({
                "name": path.name,
                "path": str(path),
                "output_dir": str(parent),
                "size": stat.st_size,
                "size_label": human_bytes(stat.st_size),
                "modified_at": stat.st_mtime,
                "download": None,
                "has_report": report.exists(),
                "batch": batch,
            })
        except Exception:
            pass

    for job in JOBS.values():
        if job.output:
            add_render(Path(job.output), job.options.get("queueBatchId") or None)
    with QUEUE_LOCK:
        stored_projects = list(QUEUE_PROJECTS)
    for project in stored_projects:
        output_dir = str(project.get("outputDir") or "")
        output_file = str(project.get("outputFile") or "")
        if output_dir and output_file:
            add_render(Path(output_dir) / output_file, None)
    for path in EXPORT_ROOT.rglob("*.mp4"):
        add_render(path, path.parent.parent.name if path.parent.parent != EXPORT_ROOT else None)
    renders.sort(key=lambda item: item["modified_at"], reverse=True)
    return {"exports": str(EXPORT_ROOT), "items": renders[:120]}


def mix_auto_sound_fx(job: Job, base_audio: Path, audio_total: float, work: Path, segments: list[Path]) -> Path:
    if not auto_sound_fx_enabled(job.options):
        job.sound_fx_summary = {"enabled": False, "reason": "desativado"}
        return base_audio
    events = build_auto_sfx_events(job, audio_total, segments, work)
    if not events:
        job.sound_fx_summary = {"enabled": False, "reason": "sem eventos adequados"}
        return base_audio
    sfx_dir = work / "sound_fx"
    sfx_dir.mkdir(exist_ok=True)
    prepared: list[tuple[dict[str, Any], Path]] = []
    sources = {"asset": 0, "procedural": 0}
    failed = 0
    for idx, event in enumerate(events, start=1):
        out = sfx_dir / f"sfx_{idx:03d}_{safe_video_basename(event['effect']) or 'fx'}.wav"
        try:
            clip, source = make_sfx_clip(event, out, work)
            if clip.exists() and clip.stat().st_size > 0:
                prepared.append((event, clip))
                sources[source] = sources.get(source, 0) + 1
        except Exception:
            failed += 1
    if not prepared:
        job.sound_fx_summary = {"enabled": False, "reason": "geracao dos efeitos falhou", "attempted_events": len(events)}
        _append_log(job, "Sound FX automatico ignorado: nenhum efeito conseguiu ser preparado.")
        return base_audio

    out = Path("glide_audio_with_sound_fx.wav")
    cmd: list[str] = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-filter_threads", "1", "-filter_complex_threads", "1"]
    base_arg = str(base_audio.relative_to(work)) if base_audio.is_absolute() and base_audio.is_relative_to(work) else str(base_audio)
    cmd += ["-i", base_arg]
    mix_engine = "pcm_s16le_event_bed"
    try:
        sfx_bed = build_pcm_sfx_event_bed(prepared, audio_total, work)
        cmd += ["-i", sfx_bed.name]
        filters = [
            "[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,asplit=2[base][voice_ref]",
            "[1:a]atrim=0:"
            f"{audio_total:.4f},asetpts=PTS-STARTPTS,"
            "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[fxmix]",
        ]
    except Exception as exc:
        mix_engine = "ffmpeg_multi_input_fallback"
        _append_log(job, f"Faixa unica de FX indisponivel; usando fallback compativel ({human_render_error(exc)}).")
        for _, clip in prepared:
            clip_arg = str(clip.relative_to(work)) if clip.is_absolute() and clip.is_relative_to(work) else str(clip)
            cmd += ["-i", clip_arg]
        filters = ["[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,asplit=2[base][voice_ref]"]
        labels: list[str] = []
        for idx, (event, _) in enumerate(prepared, start=1):
            delay = max(0, int(round(float(event["time"]) * 1000)))
            dur = max(0.08, min(3.5, float(event.get("duration") or 0.45)))
            label = f"fx{idx}"
            filters.append(
                f"[{idx}:a]atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,"
                f"adelay={delay}|{delay},aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[{label}]"
            )
            labels.append(f"[{label}]")
        filters.append("".join(labels) + f"amix=inputs={len(labels)}:duration=longest:dropout_transition=0:normalize=0[fxmix]")
    # Keep FX clearly audible without letting short transients compete with narration.
    # The old compressor attenuated the FX bus too aggressively under a normalized voice.
    filters.append("[fxmix]highpass=f=55,lowpass=f=15000[fxclean]")
    filters.append("[fxclean][voice_ref]sidechaincompress=threshold=0.16:ratio=1.32:attack=2:release=110:makeup=1.06,volume=0.70dB[fxduck]")
    filters.append("[base][fxduck]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.93:attack=5:release=55[aout]")
    script = work / "sound_fx_mix_filter.txt"
    script.write_text(";".join(filters), encoding="utf-8")
    cmd += [
        "-filter_complex_script", script.name,
        "-map", "[aout]",
        "-t", f"{audio_total:.4f}",
        "-ac", "2", "-ar", "48000",
        out.name,
    ]

    counts: dict[str, int] = {}
    for event, _ in prepared:
        counts[event["reason"]] = counts.get(event["reason"], 0) + 1
    try:
        set_stage(job, "audio", "Sound design automatico", "Aplicando efeitos sonoros cinematicos discretos")
        run_cmd(job, cmd, total_duration=audio_total or None, base=93, span=1.5, cwd=work, quiet_success=True)
    except Exception as exc:
        job.sound_fx_summary = {
            "enabled": False,
            "reason": "mixagem dos efeitos falhou; render continuou sem FX",
            "error": str(exc)[-500:],
            "attempted_events": len(events),
        }
        _append_log(job, "Sound FX automatico falhou e foi ignorado para preservar o render.")
        return base_audio

    job.sound_fx_summary = {
        "enabled": True,
        "events": len(prepared),
        "skipped_events": failed + max(0, len(events) - len(prepared) - failed),
        "intro_events": counts.get("intro", 0) + counts.get("intro_text", 0),
        "subtitle_events": counts.get("subtitle", 0),
        "transition_events": counts.get("transition", 0),
        "image_events": counts.get("image_event", 0) + counts.get("image_motion", 0),
        "motion_graphic_events": counts.get("motion_graphic", 0),
        "cut_events": counts.get("cut_event", 0),
        "camera_motion_events": counts.get("camera_motion", 0),
        "strong_moment_events": counts.get("strong_moment", 0),
        "volume_range_db": [AUTO_SFX_MIN_DB, AUTO_SFX_MAX_DB],
        "ducking": True,
        "mix_profile": "measured_peak_frame_anchored_professional",
        "mix_engine": mix_engine,
        "scope": "srt_text_image_motion_graphics_selected_transitions_camera_cuts",
        "transition_density": "reference_aware_default_38_percent_min_7s",
        "sync_target_ms": 33,
        "asset_events": sources.get("asset", 0),
        "procedural_events": sources.get("procedural", 0),
    }
    if job.export_dir:
        try:
            write_sound_design_map(job.export_dir, [event for event, _ in prepared], job.sound_fx_summary)
        except Exception:
            pass
    _append_log(job, (
        f"Sound FX automatico: {len(prepared)} efeito(s) imersivos | "
        f"intro={job.sound_fx_summary['intro_events']} | srt={job.sound_fx_summary['subtitle_events']} | "
        f"transições={job.sound_fx_summary['transition_events']} | "
        f"volume {AUTO_SFX_MIN_DB:.0f} a {AUTO_SFX_MAX_DB:.0f} dB com ducking."
    ))
    _append_log(job, f"Sound design otimizado: motor={mix_engine}, alinhamento=48 kHz.")
    return out


def encoder_choice(job: Job, label: str, args: list[str]) -> list[str]:
    if not job.encoder_logged:
        profile = "Turbo Produção, priorizando velocidade" if turbo_enabled(job) else "equilibrado para velocidade, memória e qualidade"
        _append_log(job, f"Encoder selecionado: {label}. Perfil {profile}.")
        job.encoder_logged = True
    return args


def clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(float(value))
    except Exception:
        parsed = default
    return max(minimum, min(maximum, parsed))


def export_bitrate_settings(mode: str, codec: str, options: dict[str, Any]) -> dict[str, Any]:
    mode = (mode or "standard").lower()
    codec = (codec or "hevc").lower()
    profile = str(options.get("exportProfile") or "capcut_compact")
    fast = mode == "fast"
    use_hevc = codec != "h264"

    defaults = {
        "small_file": {
            "hevc": (1100 if fast else 1900),
            "h264": (1700 if fast else 2800),
        },
        "capcut_compact": {
            "hevc": (1500 if fast else 2500),
            "h264": (2200 if fast else 3600),
        },
        "youtube_compact": {
            "hevc": (1800 if fast else 2800),
            "h264": (2500 if fast else 4000),
        },
        "balanced": {
            "hevc": (2200 if fast else 3500),
            "h264": (3000 if fast else 4800),
        },
        "high_quality": {
            "hevc": (3000 if fast else 5200),
            "h264": (4200 if fast else 6800),
        },
        "compatibility": {
            "hevc": (2200 if fast else 3600),
            "h264": (3200 if fast else 5200),
        },
    }
    key = "hevc" if use_hevc else "h264"
    fallback = defaults.get(profile, defaults["capcut_compact"])[key] if profile != "custom" else defaults["capcut_compact"][key]
    target = clamp_int(options.get("videoBitrateKbps"), fallback, 800, 14000) if profile == "custom" else fallback
    maxrate = int(round(target * (1.38 if use_hevc else 1.32)))
    bufsize = int(round(target * (2.75 if use_hevc else 2.5)))
    return {
        "profile": profile,
        "target": target,
        "maxrate": maxrate,
        "bufsize": bufsize,
        "rate_control": "vbr",
    }


def _choose_video_args_legacy(mode: str, codec: str, gpu: bool, job: Job) -> list[str]:
    mode = (mode or "standard").lower()
    use_hevc = (codec or "hevc").lower() != "h264"
    fast = mode == "fast"
    rate = export_bitrate_settings(mode, codec, job.options)
    target = f"{rate['target']}k"
    maxrate = f"{rate['maxrate']}k"
    bufsize = f"{rate['bufsize']}k"
    job.timeline_summary.update({
        "export_profile": rate["profile"],
        "video_bitrate_kbps": rate["target"],
        "rate_control": rate["rate_control"],
    })
    if not job.encoder_logged:
        _append_log(job, f"Preset de exportacao: {rate['profile']} | VBR alvo={target} | max={maxrate} | buffer={bufsize}.")

    if turbo_enabled(job):
        turbo = ensure_turbo_summary(job)
        job.timeline_summary.update({
            "codec_requested": turbo["codec_requested"],
            "codec_effective": turbo["codec_effective"],
            "encoder_effective": turbo["encoder_effective"],
            "turbo_policy": turbo["policy"],
        })
        if turbo["gpu_effective"]:
            encoder = str(turbo["encoder_effective"])
            if encoder.endswith("_nvenc"):
                args = [
                    "-c:v", encoder, "-preset", "p1", "-rc", "vbr",
                    "-b:v", target, "-maxrate", maxrate, "-bufsize", bufsize,
                ]
            elif encoder.endswith("_qsv"):
                args = [
                    "-c:v", encoder, "-preset", "veryfast",
                    "-b:v", target, "-maxrate", maxrate, "-bufsize", bufsize,
                ]
            else:
                args = [
                    "-c:v", encoder, "-quality", "speed",
                    "-b:v", target, "-maxrate", maxrate, "-bufsize", bufsize,
                ]
            if encoder.startswith("hevc_"):
                args += ["-tag:v", "hvc1"]
            return encoder_choice(job, f"Hardware {encoder.upper()} rapido", args)
        if turbo.get("codec_fallback") and not turbo.get("codec_fallback_logged"):
            _append_log(job, (
                "Turbo Produção: HEVC solicitado, mas NVENC HEVC não está disponível. "
                "Usando H.264 CPU ultrafast com a mesma resolução e bitrate alvo."
            ))
            turbo["codec_fallback_logged"] = True
        return encoder_choice(job, "CPU x264 H.264 ultrafast", [
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "fastdecode",
            "-b:v", target,
            "-maxrate", maxrate,
            "-bufsize", bufsize,
        ])

    balanced_auto_gpu = render_priority(job) == "balanced"
    if (gpu or balanced_auto_gpu) and use_hevc and encoder_available("hevc_nvenc"):
        job.timeline_summary["gpu_effective"] = True
        if balanced_auto_gpu and not gpu:
            _append_log(job, "Modo Eficiente: NVENC HEVC ativado automaticamente para acelerar sem remover recursos.")
        return encoder_choice(job, "NVIDIA NVENC HEVC p5", [
            "-c:v", "hevc_nvenc", "-preset", "p5", "-tag:v", "hvc1",
            "-rc", "vbr",
            "-spatial_aq", "1", "-temporal_aq", "1", "-rc-lookahead", "20",
            "-b:v", target,
            "-maxrate", maxrate,
            "-bufsize", bufsize,
        ])
    if (gpu or balanced_auto_gpu) and (not use_hevc) and encoder_available("h264_nvenc"):
        job.timeline_summary["gpu_effective"] = True
        if balanced_auto_gpu and not gpu:
            _append_log(job, "Modo Eficiente: NVENC H.264 ativado automaticamente para acelerar sem remover recursos.")
        return encoder_choice(job, "NVIDIA NVENC H.264 p5", [
            "-c:v", "h264_nvenc", "-preset", "p5",
            "-rc", "vbr",
            "-spatial_aq", "1", "-temporal_aq", "1", "-rc-lookahead", "20",
            "-b:v", target,
            "-maxrate", maxrate,
            "-bufsize", bufsize,
        ])
    if gpu and not job.encoder_logged:
        _append_log(job, "NVENC não disponível ou falhou na detecção: usando CPU automaticamente.")

    priority = render_priority(job)
    logical_cpus = max(2, int(os.cpu_count() or 4))
    balanced_threads = max(4, min(16, int(logical_cpus * 0.70)))
    cpu_threads = 1 if priority == "light" else (balanced_threads if priority == "balanced" else 0)
    cpu_thread_args = ["-threads", str(cpu_threads)] if cpu_threads else []
    x265_params = "log-level=error"
    if priority == "light":
        x265_params += ":pools=1:frame-threads=1"
    elif priority == "balanced":
        x265_params += f":pools={max(2, min(8, balanced_threads // 2))}:frame-threads={max(2, min(6, balanced_threads // 3))}"

    if use_hevc:
        # The balanced profile keeps all visual features while allowing enough parallelism
        # to avoid multi-hour encodes on ordinary desktop CPUs.
        return encoder_choice(job, "CPU x265 HEVC", [
            "-c:v", "libx265", "-preset", ("ultrafast" if fast else "veryfast"), "-tag:v", "hvc1",
            "-b:v", target,
            "-maxrate", maxrate,
            "-bufsize", bufsize,
            *cpu_thread_args,
            "-x265-params", x265_params,
        ])
    return encoder_choice(job, "CPU x264 H.264", [
        "-c:v", "libx264", "-preset", "veryfast",
        "-b:v", target,
        "-maxrate", maxrate,
        "-bufsize", bufsize,
        *cpu_thread_args,
    ])


def _choose_segment_video_args_legacy(mode: str, gpu: bool, job: Job, worker_count: int = 1) -> list[str]:
    """Fast high-quality intermediate used before the single final composition pass."""
    use_nvenc = encoder_available("h264_nvenc") and (
        bool(gpu) or turbo_enabled(job) or render_priority(job) == "balanced"
    )
    if use_nvenc:
        label = "H.264 NVENC p5" if not turbo_enabled(job) else "H.264 NVENC p1"
        args = [
            "-c:v", "h264_nvenc",
            "-preset", "p5" if not turbo_enabled(job) else "p1",
            "-rc", "constqp",
            "-qp", "16" if not turbo_enabled(job) else "20",
            *(["-spatial_aq", "1", "-temporal_aq", "1"] if not turbo_enabled(job) else []),
            "-g", "60",
        ]
    else:
        logical_cpus = max(2, int(os.cpu_count() or 4))
        total_budget = max(2, int(logical_cpus * 0.70))
        threads = max(2, min(12, total_budget // max(1, worker_count)))
        label = "H.264 CPU superfast"
        args = [
            "-c:v", "libx264",
            "-preset", "ultrafast" if turbo_enabled(job) else "superfast",
            "-crf", "20" if turbo_enabled(job) else "15",
            "-threads", str(threads),
            "-g", "60",
        ]
    if not job.timeline_summary.get("intermediate_encoder_logged"):
        _append_log(
            job,
            f"Pipeline otimizado: clipes processados em intermediário {label}; codec e bitrate finais aplicados uma única vez na composição.",
        )
        job.timeline_summary["intermediate_encoder"] = label
        job.timeline_summary["intermediate_encoder_logged"] = True
    return args


def choose_video_args(mode: str, codec: str, gpu: bool, job: Job) -> list[str]:
    mode = (mode or "standard").lower()
    use_hevc = (codec or "hevc").lower() != "h264"
    fast = mode == "fast"
    rate = export_bitrate_settings(mode, codec, job.options)
    target = f"{rate['target']}k"
    maxrate = f"{rate['maxrate']}k"
    bufsize = f"{rate['bufsize']}k"
    job.timeline_summary.update({
        "export_profile": rate["profile"],
        "video_bitrate_kbps": rate["target"],
        "rate_control": rate["rate_control"],
    })
    if not job.encoder_logged:
        _append_log(
            job,
            f"Preset de exportacao: {rate['profile']} | VBR alvo={target} | "
            f"max={maxrate} | buffer={bufsize}.",
        )

    if turbo_enabled(job):
        turbo = ensure_turbo_summary(job)
        job.timeline_summary.update({
            "codec_requested": turbo["codec_requested"],
            "codec_effective": turbo["codec_effective"],
            "encoder_effective": turbo["encoder_effective"],
            "turbo_policy": turbo["policy"],
        })
        if turbo["gpu_effective"] and not bool(job.options.get("_force_cpu")):
            encoder = str(turbo["encoder_effective"])
            if encoder.endswith("_nvenc"):
                args = [
                    "-c:v", encoder, "-preset", "p3", "-tune", "ll", "-rc", "vbr",
                    "-b:v", target, "-maxrate", maxrate, "-bufsize", bufsize,
                    "-g", "60", "-keyint_min", "30", "-forced-idr", "1",
                    "-threads", "4",
                ]
            elif encoder.endswith("_qsv"):
                args = [
                    "-c:v", encoder, "-preset", "veryfast",
                    "-b:v", target, "-maxrate", maxrate, "-bufsize", bufsize,
                    "-g", "60",
                    "-threads", "4",
                ]
            else:
                args = [
                    "-c:v", encoder, "-quality", "speed",
                    "-b:v", target, "-maxrate", maxrate, "-bufsize", bufsize,
                    "-g", "60",
                    "-threads", "4",
                ]
            if encoder.startswith("hevc_"):
                args += ["-tag:v", "hvc1"]
            job.timeline_summary.update({
                "gpu_effective": True,
                "hardware_encoder": encoder,
            })
            return encoder_choice(job, f"Hardware {encoder.upper()} rápido e fluido", args)
        if turbo.get("codec_fallback") and not turbo.get("codec_fallback_logged"):
            _append_log(
                job,
                "Turbo Produção: aceleração HEVC indisponível. "
                "Usando H.264 CPU ultrafast com a mesma resolução e bitrate alvo.",
            )
            turbo["codec_fallback_logged"] = True
        return encoder_choice(job, "CPU x264 H.264 ultrafast", [
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "fastdecode",
            "-b:v", target,
            "-maxrate", maxrate,
            "-bufsize", bufsize,
            "-g", "60",
            "-keyint_min", "30",
            "-threads", "4",
        ])

    balanced_auto_gpu = render_priority(job) in {"balanced", "max", "quality"}
    force_cpu = bool(job.options.get("_force_cpu"))
    requested_codec = "hevc" if use_hevc else "h264"
    hardware_encoder = None if force_cpu else (
        best_hardware_encoder(requested_codec) if (gpu or balanced_auto_gpu) else None
    )
    if hardware_encoder:
        job.timeline_summary.update({
            "gpu_effective": True,
            "hardware_encoder": hardware_encoder,
        })
        if balanced_auto_gpu and not gpu:
            _append_log(
                job,
                f"Modo Eficiente Térmico: {hardware_encoder.upper()} ativado automaticamente "
                "para acelerar sem superaquecer o computador.",
            )
        if hardware_encoder.endswith("_nvenc"):
            args = [
                "-c:v", hardware_encoder,
                "-preset", "p3",
                "-tune", "ll",
                "-rc", "vbr",
                "-cq", "20",
                "-b:v", target,
                "-maxrate", maxrate,
                "-bufsize", bufsize,
                "-g", "60",
                "-keyint_min", "30",
                "-forced-idr", "1",
                "-threads", "4",
            ]
            label = f"NVIDIA {hardware_encoder.upper()} fluido e de alta velocidade"
        elif hardware_encoder.endswith("_qsv"):
            args = [
                "-c:v", hardware_encoder, "-preset", "faster",
                "-b:v", target,
                "-maxrate", maxrate,
                "-bufsize", bufsize,
                "-g", "60",
                "-threads", "4",
            ]
            label = f"Intel Quick Sync {hardware_encoder.upper()} faster"
        else:
            args = [
                "-c:v", hardware_encoder, "-quality", "balanced",
                "-b:v", target,
                "-maxrate", maxrate,
                "-bufsize", bufsize,
                "-g", "60",
                "-threads", "4",
            ]
            label = f"AMD AMF {hardware_encoder.upper()} balanced"
        if use_hevc:
            args += ["-tag:v", "hvc1"]
        return encoder_choice(job, label, args)

    if (gpu or balanced_auto_gpu) and not force_cpu and not job.encoder_logged:
        _append_log(job, "Aceleracao de video indisponivel: usando CPU automaticamente.")
    elif force_cpu and not job.encoder_logged:
        _append_log(job, "Recuperacao de render: encoder por CPU aplicado explicitamente.")

    priority = render_priority(job)
    logical_cpus = max(2, int(os.cpu_count() or 4))
    balanced_threads = max(2, min(6, int(logical_cpus * 0.45)))
    cpu_threads = 1 if priority == "light" else (balanced_threads if priority == "balanced" else min(6, balanced_threads + 2))
    cpu_thread_args = ["-threads", str(cpu_threads)] if cpu_threads else []
    x265_params = "log-level=error"
    if priority == "light":
        x265_params += ":pools=1:frame-threads=1"
    elif priority == "balanced":
        x265_params += (
            f":pools={max(2, min(4, balanced_threads // 2))}:"
            f"frame-threads={max(1, min(3, balanced_threads // 3))}"
        )

    if use_hevc:
        return encoder_choice(job, "CPU x265 HEVC", [
            "-c:v", "libx265",
            "-preset", "ultrafast" if fast else "veryfast",
            "-tag:v", "hvc1",
            "-b:v", target,
            "-maxrate", maxrate,
            "-bufsize", bufsize,
            "-g", "60",
            "-keyint_min", "30",
            *cpu_thread_args,
            "-x265-params", x265_params,
        ])
    return encoder_choice(job, "CPU x264 H.264", [
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-b:v", target,
        "-maxrate", maxrate,
        "-bufsize", bufsize,
        "-g", "60",
        "-keyint_min", "30",
        *cpu_thread_args,
    ])


def choose_segment_video_args(mode: str, gpu: bool, job: Job, worker_count: int = 1) -> list[str]:
    """Select a fast, cool intermediate encoder while preserving pristine visual quality."""
    budget = render_performance_budget(job, gpu)
    force_cpu = bool(job.options.get("_force_cpu"))
    hardware_encoder = None if force_cpu else (
        best_hardware_encoder("h264")
        if (bool(gpu) or turbo_enabled(job) or render_priority(job) in {"balanced", "max", "quality"})
        else None
    )
    segment_threads = int(budget.get("segment_threads") or 2)
    if hardware_encoder:
        if hardware_encoder.endswith("_nvenc"):
            label = "H.264 NVENC ultra-rápido térmico" if turbo_enabled(job) else "H.264 NVENC otimizado térmico"
            args = [
                "-c:v", hardware_encoder,
                "-preset", "p3" if turbo_enabled(job) else "p4",
                "-tune", "ull",
                "-rc", "constqp",
                "-qp", "18" if turbo_enabled(job) else "16",
                "-g", "60",
                "-threads", str(segment_threads),
            ]
        elif hardware_encoder.endswith("_qsv"):
            label = "H.264 Intel Quick Sync veryfast"
            args = [
                "-c:v", hardware_encoder,
                "-preset", "veryfast",
                "-global_quality", "18" if turbo_enabled(job) else "16",
                "-g", "60",
                "-threads", str(segment_threads),
            ]
        else:
            label = "H.264 AMD AMF speed"
            args = [
                "-c:v", hardware_encoder,
                "-quality", "speed",
                "-qp_i", "18" if turbo_enabled(job) else "16",
                "-qp_p", "20" if turbo_enabled(job) else "18",
                "-g", "60",
                "-threads", str(segment_threads),
            ]
        job.timeline_summary["intermediate_hardware_encoder"] = hardware_encoder
    else:
        label = "H.264 CPU ultrafast térmico"
        args = [
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "fastdecode",
            "-crf", "18" if turbo_enabled(job) else "16",
            "-threads", str(segment_threads),
            "-g", "60",
        ]
    if not job.timeline_summary.get("intermediate_encoder_logged"):
        _append_log(
            job,
            f"Pipeline térmico acelerado: clipes processados em intermediário {label}; "
            "resolução, taxa de bits e codec finais aplicados na composição única.",
        )
        job.timeline_summary["intermediate_encoder"] = label
        job.timeline_summary["intermediate_encoder_logged"] = True
    return args


def efficient_segment_worker_count(job: Job, gpu: bool) -> int:
    return int(render_performance_budget(job, gpu).get("segment_workers") or 1)


def quality_boost_chain() -> str:
    return "hqdn3d=0.55:0.45:1.1:0.7,eq=contrast=1.045:saturation=1.055:brightness=0.002,unsharp=5:5:0.30:3:3:0.06"


def continuity_adjustments(
    job: Job,
    valid_pairs: list[tuple[Path, float]],
    work: Path,
) -> tuple[dict[str, str], dict[str, Any]]:
    enabled = bool(job.options.get("continuityMatch", False)) and bool(job.options.get("continuityOutliersOnly", True))
    if not enabled or not valid_pairs:
        return {}, {"enabled": False, "reason": "opcao desligada ou sem clipes"}
    if turbo_enabled(job):
        return {}, {
            "enabled": False,
            "reason": "suspenso no Turbo para preservar velocidade maxima",
            "mode": "suspended_turbo",
        }
    items: list[dict[str, Any]] = []
    cache_misses = 0
    for path, duration in valid_pairs:
        try:
            resolved = _resolved_media_path(path, work)
            indexed = INTELLIGENCE_DB.get_media_index(media_signature(resolved))
            if not indexed:
                cache_misses += 1
                continue
            metrics = ((indexed.get("features") or {}).get("metrics") or {})
            if metrics.get("mean") is None:
                continue
            items.append({
                "path": str(path),
                "mean": float(metrics.get("mean") or 0.0),
                "red": float(metrics.get("red_mean") or 0.0),
                "green": float(metrics.get("green_mean") or 0.0),
                "blue": float(metrics.get("blue_mean") or 0.0),
                "saturation": float(metrics.get("saturation_mean") or 0.0),
            })
        except Exception:
            continue
    if not items:
        return {}, {
            "enabled": False,
            "reason": "sem estatisticas de cor no cache; nenhuma analise extra foi executada",
            "cache_misses": cache_misses,
        }
    target_mean = _median([item["mean"] for item in items], 112.0)
    target_red = _median([item["red"] for item in items], target_mean)
    target_blue = _median([item["blue"] for item in items], target_mean)
    target_saturation = _median([item["saturation"] for item in items], 0.25)
    filters: dict[str, str] = {}
    reports: list[dict[str, Any]] = []
    skipped_stable = 0
    for item in items:
        luma_delta = abs(target_mean - item["mean"])
        red_delta = abs(target_red - item["red"])
        blue_delta = abs(target_blue - item["blue"])
        saturation_delta = abs(target_saturation - item["saturation"])
        is_outlier = (
            luma_delta >= 22.0
            or red_delta >= 18.0
            or blue_delta >= 18.0
            or saturation_delta >= 0.14
        )
        if not is_outlier:
            skipped_stable += 1
            reports.append({
                "file": Path(item["path"]).name,
                "skipped": True,
                "reason": "dentro da faixa visual do projeto",
            })
            continue
        brightness = max(-0.04, min(0.04, (target_mean - item["mean"]) / 255.0 * 0.32))
        red_shift = max(-0.02, min(0.02, (target_red - item["red"]) / 255.0 * 0.18))
        blue_shift = max(-0.02, min(0.02, (target_blue - item["blue"]) / 255.0 * 0.18))
        saturation = 1.0
        if item["saturation"] > 0:
            saturation = max(0.96, min(1.05, 1.0 + (target_saturation - item["saturation"]) * 0.18))
        parts = [f"eq=brightness={brightness:.5f}:saturation={saturation:.5f}"]
        if abs(red_shift) >= 0.002 or abs(blue_shift) >= 0.002:
            parts.append(f"colorbalance=rs={red_shift:.5f}:bs={blue_shift:.5f}:pl=1")
        filters[item["path"]] = ",".join(parts)
        reports.append({
            "file": Path(item["path"]).name,
            "brightness": round(brightness, 4),
            "red_shift": round(red_shift, 4),
            "blue_shift": round(blue_shift, 4),
            "saturation": round(saturation, 4),
        })
    return filters, {
        "enabled": True,
        "mode": "outliers_only",
        "target_luma": round(target_mean, 2),
        "target_saturation": round(target_saturation, 4),
        "skipped_stable": skipped_stable,
        "cache_misses": cache_misses,
        "applied": len(filters),
        "estimated_filters_skipped": skipped_stable,
        "estimated_seconds_saved": round(skipped_stable * 0.08, 2),
        "outlier_thresholds": {
            "luma": 22.0,
            "red": 18.0,
            "blue": 18.0,
            "saturation": 0.14,
        },
        "policy": "corrige somente outliers claros; clipes estaveis nao recebem filtros",
        "adjusted_clips": len(filters),
        "items": reports[:80],
    }


FILMIC_GRADE_PRESETS: dict[str, dict[str, Any]] = {
    "none": {
        "label": "Sem Gradação",
        "filter": "",
        "description": "Nenhum ajuste de cor adicional aplicado",
    },
    "natural_balanced": {
        "label": "Natural Balance",
        "filter": "eq=contrast=1.04:brightness=0.005:saturation=1.03",
        "description": "Equilíbrio neutro e contraste límpido sem alterar a fidelidade",
    },
    "cinema_warm": {
        "label": "Cinema Warm Documentário",
        "filter": "eq=contrast=1.05:brightness=0.01:saturation=1.05,colorbalance=rs=0.025:gs=0.008:bs=-0.025:rm=0.018:bm=-0.018",
        "description": "Aquecimento elegante para documentários, biografias e histórias",
    },
    "teal_orange": {
        "label": "Teal & Orange Cinematográfico",
        "filter": "eq=contrast=1.06:brightness=0.00:saturation=1.06,colorbalance=rs=0.020:bs=-0.015:rh=0.025:bh=-0.020",
        "description": "Estilo Hollywood para ação, suspense, mistério e impacto visual",
    },
    "vintage_archive": {
        "label": "Vintage Archive & Histórico",
        "filter": "eq=contrast=1.03:brightness=0.015:saturation=0.88,colorbalance=rs=0.035:gs=0.015:bs=-0.030",
        "description": "Dessaturação nostálgica suave com realce sépia para arquivos",
    },
    "vibrant_modern": {
        "label": "Vibrant Modern Tech",
        "filter": "eq=contrast=1.05:brightness=0.010:saturation=1.10,unsharp=3:3:0.35:3:3:0.0",
        "description": "Cores vivas e nitidez moderna para canais de tecnologia e curiosidades",
    },
}


def filmic_grade_filter_for(options: dict[str, Any] | None = None, tone: str = "explanatory") -> str:
    opts = options or {}
    explicit = str(opts.get("colorGradePreset") or opts.get("filmicGrade") or "").strip().lower()
    if explicit in {"off", "none", "", "natural_balanced", "default"}:
        return ""
    if explicit in FILMIC_GRADE_PRESETS:
        return FILMIC_GRADE_PRESETS[explicit]["filter"]
    return ""


def build_video_filter(
    w: int,
    h: int,
    setpts_factor: float,
    target_duration: float,
    zoom: str,
    idx: int,
    transitions: str = "off",
    reused: bool = False,
    quality_boost: bool = True,
    intro_fade: float = 0.0,
    continuity_filter: str = "",
    is_reversed: bool = False,
    is_outro: bool = False,
    filmic_grade: str = "",
) -> str:
    vf = ""
    if is_reversed:
        vf += "reverse,"
    vf += (
        f"fps=30,scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},setsar=1,settb=AVTB,setpts=PTS-STARTPTS"
    )
    if quality_boost:
        vf += f",{quality_boost_chain()}"
    if filmic_grade:
        vf += f",{filmic_grade}"
    if continuity_filter:
        vf += f",{continuity_filter}"
    vf += ",format=yuv420p"
    effective_zoom = zoom
    if reused and effective_zoom == "off":
        effective_zoom = "light"
    if effective_zoom != "off":
        if (idx % 2) == 0:
            zexpr = "min(1.000+0.00012*on,1.052)" if reused else "min(1.000+0.00010*on,1.045)"
        else:
            zexpr = "max(1.052-0.00012*on,1.000)" if reused else "max(1.045-0.00010*on,1.000)"
        vf += f",zoompan=z='{zexpr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps=30"
    if abs(setpts_factor - 1.0) > 0.01:
        vf += f",setpts={setpts_factor:.8f}*PTS"
    vf += f",trim=duration={target_duration:.4f},settb=AVTB,setpts=PTS-STARTPTS"
    if idx > 1 and intro_fade > 0 and target_duration > 0.25:
        fade_d = min(float(intro_fade), max(0.08, target_duration / 2.0))
        vf += f",fade=t=in:st=0:d={fade_d:.3f}"
    if is_outro and target_duration > 0.6:
        fade_out_d = min(0.8, target_duration * 0.4)
        fade_out_st = max(0.0, target_duration - fade_out_d)
        vf += f",fade=t=out:st={fade_out_st:.3f}:d={fade_out_d:.3f}"
    elif transitions not in {"off", "none", ""} and target_duration > 0.55:
        mode = str(transitions or "").lower()
        fade_cap = 0.16
        if mode in {"random_fast", "swipe", "flash", "digital_glitch", "vhs", "money", "map", "futuristic"}:
            fade_cap = 0.11
        elif mode in {"random_cinematic", "random_documentary", "random_industrial", "industrial", "bass_hit", "archive"}:
            fade_cap = 0.22
        elif mode in {"fade", "random_soft"}:
            fade_cap = 0.18
        fade_d = min(fade_cap, max(0.06, target_duration / 8))
        fade_out_at = max(0.0, target_duration - fade_d)
        if idx > 1 and intro_fade <= 0:
            vf += f",fade=t=in:st=0:d={fade_d:.3f}"
        vf += f",fade=t=out:st={fade_out_at:.3f}:d={fade_d:.3f}"
    vf += ",setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709"
    return vf


def build_image_filter_complex(
    w: int,
    h: int,
    target_duration: float,
    motion: str,
    image_path: Path | str | None = None,
    style_profile: dict[str, Any] | None = None,
    is_outro: bool = False,
    filmic_grade: str = "",
    focal_point: tuple[float, float] | None = None,
) -> str:
    frames = max(2, int(round(max(0.1, target_duration) * 30)))
    progress = f"(on/{frames})"
    motion = motion if motion in {"zoom_in", "zoom_out", "pan_left", "pan_right"} else "zoom_in"

    fx, fy = focal_point if focal_point else probe_image_focal_anchor(image_path)

    # Movimento cinematográfico contínuo, fluido e sem tremor subpixel
    if motion == "zoom_in":
        z_expr = f"min(1.000+0.100*{progress},1.100)"
        x_expr = f"(iw-iw/zoom)*{fx:.3f}"
        y_expr = f"(ih-ih/zoom)*{fy:.3f}"
    elif motion == "zoom_out":
        z_expr = f"max(1.100-0.100*{progress},1.000)"
        x_expr = f"(iw-iw/zoom)*{fx:.3f}"
        y_expr = f"(ih-ih/zoom)*{fy:.3f}"
    elif motion == "pan_right":
        z_expr = "1.100"
        x_expr = f"(iw-iw/zoom)*{progress}"
        y_expr = f"(ih-ih/zoom)*{fy:.3f}"
    else:  # pan_left
        z_expr = "1.100"
        x_expr = f"(iw-iw/zoom)*(1.0-{progress})"
        y_expr = f"(ih-ih/zoom)*{fy:.3f}"

    style_filter, _style_label = image_motion_graphics_filter(style_profile)
    filmic_chain = f",{filmic_grade}" if filmic_grade else ""

    # Micro-fade cinematográfico suave
    fade_dur = min(0.8 if is_outro else 0.28, max(0.12, target_duration * (0.35 if is_outro else 0.08)))
    fade_out_st = max(0.0, target_duration - fade_dur)
    fade_filters = f",fade=t=in:st=0:d={min(0.28, fade_dur):.2f},fade=t=out:st={fade_out_st:.2f}:d={fade_dur:.2f}"

    # Detectar se a proporção da imagem é compatível com o projeto (Caso A/C) ou precisa de background blur (Caso B)
    target_ratio = float(w) / float(max(1, h))
    img_w, img_h = (w, h)
    if image_path and Path(str(image_path)).exists():
        img_w, img_h = probe_image_dimensions(image_path)
    img_ratio = float(img_w) / float(max(1, img_h))
    ratio_diff = img_ratio / max(0.01, target_ratio)

    needs_blur = ratio_diff < 0.85 or ratio_diff > 1.28

    # Buffer 2.5K supersampling (2560x1440) para eliminar serrilhado e travamento de pixel no zoompan
    ss_w = max(2560, w)
    ss_h = max(1440, h)

    if not needs_blur:
        # Caso A / C: Proporção compatível -> enquadramento com Smart Dynamic Focal Anchor e supersampling 2.5K
        return (
            f"[0:v]scale={ss_w}:{ss_h}:force_original_aspect_ratio=increase,crop={ss_w}:{ss_h}:(in_w-out_w)*{fx:.3f}:(in_h-out_h)*{fy:.3f},setsar=1,format=yuv420p,"
            f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d={frames}:s={w}x{h}:fps=30,"
            f"trim=duration={target_duration:.4f}{style_filter}{filmic_chain}{fade_filters},settb=AVTB,setpts=PTS-STARTPTS,"
            f"setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709[vout]"
        )

    # Caso B: Proporção incompatível (vertical 9:16, quadrada 1:1, 4:3) -> Background blur elegante com supersampling
    return (
        f"[0:v]scale={ss_w}:{ss_h}:force_original_aspect_ratio=increase,crop={ss_w}:{ss_h}:(in_w-out_w)*{fx:.3f}:(in_h-out_h)*{fy:.3f},boxblur=24:3,setsar=1[bg];"
        f"[0:v]scale={ss_w}:{ss_h}:force_original_aspect_ratio=decrease,setsar=1[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p,"
        f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d={frames}:s={w}x{h}:fps=30,"
        f"trim=duration={target_duration:.4f}{style_filter}{filmic_chain}{fade_filters},settb=AVTB,setpts=PTS-STARTPTS,"
        f"setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709[vout]"
    )


def _source_offset_for(source_offsets: dict[str, float] | None, path: Path) -> float:
    if not source_offsets:
        return 0.0
    try:
        return max(0.0, float(source_offsets.get(str(path.resolve()).lower()) or 0.0))
    except Exception:
        return 0.0


def _interleave_media_editorial(
    v_list: list[tuple[Path, float]],
    i_list: list[tuple[Path, float]],
) -> list[tuple[Path, float]]:
    """Intercala imagens e vídeos de maneira perfeitamente proporcional e equilibrada,
    seja com muito mais vídeos do que imagens, muito mais imagens do que vídeos, ou proporções iguais."""
    if not v_list:
        return list(i_list)
    if not i_list:
        return list(v_list)

    nv = len(v_list)
    ni = len(i_list)
    total = nv + ni

    res: list[tuple[Path, float]] = []
    v_idx = 0
    i_idx = 0

    for _ in range(total):
        if v_idx >= nv:
            res.append(i_list[i_idx])
            i_idx += 1
        elif i_idx >= ni:
            res.append(v_list[v_idx])
            v_idx += 1
        else:
            v_prog = (v_idx + 0.5) / nv
            i_prog = (i_idx + 0.5) / ni
            if nv >= ni:
                if v_prog <= i_prog:
                    res.append(v_list[v_idx])
                    v_idx += 1
                else:
                    res.append(i_list[i_idx])
                    i_idx += 1
            else:
                if i_prog <= v_prog:
                    res.append(i_list[i_idx])
                    i_idx += 1
                else:
                    res.append(v_list[v_idx])
                    v_idx += 1
    return res


def _needs_interleaving(pairs: list[tuple[Path, float]]) -> bool:
    """Verifica se os arquivos de mídia estão aglomerados e precisam de intercalação editorial."""
    if not pairs:
        return False
    v_indices = [i for i, (src, _) in enumerate(pairs) if not is_image_path(src)]
    i_indices = [i for i, (src, _) in enumerate(pairs) if is_image_path(src)]
    if not v_indices or not i_indices:
        return False
    min_indices = v_indices if len(v_indices) <= len(i_indices) else i_indices
    if len(min_indices) >= 2:
        span = min_indices[-1] - min_indices[0] + 1
        if span <= len(min_indices) + 2:
            return True
    elif len(min_indices) == 1:
        if min_indices[0] == 0 or min_indices[0] == len(pairs) - 1:
            return True
    return False


def find_smart_sentence_snap(
    srt_path: Path | str | None,
    max_duration: float,
    min_duration: float = 6.0,
) -> float | None:
    """Localiza o fim da última frase completa (. ! ?) no SRT antes de max_duration para um fechamento semântico perfeito."""
    if not srt_path:
        return None
    p = Path(str(srt_path))
    if not p.exists() or p.stat().st_size <= 0:
        return None
    try:
        content = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    blocks = re.findall(
        r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*\n([\s\S]*?)(?=\n\n|\Z)",
        content,
    )
    if not blocks:
        return None

    def parse_srt_ts(ts: str) -> float:
        ts = ts.replace(",", ".")
        parts = ts.split(":")
        if len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        return 0.0

    candidates = []
    for start_str, end_str, text in blocks:
        end_sec = parse_srt_ts(end_str)
        cleaned_text = re.sub(r"<[^>]+>", "", text).strip()
        has_sentence_end = bool(re.search(r"[\.!\?]['\"»”]?\s*$", cleaned_text))
        if min_duration <= end_sec <= max_duration:
            candidates.append((end_sec, has_sentence_end, cleaned_text))

    if not candidates:
        return None

    # Prioridade 1: frases com pontuação final (. ! ?) antes do limite
    sentence_ends = [c[0] for c in candidates if c[1]]
    if sentence_ends:
        snap = min(max_duration, sentence_ends[-1] + 0.6)
        return round(snap, 3)

    # Prioridade 2: qualquer legenda antes do limite
    return round(min(max_duration, candidates[-1][0] + 0.5), 3)


def build_segment_plan(
    video_files: list[Path],
    video_durs: list[float],
    audio_total: float,
    min_speed: float = MIN_VIDEO_SPEED,
    source_offsets: dict[str, float] | None = None,
    allow_audio_trim: bool = True,
    srt_path: Path | str | None = None,
) -> tuple[list[SegmentPlan], dict[str, Any]]:
    import math

    if not video_files:
        raise RuntimeError("Nenhum arquivo de mídia encontrado para a montagem.")
    if audio_total <= 0:
        raise RuntimeError("A duração da narração deu 0. Verifique o arquivo de áudio.")

    pairs = list(zip(video_files, video_durs))
    v_pairs = [(src, dur) for src, dur in pairs if not is_image_path(src)]
    i_pairs = [(src, dur) for src, dur in pairs if is_image_path(src)]

    # PASSO 1, 2, 3 & 4: Calcular durações originais de vídeos e imagens
    v_effective_durs = [
        max(0.08, dur - _source_offset_for(source_offsets, src))
        for src, dur in v_pairs
    ]
    T_v = sum(v_effective_durs)

    # Imagens: base saudável de 4.0s (faixa saudável: 3–5s)
    N_i = len(i_pairs)
    N_v = len(v_pairs)
    base_img_dur = 4.0
    T_i = N_i * base_img_dur

    T_total = T_v + T_i

    # PASSO 6 & 7: Comparar duração visual com duração da narração e classificar cenário
    orig_audio_total = audio_total
    audio_trimmed = False
    smart_snapped = False
    ratio = T_total / max(0.1, audio_total)

    # CENÁRIO: Falta Crítica de Mídia (T_total < 65% da narração)
    if ratio < 0.65 and T_total < (audio_total - 12.0):
        if allow_audio_trim:
            # Estratégia de Sacrifício de Áudio Inteligente com SRT Smart Sentence Snap:
            img_dur = 5.5 if N_i > 0 else base_img_dur
            setpts_factor = 1.15 if T_v > 0 else 1.0
            max_achievable = (T_v * setpts_factor) + (N_i * img_dur)
            
            # Smart Sentence Snap: alinhar ao ponto final (. ! ?) mais próximo do SRT
            snapped = find_smart_sentence_snap(srt_path, max_achievable, min_duration=6.0)
            if snapped and snapped <= max_achievable:
                audio_total = max(8.0, min(orig_audio_total, snapped))
                smart_snapped = True
            else:
                audio_total = max(8.0, min(orig_audio_total, max_achievable))
                
            audio_trimmed = True
            ratio = 1.0
        else:
            falta = max(0.0, audio_total - T_total)
            items_rec = max(1, math.ceil(falta / 4.0))
            raise RuntimeError(
                "Mídia insuficiente para produzir um vídeo com ritmo visual adequado. "
                "Adicione mais clipes ou imagens antes de continuar.\n"
                f"• Duração da narração: {audio_total:.1f}s\n"
                f"• Duração visual disponível: {T_total:.1f}s ({N_v} vídeo(s), {N_i} imagem(ns))\n"
                f"• Mídia adicional recomendada: pelo menos ~{falta:.0f}s (cerca de {items_rec} novo(s) clipe(s) ou imagem(ns) no ritmo saudável de 3–5s)."
            )

    # PASSO 8: Aplicar estratégia apropriada de ritmo saudável
    auto_healing_applied: list[str] = []
    if not audio_trimmed:
        img_dur = base_img_dur
        setpts_factor = 1.0

        if ratio < 0.98:
            # Pequena falta de mídia (0.65 <= ratio < 0.98): compensar suavemente (Camada 1 Auto-Healing)
            deficit = audio_total - T_total
            if N_i > 0:
                max_img_boost = N_i * 1.5
                img_boost = min(deficit, max_img_boost)
                img_dur = round(base_img_dur + (img_boost / N_i), 3)
                deficit -= img_boost
                auto_healing_applied.append(f"camada_1_micro_dilation_img_{img_dur:.2f}s")
            if deficit > 0 and T_v > 0:
                setpts_factor = min(1.15, (T_v + deficit) / T_v)
                deficit = max(0.0, deficit - (T_v * (setpts_factor - 1.0)))
                auto_healing_applied.append(f"camada_1_micro_dilation_video_setpts_{setpts_factor:.2f}")
        elif ratio > 1.10:
            # Excesso de mídia: NÃO acelerar clipes! Manter velocidade natural 1.0x e imagens em 4.0s
            setpts_factor = 1.0
            img_dur = base_img_dur
        else:
            # Mídia equilibrada (0.98 <= ratio <= 1.10)
            setpts_factor = 1.0
            if N_i > 0 and abs(audio_total - T_total) > 0.1:
                img_dur = max(3.0, min(5.0, round((audio_total - T_v) / N_i, 3)))

    # PASSO 9: Cumprimento rigoroso da ordem natural da pasta (fidelidade 100% à sequência)
    ordered_items = list(pairs)

    # PASSO 10: Montagem da timeline com Organic Micro-Pace Oscillation
    PACE_HARMONICS = [0.92, 1.08, 0.95, 1.05, 1.00]
    plans: list[SegmentPlan] = []
    remaining = audio_total
    image_counter = 0

    for source_index, (src, orig_dur) in enumerate(ordered_items, start=1):
        if remaining <= 0.08:
            break
        is_img = is_image_path(src)
        if is_img:
            # Organic Micro-Pace: cadência harmônica áurea para evitar ritmo métrico robótico
            pace_factor = PACE_HARMONICS[image_counter % len(PACE_HARMONICS)]
            target_candidate = round(img_dur * pace_factor, 3)
            target = max(2.5, min(6.0, target_candidate))
            target = min(target, remaining)
            motion = IMAGE_MOTIONS[image_counter % len(IMAGE_MOTIONS)]
            image_counter += 1
            if target >= 0.08:
                plans.append(
                    SegmentPlan(
                        source=src,
                        raw_duration=orig_dur,
                        target_duration=target,
                        source_offset=0.0,
                        source_index=source_index,
                        cycle=0,
                        media_kind="image",
                        image_motion=motion,
                    )
                )
                remaining -= target
        else:
            offset = _source_offset_for(source_offsets, src)
            eff_dur = max(0.08, orig_dur - offset) * setpts_factor
            target = min(eff_dur, remaining)
            if target >= 0.08:
                plans.append(
                    SegmentPlan(
                        source=src,
                        raw_duration=orig_dur,
                        target_duration=target,
                        source_offset=offset,
                        source_index=source_index,
                        cycle=0,
                        media_kind="video",
                        image_motion="",
                    )
                )
                remaining -= target

    # -------------------------------------------------------------
    # AUTO-HEALING EDITORIAL EM 3 CAMADAS (Tratamento de Déficit Residual)
    # -------------------------------------------------------------
    if remaining > 0.08 and plans:
        # CAMADA 1: Organic Micro-Dilation (distribuição elástica imperceptível)
        max_dilation_per_plan = 0.65
        possible_dilation = len(plans) * max_dilation_per_plan
        if remaining <= possible_dilation:
            per_plan_boost = round(remaining / len(plans), 4)
            for p in plans:
                p.target_duration += per_plan_boost
            auto_healing_applied.append(f"camada_1_micro_dilation_+{per_plan_boost:.2f}s_por_clipe")
            remaining = 0.0
        else:
            for p in plans:
                p.target_duration += max_dilation_per_plan
            remaining = max(0.0, remaining - possible_dilation)
            auto_healing_applied.append("camada_1_micro_dilation_max")

        # CAMADA 2: Reverse-Motion Mirroring (Espelhamento cinematográfico de B-roll curtos)
        if remaining >= 1.5:
            v_candidates = [
                p for p in plans
                if p.media_kind == "video" and p.raw_duration >= 2.0 and not p.is_reversed
            ]
            for cand in reversed(v_candidates):
                if remaining < 0.5:
                    break
                mirror_dur = min(cand.raw_duration * 0.9, remaining)
                if mirror_dur >= 1.5:
                    plans.append(
                        SegmentPlan(
                            source=cand.source,
                            raw_duration=cand.raw_duration,
                            target_duration=round(mirror_dur, 3),
                            source_offset=0.0,
                            source_index=cand.source_index,
                            cycle=cand.cycle + 1,
                            media_kind="video",
                            image_motion="",
                            is_reversed=True,
                        )
                    )
                    remaining -= mirror_dur
                    auto_healing_applied.append(f"camada_2_reverse_mirroring_{cand.source.name}_{mirror_dur:.1f}s")

        # CAMADA 3: Outro Brand Card & Cinematic Fade Tail
        if remaining > 0.01:
            if remaining <= 2.5 and plans:
                plans[-1].target_duration += remaining
                plans[-1].is_outro = True
                auto_healing_applied.append("camada_3_outro_fade_tail")
                remaining = 0.0
            else:
                share = remaining / len(plans)
                for p in plans:
                    p.target_duration += share
                plans[-1].is_outro = True
                auto_healing_applied.append(f"camada_3_outro_tail_extended_{remaining:.1f}s")
                remaining = 0.0

    if not plans:
        raise RuntimeError("Nenhum segmento pôde ser gerado para a timeline.")

    playback_speed = 1.0 / setpts_factor
    actual_duration = sum(p.target_duration for p in plans)
    summary = {
        "audio_duration": round(audio_total, 3),
        "original_audio_duration": round(orig_audio_total, 3),
        "audio_trimmed": audio_trimmed,
        "smart_snapped": smart_snapped,
        "auto_healing": auto_healing_applied,
        "raw_video_duration": round(T_v, 3),
        "raw_image_potential": round(T_i, 3),
        "total_available_media_duration": round(T_total, 3),
        "media_ratio": round(ratio, 3),
        "setpts_factor": round(setpts_factor, 4),
        "playback_speed": round(playback_speed, 4),
        "min_speed": min_speed,
        "applied_image_duration": round(img_dur, 2),
        "segments": len(plans),
        "planned_duration": actual_duration,
        "video_segments": sum(1 for plan in plans if plan.media_kind == "video"),
        "image_segments": sum(1 for plan in plans if plan.media_kind == "image"),
        "images_used": len({plan.source_index for plan in plans if plan.media_kind == "image"}),
        "unique_clips_used": len({plan.source_index for plan in plans}),
        "dropped_clips": max(0, len(ordered_items) - len(plans)),
        "image_motion_summary": {
            motion: sum(1 for plan in plans if plan.image_motion == motion)
            for motion in IMAGE_MOTIONS
            if any(plan.image_motion == motion for plan in plans)
        },
        "reused_segments": 0,
        "quality_boost": True,
    }
    return plans, summary


def visual_clean_candidate_sources(
    valid_pairs: list[tuple[Path, float]],
    audio_total: float,
    min_speed: float,
) -> set[str]:
    if not valid_pairs:
        return set()
    video_files = [item[0] for item in valid_pairs]
    video_durs = [item[1] for item in valid_pairs]
    try:
        plans, _ = build_segment_plan(video_files, video_durs, audio_total, min_speed=min_speed)
        selected = {
            str(plan.source).replace("\\", "/")
            for plan in plans
        }
    except Exception:
        selected = {str(item[0]).replace("\\", "/") for item in valid_pairs}
    reserve_target = max(audio_total * min_speed * 1.18, 8.0)
    covered = 0.0
    for source, duration in valid_pairs:
        key = str(source).replace("\\", "/")
        if key in selected:
            covered += duration
            continue
        if covered < reserve_target:
            selected.add(key)
            covered += duration
    return selected


def filter_renderable_videos(job: Job, video_files: list[Path], work: Path) -> tuple[list[tuple[Path, float]], list[dict[str, Any]]]:
    valid_pairs: list[tuple[Path, float]] = []
    invalid_infos: list[dict[str, Any]] = []
    for p in video_files:
        if is_image_path(p):
            try:
                if p.exists() and p.is_file() and p.stat().st_size > 0:
                    valid_pairs.append((p, image_duration_default(job.options)))
                else:
                    invalid_infos.append({
                        "name": media_display_name(job, p),
                        "file": p.name,
                        "reason": "imagem ausente ou vazia",
                        "duration": 0,
                        "size_mb": 0,
                        "visual_checked": False,
                        "visible_frame": False,
                    })
            except Exception:
                invalid_infos.append({
                    "name": media_display_name(job, p),
                    "file": p.name,
                    "reason": "imagem invalida",
                    "duration": 0,
                    "size_mb": 0,
                    "visual_checked": False,
                    "visible_frame": False,
                })
            continue
        dur = safe_probe_duration(p, cwd=work)
        health = probe_video_render_health(p, dur, cwd=work)
        if health.get("valid"):
            valid_pairs.append((p, dur))
        else:
            invalid_infos.append({
                "name": media_display_name(job, p),
                "file": p.name,
                "reason": health.get("reason") or "video invalido",
                "duration": health.get("duration"),
                "size_mb": health.get("size_mb"),
                "visual_checked": health.get("visual_checked"),
                "visible_frame": health.get("visible_frame"),
            })
    return valid_pairs, invalid_infos


def log_invalid_video_filter(job: Job, invalid_infos: list[dict[str, Any]], prefix: str = "Pre-checagem") -> None:
    if not invalid_infos:
        return
    sample = ", ".join(f"{item['name']} ({item.get('reason')})" for item in invalid_infos[:5])
    more = "..." if len(invalid_infos) > 5 else ""
    _append_log(job, f"{prefix}: {len(invalid_infos)} vídeo(s) inválido(s) serão ignorados automaticamente: {sample}{more}")


def make_segments_low_memory(
    job: Job,
    video_files: list[Path],
    audio_total: float,
    mode: str,
    ratio: str,
    zoom: str,
    transitions: str,
    codec: str,
    gpu: bool,
    work: Path,
) -> list[Path]:
    if not video_files:
        raise RuntimeError("Nenhum vídeo encontrado. Envie clipes reais para a timeline.")
    if audio_total <= 0:
        raise RuntimeError("A duração total do áudio deu 0. Verifique se o áudio foi lido corretamente.")

    w, h = render_size(mode, ratio)
    valid_pairs, invalid_infos = filter_renderable_videos(job, video_files, work)
    log_invalid_video_filter(job, invalid_infos)
    performance_start(job, "visual_analysis")
    valid_pairs, visual_clean_summary = apply_visual_clean_filter(
        job,
        valid_pairs,
        audio_total,
        work,
        imported_count=len(video_files),
    )
    performance_stop(job, "visual_analysis")
    log_visual_clean_filter(job, visual_clean_summary)
    if not valid_pairs:
        raise RuntimeError("Nenhum video valido foi encontrado. Alguns arquivos podem estar corrompidos ou sem frames.")
    video_files = [item[0] for item in valid_pairs]
    video_durs = [item[1] for item in valid_pairs]
    job.preflight_summary.update({
        "videos_valid": len(video_files),
        "videos_invalid": len(invalid_infos),
        "invalid_video_names": [item["name"] for item in invalid_infos[:20]],
        "invalid_video_details": invalid_infos[:20],
        "visual_clean_filter": visual_clean_summary,
    })
    raw_total = sum(video_durs)
    if raw_total <= 0:
        raise RuntimeError("A duração total dos vídeos deu 0. Verifique os ficheiros de vídeo.")

    speed_factor = 1.0
    if raw_total < audio_total:
        speed_factor = audio_total / raw_total

    visual = effective_visual_options(job)
    performance_budget = render_performance_budget(job, gpu, len(video_files))
    worker_count = int(performance_budget.get("segment_workers") or efficient_segment_worker_count(job, gpu))
    encoder_args = choose_segment_video_args(mode, gpu, job, worker_count=worker_count)
    segments_dir = work / "segments"
    segments_dir.mkdir(exist_ok=True)
    segments: list[Path] = []
    remaining = audio_total
    _append_log(job, (
        f"Motor v0.5 seguro: render segmentado. Vídeos={len(video_files)} | "
        f"Áudio={audio_total:.2f}s | Vídeo bruto={raw_total:.2f}s | "
        f"Speed factor={speed_factor:.4f} | Resolução={w}x{h} | transições seguras={transitions} | sem faststart para evitar WinError/memória."
    ))

    for idx, (src, dur) in enumerate(zip(video_files, video_durs), start=1):
        if remaining <= 0.08:
            break
        adjusted = max(0.01, dur * speed_factor)
        target = min(adjusted, remaining)
        if target < 0.08:
            break
        out = segments_dir / f"seg_{idx:04d}.mp4"
        job.message = f"Renderizando clip {idx}/{len(video_files)}"
        job.percent = min(92.0, 15.0 + ((audio_total - remaining) / audio_total) * 77.0)
        if is_image_path(src):
            style_profile = job.options.get("_style_profile_effective") or reference_style_profile(job.options)
            filter_complex = build_image_filter_complex(w, h, target, image_motion_for(src, idx), src, style_profile)
            cmd = [
                FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-filter_threads", "1",
                "-i", str(src),
                "-filter_complex", filter_complex,
                "-map", "[vout]",
                "-an", "-r", "30",
                *encoder_args,
                "-pix_fmt", "yuv420p",
                str(out),
            ]
        else:
            vf = build_video_filter(
                w,
                h,
                speed_factor,
                target,
                visual["zoom"],
                idx,
                visual["transitions"],
                quality_boost=visual["quality_boost"],
                intro_fade=(0.75 if idx == 1 else 0.0),
            )
            cmd = [
                FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-filter_threads", "1",
                "-i", str(src),
                "-vf", vf,
                "-an", "-r", "30",
                *encoder_args,
                "-pix_fmt", "yuv420p",
                str(out),
            ]
        run_cmd(job, cmd, cwd=work, quiet_success=True)
        if out.exists() and out.stat().st_size > 0:
            segments.append(out)
            remaining -= target
        else:
            raise RuntimeError(f"Falha ao criar segmento: {out.name}")

    if not segments:
        raise RuntimeError("Nenhum segmento de vídeo foi gerado.")
    if remaining > 1.0:
        _append_log(job, f"Aviso: ainda faltariam {remaining:.2f}s. O último frame pode ser estendido em versões futuras.")
    return segments


def make_segments_smart(
    job: Job,
    video_files: list[Path],
    audio_total: float,
    mode: str,
    ratio: str,
    zoom: str,
    transitions: str,
    codec: str,
    gpu: bool,
    work: Path,
    subtitles: list[Path] | None = None,
) -> list[Path]:
    if not video_files:
        raise RuntimeError("Nenhum video encontrado. Envie clipes reais para a timeline.")
    if audio_total <= 0:
        raise RuntimeError("A duracao total do audio deu 0. Verifique se o audio foi lido corretamente.")

    w, h = render_size(mode, ratio)
    valid_pairs, invalid_infos = filter_renderable_videos(job, video_files, work)
    log_invalid_video_filter(job, invalid_infos)
    min_speed = float(job.options.get("minSpeed") or MIN_VIDEO_SPEED)
    candidate_sources = visual_clean_candidate_sources(valid_pairs, audio_total, min_speed)
    performance_start(job, "visual_analysis")
    valid_pairs, visual_clean_summary = apply_visual_clean_filter(
        job,
        valid_pairs,
        audio_total,
        work,
        candidate_sources=candidate_sources,
        imported_count=len(video_files),
    )
    # Semantic B-Roll Matcher: alinha tematicamente clipes com as falas da narracao
    cues_for_matching = list(job.subtitle_cues or [])
    if not cues_for_matching and subtitles:
        for srt_f in subtitles:
            if srt_f.exists():
                cues_for_matching = parse_srt_file(srt_f)
                break
    valid_pairs, semantic_b_roll_summary = match_media_to_subtitles(job, valid_pairs, cues_for_matching, audio_total)
    job.preflight_summary["semantic_b_roll"] = semantic_b_roll_summary
    # Clean Opening Protocol: protege estritamente os primeiros 10 slots com B-roll limpo
    valid_pairs, clean_opening_summary = enforce_clean_opening_protocol(job, valid_pairs, work, max_opening_slots=10)
    job.preflight_summary["clean_opening"] = clean_opening_summary
    performance_stop(job, "visual_analysis")
    log_visual_clean_filter(job, visual_clean_summary)
    if not valid_pairs:
        raise RuntimeError("Nenhum video valido foi encontrado. Remova arquivos corrompidos ou adicione novos clipes.")
    original_video_count = len(video_files)
    performance_start(job, "continuity")
    continuity_filters, continuity_summary = continuity_adjustments(job, valid_pairs, work)
    performance_stop(job, "continuity")
    job.continuity_summary = continuity_summary
    video_files = [item[0] for item in valid_pairs]
    video_durs = [item[1] for item in valid_pairs]
    source_offsets: dict[str, float] = {}
    for src, dur in valid_pairs:
        if not is_image_path(src):
            v_health = probe_video_render_health(src, dur, cwd=work)
            if v_health.get("suggested_offset", 0.0) > 0.3:
                source_offsets[str(src.resolve()).lower()] = float(v_health["suggested_offset"])
    visual_window_summary: dict[str, Any] = {
        "enabled": bool(job.options.get("scoreVisualWindows", True)),
        "analyzed": 0,
        "adjusted": 0,
        "cache_hits": 0,
        "budget_skipped": 0,
        "items": [],
        "policy": "usa a melhor janela interna do clipe quando ha trecho saudavel",
    }
    window_scores_by_source: dict[str, dict[str, Any]] = {}
    if visual_window_summary["enabled"]:
        performance_start(job, "visual_windows")
        for src, dur in valid_pairs:
            if is_image_path(src) or dur <= 1.2:
                continue
            window_cache_key = visual_clean_cache_key(src, dur, cwd=work, scope="windows_v3_batch")
            cached_window = VISUAL_CLEAN_CACHE.get(window_cache_key)
            if (turbo_enabled(job) or len(valid_pairs) > 40) and not isinstance(cached_window, dict):
                visual_window_summary["budget_skipped"] += 1
                if "visual_windows_cache_only_turbo" not in job.render_budget_fallbacks:
                    job.render_budget_fallbacks.append("visual_windows_cache_only_turbo")
                continue
            if not isinstance(cached_window, dict) and not budget_allows_optional(job, 1.2, reserve_ratio=0.58):
                visual_window_summary["budget_skipped"] += 1
                if "visual_windows_quota_exhausted" not in job.render_budget_fallbacks:
                    job.render_budget_fallbacks.append("visual_windows_quota_exhausted")
                continue
            info = probe_visual_window_scores(src, dur, cwd=work)
            if not info.get("enabled"):
                continue
            key = str(src.resolve()).lower()
            window_scores_by_source[key] = info
            visual_window_summary["analyzed"] += 1
            if info.get("cache_hit"):
                visual_window_summary["cache_hits"] += 1
            best_offset = max(0.0, float(info.get("best_offset") or 0.0))
            best_score = float(info.get("best_score") or 0.0)
            if best_offset >= 0.25 and best_score >= 0.45 and dur - best_offset >= 0.75:
                source_offsets[key] = best_offset
                visual_window_summary["adjusted"] += 1
            if len(visual_window_summary["items"]) < 80:
                visual_window_summary["items"].append({
                    "file": media_display_name(job, src),
                    "best_offset": round(best_offset, 3),
                    "best_score": round(best_score, 3),
                    "label": info.get("best_label"),
                    "reason": info.get("best_reason"),
                    "cache_hit": bool(info.get("cache_hit")),
                })
        performance_stop(job, "visual_windows")
    allow_audio_trim = bool(job.options.get("allowAudioTrim", True))
    srt_file = None
    if subtitles:
        srt_file = subtitles[0] if Path(str(subtitles[0])).exists() else None
    if not srt_file and hasattr(job, "upload_paths"):
        for p in job.upload_paths.values():
            if str(p).lower().endswith(".srt") and p.exists():
                srt_file = p
                break
    if not srt_file and getattr(job, "srt_path", None) and Path(str(job.srt_path)).exists():
        srt_file = Path(str(job.srt_path))
    plans, summary = build_segment_plan(video_files, video_durs, audio_total, min_speed=min_speed, source_offsets=source_offsets, allow_audio_trim=allow_audio_trim, srt_path=srt_file)
    if summary.get("audio_trimmed"):
        audio_total = float(summary["audio_duration"])
        if summary.get("smart_snapped"):
            _append_log(job, f"SRT Smart Sentence Snap: Áudio ajustado ao ponto final da frase em {audio_total:.1f}s (reduzido de {summary.get('original_audio_duration', 0):.1f}s) com fade suave e encerramento semântico perfeito.")
        else:
            _append_log(job, f"Ajuste de Mídia: Áudio sacrificado/encurtado de {summary.get('original_audio_duration', 0):.1f}s para {audio_total:.1f}s com fade suave para respeitar a mídia disponível sem repetições.")
    job.timeline_summary = summary
    summary["original_clip_count"] = original_video_count
    summary["valid_clip_count"] = len(video_files)
    summary["preflight_invalid_videos"] = len(invalid_infos)
    summary["preflight_invalid_details"] = invalid_infos[:20]
    summary["visual_clean_summary"] = visual_clean_summary
    summary["visual_window_scores"] = visual_window_summary
    summary["continuity_summary"] = continuity_summary
    summary["skipped_segments"] = len(invalid_infos)
    summary["decode_failed_segments"] = 0
    summary["decode_failed_names"] = []
    summary["fill_segments"] = 0
    summary["actual_rendered_duration"] = 0.0
    visual = effective_visual_options(job)
    summary["quality_boost_requested"] = bool(job.options.get("qualityBoost", True))
    summary["quality_boost"] = visual["quality_boost"]
    summary["zoom_requested"] = str(job.options.get("zoom") or "off")
    summary["zoom_effective"] = visual["zoom"]
    summary["transitions_requested"] = str(job.options.get("transitions") or "off")
    summary["transitions_effective"] = visual["transitions"]
    job.preflight_summary.update({
        "videos_total": original_video_count,
        "videos_valid": len(video_files),
        "videos_invalid": len(invalid_infos),
        "invalid_video_names": [item["name"] for item in invalid_infos[:20]],
        "invalid_video_details": invalid_infos[:20],
        "visual_clean_filter": visual_clean_summary,
        "visual_window_scores": {
            key: value for key, value in visual_window_summary.items() if key != "items"
        },
    })

    performance_budget = render_performance_budget(job, gpu, len(plans))
    worker_count = int(performance_budget.get("segment_workers") or efficient_segment_worker_count(job, gpu))
    encoder_args = choose_segment_video_args(mode, gpu, job, worker_count=worker_count)
    summary["segment_workers"] = worker_count
    summary["render_performance_budget"] = performance_budget
    summary["segment_validation"] = "probe_on_suspicion"
    segments_dir = work / "segments"
    segments_dir.mkdir(exist_ok=True)
    segments: list[Path] = []
    accepted_plans: list[SegmentPlan] = []
    failed_sources: set[str] = set()
    _append_log(job, (
        f"Motor v0.8 otimizado: áudio={summary.get('audio_duration', audio_total):.2f}s | "
        f"vídeo bruto={summary.get('raw_video_duration', 0.0):.2f}s | velocidade={summary.get('playback_speed', 1.0):.2f}x | "
        f"segmentos={len(plans)} | reutilizados={summary.get('reused_segments', 0)} | "
        f"descartados={summary.get('dropped_clips', 0)} | resolução={w}x{h} | quality_boost={'on' if summary.get('quality_boost') else 'off'}."
    ))

    tone = str(
        getattr(job, "audio_analysis", {}).get("tone")
        or getattr(job, "emotion_summary", {}).get("tone")
        or getattr(job, "audio_health_summary", {}).get("tone")
        or (job.options or {}).get("projectTone")
        or (job.options or {}).get("tone")
        or "explanatory"
    )
    filmic_grade = filmic_grade_filter_for(job.options, tone)
    summary["filmic_grade"] = filmic_grade
    summary["filmic_grade_preset"] = str((job.options or {}).get("colorGradePreset") or tone)

    rendered_duration = 0.0
    next_segment_no = 1
    completed_planned_duration = 0.0
    render_state_lock = threading.RLock()

    def render_one(plan: SegmentPlan, segment_no: int) -> tuple[Path | None, float]:
        nonlocal completed_planned_duration
        source_key = str(plan.source)
        with render_state_lock:
            if source_key in failed_sources:
                summary["skipped_segments"] += 1
                return None, 0.0
        display_name = media_display_name(job, plan.source)
        out = segments_dir / f"seg_{segment_no:04d}.mp4"
        label_total = max(len(plans), segment_no)
        stage_label = "imagem" if plan.media_kind == "image" else "clipe"
        set_stage(job, "rendering", f"Renderizando {stage_label} {segment_no}/{label_total}", f"Renderizando {stage_label} {segment_no}/{label_total}")
        segment_filter_threads = max(1, int(performance_budget.get("segment_filter_threads") or 1))
        segment_threads = max(1, int(performance_budget.get("segment_threads") or 2))
        segment_thread_args = ["-threads", str(segment_threads), "-filter_threads", str(segment_filter_threads)]
        if plan.media_kind == "image" or is_image_path(plan.source):
            style_profile = job.options.get("_style_profile_effective") or reference_style_profile(job.options)
            filter_complex = build_image_filter_complex(
                w,
                h,
                plan.target_duration,
                plan.image_motion or image_motion_for(plan.source, segment_no),
                plan.source,
                style_profile,
                is_outro=plan.is_outro,
                filmic_grade=filmic_grade,
            )
            cmd = [
                FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *segment_thread_args,
                "-i", str(plan.source),
                "-filter_complex", filter_complex,
                "-map", "[vout]",
                "-an", "-r", "30",
                *encoder_args,
                "-pix_fmt", "yuv420p",
                str(out),
            ]
        else:
            vf = build_video_filter(
                w,
                h,
                summary["setpts_factor"],
                plan.target_duration,
                visual["zoom"],
                segment_no,
                visual["transitions"],
                reused=(plan.cycle > 0 and not turbo_enabled(job)),
                quality_boost=(
                    visual["quality_boost"]
                    and not (
                        bool(job.options.get("adaptiveQualityBoost", True))
                        and float(window_scores_by_source.get(str(plan.source.resolve()).lower(), {}).get("best_score") or 0.0) >= 0.86
                    )
                ),
                intro_fade=0.0,
                continuity_filter=continuity_filters.get(str(plan.source), ""),
                is_reversed=plan.is_reversed,
                is_outro=plan.is_outro,
                filmic_grade=filmic_grade,
            )
            input_limit = max(0.5, (plan.target_duration / max(0.08, float(summary.get("setpts_factor", 1.0)))) + 1.25)
            seek_args = []
            if plan.source_offset > 0.0:
                seek_args.extend(["-ss", f"{plan.source_offset:.3f}"])
            seek_args.extend(["-t", f"{input_limit:.3f}"])
            cmd = [
                FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *segment_thread_args,
                *seek_args,
                "-i", str(plan.source),
                "-vf", vf,
                "-an", "-r", "30",
                *encoder_args,
                "-pix_fmt", "yuv420p",
                str(out),
            ]
        try:
            run_cmd(job, cmd, cwd=work, quiet_success=True)
        except RenderCancelled:
            raise
        except RuntimeError as exc:
            with render_state_lock:
                summary["skipped_segments"] += 1
                summary["decode_failed_segments"] += 1
                if display_name not in summary["decode_failed_names"]:
                    summary["decode_failed_names"].append(display_name)
                failed_sources.add(source_key)
            try:
                if out.exists():
                    out.unlink()
            except Exception:
                pass
            _append_log(job, (
                f"Clip ignorado: {display_name} falhou na decodificação "
                f"({ffmpeg_decode_hint(exc)}). O motor vai compensar com outros clipes."
            ))
            return None, 0.0
        file_size = out.stat().st_size if out.exists() else 0
        suspicious_size = file_size < max(4096, int(plan.target_duration * 1200))
        actual = safe_probe_duration(out) if suspicious_size else plan.target_duration
        if not out.exists() or file_size <= 0 or actual <= 0.08:
            with render_state_lock:
                summary["skipped_segments"] += 1
                failed_sources.add(source_key)
                if display_name not in summary["decode_failed_names"]:
                    summary["decode_failed_names"].append(display_name)
            _append_log(job, f"Clip ignorado: {display_name} não gerou frames de vídeo válidos.")
            return None, 0.0
        if actual + 0.30 < plan.target_duration:
            _append_log(job, f"Clip curto: {display_name} planeado={plan.target_duration:.2f}s real={actual:.2f}s. O motor vai compensar.")
        with render_state_lock:
            completed_planned_duration += min(plan.target_duration, actual)
            job.percent = min(92.0, 15.0 + (completed_planned_duration / audio_total) * 77.0)
        return out, actual

    performance_start(job, "segments")
    if worker_count > 1 and len(plans) > 1:
        _append_log(
            job,
            f"{performance_budget.get('mode_label')}: {worker_count} clipes processados em paralelo "
            f"com orçamento controlado de CPU/GPU "
            f"(encoder={performance_budget.get('hardware_encoder') or 'CPU'}, "
            f"CPU={performance_budget.get('logical_cpus')} threads, RAM={performance_budget.get('ram_gb')} GB).",
        )
        ordered_results: dict[int, tuple[SegmentPlan, Path | None, float]] = {}
        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="glide-segment") as executor:
            futures = {
                executor.submit(render_one, plan, index): (index, plan)
                for index, plan in enumerate(plans, start=1)
            }
            for future in as_completed(futures):
                index, plan = futures[future]
                out, actual = future.result()
                ordered_results[index] = (plan, out, actual)
        for index in sorted(ordered_results):
            plan, out, actual = ordered_results[index]
            if out:
                segments.append(out)
                accepted_plans.append(plan)
                rendered_duration += actual
        next_segment_no = len(plans) + 1
    else:
        for plan in plans:
            out, actual = render_one(plan, next_segment_no)
            next_segment_no += 1
            if out:
                segments.append(out)
                accepted_plans.append(plan)
                rendered_duration += actual

    target_floor = audio_total - 0.35
    if rendered_duration < target_floor:
        missing = audio_total - rendered_duration
        _append_log(job, f"Timeline curta apos render real: faltam {missing:.2f}s. Usando clipes extras/reuso automatico.")
        source_infos = [(idx, src, dur) for idx, (src, dur) in enumerate(zip(video_files, video_durs), start=1)]
        last_first_cycle = max((plan.source_index for plan in plans if plan.cycle == 0), default=0)
        max_attempts = max(20, len(source_infos) * 4)
        attempts = 0
        fill_cycle = 0
        while rendered_duration < target_floor and attempts < max_attempts:
            if fill_cycle == 0 and last_first_cycle < len(source_infos):
                candidates = source_infos[last_first_cycle:]
                cycle_value = 0
            else:
                candidates = source_infos
                cycle_value = max(1, fill_cycle)
            made_progress = False
            for source_index, src, dur in candidates:
                if rendered_duration >= target_floor or attempts >= max_attempts:
                    break
                attempts += 1
                remaining = audio_total - rendered_duration
                if remaining <= 0.35:
                    break
                target = min(max(0.01, dur * summary["setpts_factor"]), remaining + 0.75)
                if target < 0.08:
                    continue
                fill_plan = SegmentPlan(
                    source=src,
                    raw_duration=dur,
                    target_duration=target,
                    source_offset=_source_offset_for(source_offsets, src) if not is_image_path(src) else 0.0,
                    source_index=source_index,
                    cycle=cycle_value,
                    media_kind="image" if is_image_path(src) else "video",
                    image_motion=image_motion_for(src, source_index + cycle_value) if is_image_path(src) else "",
                )
                out, actual = render_one(fill_plan, next_segment_no)
                next_segment_no += 1
                if out:
                    segments.append(out)
                    accepted_plans.append(fill_plan)
                    rendered_duration += actual
                    summary["fill_segments"] += 1
                    made_progress = True
            fill_cycle += 1
            if not made_progress and fill_cycle > 1:
                break

    if not segments:
        raise RuntimeError("Nenhum segmento de video foi gerado.")
    if rendered_duration < target_floor:
        skipped = summary.get("skipped_segments", 0)
        raise RuntimeError(
            f"Vídeo renderizado ainda ficou curto: vídeo={rendered_duration:.2f}s, áudio={audio_total:.2f}s. "
            f"{skipped} clipe(s) foram ignorados por falha de frames/decodificação. Remova esses clipes ou adicione mais vídeos."
        )

    used_first_cycle = {plan.source_index for plan in accepted_plans if plan.cycle == 0}
    summary["segments"] = len(segments)
    summary["unique_clips_used"] = len({plan.source_index for plan in accepted_plans})
    summary["image_segments"] = sum(1 for plan in accepted_plans if plan.media_kind == "image")
    summary["images_used"] = len({str(plan.source) for plan in accepted_plans if plan.media_kind == "image"})
    summary["image_motion_summary"] = {
        motion: sum(1 for plan in accepted_plans if plan.image_motion == motion)
        for motion in ("zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down")
        if any(plan.image_motion == motion for plan in accepted_plans)
    }
    style_profile = job.options.get("_style_profile_effective") or reference_style_profile(job.options)
    _style_filter, style_label = image_motion_graphics_filter(style_profile)
    if summary["image_segments"]:
        summary["image_motion_graphics"] = {
            "style": style_label,
            "source": style_profile.get("source") or "glide_package",
            "segments": summary["image_segments"],
        }
    summary["reused_segments"] = sum(1 for plan in accepted_plans if plan.cycle > 0)
    summary["dropped_clips"] = max(0, len(video_files) - len(used_first_cycle)) if summary["raw_video_duration"] > audio_total else 0
    summary["planned_duration"] = round(sum(plan.target_duration for plan in accepted_plans), 3)
    summary["actual_rendered_duration"] = round(rendered_duration, 3)
    if bool(job.options.get("adaptiveQualityBoost", True)):
        boosted = 0
        minimal = 0
        for plan in accepted_plans:
            score = float(window_scores_by_source.get(str(plan.source.resolve()).lower(), {}).get("best_score") or 0.0)
            if plan.media_kind == "video" and score >= 0.86 and visual["quality_boost"]:
                minimal += 1
            elif plan.media_kind == "video" and visual["quality_boost"]:
                boosted += 1
        summary["adaptive_quality_boost"] = {
            "enabled": True,
            "boosted_segments": boosted,
            "minimal_segments": minimal,
            "estimated_filters_skipped": minimal,
            "estimated_seconds_saved": round(minimal * 0.14, 2),
            "policy": "clipes visualmente limpos recebem filtro minimo; clipes fracos mantem boost",
        }
    else:
        summary["adaptive_quality_boost"] = {"enabled": False}
    performance_stop(job, "segments")
    visual_clean_summary["used_in_final"] = len({
        str(plan.source).replace("\\", "/")
        for plan in accepted_plans
    })
    visual_clean_summary["used_as_fallback"] = min(
        int(visual_clean_summary.get("fallback_used") or 0),
        visual_clean_summary["used_in_final"],
    )
    summary["performance_breakdown"] = dict(job.performance_breakdown)
    if summary["skipped_segments"] or summary["fill_segments"]:
        _append_log(job, (
            f"Autoajuste de timeline: video real={rendered_duration:.2f}s | "
            f"ignorados={summary['skipped_segments']} | falhas_decode={summary['decode_failed_segments']} | extras={summary['fill_segments']}."
        ))
    return segments


def concat_segments_and_mux(
    job: Job,
    segments: list[Path],
    audio_file: Path,
    audio_total: float,
    out_file: Path,
    work: Path,
    subtitle_ass: Path | None = None,
    graph: RenderGraph | None = None,
    segments_cache_key: str = "",
    audio_foundation_key: str = "",
):
    job.message = "Juntando segmentos sem estourar memória"
    job.percent = max(job.percent, 93)
    concat_list = work / "concat_segments.txt"
    # segment paths are relative to work in this file to keep Windows commands short
    valid_segments = []
    for seg in segments:
        if seg.exists() and seg.stat().st_size > 0:
            valid_segments.append(seg)
        else:
            _append_log(job, f"Aviso de montagem: segmento {seg.name} inválido ou vazio, ignorado na concatenação.")
    lines = []
    for s in valid_segments:
        rel = s.relative_to(work).as_posix().replace("'", "'\\''")
        lines.append(f"file '{rel}'")
    concat_list.write_text("\n".join(lines), encoding="utf-8")

    video_concat = work / "video_concat.mp4"
    assembly_key = ""
    assembly_cached = None
    if graph:
        assembly_key, assembly_cached = graph.begin(
            "assembly",
            {
                "segments_key": segments_cache_key,
                # The segment node key already identifies their content. Avoid
                # temporary restore paths/mtimes invalidating this node.
                "segments": [] if segments_cache_key else [graph_media_token(path) for path in segments],
                "duration": round(audio_total, 4),
                "composition_version": "unified_tpad_v2",
                "pipeline": RENDER_PIPELINE_VERSION,
            },
            "Montagem",
        )
    if assembly_cached:
        graph.restore(assembly_cached, {"video_concat.mp4": video_concat})
        if not video_concat.exists() or video_concat.stat().st_size <= 0:
            assembly_cached = None
    if not assembly_cached:
        performance_start(job, "concat")
        cmd_concat = [
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-filter_threads", "1",
            "-fflags", "+genpts",
            "-f", "concat", "-safe", "0", "-i", concat_list.name,
            "-c", "copy", "-avoid_negative_ts", "make_zero", str(video_concat.name),
        ]
        run_cmd(job, cmd_concat, cwd=work, quiet_success=True)
        performance_stop(job, "concat")
        if graph:
            graph.commit(
                stage="assembly",
                cache_key=assembly_key,
                artifacts={"video_concat.mp4": video_concat},
                metadata={"segments": len(segments), "duration": round(audio_total, 4)},
            )
    elif graph:
        _append_log(job, "Render Graph: montagem de segmentos reutilizada.")
    if graph:
        sync_graph_summary(job, graph)

    video_source = video_concat
    cta_lang = str(job.options.get("ctaLanguage") or "").strip().lower()
    cta: dict[str, Any] | None = None
    cta_times: list[float] = []
    if CTA_REQUIRED and not cta_lang:
        raise RuntimeError("Escolha um CTA de inscricao antes de renderizar.")
    if cta_lang:
        cta = prepare_cta_asset(job, cta_lang)
        if graph and cta:
            graph.record_metadata(
                stage="cta_alpha",
                payload={
                    "language": cta_lang,
                    "video": graph_media_token(Path(cta["video"])) if cta.get("video") else None,
                    "audio": graph_media_token(Path(cta["audio_source"])) if cta.get("audio_source") else None,
                    "position": job.options.get("ctaPositionPreset"),
                    "pipeline": RENDER_PIPELINE_VERSION,
                },
                metadata={"cta_asset": {key: cta.get(key) for key in ("label", "duration", "has_audio", "language")}},
                label="CTA alpha",
            )
        cta_duration = float(cta.get("duration") or 0.0)
        cta_times = choose_cta_times(job, audio_total, cta_duration)
        smart_cta_summary = dict(job.cta_summary)
        smart_position = str(smart_cta_summary.get("smart_position_preset") or job.options.get("ctaPositionPreset") or "top_right")
        if job.caption_summary.get("valid", job.caption_summary.get("kept", 0)) and smart_position.startswith("bottom_"):
            previous_position = smart_position
            smart_position = "top_right" if smart_position != "bottom_right" else "top_left"
            job.layer_collision_summary.update({
                "captions_safe_zone": "bottom",
                "cta_repositioned": True,
                "cta_original_position": previous_position,
                "cta_effective_position": smart_position,
                "reason": "Legendas reais reservaram a zona inferior.",
            })
        job.cta_summary = {
            "enabled": True,
            "language": cta_lang,
            "label": cta.get("label"),
            "has_audio": bool(cta.get("has_audio")),
            "occurrences": len(cta_times),
            "times": [round(value, 3) for value in cta_times],
            "duration": round(cta_duration, 3),
            "timing_policy": str(smart_cta_summary.get("timing_policy") or "director_contextual_max_2"),
            "position_preset": smart_position,
            "smart_position_preset": smart_position,
            "selection_reason": smart_cta_summary.get("selection_reason"),
            "selected_windows": smart_cta_summary.get("selected_windows") or [],
            "candidate_count": smart_cta_summary.get("candidate_count"),
            "max_occurrences": 2,
            "offset_x": clamp_float(job.options.get("ctaOffsetX"), 0.0, -35.0, 35.0),
            "offset_y": clamp_float(job.options.get("ctaOffsetY"), 0.0, -35.0, 35.0),
            "scale_width_px": cta_scale_width(job, render_size(job.options.get("mode", "standard"), job.options.get("ratio", "16:9"))[0]),
        }
        _append_log(job, (
            f"CTA aplicado: {cta.get('label')} | vezes={len(cta_times)} | "
            f"tempos={', '.join(f'{t:.2f}s' for t in cta_times)} | audio={'sim' if cta.get('has_audio') else 'nao'}."
        ))
    audio_key = ""
    audio_cached = None
    graph_audio = work / "graph_audio_final.wav"
    if graph:
        audio_key, audio_cached = graph.begin(
            "audio_mix",
            {
                "voice_music": audio_foundation_key or graph_media_token(audio_file),
                "segments_key": segments_cache_key,
                "cta": {
                    "language": cta_lang,
                    "times": cta_times,
                    "video": graph_media_token(Path(cta["video"])) if cta else None,
                    "audio": graph_media_token(Path(cta["audio_source"])) if cta and cta.get("audio_source") else None,
                },
                "duration": round(audio_total, 4),
                "options": {
                    key: job.options.get(key)
                    for key in (
                        "autoSoundFx", "subtitleAnimation", "transitions",
                        "projectTone", "strongMomentEnhance", "audioMastering", "platformMasterProfile",
                    )
                },
                "pipeline": RENDER_PIPELINE_VERSION,
            },
            "Mixagem e master",
        )
    if audio_cached:
        audio_metadata = graph.restore(audio_cached, {"audio.wav": graph_audio})
        if graph_audio.exists() and graph_audio.stat().st_size > 0:
            audio_file = graph_audio
            for source, target in (
                ("cta_summary", "cta_summary"),
                ("sound_fx_summary", "sound_fx_summary"),
                ("audio_master_summary", "audio_master_summary"),
            ):
                value = audio_metadata.get(source)
                if isinstance(value, dict):
                    setattr(job, target, value)
            _append_log(job, "Render Graph: mixagem e master de audio reutilizados.")
        else:
            audio_cached = None
    if not audio_cached:
        if cta:
            audio_file = mix_cta_audio(job, audio_file, cta, cta_times, audio_total, work)
        performance_start(job, "sound_fx")
        try:
            audio_file = mix_auto_sound_fx(job, audio_file, audio_total, work, segments)
        finally:
            performance_stop(job, "sound_fx")
        audio_file = master_final_audio(job, audio_file, work)
        if graph:
            graph.record_metadata(
                stage="audio_master",
                payload={
                    "audio": graph_media_token(audio_file),
                    "profile": job.options.get("platformMasterProfile") or "youtube_long",
                    "audioMastering": bool(job.options.get("audioMastering", True)),
                    "pipeline": RENDER_PIPELINE_VERSION,
                },
                metadata={"audio_master_summary": job.audio_master_summary},
                label="Master",
            )
        if graph:
            graph.commit(
                stage="audio_mix",
                cache_key=audio_key,
                artifacts={"audio.wav": audio_file},
                metadata={
                    "cta_summary": job.cta_summary,
                    "sound_fx_summary": job.sound_fx_summary,
                    "audio_master_summary": job.audio_master_summary,
                },
            )
    if graph:
        sync_graph_summary(job, graph)

    visual_key = ""
    visual_cached = None
    graph_visual = work / "graph_visual_final.mp4"
    if graph:
        visual_key, visual_cached = graph.begin(
            "visual_composition",
            {
                "assembly_key": assembly_key or segments_cache_key,
                "cta": {
                    "language": cta_lang,
                    "times": cta_times,
                    "video": graph_media_token(Path(cta["video"])) if cta else None,
                    "position": (job.cta_summary or {}).get("position_preset") or job.options.get("ctaPositionPreset"),
                    "smart_position": (job.cta_summary or {}).get("smart_position_preset"),
                    "timing_policy": (job.cta_summary or {}).get("timing_policy"),
                    "offset_x": job.options.get("ctaOffsetX"),
                    "offset_y": job.options.get("ctaOffsetY"),
                },
                "subtitle": graph_content_token(subtitle_ass) if subtitle_ass and subtitle_ass.exists() else None,
                "mode": job.options.get("mode"),
                "ratio": job.options.get("ratio"),
                "duration": round(audio_total, 4),
                "pipeline": RENDER_PIPELINE_VERSION,
            },
            "Composicao visual",
        )
    if visual_cached:
        visual_metadata = graph.restore(visual_cached, {"video.mp4": graph_visual})
        if graph_visual.exists() and graph_visual.stat().st_size > 0:
            video_source = graph_visual
            subtitle_value = visual_metadata.get("subtitle_summary")
            if isinstance(subtitle_value, dict):
                job.subtitle_summary = subtitle_value
            caption_value = visual_metadata.get("caption_summary")
            if isinstance(caption_value, dict):
                job.caption_summary = caption_value
            collision_value = visual_metadata.get("layer_collision_summary")
            if isinstance(collision_value, dict):
                job.layer_collision_summary = collision_value
            _append_log(job, "Render Graph: CTA, Textos e Legendas reutilizados.")
        else:
            visual_cached = None
    if not visual_cached:
        performance_start(job, "composition")
        if cta:
            try:
                video_source = compose_final_visuals(
                    job,
                    video_source,
                    cta,
                    cta_times,
                    subtitle_ass,
                    work,
                    audio_total,
                )
            except RenderCancelled:
                raise
            except RuntimeError as exc:
                if turbo_enabled(job):
                    turbo = ensure_turbo_summary(job)
                    turbo.update({
                        "unified_composition": False,
                        "fallback_used": True,
                        "visual_passes_effective": 3 if subtitle_ass and subtitle_ass.exists() else 2,
                        "visual_passes_avoided": 0,
                        "fallback_reason": human_render_error(exc),
                    })
                job.timeline_summary.update({
                    "unified_final_composition": False,
                    "visual_passes_effective": 3 if subtitle_ass and subtitle_ass.exists() else 2,
                    "visual_passes_avoided": 0,
                    "composition_fallback_reason": human_render_error(exc),
                })
                _append_log(job, f"Composição unificada falhou; usando fluxo compatível. Motivo: {human_render_error(exc)}")
                video_source = overlay_cta_on_video(job, video_source, cta, cta_times, work)
                if subtitle_ass and subtitle_ass.exists():
                    video_source = burn_subtitles_on_video(
                        job,
                        video_source,
                        subtitle_ass,
                        work,
                        "video_subtitled_fallback.mp4",
                        audio_total,
                    )
        elif subtitle_ass and subtitle_ass.exists():
            video_source = burn_subtitles_on_video(
                job,
                video_source,
                subtitle_ass,
                work,
                target_duration=audio_total,
            )
        performance_stop(job, "composition")
        if graph:
            graph.commit(
                stage="visual_composition",
                cache_key=visual_key,
                artifacts={"video.mp4": video_source},
                metadata={
                    "cta_summary": job.cta_summary,
                    "subtitle_summary": job.subtitle_summary,
                    "caption_summary": job.caption_summary,
                    "layer_collision_summary": job.layer_collision_summary,
                },
            )
    if graph:
        sync_graph_summary(job, graph)

    video_source = ensure_video_duration(job, video_source, audio_total, work)
    video_duration = safe_probe_duration(video_source)

    job.message = "Muxando áudio + vídeo final"
    job.percent = 96
    set_stage(job, "muxing", "Finalizando MP4", job.message, percent=96)
    # Important: do NOT use -movflags +faststart here. On some Windows PCs/projects it triggers
    # "Cannot allocate memory" during the moov atom second pass, even when the render is complete.
    mux_key = ""
    mux_cached = None
    if graph:
        mux_key, mux_cached = graph.begin(
            "mux",
            {
                "visual_key": visual_key or assembly_key or segments_cache_key,
                "audio_key": audio_key or graph_media_token(audio_file),
                "duration": round(audio_total, 4),
                "audio_codec": "aac_160k_48k_stereo",
                "pipeline": RENDER_PIPELINE_VERSION,
            },
            "Mux final",
        )
    if mux_cached:
        graph.restore(mux_cached, {"final.mp4": out_file})
        if not out_file.exists() or out_file.stat().st_size <= 0:
            mux_cached = None
        else:
            _append_log(job, "Render Graph: mux final reutilizado.")
    if not mux_cached:
        performance_start(job, "mux")
        cmd_mux = [
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-filter_threads", "1", "-filter_complex_threads", "1",
            "-fflags", "+genpts",
            "-i", str(video_source.name),
            "-i", str(audio_file),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
            "-avoid_negative_ts", "make_zero",
            "-movflags", "+faststart",
            str(out_file),
        ]
        run_cmd(job, cmd_mux, cwd=work, quiet_success=True)
        performance_stop(job, "mux")
        if graph:
            graph.commit(
                stage="mux",
                cache_key=mux_key,
                artifacts={"final.mp4": out_file},
                metadata={"duration": round(audio_total, 4), "video_duration": round(video_duration, 4)},
            )
    if graph:
        sync_graph_summary(job, graph)
    final_duration = safe_probe_duration(out_file)
    job.timeline_summary["performance_breakdown"] = dict(job.performance_breakdown)
    job.timeline_summary["subtitle_timing_summary"] = dict(job.subtitle_timing_summary)
    _append_log(job, f"MP4 final pronto: {out_file.name} | duracao={final_duration:.2f}s | audio={audio_total:.2f}s.")
    return final_duration


def generate_youtube_chapters_and_metadata(job: Job, out_file: Path, final_duration: float):
    """Gera automaticamente o arquivo com Capítulos para a descrição do YouTube e Tags sugeridas a partir da narração."""
    try:
        from collections import Counter
        target_dir = out_file.parent if out_file.exists() else job.export_dir
        if not target_dir:
            return
        chapters_file = target_dir / f"{out_file.stem}_Capitulos_YouTube.txt"
        
        cues = list(job.srt_cues or [])
        chapters = [(0.0, "Introdução")]
        
        if cues and final_duration > 30.0:
            interval = max(90.0, min(240.0, final_duration / 6.0))
            next_target = interval
            for cue in cues:
                if cue.start >= next_target and cue.start <= final_duration - 40.0:
                    text_clean = cue.text.replace("\n", " ").strip()
                    words = [w for w in re.findall(r"[\w\u00C0-\u00FF]+", text_clean) if len(w) > 2]
                    title = " ".join(words[:4]).capitalize() if words else f"Parte {len(chapters) + 1}"
                    chapters.append((cue.start, title))
                    next_target = cue.start + interval
        
        def fmt_time(s: float) -> str:
            m = int(s // 60)
            sec = int(s % 60)
            return f"{m:02d}:{sec:02d}"
        
        lines = [
            "======================================================",
            "GLIDE STUDIO - CAPÍTULOS & METADADOS DO YOUTUBE",
            f"Vídeo: {out_file.name}",
            f"Duração Total: {fmt_time(final_duration)} ({final_duration:.1f}s)",
            "======================================================",
            "",
            "📌 CAPÍTULOS PARA A DESCRIÇÃO DO YOUTUBE (Copie e cole):",
            "",
        ]
        for start_sec, ch_title in chapters:
            lines.append(f"{fmt_time(start_sec)} - {ch_title}")
        
        lines.extend([
            "",
            "======================================================",
            "🏷️ TAGS / PALAVRAS-CHAVE SUGERIDAS PARA O YOUTUBE:",
            "",
        ])
        all_text = " ".join([c.text for c in cues]) if cues else out_file.stem
        stop_words = {
            "para", "como", "com", "que", "uma", "um", "dos", "das", "por", "mais",
            "seu", "sua", "esse", "esta", "isso", "quando", "sobre", "entre", "onde",
            "quem", "muito", "mesmo", "depois", "ainda", "assim", "agora", "porque", "entao"
        }
        raw_words = re.findall(r"[A-Za-z\u00C0-\u00FF]{4,}", all_text.lower())
        word_freq = Counter([w for w in raw_words if w not in stop_words])
        top_tags = [w for w, _ in word_freq.most_common(12)]
        if top_tags:
            lines.append(", ".join(top_tags))
        else:
            lines.append(f"{out_file.stem}, documentario, historia, fatos, curiosidades")
            
        lines.append("======================================================\n")
        chapters_file.write_text("\n".join(lines), encoding="utf-8")
        _append_log(job, f"Capítulos e Tags para YouTube gerados com sucesso em {chapters_file.name}")
    except Exception:
        pass


def write_render_report(job: Job, out_file: Path, final_duration: float):
    if not job.export_dir:
        return
    generate_youtube_chapters_and_metadata(job, out_file, final_duration)
    write_editorial_intelligence_plan(job, "final")
    visual_clean = (job.timeline_summary or {}).get("visual_clean_summary") or (job.preflight_summary or {}).get("visual_clean_filter") or {}
    lines = [
        "GLIDE STUDIO - RELATORIO DO RENDER",
        f"Arquivo final: {out_file.name}",
        f"Duracao final: {final_duration:.2f}s",
        f"Perfil: {job.preflight_summary.get('export_profile', 'capcut_compact')}",
        f"Quality Boost: {'ligado' if job.preflight_summary.get('quality_boost') else 'desligado'}",
        f"Turbo Produção: {'ligado' if job.turbo_summary.get('enabled') else 'desligado'}",
        f"Encoder efetivo: {job.turbo_summary.get('encoder_effective') or 'preset do projeto'}",
        f"Codec efetivo: {job.turbo_summary.get('codec_effective') or job.options.get('codec', 'hevc')}",
        (
            "Filtro visual: "
            f"{'ligado' if visual_clean.get('enabled') else 'desligado'} | "
            f"removidos={visual_clean.get('hard_rejected', 0)} | "
            f"rebaixados={visual_clean.get('soft_demoted', 0)} | "
            f"fallback={visual_clean.get('fallback_used', 0)}"
        ),
        f"CTA: {job.cta_summary.get('label') or job.options.get('ctaLanguage') or 'nao informado'}",
        f"Intro: {job.intro_summary.get('mode', 'standard')}",
        "",
        "Timeline",
        json.dumps(job.timeline_summary or {}, ensure_ascii=False, indent=2),
        "",
        "Textos editoriais",
        json.dumps(job.subtitle_summary or {}, ensure_ascii=False, indent=2),
        "",
        "Legendas reais",
        json.dumps(job.caption_summary or {}, ensure_ascii=False, indent=2),
        "",
        "Colisoes de camadas",
        json.dumps(job.layer_collision_summary or {}, ensure_ascii=False, indent=2),
        "",
        "Musica de fundo",
        json.dumps(job.background_music_summary or {}, ensure_ascii=False, indent=2),
        "",
        "Tom / emocao",
        json.dumps(job.emotion_summary or {}, ensure_ascii=False, indent=2),
        "",
        "Ducking musical",
        json.dumps(job.ducking_summary or {}, ensure_ascii=False, indent=2),
        "",
        "Enfases editoriais dos Textos",
        json.dumps(job.strong_moments_summary or {}, ensure_ascii=False, indent=2),
        "",
        "Efeitos sonoros",
        json.dumps(job.sound_fx_summary or {}, ensure_ascii=False, indent=2),
        "",
        "Recuperacao",
        json.dumps(job.recovery_summary or {}, ensure_ascii=False, indent=2),
        "",
        "Preflight",
        json.dumps(job.preflight_summary or {}, ensure_ascii=False, indent=2),
        "",
        "Auto-Fix",
        json.dumps(job.auto_fix_summary or {}, ensure_ascii=False, indent=2),
        "",
        "Direcao inteligente",
        json.dumps(job.director_summary or {}, ensure_ascii=False, indent=2),
        "",
        "Energia da narracao",
        json.dumps(job.energy_summary or {}, ensure_ascii=False, indent=2),
        "",
        "Confianca",
        json.dumps(job.confidence_summary or {}, ensure_ascii=False, indent=2),
        "",
        "Continuidade visual",
        json.dumps(job.continuity_summary or {}, ensure_ascii=False, indent=2),
        "",
        "Antirrepeticao",
        json.dumps(job.anti_repeat_summary or {}, ensure_ascii=False, indent=2),
        "",
        "Aprendizado do canal",
        json.dumps(job.learning_summary or {}, ensure_ascii=False, indent=2),
        "",
        "Master de audio",
        json.dumps(job.audio_master_summary or {}, ensure_ascii=False, indent=2),
        "",
        "Render Graph",
        json.dumps(job.render_graph_run or {}, ensure_ascii=False, indent=2),
        "",
        "Inteligencia editorial",
        json.dumps(job.editorial_intelligence_plan or {}, ensure_ascii=False, indent=2),
    ]
    (job.export_dir / "relatorio_render.txt").write_text(
        str(clean_ui_text("\n".join(lines))),
        encoding="utf-8",
        errors="ignore",
    )
    (job.export_dir / "visual_analysis.json").write_text(
        json.dumps({
            "jobId": job.id,
            "createdAt": _now_iso(),
            "summary": visual_clean,
            "performance": job.performance_breakdown,
            "subtitleTiming": job.subtitle_timing_summary,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    atomic_write_text(
        job.export_dir / "editorial_plan.json",
        json.dumps({
            "jobId": job.id,
            "createdAt": _now_iso(),
            "director": job.director_summary,
            "energy": job.energy_summary,
            "confidence": job.confidence_summary,
            "continuity": job.continuity_summary,
            "antiRepeat": job.anti_repeat_summary,
            "learning": job.learning_summary,
            "editorialIntelligence": job.editorial_intelligence_plan,
            "semanticModel": semantic_model_status(),
        }, ensure_ascii=False, indent=2),
    )
    atomic_write_text(
        job.export_dir / "editorial_intelligence_plan.json",
        json.dumps(job.editorial_intelligence_plan or {}, ensure_ascii=False, indent=2),
    )
    atomic_write_text(
        job.export_dir / "audio_master_report.json",
        json.dumps(job.audio_master_summary or {"enabled": False}, ensure_ascii=False, indent=2),
    )
    atomic_write_text(
        job.export_dir / "render_graph_run.json",
        json.dumps(job.render_graph_run or {}, ensure_ascii=False, indent=2),
    )


def human_render_error(exc: Exception) -> str:
    raw = str(exc)
    if isinstance(exc, RenderCancelled) or "render cancelado pelo usuario" in raw.lower():
        return "Render cancelado pelo usuario."
    lowered = raw.lower()
    if "invalid nal unit" in lowered or "missing picture" in lowered or "invalid data found" in lowered:
        return (
            "FFmpeg encontrou um clipe de video corrompido ou incompleto durante o render. "
            "O editor tenta pular clipes suspeitos na pre-checagem, mas este arquivo falhou ao decodificar no meio do processo. "
            "Abra os detalhes tecnicos/render_log.txt para ver o clipe perto do ultimo comando e remova/substitua esse arquivo."
        )
    if "no such file" in lowered or "cannot find" in lowered:
        return "Um arquivo do projeto nao foi encontrado durante o render. Limpe o projeto, importe novamente os arquivos e tente renderizar."
    if "ffmpeg nao encontrado" in lowered or "ffprobe" in lowered:
        return "FFmpeg/ffprobe nao foi encontrado. Coloque ffmpeg.exe e ffprobe.exe ao lado do app ou adicione FFmpeg ao PATH."
    if "cta" in lowered and ("indisponivel" in lowered or "invalido" in lowered):
        return "CTA indisponivel ou nao selecionado. Escolha um CTA no painel antes de renderizar."
    if "cinematic precisa" in lowered:
        return "A abertura cinematografica pode usar um Texto forte ou seguir apenas com fade-in."
    if "video final ficou curto" in lowered:
        return raw
    return raw


def recovery_enabled(options: dict[str, Any]) -> bool:
    return bool(options.get("renderRecovery", True))


def recovery_attempt_index(job: Job) -> int:
    try:
        return int(job.options.get("_recovery_attempt") or 0)
    except Exception:
        return 0


def suspect_video_names(job: Job, exc: Exception) -> list[str]:
    text = str(exc).lower()
    names: list[str] = []
    manifest_video_names = {
        str(item.get("name") or Path(str(item.get("rel") or "")).name)
        for item in job.manifest
        if isinstance(item, dict) and str(item.get("kind") or "") == "video"
    }
    for item in (job.preflight_summary.get("invalid_video_names") or []):
        if item and str(item) in manifest_video_names and item not in names:
            names.append(str(item))
    for item in (job.timeline_summary.get("decode_failed_names") or []):
        if item and str(item) in manifest_video_names and item not in names:
            names.append(str(item))
    if not names:
        for name in manifest_video_names:
            if name and name.lower() in text and name not in names:
                names.append(name)
    return names[:6]


def write_recovery_report(job: Job, action: dict[str, Any]) -> None:
    if not job.export_dir:
        return
    report = dict(job.recovery_summary or {})
    report["latest_action"] = action
    report["updated_at"] = _now_iso()
    try:
        (job.export_dir / "recovery_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def plan_recovery_retry(job: Job, exc: Exception) -> dict[str, Any] | None:
    if isinstance(exc, RenderCancelled) or job.cancel_requested:
        return None
    if not recovery_enabled(job.options):
        return None
    lowered = str(exc).lower()
    if (
        "nenhum audio de narracao valido" in lowered
        or "nenhum áudio de narração válido" in lowered
        or "nenhum audio encontrado" in lowered
        or "nenhum áudio encontrado" in lowered
    ):
        # Codec/GPU retries cannot repair an absent or unreadable narration and
        # must never classify the narration itself as a bad video clip.
        return None
    attempt = recovery_attempt_index(job)
    if attempt >= 3:
        return None
    skipped_names = set(str(item) for item in (job.options.get("_recovery_skip_video_names") or []))
    suspects = [name for name in suspect_video_names(job, exc) if name not in skipped_names]
    if attempt == 0 and suspects:
        return {"kind": "skip_bad_clip", "label": "Pular clipe suspeito", "skip": suspects[:2]}
    if str(job.options.get("codec") or "hevc").lower() != "h264":
        return {"kind": "codec_fallback", "label": "Trocar HEVC por H.264", "codec": "h264"}
    hardware_was_active = bool(
        job.options.get("gpu", False)
        or job.timeline_summary.get("gpu_effective")
        or job.timeline_summary.get("hardware_encoder")
        or job.timeline_summary.get("intermediate_hardware_encoder")
    )
    if hardware_was_active and not bool(job.options.get("_force_cpu")):
        return {"kind": "cpu_fallback", "label": "Trocar GPU por CPU", "gpu": False}
    if suspects:
        return {"kind": "skip_bad_clip", "label": "Pular clipe suspeito", "skip": suspects[:2]}
    return None


def apply_recovery_action(job: Job, action: dict[str, Any], exc: Exception) -> None:
    attempt = recovery_attempt_index(job) + 1
    job.options["_recovery_attempt"] = attempt
    if action.get("kind") == "skip_bad_clip":
        existing = list(job.options.get("_recovery_skip_video_names") or [])
        for name in action.get("skip") or []:
            if name not in existing:
                existing.append(str(name))
        job.options["_recovery_skip_video_names"] = existing
    elif action.get("kind") == "codec_fallback":
        job.options["codec"] = "h264"
        job.options["gpu"] = False
    elif action.get("kind") == "cpu_fallback":
        job.options["gpu"] = False
        job.options["_force_cpu"] = True
    attempts = list((job.recovery_summary or {}).get("attempts") or [])
    attempts.append({
        "attempt": attempt,
        "action": action,
        "error": human_render_error(exc),
        "raw_error": str(exc)[-900:],
        "at": _now_iso(),
    })
    job.recovery_summary = {
        "enabled": True,
        "recovered": False,
        "attempt": attempt,
        "max_attempts": 4,
        "attempts": attempts,
    }
    write_recovery_report(job, action)


def graph_media_token(path: Path) -> dict[str, Any]:
    try:
        resolved = path.resolve()
        stat = resolved.stat()
        return {
            "path": str(resolved),
            "size": int(stat.st_size),
            "modified_ns": int(stat.st_mtime_ns),
        }
    except Exception:
        return {"path": str(path), "size": 0, "modified_ns": 0}


def graph_content_token(path: Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        resolved = path.resolve()
        digest = hashlib.sha256()
        with resolved.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return {"sha256": digest.hexdigest(), "size": int(resolved.stat().st_size)}
    except Exception:
        return graph_media_token(path)


def graph_job_media_token(job: Job, path: Path) -> dict[str, Any]:
    rel = manifest_rel_for_path(job, path)
    normalized_rel = str(rel or path.name).replace("\\", "/")
    for item in job.manifest:
        item_rel = str(item.get("rel") or item.get("name") or "").replace("\\", "/")
        if item_rel != normalized_rel and Path(item_rel).name != Path(normalized_rel).name:
            continue
        return {
            "rel": normalized_rel,
            "size": int(item.get("size") or 0),
            "modified_ms": int(item.get("lastModified") or 0),
        }
    token = graph_media_token(path)
    token.pop("path", None)
    token["rel"] = normalized_rel
    return token


def create_render_graph(job: Job) -> RenderGraph:
    graph = RenderGraph(
        db=INTELLIGENCE_DB,
        cache_root=RENDER_GRAPH_CACHE_ROOT,
        job_id=job.id,
        project_id=str(job.options.get("queueProjectId") or ""),
    )
    cleanup = graph.cleanup()
    if cleanup.get("removed"):
        _append_log(
            job,
            f"Render Graph: limpeza LRU removeu {cleanup['removed']} no(s) e recuperou "
            f"{human_bytes(int(cleanup.get('reclaimed_bytes') or 0))}.",
        )
    job.render_graph_run = graph.summary()
    return graph


def sync_graph_summary(job: Job, graph: RenderGraph) -> None:
    job.render_graph_run = graph.summary()


def manifest_rel_for_path(job: Job, path: Path) -> str:
    target = str(path.resolve()).lower()
    for rel, candidate in job.upload_paths.items():
        try:
            if str(candidate.resolve()).lower() == target and "/" in str(rel).replace("\\", "/"):
                return str(rel).replace("\\", "/")
        except Exception:
            continue
    for item in job.manifest:
        rel = str(item.get("rel") or item.get("name") or "").replace("\\", "/")
        candidate = job.upload_paths.get(rel) or job.upload_paths.get(Path(rel).name)
        try:
            if candidate and str(candidate.resolve()).lower() == target:
                return rel
        except Exception:
            continue
    return path.name


def project_channel_key(job: Job) -> str:
    return str(
        job.options.get("identity")
        or job.options.get("queueProjectName")
        or job.options.get("projectName")
        or job.options.get("outputName")
        or "default"
    ).strip()[:120]


def apply_channel_preferences(job: Job) -> dict[str, Any]:
    enabled = bool(job.options.get("channelLearning", True))
    channel = project_channel_key(job)
    preferences = INTELLIGENCE_DB.preferences(channel) if enabled else []
    applied: list[dict[str, Any]] = []
    observing: list[dict[str, Any]] = []
    category_weights: dict[str, float] = {}
    term_weights: dict[str, float] = {}
    for item in preferences:
        key = str(item.get("preference_key") or "")
        value = item.get("value") if isinstance(item.get("value"), dict) else {}
        evidence = int(item.get("evidence_count") or 0)
        try:
            weight = float(item.get("weight") or 0.0)
        except Exception:
            weight = 0.0
        sign = -1.0 if key.startswith(("reject", "remove", "avoid")) else 1.0
        for raw_category in value.get("categories") or value.get("matched_categories") or []:
            category = str(raw_category).strip().lower()
            if category:
                category_weights[category] = round(category_weights.get(category, 0.0) + sign * max(0.1, weight), 3)
        for raw_term in value.get("keywords") or value.get("terms") or []:
            term = str(raw_term).strip().lower()
            if term:
                term_weights[term] = round(term_weights.get(term, 0.0) + sign * max(0.1, weight), 3)
        if evidence < 3:
            if key:
                observing.append({
                    "preference": key,
                    "evidence": evidence,
                    "needed": max(0, 3 - evidence),
                    "status": "aprendizado observando, ainda sem aplicar",
                })
            continue
        if key == "cta_language" and not str(job.options.get("ctaLanguage") or "").strip():
            language = str(value.get("language") or "").strip().lower()
            if language in CTA_LANGUAGES:
                job.options["ctaLanguage"] = language
                applied.append({"preference": key, "value": language, "evidence": evidence})
        elif key == "music_genre" and not str(job.options.get("backgroundMusicGenre") or "").strip():
            genre = str(value.get("genre") or "").strip().lower()
            if genre in PRESET_MUSIC_GENRES:
                job.options["backgroundMusicGenre"] = genre
                applied.append({"preference": key, "value": genre, "evidence": evidence})
        elif key == "subtitle_animation" and str(job.options.get("subtitleAnimation") or "mixed") in {"", "mixed"}:
            animation = str(value.get("animation") or "").strip()
            if animation:
                job.options["subtitleAnimation"] = animation
                applied.append({"preference": key, "value": animation, "evidence": evidence})
        elif key == "transition_style" and str(job.options.get("transitions") or "off") in {"", "off", "random_balanced"}:
            transition = str(value.get("transition") or "").strip()
            if transition and transition != "off":
                job.options["transitions"] = transition
                applied.append({"preference": key, "value": transition, "evidence": evidence})
        elif key == "music_intensity" and not str(job.options.get("backgroundMusicPreset") or "").strip():
            preset = str(value.get("preset") or "").strip()
            if preset:
                job.options["backgroundMusicPreset"] = preset
                applied.append({"preference": key, "value": preset, "evidence": evidence})
        elif key == "subtitle_style" and not isinstance(job.options.get("subtitleStyle"), dict):
            preset = str(value.get("preset") or "").strip()
            if preset:
                job.options["subtitlePreset"] = preset
                applied.append({"preference": key, "value": preset, "evidence": evidence})
    summary = {
        "enabled": enabled,
        "channel": channel,
        "minimum_signals": 3,
        "active_preferences": preferences,
        "applied": applied,
        "observing": observing[:12],
        "category_weights": dict(sorted(category_weights.items(), key=lambda item: abs(item[1]), reverse=True)[:16]),
        "term_weights": dict(sorted(term_weights.items(), key=lambda item: abs(item[1]), reverse=True)[:16]),
        "memory_policy": "preferencias do canal entram como peso suave depois de tres sinais manuais semelhantes",
        "status": (
            "preferencia aplicada"
            if applied else (
                "aprendizado observando, ainda sem aplicar"
                if observing else ("desativado" if not enabled else "sem sinais suficientes")
            )
        ),
    }
    job.learning_summary = summary
    if applied:
        _append_log(job, f"Aprendizado do canal aplicou {len(applied)} preferencia(s) conservadora(s).")
    elif observing:
        _append_log(job, "Aprendizado do canal em observacao: ainda aguardando 3 sinais semelhantes.")
    if job.export_dir:
        atomic_write_text(
            job.export_dir / "channel_learning_summary.json",
            json.dumps(summary, ensure_ascii=False, indent=2),
        )
    return summary


def analyze_voice_energy(audio_file: Path, duration: float, work: Path) -> dict[str, Any]:
    if not FFMPEG or duration <= 0 or not audio_file.exists():
        return {"available": False, "points": [], "reason": "audio indisponivel"}
    try:
        result = _run_hidden(
            [
                FFMPEG, "-hide_banner", "-loglevel", "error",
                "-i", str(audio_file), "-vn", "-ac", "1", "-ar", "1000",
                "-f", "s16le", "-",
            ],
            cwd=work,
            capture_output=True,
            timeout=max(90, int(duration * 0.12) + 30),
        )
        if result.returncode != 0 or not result.stdout:
            return {"available": False, "points": [], "reason": "amostra PCM indisponivel"}
        samples = array("h")
        samples.frombytes(result.stdout)
        window = 1000
        rms_values: list[float] = []
        for start in range(0, len(samples), window):
            chunk = samples[start:start + window]
            if not chunk:
                continue
            square_mean = sum(float(value) * float(value) for value in chunk) / len(chunk)
            rms_values.append(square_mean ** 0.5)
        if not rms_values:
            return {"available": False, "points": [], "reason": "sem amostras"}
        floor = max(1.0, sorted(rms_values)[max(0, int(len(rms_values) * 0.12) - 1)])
        ceiling = max(floor + 1.0, sorted(rms_values)[min(len(rms_values) - 1, int(len(rms_values) * 0.92))])
        normalized = [
            max(0.0, min(1.0, (value - floor) / (ceiling - floor)))
            for value in rms_values
        ]
        variation = sum(abs(normalized[index] - normalized[index - 1]) for index in range(1, len(normalized))) / max(1, len(normalized) - 1)
        return {
            "available": True,
            "sample_rate_hz": 1,
            "points": [round(value, 4) for value in normalized],
            "average": round(sum(normalized) / len(normalized), 4),
            "variation": round(variation, 4),
            "seconds": len(normalized),
        }
    except Exception as exc:
        return {"available": False, "points": [], "reason": str(exc)[:180]}


def merge_voice_energy(energy: dict[str, Any], voice: dict[str, Any]) -> dict[str, Any]:
    points = list(voice.get("points") or [])
    if not voice.get("available") or not points:
        energy["voice"] = voice
        return energy
    for item in energy.get("points") or []:
        start = max(0, int(float(item.get("time") or 0.0)))
        end = max(start + 1, int(float(item.get("end") or start + 1.0) + 0.999))
        window = points[start:min(len(points), end)]
        voice_level = sum(window) / len(window) if window else points[min(start, len(points) - 1)]
        text_level = float(item.get("energy") or 0.0)
        item["text_energy"] = round(text_level, 3)
        item["voice_energy"] = round(voice_level, 3)
        item["energy"] = round(max(0.0, min(1.0, text_level * 0.58 + voice_level * 0.42)), 3)
    energy["average"] = round(
        sum(float(item.get("energy") or 0.0) for item in energy.get("points") or [])
        / max(1, len(energy.get("points") or [])),
        3,
    )
    energy["voice"] = {key: value for key, value in voice.items() if key != "points"}
    return energy


def persist_editorial_state(
    job: Job,
    *,
    director_state: dict[str, Any] | None = None,
    previous_order: list[str] | None = None,
) -> None:
    project_id = str(job.options.get("queueProjectId") or "").strip()
    if not project_id:
        return
    with QUEUE_LOCK:
        project = _find_queue_project(project_id)
        if not project:
            return
        if previous_order:
            history = list(project.get("timelineHistory") or [])
            if not history or history[-1].get("order") != previous_order:
                history.append({
                    "createdAt": _now_iso(),
                    "source": "auto_director",
                    "order": list(previous_order),
                })
            project["timelineHistory"] = history[-10:]
        if director_state is not None:
            project["directorState"] = director_state
            video_order = list(director_state.get("video_order") or [])
            if video_order:
                media = project.get("media") if isinstance(project.get("media"), dict) else {}
                media["videos"] = video_order
                project["media"] = media
                options = project.get("options") if isinstance(project.get("options"), dict) else {}
                options["videoOrder"] = video_order
                project["options"] = options
        project["updatedAt"] = _now_iso()
        _save_queue_projects(QUEUE_PROJECTS)


def apply_auto_director(
    job: Job,
    videos: list[Path],
    subtitle_cues: list[SubtitleCue],
    total_duration: float,
    graph: RenderGraph,
    narration_audio: Path | None = None,
    narration_cache_key: str = "",
) -> list[Path]:
    if not videos:
        return videos
    auto_enabled, director_state = smart_visual_director_effective(job.options, bool(subtitle_cues))
    if not auto_enabled:
        current_order = [manifest_rel_for_path(job, path) for path in videos]
        input_hash = stable_hash({
            "director_version": DIRECTOR_VERSION,
            "media": [graph_job_media_token(job, path) for path in videos],
            "subtitle_count": len(subtitle_cues),
            "state": director_state,
            "priority": render_priority(job),
        })
        job.director_summary = {
            "enabled": False,
            "state": director_state,
            "reason": {
                "suspenso_turbo": "suspenso no Turbo para preservar velocidade maxima",
                "desativado": "opcao desligada pelo usuario",
                "sem_srt_valido": "sem SRT valido para orientar a narracao",
            }.get(director_state, "diretor visual inativo"),
            "input_hash": input_hash,
            "cache_policy": "skip_before_narrative_analysis",
            "video_order": current_order,
            "blocks": [],
            "mode": "smart_scene_fit",
            "decision_mode": _normalized_director_decision_mode(job.options),
            "heavy_analysis_skipped": True,
        }
        job.energy_summary = {
            "enabled": False,
            "reason": job.director_summary["reason"],
            "analysis_skipped": True,
        }
        graph.record_metadata(
            stage="direction",
            payload={"input_hash": input_hash, "enabled": False},
            metadata=job.director_summary,
            label="Direcao inteligente",
        )
        sync_graph_summary(job, graph)
        if job.export_dir:
            atomic_write_text(
                job.export_dir / "smart_director_plan.json",
                json.dumps(job.director_summary, ensure_ascii=False, indent=2),
            )
            atomic_write_text(
                job.export_dir / "energy_map.json",
                json.dumps(job.energy_summary, ensure_ascii=False, indent=2),
            )
        return videos
    narrative_payload = {
        "cues": [
            {"start": round(float(cue.start), 3), "end": round(float(cue.end), 3), "text": cue.text}
            for cue in subtitle_cues
        ],
        "duration": round(total_duration, 3),
        "audio": {"cache_key": narration_cache_key} if narration_cache_key else (
            graph_content_token(narration_audio) if narration_audio else None
        ),
        "energy_enabled": bool(job.options.get("energyEditing", True)),
    }
    narrative_key, narrative_cached = graph.begin("narrative_analysis", narrative_payload, "Analise narrativa")
    narrative_metadata = dict((narrative_cached.get("manifest") or {}).get("metadata") or {}) if narrative_cached else {}
    blocks = list(narrative_metadata.get("blocks") or [])
    energy = dict(narrative_metadata.get("energy") or {})
    if not blocks and subtitle_cues:
        blocks = build_narrative_blocks(subtitle_cues, total_duration)
    if not energy:
        energy = build_energy_map(subtitle_cues, total_duration)
        if narration_audio and bool(job.options.get("energyEditing", True)):
            energy = merge_voice_energy(energy, analyze_voice_energy(narration_audio, total_duration, job.work or narration_audio.parent))
    if bool(job.options.get("energyEditing", True)) and energy.get("points"):
        style_profile = job.options.get("_style_profile_effective") or reference_style_profile(job.options)
        scene_rhythm = scene_rhythm_profile_from_style(style_profile)
        role_targets = scene_rhythm.get("role_targets") if isinstance(scene_rhythm.get("role_targets"), dict) else {}
        role_limits = {}
        for role in ("introduction", "explanation", "conflict", "reveal", "conclusion", "cta"):
            target = _safe_float(role_targets.get(role), 0.0)
            if target > 0:
                role_limits[role] = (max(1.2, target * 0.76), min(7.5, target * 1.18))
        role_limits.update({
            key: value for key, value in {
                "introduction": (2.0, 3.5),
                "explanation": (3.0, 5.0),
                "conflict": (1.8, 3.2),
                "reveal": (1.5, 2.8),
                "conclusion": (3.5, 6.0),
                "cta": (3.5, 5.5),
            }.items() if key not in role_limits
        })
        for block in blocks:
            block_points = [
                point for point in energy["points"]
                if float(block.get("start") or 0.0) <= float(point.get("time") or 0.0) <= float(block.get("end") or 0.0)
            ]
            if not block_points:
                continue
            block_energy = sum(float(point.get("energy") or 0.0) for point in block_points) / len(block_points)
            low, high = role_limits.get(str(block.get("role") or "explanation"), (3.0, 5.0))
            block["energy"] = round(block_energy, 3)
            block["shot_duration"] = round(high - (high - low) * block_energy, 2)
        energy["block_summary"] = [
            {
                "block": int(block.get("index") or 0),
                "role": block.get("role"),
                "start": round(float(block.get("start") or 0.0), 3),
                "end": round(float(block.get("end") or 0.0), 3),
                "energy": block.get("energy"),
                "shot_duration": block.get("shot_duration"),
                "mode": "blocos_narrativos",
                "style_rhythm": scene_rhythm.get("cut_rhythm"),
            }
            for block in blocks
        ]
        energy["scene_rhythm"] = scene_rhythm
    if not narrative_cached:
        graph.commit(
            stage="narrative_analysis",
            cache_key=narrative_key,
            metadata={"blocks": blocks, "energy": energy},
        )
    sync_graph_summary(job, graph)
    job.energy_summary = energy
    energy_path = job.export_dir / "energy_map.json" if job.export_dir else None
    if energy_path:
        atomic_write_text(energy_path, json.dumps(energy, ensure_ascii=False, indent=2))

    canonical_media = sorted(
        (
            {
                "rel": manifest_rel_for_path(job, path),
                "token": graph_job_media_token(job, path),
            }
            for path in videos
        ),
        key=lambda item: str(item["rel"]).lower(),
    )
    current_order = [manifest_rel_for_path(job, path) for path in videos]
    decision_mode = _normalized_director_decision_mode(job.options)
    input_hash = stable_hash({
        "director_version": f"{DIRECTOR_VERSION}:scene_fit_srt_cta_v1",
        "media": canonical_media,
        "cues": [
            {
                "start": round(float(cue.start), 3),
                "end": round(float(cue.end), 3),
                "text": cue.text,
            }
            for cue in subtitle_cues
        ],
        "options": {
            "smartVisualDirector": smart_visual_director_requested(job.options),
            "energyEditing": bool(job.options.get("energyEditing", True)),
            "antiRepeat": bool(job.options.get("antiRepeat", True)),
            "semanticVisualIndex": bool(job.options.get("semanticVisualIndex", True)),
            "directorDecisionMode": decision_mode,
            "renderPriority": render_priority(job),
            "styleProfile": job.options.get("_style_profile_effective") or reference_style_profile(job.options),
        },
    })
    project_id = str(job.options.get("queueProjectId") or "")
    existing_state: dict[str, Any] = {}
    if project_id:
        with QUEUE_LOCK:
            project = _find_queue_project(project_id)
            if project and isinstance(project.get("directorState"), dict):
                existing_state = dict(project["directorState"])

    auto_enabled, director_state = smart_visual_director_effective(job.options, bool(subtitle_cues))
    if not auto_enabled:
        job.director_summary = {
            "enabled": False,
            "state": director_state,
            "reason": {
                "suspenso_turbo": "suspenso no Turbo para preservar velocidade maxima",
                "desativado": "opcao desligada pelo usuario",
                "sem_srt_valido": "sem SRT valido para orientar a narracao",
            }.get(director_state, "diretor visual inativo"),
            "input_hash": input_hash,
            "cache_policy": "media_srt_modo",
            "video_order": current_order,
            "blocks": blocks,
            "mode": "smart_scene_fit",
            "decision_mode": decision_mode,
        }
        graph.record_metadata(
            stage="direction",
            payload={"input_hash": input_hash, "enabled": False},
            metadata=job.director_summary,
            label="Direcao inteligente",
        )
        sync_graph_summary(job, graph)
        if job.export_dir:
            atomic_write_text(
                job.export_dir / "smart_director_plan.json",
                json.dumps(job.director_summary, ensure_ascii=False, indent=2),
            )
        return videos

    stored_order = existing_state.get("video_order") if existing_state.get("input_hash") == input_hash else None
    if isinstance(stored_order, list) and stored_order:
        by_rel = {manifest_rel_for_path(job, path): path for path in videos}
        reordered = [by_rel[rel] for rel in stored_order if rel in by_rel]
        reordered.extend(path for path in videos if path not in reordered)
        job.director_summary = dict(existing_state)
        job.director_summary["reused"] = True
        job.director_summary["indexing_skipped"] = True
        job.director_summary["cache_policy"] = "media_srt_modo"
        job.director_summary["cache_reused_reason"] = "midia, SRT e modo de decisao sem alteracoes"
        if not isinstance(job.director_summary.get("scene_fit_plan"), dict):
            job.director_summary["scene_fit_plan"] = build_director_scene_fit_plan(job, total_duration)
        graph.record_metadata(
            stage="direction",
            payload={"input_hash": input_hash, "stored": True},
            metadata=job.director_summary,
            label="Direcao inteligente",
        )
        sync_graph_summary(job, graph)
        if job.export_dir:
            atomic_write_text(
                job.export_dir / "smart_director_plan.json",
                json.dumps(job.director_summary, ensure_ascii=False, indent=2),
            )
        _append_log(job, "Diretor Visual Inteligente: ordem aprovada reutilizada sem repetir a indexacao visual.")
        return reordered

    semantic_status = semantic_model_status()
    semantic_requested = bool(job.options.get("semanticVisualIndex", True))
    semantic_active = bool(semantic_requested and semantic_status.get("active"))
    index_payload = {
        "media": canonical_media,
        "semantic_requested": semantic_requested,
        "semantic_active": semantic_active,
        "model": semantic_status.get("mode") if semantic_active else "smart_fast_heuristic",
        "director_version": f"{DIRECTOR_VERSION}:scene_fit_srt_cta_v1",
    }
    index_key, index_cached = graph.begin("indexing", index_payload, "Indexacao visual")
    video_items: list[dict[str, Any]] = []
    if index_cached:
        cached_items = ((index_cached.get("manifest") or {}).get("metadata") or {}).get("items") or []
        by_path = {str(item.get("path") or "").lower(): item for item in cached_items if isinstance(item, dict)}
        for path in videos:
            item = by_path.get(str(path.resolve()).lower())
            if item:
                cached_item = dict(item)
                cached_item["media_type"] = "image" if is_image_path(path) else str(cached_item.get("media_type") or "video")
                video_items.append(cached_item)
        if len(video_items) != len(videos):
            video_items = []
    if not video_items:
        for original_index, path in enumerate(videos):
            indexed: dict[str, Any] = {}
            try:
                cached = INTELLIGENCE_DB.get_media_index(media_signature(path))
                if isinstance(cached, dict):
                    indexed = cached
                if semantic_active and (not indexed or str(indexed.get("model_version") or "") != "mobileclip"):
                    indexed = index_media_file(path, duration=0.0, cwd=job.work, detailed=False)
            except Exception:
                indexed = {}
            features = indexed.get("features") if isinstance(indexed.get("features"), dict) else {}
            category = str(features.get("category") or "")
            category_items = indexed.get("categories") if isinstance(indexed.get("categories"), list) else categories_for_path(path)
            categories = [
                str(item.get("name") if isinstance(item, dict) else item)
                for item in category_items
                if str(item.get("name") if isinstance(item, dict) else item).strip()
            ]
            if not categories:
                categories = [str(item.get("name")) for item in categories_for_path(path) if item.get("name")]
            clip_keywords = keyword_terms(
                f"{path.stem.replace('_', ' ')} {' '.join(categories)}",
                limit=16,
            )
            video_items.append({
                "path": str(path.resolve()),
                "rel": manifest_rel_for_path(job, path),
                "media_type": "image" if is_image_path(path) else "video",
                "categories": categories[:6],
                "keywords": clip_keywords,
                "fingerprint": str(indexed.get("fingerprint") or media_signature(path)[:16]),
                "clip_number": clip_number_hint(path),
                "original_index": original_index,
                "suspect": category in {
                    "text_dominant", "text_suspect", "presenter_suspect",
                    "static_center_suspect", "black",
                },
                "visual_category": category,
            })
        graph.commit(
            stage="indexing",
            cache_key=index_key,
            metadata={
                "items": video_items,
                "model": {"mode": semantic_status.get("mode") if semantic_active else "smart_fast_heuristic", "semantic": semantic_active},
                "indexed": len(video_items),
                "note": "Indice leve: nome do arquivo, cache visual existente, numeracao e assinatura local.",
                "semantic_active": semantic_active,
                "semantic_model": semantic_status,
            },
        )
    sync_graph_summary(job, graph)
    category_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    for item in video_items:
        categories = [str(value) for value in (item.get("categories") or []) if str(value).strip()]
        if not categories:
            categories = ["general"]
        for category in categories[:3]:
            category_counts[category] = category_counts.get(category, 0) + 1
        source = "cache" if index_cached else ("semantic_model" if semantic_active else "heuristic")
        if item.get("visual_category") in {"text_dominant", "text_suspect", "presenter_suspect", "black"}:
            source = "visual_clean_cache"
        source_counts[source] = source_counts.get(source, 0) + 1
    visual_index_summary = {
        "enabled": semantic_requested,
        "incremental": True,
        "cache_reused": bool(index_cached),
        "semantic_active": semantic_active,
        "model": semantic_status.get("mode") if semantic_active else "smart_fast_heuristic",
        "items": len(video_items),
        "categories": category_counts,
        "sources": source_counts,
        "note": "Categorias simples para pesquisa visual: pessoa/documento/máquina/cidade/veículo/comida/natureza/texto/estático quando disponível.",
    }
    if job.export_dir:
        atomic_write_text(
            job.export_dir / "visual_index_summary.json",
            json.dumps(visual_index_summary, ensure_ascii=False, indent=2),
        )

    channel = project_channel_key(job)
    recent = (
        INTELLIGENCE_DB.recent_visual_fingerprints(channel, limit_jobs=5)
        if bool(job.options.get("antiRepeat", True))
        else set()
    )
    preferences = (
        INTELLIGENCE_DB.preferences(channel)
        if bool(job.options.get("channelLearning", True))
        else []
    )
    job.learning_summary.update({
        "enabled": bool(job.options.get("channelLearning", True)),
        "channel": channel,
        "active_preferences": preferences,
        "minimum_signals": 3,
        "director_decision_mode": decision_mode,
    })
    directed = direct_timeline(
        video_items,
        [
            {**block, "total_duration": total_duration}
            for block in blocks
        ],
        recent_fingerprints=recent,
        preferences=preferences,
        decision_mode=decision_mode,
    )
    ordered_paths = [Path(path) for path in directed.get("order") or []]
    by_resolved = {str(path.resolve()).lower(): path for path in videos}
    reordered = [
        by_resolved[str(path.resolve()).lower()]
        for path in ordered_paths
        if str(path.resolve()).lower() in by_resolved
    ]
    reordered.extend(path for path in videos if path not in reordered)
    new_order = [manifest_rel_for_path(job, path) for path in reordered]
    order_comparison = [
        {
            "position": index + 1,
            "before": current_order[index] if index < len(current_order) else "",
            "after": new_order[index] if index < len(new_order) else "",
            "changed": (current_order[index] if index < len(current_order) else "") != (new_order[index] if index < len(new_order) else ""),
        }
        for index in range(max(len(current_order), len(new_order)))
    ]
    changed_positions = sum(1 for item in order_comparison if item.get("changed"))
    if decision_mode == "conservative" and changed_positions > max(3, int(len(new_order) * 0.18)):
        reordered = list(videos)
        new_order = list(current_order)
        order_comparison = [
            {
                "position": index + 1,
                "before": current_order[index] if index < len(current_order) else "",
                "after": current_order[index] if index < len(current_order) else "",
                "changed": False,
            }
            for index in range(len(current_order))
        ]
        changed_positions = 0
        directed["reordered"] = False
        directed["guardrail"] = {
            "triggered": True,
            "reason": "Modo conservador bloqueou uma reorganizacao ampla demais.",
            "max_local_changes": max(3, int(len(new_order) * 0.18)),
        }
    assignment_preview = [
        {
            "block": item.get("block"),
            "role": item.get("role"),
            "path": item.get("path"),
            "score": item.get("score"),
            "confidence": item.get("confidence"),
            "reason": item.get("reason"),
            "matched_keywords": item.get("matched_keywords") or [],
            "matched_categories": item.get("matched_categories") or [],
        }
        for item in (directed.get("assignments") or [])[:80]
    ]
    assignments_by_block: dict[int, list[dict[str, Any]]] = {}
    for item in directed.get("assignments") or []:
        try:
            block_index = int(item.get("block") or 0)
        except Exception:
            block_index = 0
        assignments_by_block.setdefault(block_index, []).append(item)
    coverage_by_block: list[dict[str, Any]] = []
    for block in blocks:
        block_index = int(block.get("index") or 0)
        selected = assignments_by_block.get(block_index, [])
        target_duration = max(0.0, float(block.get("end") or 0.0) - float(block.get("start") or 0.0))
        avg_score = sum(float(item.get("score") or 0.0) for item in selected) / max(1, len(selected))
        matched_keywords = sorted({
            str(keyword)
            for item in selected
            for keyword in (item.get("matched_keywords") or [])
            if str(keyword).strip()
        })[:12]
        matched_categories = sorted({
            str(category)
            for item in selected
            for category in (item.get("matched_categories") or [])
            if str(category).strip()
        })[:8]
        coverage_score = min(100, round(max(0.0, avg_score) * 18 + min(1.0, len(selected) / max(1.0, target_duration / max(1.2, float(block.get("shot_duration") or 4.0)))) * 34))
        coverage_by_block.append({
            "block": block_index,
            "role": block.get("role"),
            "start": round(float(block.get("start") or 0.0), 3),
            "end": round(float(block.get("end") or 0.0), 3),
            "target_duration": round(target_duration, 3),
            "shot_duration": block.get("shot_duration"),
            "selected_clips": len(selected),
            "average_score": round(avg_score, 3),
            "coverage_score": coverage_score,
            "keywords": block.get("keywords") or [],
            "matched_keywords": matched_keywords,
            "matched_categories": matched_categories,
        })
    state = {
        "enabled": True,
        "input_hash": input_hash,
        "updatedAt": _now_iso(),
        "mode": "smart_scene_fit",
        "decision_mode": decision_mode,
        "cache_policy": "media_srt_modo",
        "state": "ativo",
        "video_order": new_order,
        "previous_order": current_order,
        "reordered": new_order != current_order,
        "changed_positions": changed_positions,
        "comparison": order_comparison[:160],
        "blocks": blocks,
        "assignments": directed.get("assignments") or [],
        "assignment_preview": assignment_preview,
        "coverage_by_block": coverage_by_block,
        "anti_repeat": {
            **(directed.get("anti_repeat") or {}),
            "enabled": bool(job.options.get("antiRepeat", True)),
            "policy": "penalizar repeticoes e rebaixar para fallback; nao remover quando faltar cobertura",
            "reason_types": ["repeticao_visual", "repeticao_por_canal", "repeticao_sequencial"],
        },
        "guardrail": directed.get("guardrail") or {},
        "visual_index": visual_index_summary,
        "model": {"mode": semantic_status.get("mode") if semantic_active else "smart_fast_heuristic", "semantic": semantic_active},
        "style_profile": job.options.get("_style_profile_effective") or reference_style_profile(job.options),
        "scene_rhythm": scene_rhythm_profile_from_style(job.options.get("_style_profile_effective") or reference_style_profile(job.options)),
    }
    job.director_summary = state
    state["scene_fit_plan"] = build_director_scene_fit_plan(job, total_duration)
    job.director_summary = state
    job.anti_repeat_summary = dict(state["anti_repeat"])
    if state["reordered"]:
        persist_editorial_state(job, director_state=state, previous_order=current_order)
        job.options["videoOrder"] = new_order
        _append_log(job, f"Diretor automatico reorganizou {len(new_order)} clipe(s) em {len(blocks)} bloco(s) narrativo(s).")
    else:
        persist_editorial_state(job, director_state=state)
    graph.record_metadata(
        stage="direction",
        payload={"input_hash": input_hash, "channel": channel},
        metadata=state,
        label="Direcao inteligente",
    )
    if job.export_dir:
        atomic_write_text(
            job.export_dir / "smart_director_plan.json",
            json.dumps(state, ensure_ascii=False, indent=2),
        )
    sync_graph_summary(job, graph)
    return reordered


def prepare_audio_foundation(
    job: Job,
    audios: list[Path],
    background_tracks: list[Path],
    subtitles: list[Path],
    subtitle_preview_cues: list[SubtitleCue],
    music_genre: str,
    preset_available_total: int,
    graph: RenderGraph,
) -> tuple[Path, Path, float, float, float, str, str]:
    if not job.work:
        raise RuntimeError("Job sem pasta de trabalho.")
    work = job.work
    mode_intro = intro_mode(job.options)
    intro_seconds = intro_duration(job.options)
    visual = effective_visual_options(job)
    dynamic_pause_enabled = bool(subtitles and visual["dynamic_pauses"])
    music_options = {
        key: job.options.get(key)
        for key in (
            "backgroundMusicVolume", "backgroundMusicVolumeDb",
            "backgroundMusicMode", "backgroundMusicPreset",
            "backgroundMusicDucking", "adaptiveDucking",
            "backgroundMusicGenre",
        )
    } if background_tracks else {}
    payload = {
        "audios": [graph_job_media_token(job, path) for path in audios],
        "background": [graph_job_media_token(job, path) for path in background_tracks],
        "subtitles": [graph_content_token(path) for path in subtitles] if dynamic_pause_enabled else [],
        "options": {
            key: job.options.get(key)
            for key in (
                "voiceNormalize", "dynamicPauses", "dynamicPauseIntensity",
                "introMode", "introDuration", "sampleRender", "smartSampleBlocks", "previewDurationSeconds",
            )
        },
        "music_options": music_options,
        "priority": render_priority(job),
        "pipeline": RENDER_PIPELINE_VERSION,
    }
    cache_key, cached = graph.begin("audio_foundation", payload, "Narracao e musica")
    narration_cached = work / "graph_narration.wav"
    foundation_cached = work / "graph_audio_foundation.wav"
    if cached:
        metadata = graph.restore(
            cached,
            {"narration.wav": narration_cached, "foundation.wav": foundation_cached},
        )
        if narration_cached.exists() and foundation_cached.exists():
            audio_total = float(metadata.get("audio_total") or 0.0)
            timeline_total = float(metadata.get("timeline_total") or 0.0)
            if audio_total > 0 and timeline_total > 0:
                for source, target in (
                    ("audio_health_summary", "audio_health_summary"),
                    ("background_music_summary", "background_music_summary"),
                    ("ducking_summary", "ducking_summary"),
                    ("dynamic_pause_summary", "dynamic_pause_summary"),
                    ("intro_summary", "intro_summary"),
                ):
                    value = metadata.get(source)
                    if isinstance(value, dict):
                        setattr(job, target, value)
                sample_meta = metadata.get("smart_sample_summary")
                if isinstance(sample_meta, dict) and sample_meta.get("enabled") and isinstance(sample_meta.get("windows"), list):
                    job.options["_smart_sample_windows"] = sample_meta["windows"]
                    job.options["_smart_sample_duration"] = float(sample_meta.get("duration") or audio_total)
                _append_log(job, "Render Graph: narracao, musica e ducking reutilizados.")
                sync_graph_summary(job, graph)
                return (
                    narration_cached,
                    foundation_cached,
                    audio_total,
                    timeline_total,
                    float(metadata.get("intro_seconds") or intro_seconds),
                    str(metadata.get("intro_mode") or mode_intro),
                    cache_key,
                )

    set_stage(job, "audio", "Preparando audio", "Preparando audio")
    performance_start(job, "audio")
    audio_concat, audio_total = make_concat_audio(job, audios, work)
    analyze_audio_health(job, audio_concat, audio_total, work)
    if subtitles and visual["dynamic_pauses"]:
        pause_source_cues = subtitle_preview_cues
        if not pause_source_cues:
            try:
                subtitle_path = subtitles[0] if subtitles[0].is_absolute() else work / subtitles[0]
                pause_source_cues = parse_srt_file(subtitle_path)
            except Exception:
                pause_source_cues = []
        pause_cues, _ = normalize_subtitles(
            pause_source_cues,
            audio_total,
            min_duration=float(job.options.get("subtitleMinDuration") or MIN_SUBTITLE_SECONDS),
        )
        pause_plan = build_dynamic_pause_plan(job, pause_cues, audio_total)
        if pause_plan:
            audio_concat, audio_total = insert_dynamic_pauses(job, audio_concat, audio_total, pause_plan, work)
            analyze_audio_health(job, audio_concat, audio_total, work)
    else:
        reason = "suspenso pelo Turbo Produção" if turbo_enabled(job) and bool(job.options.get("dynamicPauses", False)) else "sem SRT ou opção desligada"
        job.dynamic_pause_summary = {
            "enabled": False,
            "requested": bool(job.options.get("dynamicPauses", False)),
            "suspended_by_turbo": bool(turbo_enabled(job) and job.options.get("dynamicPauses", False)),
            "reason": reason,
        }

    smart_sample_summary: dict[str, Any] | None = None
    if bool(job.options.get("sampleRender")) and bool(job.options.get("smartSampleBlocks")):
        sample_seconds = clamp_float(job.options.get("previewDurationSeconds"), 30.0, 12.0, 90.0)
        try:
            sample_source_cues = subtitle_preview_cues
            if not sample_source_cues and subtitles:
                subtitle_path = subtitles[0] if subtitles[0].is_absolute() else work / subtitles[0]
                sample_source_cues = parse_srt_file(subtitle_path)
            windows = build_smart_sample_windows(sample_source_cues, audio_total, sample_seconds)
            sample_audio, sample_total = compose_smart_sample_audio(job, audio_concat, windows, work)
            if sample_total > 0:
                audio_concat = sample_audio
                audio_total = sample_total
                job.options["_smart_sample_windows"] = windows
                job.options["_smart_sample_duration"] = round(sample_total, 3)
                smart_sample_summary = {
                    "enabled": True,
                    "mode": "blocos_narrativos",
                    "duration": round(sample_total, 3),
                    "windows": windows,
                }
                _append_log(job, "Amostra inteligente por blocos: " + ", ".join(f"{item['role']} {item['source_start']:.1f}-{item['source_end']:.1f}s" for item in windows))
        except Exception as exc:
            job.options.pop("_smart_sample_windows", None)
            job.options.pop("_smart_sample_duration", None)
            smart_sample_summary = {"enabled": False, "fallback": True, "reason": human_render_error(exc)}
            _append_log(job, f"Amostra por blocos usou fallback simples: {human_render_error(exc)}")

    timeline_total = audio_total + intro_seconds
    if bool(job.options.get("sampleRender")):
        sample_seconds = clamp_float(job.options.get("previewDurationSeconds"), 30.0, 8.0, 90.0)
        minimum = intro_seconds + 4.0 if intro_seconds else 8.0
        if smart_sample_summary and smart_sample_summary.get("enabled"):
            timeline_total = audio_total + intro_seconds
            _append_log(job, f"Amostra ativa por blocos: render limitado a {timeline_total:.2f}s sem alterar o render final.")
        else:
            timeline_total = min(timeline_total, max(minimum, sample_seconds))
            _append_log(job, f"Amostra ativa: render limitado a {timeline_total:.2f}s para validacao rapida.")
    job.intro_summary = {
        "mode": mode_intro,
        "intro_duration": round(intro_seconds, 3),
        "narration_duration": round(audio_total, 3),
        "timeline_duration": round(timeline_total, 3),
        "voice_delay": round(intro_seconds, 3),
        "background_intro_volume_db": intro_music_db(job.options) if intro_seconds else None,
        "sample_render": bool(job.options.get("sampleRender")),
        "smart_sample": smart_sample_summary,
    }
    final_audio = delay_voiceover_for_intro(job, audio_concat, timeline_total, work, intro_seconds) if intro_seconds else audio_concat
    if background_tracks:
        set_stage(job, "audio", "Preparando música de fundo", "Ajustando música de fundo à narração")
        if job.options.get("backgroundMusicAutoLibrary"):
            _append_log(job, (
                f"Biblioteca musical automatica: genero={music_genre}, "
                f"candidatas={len(background_tracks)}/{preset_available_total or len(background_tracks)}."
            ))
        background_audio = make_background_music(
            job,
            background_tracks,
            timeline_total,
            work,
            render_volume_override=(intro_music_db(job.options) if intro_seconds else None),
        )
        try:
            record_music_usage(
                MUSIC_HISTORY_FILE,
                job_id=job.id,
                genre=music_genre,
                source=str(job.background_music_summary.get("source") or "timeline"),
                tracks=[Path(path).name for path in background_tracks],
                summary=job.background_music_summary,
                channel=project_channel_key(job),
                project_id=str(job.options.get("queueProjectId") or ""),
                status="selected",
            )
        except Exception:
            pass
        final_audio = mix_voiceover_with_background(
            job,
            final_audio,
            background_audio,
            timeline_total,
            work,
            intro_seconds=intro_seconds,
        )
    elif intro_seconds:
        _append_log(job, "Intro Cinematic sem musica de fundo: abertura visual/texto com silencio antes da narracao.")
    performance_stop(job, "audio")
    graph.commit(
        stage="audio_foundation",
        cache_key=cache_key,
        artifacts={
            "narration.wav": audio_concat if audio_concat.is_absolute() else work / audio_concat,
            "foundation.wav": final_audio if final_audio.is_absolute() else work / final_audio,
        },
        metadata={
            "audio_total": round(audio_total, 4),
            "timeline_total": round(timeline_total, 4),
            "intro_seconds": round(intro_seconds, 4),
            "intro_mode": mode_intro,
            "audio_health_summary": job.audio_health_summary,
            "background_music_summary": job.background_music_summary,
            "ducking_summary": job.ducking_summary,
            "dynamic_pause_summary": job.dynamic_pause_summary,
            "intro_summary": job.intro_summary,
            "smart_sample_summary": smart_sample_summary,
        },
    )
    sync_graph_summary(job, graph)
    return audio_concat, final_audio, audio_total, timeline_total, intro_seconds, mode_intro, cache_key


def master_final_audio(job: Job, audio_file: Path, work: Path) -> Path:
    if not bool(job.options.get("audioMastering", True)):
        job.audio_master_summary = {"enabled": False, "reason": "opcao desligada"}
        return audio_file
    performance_start(job, "mastering")
    master_profile = str(job.options.get("platformMasterProfile") or "youtube_long")
    first_cmd = [
        FFMPEG, "-hide_banner", "-nostats", "-i", str(audio_file),
        "-vn", "-af", first_pass_filter(master_profile), "-f", "null", os.devnull,
    ]
    try:
        assert_render_budget(job, "análise de loudness")
        first = _run_hidden(
            first_cmd,
            cwd=work,
            priority=render_priority(job),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=max(120, int(max(1.0, job.estimated_render_duration) * 2.5)),
        )
        assert_render_budget(job, "análise de loudness")
        measurement = parse_loudnorm_output((first.stderr or "") + "\n" + (first.stdout or ""))
        if first.returncode != 0 or not measurement:
            raise RuntimeError("FFmpeg nao retornou medicao loudness valida")
        mastered = work / "audio_mastered.wav"
        second_filter = second_pass_filter(measurement, master_profile) + f",alimiter=limit={limiter_value(master_profile)}"
        run_cmd(
            job,
            [
                FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(audio_file), "-vn",
                "-af", second_filter,
                "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le",
                str(mastered),
            ],
            cwd=work,
            quiet_success=True,
        )
        # The measured two-pass parameters deterministically define the second
        # pass. Avoid decoding the complete mastered file a third time merely
        # to repeat the same loudness measurement.
        job.audio_master_summary = audio_master_report(measurement, measurement, master_profile)
        job.audio_master_summary["verification"] = "second_pass_parameters"
        job.audio_master_summary["verification_pass_avoided"] = True
        job.audio_master_summary["output"] = mastered.name
        _append_log(
            job,
            f"Master de audio ({job.audio_master_summary.get('profile_label')}): "
            f"alvo {job.audio_master_summary.get('target_lufs')} LUFS / {job.audio_master_summary.get('target_true_peak_dbtp')} dBTP; "
            f"saida={job.audio_master_summary.get('output_lufs')} LUFS, "
            f"pico={job.audio_master_summary.get('output_true_peak_dbtp')} dBTP.",
        )
        return mastered
    except RenderCancelled:
        raise
    except Exception as exc:
        job.audio_master_summary = {
            "enabled": True,
            "fallback": True,
            "reason": human_render_error(exc),
            "output": audio_file.name,
        }
        _append_log(job, f"Master de audio usou fallback seguro: {human_render_error(exc)}")
        return audio_file
    finally:
        performance_stop(job, "mastering")


def render_worker(job_id: str):
    job = JOBS[job_id]
    graph: RenderGraph | None = None
    try:
        if not FFMPEG or not FFPROBE:
            raise RuntimeError("FFmpeg/ffprobe não encontrado. Instale FFmpeg e adicione ao PATH, ou coloque ffmpeg.exe e ffprobe.exe na pasta do Glide Studio.")
        if not job.work or not job.export_dir:
            raise RuntimeError("Job sem pasta de trabalho/exportação.")

        if job.cancel_requested or job.status == "cancelled":
            raise RenderCancelled("Render cancelado pelo usuario.")

        job.status = "running"
        set_system_keep_awake(True, "render")
        job.started_at = time.time()
        initial_duration = max(0.0, float(job.options.get("estimatedDurationSeconds") or 0.0))
        initial_estimate = render_time_estimate(initial_duration, job.options) if initial_duration > 0 else {}
        if initial_duration > 0 and not bool(initial_estimate.get("budget_feasible", True)):
            _append_log(
                job,
                f"Aviso de tempo: estimativa para {render_mode_label(render_priority(job))} "
                f"({initial_estimate.get('minimum_required_seconds')}s) ajustou o orçamento inicial automaticamente."
            )
        if initial_duration > 0:
            calc_budget = render_budget_for_duration(initial_duration, render_priority(job), job.options)
            min_req = float(initial_estimate.get("minimum_required_seconds") or 0.0)
            job.render_budget_seconds = max(calc_budget, min_req * 1.5) if calc_budget > 0 else 0.0
            if job.render_budget_seconds > 0:
                job.render_deadline_at = job.started_at + job.render_budget_seconds
                job.render_budget_state = "active"
            else:
                job.render_deadline_at = 0.0
                job.render_budget_state = "disabled"
        performance_start(job, "total")
        job.percent = max(job.percent, 10)
        set_stage(job, "preparing", "Preparando render", "Render em segundo plano iniciado - mantenha o app aberto")
        graph = create_render_graph(job)
        apply_channel_preferences(job)
        graph.record_metadata(
            stage="validation",
            payload={
                "manifest": job.manifest,
                "options": {
                    key: value
                    for key, value in job.options.items()
                    if not str(key).startswith("_recovery_")
                },
            },
            metadata={"preflight": compact_preflight_summary(build_preflight_summary(job.manifest, job.options))},
            label="Validacao",
        )
        sync_graph_summary(job, graph)

        # Persist project information in the export folder before render starts.
        (job.export_dir / "manifest.json").write_text(json.dumps(job.manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        (job.export_dir / "options.json").write_text(json.dumps(job.options, indent=2, ensure_ascii=False), encoding="utf-8")
        attach_script_guide_plan_to_job(job)
        preflight_now = build_preflight_summary(job.manifest, job.options)
        job.auto_fix_summary = preflight_now.get("auto_fix_plan") or {}
        job.preflight_summary.update(preflight_now)
        job.render_decisions = build_render_decisions(job)
        apply_render_decisions(job)
        atomic_write_text(
            job.export_dir / "render_decisions.json",
            json.dumps(job.render_decisions, ensure_ascii=False, indent=2),
        )
        write_editorial_intelligence_plan(job, "pre_render")
        priority = render_priority(job)
        job.turbo_summary = turbo_profile(job.options)
        visual = effective_visual_options(job)
        job.preflight_summary["turbo_summary"] = job.turbo_summary
        hw = hardware_profile()
        _append_log(
            job,
            "Hardware detectado: "
            f"{hw.get('acceleration') or 'CPU'} | GPU={hw.get('preferred_gpu') or 'nao identificada'} | "
            f"CPU={hw.get('cpu_count')} threads | RAM={hw.get('ram_gb')} GB | classe={hw.get('performance_class')}.",
        )
        if priority == "max":
            _append_log(job, (
                "Turbo Produção aplicado: zoom, Quality Boost, transições visuais, pausas dinâmicas e "
                "reforços de momentos fortes suspensos somente neste render."
            ))
            _append_log(job, (
                f"Turbo Produção: resolução={job.turbo_summary['resolution']} | "
                f"bitrate={job.turbo_summary['bitrate_kbps']} kbps | "
                f"codec={job.turbo_summary['codec_requested']}->{job.turbo_summary['codec_effective']} | "
                f"encoder={job.turbo_summary['encoder_effective']} {job.turbo_summary['encoder_preset']}."
            ))
        else:
            _append_log(job, "Modo Eficiente aplicado: efeitos visuais e codec do projeto preservados com recursos equilibrados.")
        director_effective, director_state = smart_visual_director_effective(job.options, True)
        _append_log(
            job,
            "Diretor Visual Inteligente: "
            f"{director_state} | solicitado={'sim' if smart_visual_director_requested(job.options) else 'nao'} | "
            f"efetivo={'sim' if director_effective else 'nao'}."
        )

        ordered_video_keys: list[str] = job.options.get("videoOrder") or []
        ordered_audio_keys: list[str] = job.options.get("audioOrder") or []
        ordered_background_keys: list[str] = job.options.get("backgroundMusicOrder") or []
        ordered_subtitle_keys: list[str] = job.options.get("textOrder") or job.options.get("subtitleOrder") or []
        ordered_caption_keys: list[str] = job.options.get("captionOrder") or []

        video_candidates: list[tuple[str, Path]] = []
        audio_candidates: list[tuple[str, Path]] = []
        background_candidates: list[tuple[str, Path]] = []
        subtitle_candidates: list[tuple[str, Path]] = []
        caption_candidates: list[tuple[str, Path]] = []
        script_guide_candidates: list[tuple[str, Path]] = []
        for item in job.manifest:
            rel = item.get("rel") or item.get("name")
            path = job.upload_paths.get(rel) or job.upload_paths.get(Path(str(rel)).name)
            if not path:
                continue
            ext = path.suffix.lower()
            kind = item.get("kind")
            if kind == "background_music":
                background_candidates.append((rel, path))
            elif kind == "script_guide" or ext in SCRIPT_GUIDE_EXTS:
                script_guide_candidates.append((rel, path))
            elif kind == "caption_srt":
                caption_candidates.append((rel, path))
            elif kind in {"text_srt", "subtitle"} or ext in SRT_EXTS:
                subtitle_candidates.append((rel, path))
            elif kind in {"video", "image"} or (kind not in {"audio", "background_music", "subtitle", "text_srt", "caption_srt", "script_guide"} and (ext in VIDEO_EXTS or ext in IMAGE_EXTS)):
                video_candidates.append((rel, path))
            elif kind == "audio" or (kind not in {"background_music", "subtitle", "text_srt", "caption_srt", "script_guide", "video", "image"} and ext in AUDIO_EXTS):
                audio_candidates.append((rel, path))

        def order_by(keys: list[str], pairs: list[tuple[str, Path]]) -> list[Path]:
            key_set = set(keys)
            by_key = {k: p for k, p in pairs}
            selected = [by_key[k] for k in keys if k in by_key]
            remaining = [p for k, p in pairs if k not in key_set]
            return selected + sorted(remaining, key=lambda p: natural_key(p.name))

        # Persisted queue media lives outside the per-render work directory.
        # Keep its resolved path instead of collapsing it to the hashed filename;
        # uploaded files are absolute too, so downstream `work / path` operations
        # continue to resolve correctly for both storage modes.
        videos = order_by(ordered_video_keys, video_candidates)
        audios = order_by(ordered_audio_keys, audio_candidates)
        background_tracks = order_by(ordered_background_keys, background_candidates)
        subtitles = order_by(ordered_subtitle_keys, subtitle_candidates)
        captions = order_by(ordered_caption_keys, caption_candidates)
        skip_names = {str(item) for item in (job.options.get("_recovery_skip_video_names") or [])}
        if skip_names:
            before_skip = len(videos)
            videos = [
                path for path in videos
                if path.name not in skip_names and media_display_name(job, path) not in skip_names
            ]
            skipped = before_skip - len(videos)
            if skipped:
                job.preflight_summary["recovery_skipped_videos"] = skipped
                _append_log(job, f"Recuperacao: {skipped} clipe(s) suspeito(s) removidos desta tentativa.")
        music_genre = preset_music_genre(job.options)
        subtitle_preview_cues: list[SubtitleCue] = []
        if subtitles:
            try:
                preview_path = subtitles[0] if subtitles[0].is_absolute() else job.work / subtitles[0]
                subtitle_preview_cues = parse_srt_file(preview_path)[:80]
            except Exception:
                subtitle_preview_cues = []
        job.emotion_summary = infer_project_tone(job.options, job.manifest, subtitle_preview_cues)
        job.preflight_summary["project_tone"] = job.emotion_summary.get("tone")
        _append_log(job, (
            f"Tom do projeto: {job.emotion_summary.get('tone')} "
            f"({job.emotion_summary.get('mode')}); evidencias={', '.join(job.emotion_summary.get('evidence') or []) or 'fallback'}."
        ))
        preset_available_total = 0
        if not background_tracks and bool(job.options.get("backgroundMusicUseLibrary", True)):
            available_preset_tracks = list_preset_music_files(music_genre)
            preset_available_total = len(available_preset_tracks)
            stored_selection = [
                Path(value)
                for value in (job.options.get("backgroundMusicAutoSelection") or [])
                if str(value).strip() and Path(value).exists()
            ]
            if stored_selection:
                preset_tracks = stored_selection
            else:
                stable_music_seed = str(
                    job.options.get("queueProjectId")
                    or job.options.get("projectName")
                    or job.options.get("outputName")
                    or job.id
                )
                preset_tracks, preset_available_total = choose_preset_music_files(
                    music_genre,
                    stable_music_seed,
                    tone=str(job.emotion_summary.get("tone") or "explanatory"),
                    channel=project_channel_key(job),
                )
                if preset_tracks:
                    job.options["backgroundMusicAutoSelection"] = [str(path) for path in preset_tracks]
                    project_id = str(job.options.get("queueProjectId") or "")
                    if project_id:
                        with QUEUE_LOCK:
                            project = _find_queue_project(project_id)
                            if project:
                                project_options = project.get("options") if isinstance(project.get("options"), dict) else {}
                                project_options["backgroundMusicAutoSelection"] = list(job.options["backgroundMusicAutoSelection"])
                                project["options"] = project_options
                                project["updatedAt"] = _now_iso()
                                _save_queue_projects(QUEUE_PROJECTS)
            if preset_tracks:
                background_tracks = preset_tracks
                job.options["backgroundMusicAutoLibrary"] = True
                job.options["backgroundMusicGenre"] = music_genre
            else:
                job.options["backgroundMusicAutoLibrary"] = False
        job.preflight_summary.update({
            "videos_total": len(videos),
            "real_videos_total": len([path for path in videos if is_video_path(path)]),
            "images_total": len([path for path in videos if is_image_path(path)]),
            "visual_media_total": len(videos),
            "audios_total": len(audios),
            "background_tracks_total": len(background_tracks),
            "background_source": "preset_library" if job.options.get("backgroundMusicAutoLibrary") else ("timeline" if background_tracks else "none"),
            "background_genre": music_genre,
            "preset_music_available": preset_available_total,
            "subtitles_total": len(subtitles),
            "texts_total": len(subtitles),
            "captions_total": len(captions),
            "cta_selected": bool(job.options.get("ctaLanguage")),
            "quality_boost_requested": bool(job.options.get("qualityBoost", True)),
            "quality_boost": visual["quality_boost"],
            "export_profile": str(job.options.get("exportProfile") or "capcut_compact"),
            "background_ducking": True,
            "adaptive_ducking": True,
            "dynamic_pauses_requested": False,
            "dynamic_pauses": visual["dynamic_pauses"],
            "strong_moment_enhance_requested": bool(job.options.get("strongMomentEnhance", True)),
            "strong_moment_enhance": visual["strong_moments"],
            "render_recovery": bool(job.options.get("renderRecovery", True)),
            "render_priority": priority,
            "render_priority_requested": str(job.options.get("renderPriority") or "balanced"),
            "render_priority_effective": priority,
            "gpu_requested": bool(job.options.get("gpu", False)),
            "gpu_enabled": (
                bool(job.turbo_summary.get("gpu_effective"))
                if priority == "max"
                else bool(
                    job.timeline_summary.get("gpu_effective")
                    or best_hardware_encoder(
                        "h264"
                        if str(job.options.get("codec") or "hevc").lower() == "h264"
                        else "hevc"
                    )
                )
            ),
            "turbo_summary": job.turbo_summary,
            "intro_mode": intro_mode(job.options),
            "auto_sound_fx": auto_sound_fx_enabled(job.options),
        })
        job.render_plan = build_render_plan(
            app_version=APP_VERSION,
            job_id=job.id,
            options=job.options,
            videos=videos,
            audios=audios,
            background_tracks=background_tracks,
            subtitles=subtitles,
            captions=captions,
            preflight=job.preflight_summary,
        )
        if not videos:
            raise RuntimeError("Nenhum arquivo de vídeo ou imagem reconhecido para a timeline.")
        if not audios:
            raise RuntimeError("Nenhum arquivo de áudio reconhecido.")
        write_render_plan(job.export_dir, job.render_plan)

        (
            audio_concat,
            final_audio,
            audio_total,
            timeline_total,
            intro_seconds,
            mode_intro,
            audio_foundation_key,
        ) = prepare_audio_foundation(
            job,
            audios,
            background_tracks,
            subtitles,
            subtitle_preview_cues,
            music_genre,
            preset_available_total,
            graph,
        )
        narration_analysis_key = stable_hash({
            "audios": [graph_job_media_token(job, path) for path in audios],
            "voice_normalize": bool(job.options.get("voiceNormalize", True)),
            "dynamic_pauses": bool(effective_visual_options(job).get("dynamic_pauses")),
            "dynamic_pause_intensity": job.options.get("dynamicPauseIntensity"),
            "subtitles": [
                graph_content_token(path)
                for path in subtitles
            ] if bool(effective_visual_options(job).get("dynamic_pauses")) else [],
            "pipeline": RENDER_PIPELINE_VERSION,
        })
        performance_start(job, "direction")
        try:
            videos = apply_auto_director(
                job,
                videos,
                subtitle_preview_cues,
                timeline_total,
                graph,
                narration_audio=audio_concat,
                narration_cache_key=narration_analysis_key,
            )
        finally:
            performance_stop(job, "direction")
        job.options["videoOrder"] = [manifest_rel_for_path(job, path) for path in videos]
        job.preflight_summary["director"] = {
            "enabled": bool(job.director_summary.get("enabled")),
            "state": str(job.director_summary.get("state") or ("ativo" if job.director_summary.get("enabled") else "desativado")),
            "mode": str(job.director_summary.get("mode") or "smart_fast"),
            "reordered": bool(job.director_summary.get("reordered")),
            "blocks": len(job.director_summary.get("blocks") or []),
        }
        job.preflight_summary["semantic_model"] = semantic_model_status()
        write_editorial_intelligence_plan(job, "after_direction")
        estimate = render_time_estimate(timeline_total, job.options, priority)
        job.estimated_render_duration = timeline_total
        job.estimated_total_seconds = float(estimate.get("seconds") or 0.0)
        job.estimate_confidence = str(estimate.get("confidence") or "heuristic")
        calc_budget = render_budget_for_duration(timeline_total, priority, job.options)
        min_est = float(estimate.get("minimum_required_seconds") or 0.0)
        job.render_budget_seconds = max(calc_budget, min_est * 1.5) if calc_budget > 0 else 0.0
        if job.render_budget_seconds > 0:
            job.render_deadline_at = float(job.started_at or time.time()) + job.render_budget_seconds
        else:
            job.render_deadline_at = 0.0
            job.render_budget_state = "disabled"
        if not bool(estimate.get("budget_feasible", True)):
            _append_log(
                job,
                f"Aviso de tempo: estimativa ({estimate.get('minimum_required_seconds')}s) "
                f"ajustou o orçamento total para {round(job.render_budget_seconds)}s automaticamente."
            )
        job.preflight_summary["active_render_estimate"] = estimate
        job.preflight_summary["render_budget"] = {
            "mode": render_mode_label(priority),
            "limit_seconds": round(job.render_budget_seconds),
            "multiplier": render_budget_multiplier(priority, job.options),
            "feasible": bool(estimate.get("budget_feasible", True)),
        }
        _append_log(job, (
            f"Estimativa inicial: {estimate['label']} entre "
            f"{estimate['minimum_seconds']}s e {estimate['maximum_seconds']}s "
            f"({estimate['confidence']}, RTF={estimate['realtime_factor']})."
        ))
        job.render_plan = build_render_plan(
            app_version=APP_VERSION,
            job_id=job.id,
            options=job.options,
            videos=videos,
            audios=audios,
            background_tracks=background_tracks,
            subtitles=subtitles,
            captions=captions,
            preflight=job.preflight_summary,
            timeline={
                "narration_duration": round(audio_total, 3),
                "intro_duration": round(intro_seconds, 3),
                "target_duration": round(timeline_total, 3),
            },
        )
        write_render_plan(job.export_dir, job.render_plan)
        _append_log(job, (
            f"Abertura: modo={mode_intro} | narracao={audio_total:.2f}s | "
            f"intro={intro_seconds:.2f}s | timeline_final={timeline_total:.2f}s."
        ))
        job.percent = max(job.percent, 15)

        subtitle_ass = None
        if subtitles:
            set_stage(job, "analyzing_subtitles", "Preparando camadas", "Analisando Textos e Legendas")
            w, h = render_size(job.options.get("mode", "standard"), job.options.get("ratio", "16:9"))
            subtitle_path = subtitles[0] if subtitles[0].is_absolute() else job.work / subtitles[0]
            caption_path = (
                captions[0] if captions and captions[0].is_absolute()
                else (job.work / captions[0] if captions else None)
            )
            ass_key, ass_cached = graph.begin(
                "subtitles_ass",
                {
                    "subtitle": graph_content_token(subtitle_path),
                    "captions": graph_content_token(caption_path) if caption_path else None,
                    "duration": round(timeline_total, 4),
                    "size": [w, h],
                    "style": {
                        key: job.options.get(key)
                        for key in ("subtitleAnimation", "subtitlePreset", "subtitleStyle", "textStyle", "captionStyle", "strongMomentEnhance", "smartSubtitlePlacement", "cinematicOpeningPolicy")
                    },
                    "director_scene_fit": stable_hash(job.director_summary.get("scene_fit_plan") or {}),
                    "style_profile": stable_hash(job.options.get("_style_profile_effective") or reference_style_profile(job.options)),
                    "subtitle_layout_policy": "smart_safe_zones_v1",
                    "pipeline": RENDER_PIPELINE_VERSION,
                },
                "ASS de Textos e Legendas",
            )
            cached_ass = job.work / "combined_layers.ass"
            if ass_cached:
                graph.restore(ass_cached, {"combined_layers.ass": cached_ass})
                if cached_ass.exists() and cached_ass.stat().st_size > 0:
                    subtitle_ass = cached_ass
                    ass_meta = dict((ass_cached.get("manifest") or {}).get("metadata") or {})
                    if isinstance(ass_meta.get("subtitle_summary"), dict):
                        job.subtitle_summary = ass_meta["subtitle_summary"]
                    if isinstance(ass_meta.get("caption_summary"), dict):
                        job.caption_summary = ass_meta["caption_summary"]
                    if isinstance(ass_meta.get("layer_collision_summary"), dict):
                        job.layer_collision_summary = ass_meta["layer_collision_summary"]
                    _append_log(job, "Render Graph: ASS de Textos e Legendas reutilizado.")
            if subtitle_ass is None:
                performance_start(job, "subtitles_ass")
                try:
                    subtitle_ass = build_ass_file(
                        job, subtitle_path, timeline_total, w, h, job.work,
                        caption_path=caption_path,
                    )
                    if subtitle_ass and subtitle_ass.exists():
                        graph.commit(
                            stage="subtitles_ass",
                            cache_key=ass_key,
                            artifacts={"combined_layers.ass": subtitle_ass},
                            metadata={
                                "subtitle_summary": job.subtitle_summary,
                                "caption_summary": job.caption_summary,
                                "layer_collision_summary": job.layer_collision_summary,
                            },
                        )
                finally:
                    performance_stop(job, "subtitles_ass")
            sync_graph_summary(job, graph)

        effective_visual = effective_visual_options(job)
        segment_payload = {
            "videos": [graph_job_media_token(job, path) for path in videos],
            "timeline_total": round(timeline_total, 4),
            "mode": job.options.get("mode", "standard"),
            "ratio": job.options.get("ratio", "16:9"),
            "zoom": effective_visual.get("zoom"),
            "transitions": effective_visual.get("transitions"),
            "quality_boost": effective_visual.get("quality_boost"),
            "continuity": False,
            "continuity_outliers_only": bool(job.options.get("continuityOutliersOnly", True)),
            "visual_clean": bool(job.options.get("visualCleanFilter", True)),
            "score_visual_windows": bool(job.options.get("scoreVisualWindows", True)),
            "adaptive_quality_boost": bool(job.options.get("adaptiveQualityBoost", True)),
            "codec": job.options.get("codec", "hevc"),
            "gpu": bool(job.options.get("gpu", False)),
            "priority": render_priority(job),
            "director_order": job.options.get("videoOrder") or [],
            "decisions_hash": stable_hash(job.render_decisions.get("effectiveOptions") if isinstance(job.render_decisions, dict) else {}),
            "pipeline": RENDER_PIPELINE_VERSION,
        }
        segment_cache_key, segment_cached = graph.begin("segments", segment_payload, "Segmentos")
        segments: list[Path] = []
        if segment_cached:
            segment_metadata = dict((segment_cached.get("manifest") or {}).get("metadata") or {})
            segment_names = [
                str(name)
                for name in (segment_metadata.get("segment_names") or [])
                if str(name).lower().endswith(".mp4")
            ]
            destinations = {
                name: job.work / "segments" / Path(name).name
                for name in segment_names
            }
            graph.restore(segment_cached, destinations)
            segments = [destinations[name] for name in segment_names if destinations[name].exists()]
            if len(segments) != len(segment_names) or not segments:
                segments = []
            else:
                job.timeline_summary = dict(segment_metadata.get("timeline_summary") or {})
                job.continuity_summary = dict(segment_metadata.get("continuity_summary") or {})
                _append_log(job, f"Render Graph: {len(segments)} segmento(s) reutilizado(s) do cache.")
        if not segments:
            segments = make_segments_smart(
                job,
                videos,
                timeline_total,
                mode=job.options.get("mode", "standard"),
                ratio=job.options.get("ratio", "16:9"),
                zoom=job.options.get("zoom", "off"),
                transitions=job.options.get("transitions", "off"),
                codec=job.options.get("codec", "hevc"),
                gpu=bool(job.options.get("gpu", False)),
                work=job.work,
                subtitles=subtitles,
            )
            graph.commit(
                stage="segments",
                cache_key=segment_cache_key,
                artifacts={path.name: path for path in segments},
                metadata={
                    "segment_names": [path.name for path in segments],
                    "timeline_summary": job.timeline_summary,
                    "continuity_summary": job.continuity_summary,
                },
            )
        sync_graph_summary(job, graph)
        job.timeline_summary["subtitle_timing_summary"] = dict(job.subtitle_timing_summary)
        job.timeline_summary["performance_breakdown"] = dict(job.performance_breakdown)
        visual_summary = job.timeline_summary.get("visual_clean_summary") or {}
        raw_video_duration = float(job.timeline_summary.get("raw_video_duration") or 0.0)
        invalid_total = int(job.timeline_summary.get("preflight_invalid_videos") or 0)
        job.confidence_summary = confidence_summary(
            media_total=max(1, len(videos) + invalid_total),
            media_valid=max(0, int(job.timeline_summary.get("valid_clip_count") or len(videos))),
            subtitle_count=len(job.subtitle_cues or subtitle_preview_cues),
            audio_ok=str(job.audio_health_summary.get("status") or "").lower() not in {"problem", "problema"},
            coverage_ratio=min(1.0, raw_video_duration / max(0.1, timeline_total)),
            technical_risk=min(
                1.0,
                (
                    invalid_total
                    + int(visual_summary.get("hard_rejected") or 0)
                    + int(job.timeline_summary.get("decode_failed_segments") or 0)
                )
                / max(1, len(videos) + invalid_total),
            ),
        )
        job.preflight_summary["confidence"] = job.confidence_summary

        output_name = output_name_from_options(job.options)
        technical_out_file = job.export_dir / output_name
        final_duration = concat_segments_and_mux(
            job,
            segments,
            final_audio,
            timeline_total,
            technical_out_file,
            job.work,
            subtitle_ass=subtitle_ass,
            graph=graph,
            segments_cache_key=segment_cache_key,
            audio_foundation_key=audio_foundation_key,
        )
        sync_graph_summary(job, graph)
        performance_start(job, "delivery")
        try:
            out_file = deliver_final_video(job, technical_out_file)
            validate_final_output(job, out_file, final_duration)
        finally:
            performance_stop(job, "delivery")
        if job.render_budget_seconds and render_budget_elapsed(job) > job.render_budget_seconds:
            _append_log(
                job,
                f"Conclusão: render finalizado com sucesso em {round(render_budget_elapsed(job))}s "
                f"(orçamento nominal de {round(job.render_budget_seconds)}s)."
            )
        job.render_plan = build_render_plan(
            app_version=APP_VERSION,
            job_id=job.id,
            options=job.options,
            videos=videos,
            audios=audios,
            background_tracks=background_tracks,
            subtitles=subtitles,
            captions=captions,
            preflight=job.preflight_summary,
            timeline={
                "narration_duration": round(audio_total, 3),
                "intro_duration": round(intro_seconds, 3),
                "target_duration": round(timeline_total, 3),
                "final_duration": round(final_duration, 3),
                "segments": len(segments),
            },
            output=str(out_file),
        )
        performance_stop(job, "total")
        job.timeline_summary["performance_breakdown"] = dict(job.performance_breakdown)
        write_render_plan(job.export_dir, job.render_plan)
        job.render_graph_run = graph.finish("complete")
        write_render_report(job, out_file, final_duration)
        try:
            audit = {
                "kind": "glide_ultra_performance_audit",
                "version": APP_VERSION,
                "project_id": job.options.get("queueProjectId") or "",
                "project_name": job.options.get("queueProjectName") or "",
                "render_priority": render_priority(job),
                "safe_render": bool(job.options.get("safeRenderMode")),
                "duration_seconds": round(float(final_duration or 0.0), 3),
                "breakdown": dict(job.performance_breakdown),
                "render_graph": job.render_graph_run,
                "codec": {
                    "requested": job.options.get("codec"),
                    "gpu": bool(job.options.get("gpu")),
                    "turbo": turbo_enabled(job),
                },
                "created_at": _now_iso(),
            }
            atomic_write_text(job.export_dir / "performance_audit.json", json.dumps(audit, ensure_ascii=False, indent=2))
        except Exception as exc:
            _append_log(job, f"Auditoria de performance nao foi salva ({exc}).")
        if recovery_attempt_index(job) > 0:
            job.recovery_summary.update({
                "enabled": True,
                "recovered": True,
                "final_attempt": recovery_attempt_index(job),
                "output": str(out_file),
            })
            write_recovery_report(job, {"kind": "success", "label": "Render recuperado com sucesso"})
            write_render_report(job, out_file, final_duration)
            _append_log(job, f"RECOVERY: render concluido apos {recovery_attempt_index(job)} tentativa(s) de recuperacao.")

        job.output = str(out_file)
        job.output_dir = str(out_file.parent)
        job.percent = 100
        job.status = "done"
        job.render_budget_state = (
            "met" if not job.render_budget_seconds or render_budget_elapsed(job) <= job.render_budget_seconds
            else "exceeded"
        )
        delivery_label = job.delivery_summary.get("label") or "destino final"
        set_stage(job, "done", "Render concluído", f"Render concluído - arquivo salvo em {delivery_label}", percent=100)
        job.finished_at = time.time()
        try:
            if bool(job.options.get("antiRepeat", True)):
                used_paths = {
                    str(item.get("path") or "")
                    for item in (job.director_summary.get("assignments") or [])
                    if item.get("path")
                }
                indexed_usage = []
                for path_text in used_paths:
                    indexed = index_media_file(Path(path_text), detailed=False)
                    indexed_usage.append({
                        "path": path_text,
                        "fingerprint": indexed.get("fingerprint"),
                    })
                INTELLIGENCE_DB.record_visual_usage(
                    channel=project_channel_key(job),
                    project_id=str(job.options.get("queueProjectId") or ""),
                    job_id=job.id,
                    items=indexed_usage,
                )
        except Exception as exc:
            _append_log(job, f"Antirrepeticao: historico visual nao foi atualizado ({exc}).")
        record_render_performance(job, final_duration)
        _append_log(job, f"FINAL: {out_file}")
        (job.export_dir / "render_log.txt").write_text("\n".join(job.log), encoding="utf-8", errors="ignore")
        persist_job_summary_to_queue(job)
    except RenderBudgetExceeded as exc:
        if graph:
            graph.fail_running(str(exc))
            job.render_graph_run = graph.finish("budget_exceeded")
        performance_stop(job, "total")
        job.status = "error"
        job.render_budget_state = "exceeded"
        job.error = human_render_error(exc)
        job.finished_at = time.time()
        record_render_performance(
            job,
            max(1.0, float(job.estimated_render_duration or job.options.get("estimatedDurationSeconds") or 0.0)),
        )
        set_stage(job, "error", "Orçamento excedido", "Render interrompido para respeitar o limite do modo.")
        _append_log(job, "BUDGET_EXCEEDED: " + job.error)
        try:
            if job.export_dir:
                atomic_write_text(job.export_dir / "render_budget_error.json", json.dumps({
                    "status": "budget_exceeded",
                    "mode": render_mode_label(render_priority(job)),
                    "budget_seconds": round(job.render_budget_seconds),
                    "elapsed_seconds": round(render_budget_elapsed(job)),
                    "fallbacks": job.render_budget_fallbacks,
                    "message": job.error,
                }, ensure_ascii=False, indent=2))
        except Exception:
            pass
        persist_job_summary_to_queue(job)
    except RenderCancelled as exc:
        if graph:
            graph.fail_running(str(exc))
            job.render_graph_run = graph.finish("cancelled")
        performance_stop(job, "total")
        job.cancel_requested = True
        job.cancelled_at = time.time()
        job.status = "cancelled"
        job.error = human_render_error(exc)
        job.finished_at = time.time()
        set_stage(job, "cancelled", "Render cancelado", "Render cancelado pelo usuario.", percent=max(job.percent, 1))
        _append_log(job, "CANCELLED: Render cancelado pelo usuario.")
        try:
            if job.export_dir:
                (job.export_dir / "render_log.txt").write_text("\n".join(job.log), encoding="utf-8", errors="ignore")
                (job.export_dir / "cancelled_render.json").write_text(json.dumps({
                    "status": "cancelled",
                    "cancelled_at": _now_iso(),
                    "message": job.error,
                    "percent": round(job.percent, 1),
                }, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        persist_job_summary_to_queue(job)
    except Exception as exc:
        if graph:
            graph.fail_running(str(exc))
            job.render_graph_run = graph.finish("failed")
        performance_stop(job, "total")
        job.status = "error"
        job.error = human_render_error(exc)
        set_stage(job, "error", "Erro no render", "Erro no render")
        job.percent = max(job.percent, 1)
        job.finished_at = time.time()
        _append_log(job, "ERROR: " + job.error)
        _append_log(job, "ERROR_RAW: " + str(exc))
        try:
            if job.export_dir:
                (job.export_dir / "render_log.txt").write_text("\n".join(job.log), encoding="utf-8", errors="ignore")
                (job.export_dir / "error_actions.json").write_text(json.dumps({
                    "error": job.error,
                    "actions": recommended_error_actions(job.error or str(exc), job),
                    "created_at": _now_iso(),
                }, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        action = plan_recovery_retry(job, exc)
        if action:
            apply_recovery_action(job, action, exc)
            _append_log(job, f"RECOVERY: {action.get('label')} e tentando novamente (tentativa {recovery_attempt_index(job)}/4).")
            job.status = "running"
            job.error = None
            job.percent = max(5.0, min(job.percent, 20.0))
            job.finished_at = None
            set_stage(job, "recovery", "Recuperando render", str(action.get("label") or "Tentando fallback"), percent=job.percent)
            return render_worker(job_id)
        persist_job_summary_to_queue(job)
    finally:
        if not any(other_id != job_id and other.status == "running" for other_id, other in JOBS.items()):
            set_system_keep_awake(False, "render_finished")


@app.post("/api/create-render-job")
async def create_render_job(manifest: str = Form("[]"), options: str = Form("{}")):
    try:
        files_manifest = json.loads(manifest)
        options_obj = json.loads(options)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Manifest/options inválidos: {exc}")
    if isinstance(options_obj, dict):
        options_obj = apply_render_execution_profile(options_obj)


    job_id = uuid.uuid4().hex[:12]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_id_raw = str(options_obj.get("queueBatchId") or "").strip()
    queue_project_raw = str(options_obj.get("queueProjectName") or options_obj.get("outputName") or "").strip()
    queue_index = int(clamp_float(options_obj.get("queueProjectIndex"), 0, 0, 9999))
    if batch_id_raw:
        batch_name = safe_folder_component(batch_id_raw, f"batch_{stamp}")
        project_name = safe_folder_component(queue_project_raw, f"projeto_{queue_index or 1:02d}")
        prefix = f"{queue_index:02d}_" if queue_index else ""
        export_dir = EXPORT_ROOT / batch_name / f"{prefix}{project_name}_{job_id}"
    else:
        export_dir = EXPORT_ROOT / f"render_{stamp}_{job_id}"
    work = UPLOAD_ROOT / job_id
    export_dir.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)

    job = Job(
        id=job_id,
        status="uploading",
        percent=0,
        message="Copiando arquivos para o motor local",
        expected_files=len(files_manifest),
        manifest=files_manifest,
        options=options_obj,
        work=work,
        export_dir=export_dir,
        output_dir=str(export_dir),
    )
    for item in files_manifest:
        if not isinstance(item, dict):
            continue
        source = _resolve_persisted_manifest_item(item)
        if not source:
            continue
        rel_key = str(item.get("rel") or item.get("name") or source.name).replace("\\", "/")
        display_name = Path(rel_key).name or source.name
        job.upload_paths[rel_key] = source
        job.upload_paths[Path(rel_key).name] = source
        job.upload_names[rel_key] = display_name
        job.upload_names[Path(rel_key).name] = display_name
        job.upload_names[source.name] = display_name
        job.uploaded_files += 1
    initial_duration = options_obj.get("estimatedDurationSeconds") or 0
    if initial_duration:
        initial_estimate = render_time_estimate(initial_duration, options_obj)
        job.estimated_render_duration = float(initial_duration)
        job.estimated_total_seconds = float(initial_estimate.get("seconds") or 0.0)
        job.estimate_confidence = str(initial_estimate.get("confidence") or "heuristic")
    JOBS[job_id] = job
    return {
        "job_id": job_id,
        "export_dir": str(export_dir),
        "persisted_files": job.uploaded_files,
        "expected_files": job.expected_files,
    }


@app.post("/api/upload-file/{job_id}")
async def upload_file(
    job_id: str,
    file: UploadFile = File(...),
    rel: str = Form(...),
    kind: str = Form("file"),
    index: int = Form(0),
):
    job = JOBS.get(job_id)
    if not job or not job.work:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if job.status not in {"uploading", "created"}:
        raise HTTPException(status_code=400, detail="Este job já saiu da fase de upload")

    original = rel or file.filename or f"upload_{index}"
    rel_key = original.replace("\\", "/")
    ext = Path(safe_name(original)).suffix.lower() or Path(file.filename or "").suffix.lower() or ".bin"
    if ext not in VIDEO_EXTS and ext not in IMAGE_EXTS and ext not in AUDIO_EXTS and ext not in SRT_EXTS:
        ext = Path(file.filename or f"upload_{index}").suffix.lower() or ".bin"
    dest = job.work / f"u{index:04d}{ext}"
    with dest.open("wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)

    job.upload_paths[rel_key] = dest
    job.upload_paths[Path(rel_key).name] = dest
    display_name = Path(original).name or original
    job.upload_names[rel_key] = display_name
    job.upload_names[Path(rel_key).name] = display_name
    job.upload_names[dest.name] = display_name
    job.uploaded_files += 1
    if job.expected_files:
        job.percent = min(9.9, (job.uploaded_files / job.expected_files) * 10.0)
    job.message = f"Arquivos copiados: {job.uploaded_files}/{job.expected_files}"
    return {"ok": True, "uploaded": job.uploaded_files, "expected": job.expected_files}


@app.post("/api/launch-render/{job_id}")
def launch_render(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if job.thread_started:
        return {"job_id": job.id, "already_started": True}
    if job.expected_files and job.uploaded_files < job.expected_files:
        raise HTTPException(status_code=400, detail=f"Upload incompleto: {job.uploaded_files}/{job.expected_files}")
    job.status = "ready"
    job.message = "Render enviado para segundo plano"
    job.thread_started = True
    t = threading.Thread(target=render_worker, args=(job_id,), daemon=True)
    t.start()
    return {"job_id": job.id, "background": True, "message": "Render em segundo plano iniciado"}


@app.post("/api/cancel-render/{job_id}")
def cancel_render(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nao encontrado")
    if job.status in {"done", "error", "cancelled"}:
        return {"ok": True, "job_id": job.id, "status": job.status, "message": job.message}
    job.cancel_requested = True
    job.cancelled_at = time.time()
    _terminate_job_processes(job)
    job.status = "cancelled"
    job.error = "Render cancelado pelo usuario."
    job.message = "Render cancelado pelo usuario."
    job.finished_at = time.time()
    set_stage(job, "cancelled", "Render cancelado", "Render cancelado pelo usuario.", percent=max(job.percent, 1))
    _append_log(job, "CANCEL: cancelamento solicitado pelo usuario.")
    try:
        if job.export_dir:
            (job.export_dir / "render_log.txt").write_text("\n".join(job.log), encoding="utf-8", errors="ignore")
    except Exception:
        pass
    return {"ok": True, "job_id": job.id, "status": job.status, "message": job.message}


# Legacy one-shot endpoint kept, but the frontend now uses the safer staged upload flow.
@app.post("/api/start-render")
async def start_render_legacy(files: list[UploadFile] = File(...), manifest: str = Form("[]"), options: str = Form("{}")):
    created = await create_render_job(manifest=manifest, options=options)
    job_id = created["job_id"]
    for idx, uf in enumerate(files):
        original = uf.filename or f"upload_{idx}"
        kind = "file"
        try:
            parsed_manifest = json.loads(manifest)
            if idx < len(parsed_manifest):
                kind = parsed_manifest[idx].get("kind", "file")
        except Exception:
            pass
        # save without recursively calling UploadFile endpoint
        job = JOBS[job_id]
        rel_key = original.replace("\\", "/")
        ext = Path(safe_name(original)).suffix.lower() or ".bin"
        dest = job.work / f"u{idx:04d}{ext}"
        with dest.open("wb") as f:
            while True:
                chunk = await uf.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        job.upload_paths[rel_key] = dest
        job.upload_paths[Path(rel_key).name] = dest
        display_name = Path(original).name or original
        job.upload_names[rel_key] = display_name
        job.upload_names[Path(rel_key).name] = display_name
        job.upload_names[dest.name] = display_name
        job.uploaded_files += 1
    launch_render(job_id)
    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
def status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    elapsed = max(0.0, (job.finished_at or time.time()) - (job.started_at or job.created_at))
    estimated_total = max(0.0, float(job.estimated_total_seconds or 0.0))
    active_estimate = (job.preflight_summary or {}).get("active_render_estimate") or {}
    stage_forecast = dict(active_estimate.get("stage_forecast") or {})
    stage_remaining: dict[str, float] = {}
    if job.status == "running" and stage_forecast:
        for key, forecast_value in stage_forecast.items():
            forecast = max(0.0, float(forecast_value or 0.0))
            completed = max(0.0, float(job.performance_breakdown.get(key) or 0.0))
            active_started = job.performance_marks.get(key)
            active_elapsed = max(0.0, time.perf_counter() - active_started) if active_started else 0.0
            if completed > 0 and not active_started:
                stage_remaining[key] = 0.0
                continue
            active_forecast = forecast
            if active_started and job.stage_progress_total > 0 and job.stage_progress_seconds > 0:
                progress_fraction = max(
                    0.03,
                    min(0.98, job.stage_progress_seconds / max(0.1, job.stage_progress_total)),
                )
                active_forecast = max(forecast, active_elapsed / progress_fraction)
            stage_remaining[key] = round(max(0.0, active_forecast - active_elapsed), 1)
        stage_based_total = elapsed + sum(stage_remaining.values())
        if stage_based_total > elapsed:
            estimated_total = estimated_total * 0.42 + stage_based_total * 0.58 if estimated_total else stage_based_total
    elif job.status == "running" and elapsed > 12.0 and job.stage_progress_total > 0:
        progress_fraction = max(
            0.04,
            min(0.98, job.stage_progress_seconds / max(0.1, job.stage_progress_total)),
        )
        observed_total = elapsed / progress_fraction
        estimated_total = estimated_total * 0.58 + observed_total * 0.42 if estimated_total else observed_total
    if job.status == "running":
        # A deadline is a guardrail, not an ETA clamp. Keep showing the honest
        # forecast when a stage is slower than expected.
        estimated_total = max(elapsed + 1.0, estimated_total)
    remaining = max(0.0, estimated_total - elapsed) if job.status == "running" else 0.0
    eta_confidence = str(job.estimate_confidence or "heuristic")
    eta_state = "complete" if job.status != "running" else "estimated"
    eta_reason = ""
    if job.status == "running":
        if elapsed < 15.0 or job.percent < 8.0:
            eta_state = "warming_up"
            eta_confidence = "low"
            eta_reason = "coletando dados iniciais deste render"
        elif not estimated_total:
            eta_state = "unknown"
            eta_confidence = "low"
            eta_reason = "sem historico suficiente para estimar"
        elif eta_confidence != "historical" and job.percent < 35.0:
            eta_state = "variable"
            eta_confidence = "low"
            eta_reason = "estimativa ainda variavel"
        elif eta_confidence == "historical":
            eta_state = "calibrated"
            eta_reason = "baseada no historico deste PC"
        else:
            eta_state = "adaptive"
            eta_reason = "ajustada pelo progresso observado"
    spread = 0.16 if eta_state == "calibrated" else (0.28 if eta_state == "adaptive" else 0.42)
    eta_summary = {
        "elapsed_seconds": round(elapsed),
        "estimated_total_seconds": round(estimated_total),
        "estimated_remaining_seconds": round(remaining),
        "remaining_min_seconds": round(max(0.0, remaining * (1.0 - spread))),
        "remaining_max_seconds": round(max(0.0, remaining * (1.0 + spread))),
        "render_duration_seconds": round(job.estimated_render_duration, 3),
        "confidence": eta_confidence,
        "state": eta_state,
        "reason": eta_reason,
        "stage": job.stage,
        "stage_progress_seconds": round(job.stage_progress_seconds, 1),
        "stage_progress_total": round(job.stage_progress_total, 1),
        "stage_remaining": stage_remaining,
        "budget_seconds": round(job.render_budget_seconds),
        "budget_remaining_seconds": round(render_budget_remaining(job)) if job.status == "running" else 0,
        "budget_state": job.render_budget_state,
        "budget_fallbacks": list(job.render_budget_fallbacks),
    }
    payload = {
        "id": job.id,
        "project_id": job.options.get("queueProjectId"),
        "queueProjectName": job.options.get("queueProjectName"),
        "status": job.status,
        "percent": round(job.percent, 1),
        "message": job.message,
        "stage": job.stage,
        "stage_label": job.stage_label,
        "error": job.error,
        "error_actions": recommended_error_actions(job.error, None) if job.error else [],
        "download": f"/api/download/{job_id}" if job.output else None,
        "output_name": Path(job.output).name if job.output else None,
        "output_dir": job.output_dir,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "cancelled_at": job.cancelled_at,
        "uploaded_files": job.uploaded_files,
        "expected_files": job.expected_files,
        "render_priority_requested": str(job.options.get("renderPriority") or "balanced"),
        "render_priority_effective": render_priority(job),
        "gpu_requested": bool(job.options.get("gpu", False)),
        "gpu_enabled": (
            bool(job.turbo_summary.get("gpu_effective"))
            if turbo_enabled(job)
            else bool(
                job.timeline_summary.get("gpu_effective")
                or job.timeline_summary.get("hardware_encoder")
                or (
                    not bool(job.options.get("_force_cpu"))
                    and best_hardware_encoder(
                        "h264"
                        if str(job.options.get("codec") or "hevc").lower() == "h264"
                        else "hevc"
                    )
                )
            )
        ),
        "turbo_summary": job.turbo_summary,
        "timeline_summary": compact_timeline_summary(job.timeline_summary),
        "preflight_summary": compact_preflight_summary(job.preflight_summary),
        "subtitle_summary": job.subtitle_summary,
        "caption_summary": job.caption_summary,
        "layer_collision_summary": job.layer_collision_summary,
        "background_music_summary": job.background_music_summary,
        "cta_summary": job.cta_summary,
        "intro_summary": job.intro_summary,
        "audio_health_summary": job.audio_health_summary,
        "sound_fx_summary": job.sound_fx_summary,
        "auto_fix_summary": job.auto_fix_summary,
        "emotion_summary": job.emotion_summary,
        "ducking_summary": job.ducking_summary,
        "dynamic_pause_summary": job.dynamic_pause_summary,
        "strong_moments_summary": job.strong_moments_summary,
        "recovery_summary": job.recovery_summary,
        "delivery_summary": job.delivery_summary,
        "director_summary": job.director_summary,
        "energy_summary": job.energy_summary,
        "confidence_summary": job.confidence_summary,
        "continuity_summary": job.continuity_summary,
        "anti_repeat_summary": job.anti_repeat_summary,
        "audio_master_summary": job.audio_master_summary,
        "learning_summary": job.learning_summary,
        "render_graph_run": job.render_graph_run,
        "render_decisions": job.render_decisions,
        "editorial_intelligence_plan": job.editorial_intelligence_plan,
        "performance_history": performance_history_for_project(str(job.options.get("queueProjectId") or "")),
        "render_plan": job.render_plan,
        "eta_summary": eta_summary,
        "render_budget": {
            "mode": render_mode_label(render_priority(job)),
            "limit_seconds": round(job.render_budget_seconds),
            "elapsed_seconds": round(elapsed),
            "remaining_seconds": round(render_budget_remaining(job)) if job.status == "running" else 0,
            "deadline_at": (
                datetime.fromtimestamp(job.render_deadline_at).astimezone().isoformat(timespec="seconds")
                if job.render_deadline_at
                else None
            ),
            "state": job.render_budget_state,
            "fallbacks": list(job.render_budget_fallbacks),
        },
        "log": job.log[-80:],
    }
    return clean_ui_text(payload)


@app.get("/api/jobs/{job_id}/visual-analysis")
def job_visual_analysis(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nao encontrado")
    summary = (job.timeline_summary or {}).get("visual_clean_summary")
    if not isinstance(summary, dict):
        summary = (job.preflight_summary or {}).get("visual_clean_filter")
    if not isinstance(summary, dict):
        summary = {}
    return {
        "jobId": job.id,
        "status": job.status,
        "summary": summary,
        "performance": dict(job.performance_breakdown),
        "subtitleTiming": dict(job.subtitle_timing_summary),
    }


@app.get("/api/jobs")
def list_jobs():
    items = []
    for job in sorted(JOBS.values(), key=lambda j: j.created_at, reverse=True)[:20]:
        items.append({
            "id": job.id,
            "status": job.status,
            "percent": round(job.percent, 1),
            "message": job.message,
            "download": f"/api/download/{job.id}" if job.output else None,
            "output_name": Path(job.output).name if job.output else None,
            "output_dir": job.output_dir,
            "delivery_summary": job.delivery_summary,
            "created_at": job.created_at,
            "finished_at": job.finished_at,
            "error": job.error,
        })
    return {"jobs": items, "exports": str(EXPORT_ROOT)}


@app.get("/api/desktop")
def desktop_status():
    active = [
        job.id for job in JOBS.values()
        if job.status in {"uploading", "ready", "running"}
    ]
    return {
        "version": APP_VERSION,
        "desktop": bool(getattr(sys, "frozen", False) or os.environ.get("GLIDE_ULTRA_DESKTOP")),
        "active_jobs": active,
        "heartbeat_age_seconds": round(time.time() - DESKTOP_HEARTBEAT_AT, 1),
        "exports": str(EXPORT_ROOT),
        "data_root": str(DATA_ROOT),
    }


@app.post("/api/desktop-heartbeat")
def desktop_heartbeat():
    global DESKTOP_HEARTBEAT_AT
    DESKTOP_HEARTBEAT_AT = time.time()
    return {"ok": True, "at": DESKTOP_HEARTBEAT_AT}


@app.post("/api/open-output/{job_id}")
def open_output(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nao encontrado")
    target = Path(job.output) if job.output else Path(job.output_dir or job.export_dir or EXPORT_ROOT)
    if not target.exists():
        raise HTTPException(status_code=404, detail="Pasta de saída não encontrada")
    try:
        _open_path(target)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao abrir pasta: {exc}") from exc
    return {"ok": True, "path": str(target)}


@app.post("/api/open-exports")
def open_exports():
    try:
        _open_path(EXPORT_ROOT)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao abrir exports: {exc}") from exc
    return {"ok": True, "path": str(EXPORT_ROOT)}


@app.get("/api/download/{job_id}")
def download(job_id: str):
    job = JOBS.get(job_id)
    if not job or not job.output:
        raise HTTPException(status_code=404, detail="Render ainda não disponível")
    path = Path(job.output)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo final não encontrado")
    return FileResponse(path, media_type="video/mp4", filename=path.name)


@app.post("/api/clean-project")
def clean_project():
    active_statuses = {"uploading", "ready", "running"}
    active_jobs = [job for job in JOBS.values() if job.status in active_statuses]
    protected: set[Path] = set()
    for job in active_jobs:
        for candidate in (job.work, job.export_dir, Path(job.output_dir) if job.output_dir else None):
            if candidate:
                try:
                    protected.add(candidate.resolve())
                except Exception:
                    pass

    removed = {
        "export_dirs": 0,
        "temp_dirs": 0,
        "project_media_dirs": 0,
        "legacy_items": 0,
    }
    recovered = 0
    errors: list[str] = []

    def is_protected(path: Path) -> bool:
        try:
            resolved = path.resolve()
        except Exception:
            return True
        return any(resolved == item or item in resolved.parents for item in protected)

    def remove_path(path: Path, bucket: str):
        nonlocal recovered
        if is_protected(path):
            return
        try:
            recovered += path_size(path)
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=False)
            else:
                path.unlink(missing_ok=True)
            removed[bucket] += 1
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")

    for folder in (EXPORT_ROOT, UPLOAD_ROOT, PROJECT_MEDIA_ROOT, RENDER_ROOT):
        folder.mkdir(parents=True, exist_ok=True)

    for path in EXPORT_ROOT.iterdir():
        if path.is_dir() and (path.name.startswith("render_") or path.name.startswith("batch_")):
            remove_path(path, "export_dirs")
    for path in UPLOAD_ROOT.iterdir():
        remove_path(path, "temp_dirs")
    for path in PROJECT_MEDIA_ROOT.iterdir():
        remove_path(path, "project_media_dirs")
    for path in RENDER_ROOT.iterdir():
        remove_path(path, "legacy_items")

    for job_id, job in list(JOBS.items()):
        if job.status not in active_statuses:
            JOBS.pop(job_id, None)

    return {
        "ok": True,
        "removed": removed,
        "bytes_recovered": recovered,
        "space_recovered": human_bytes(recovered),
        "active_jobs_kept": len(active_jobs),
        "errors": errors[:8],
        "exports": str(EXPORT_ROOT),
    }


@app.post("/api/clean")
def clean():
    return clean_project()
