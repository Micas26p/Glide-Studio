from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_music_history(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {"version": 1, "renders": []}


def recently_used_names(path: Path, genre: str, limit: int = 36) -> set[str]:
    data = load_music_history(path)
    names: list[str] = []
    for item in reversed(data.get("renders", [])):
        if item.get("genre") != genre:
            continue
        names.extend(str(name) for name in item.get("tracks", []))
        if len(names) >= limit:
            break
    return set(names[:limit])


def channel_music_scores(path: Path, channel: str, genre: str) -> dict[str, float]:
    data = load_music_history(path)
    channel_key = str(channel or "").strip().lower()
    scores: dict[str, float] = {}
    if not channel_key:
        return scores
    for item in data.get("renders", []):
        if item.get("genre") != genre:
            continue
        if str(item.get("channel") or "").strip().lower() != channel_key:
            continue
        summary = item.get("summary") if isinstance(item.get("summary"), dict) else {}
        problematic = bool(summary.get("fallback") or summary.get("problematic") or summary.get("invalid"))
        repeated = bool(summary.get("repeated"))
        for name in item.get("tracks", []):
            key = str(name)
            scores[key] = scores.get(key, 0.0) + (-2.4 if problematic else 0.55)
            if repeated:
                scores[key] = scores.get(key, 0.0) - 0.8
    return scores


def avoid_recent_music(files: list[Path], history_path: Path, genre: str) -> list[Path]:
    recent = recently_used_names(history_path, genre)
    if not recent:
        return files
    fresh = [path for path in files if path.name not in recent]
    stale = [path for path in files if path.name in recent]
    return fresh + stale if fresh else files


def record_music_usage(
    history_path: Path,
    *,
    job_id: str,
    genre: str,
    source: str,
    tracks: list[str],
    summary: dict[str, Any] | None = None,
    channel: str | None = None,
    project_id: str | None = None,
    status: str | None = None,
    max_items: int = 80,
) -> None:
    data = load_music_history(history_path)
    renders = list(data.get("renders", []))
    renders.append({
        "job_id": job_id,
        "genre": genre,
        "source": source,
        "tracks": tracks[:80],
        "channel": channel or "",
        "project_id": project_id or "",
        "status": status or "selected",
        "at": time.time(),
        "summary": summary or {},
    })
    data["renders"] = renders[-max_items:]
    _atomic_write_json(history_path, data)
