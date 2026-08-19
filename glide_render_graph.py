from __future__ import annotations

import json
import os
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from glide_intelligence_db import IntelligenceDB, stable_hash


GRAPH_VERSION = "2.0"
# Keep the resume cache useful without letting it dominate the whole workspace.
# Large projects can create multi-GB artifacts quickly; 8 GB is enough for recent
# retries while avoiding the sluggish filesystem scans caused by a 20 GB cache.
DEFAULT_MAX_BYTES = 8 * 1024 * 1024 * 1024
DEFAULT_RETENTION_SECONDS = 7 * 24 * 60 * 60
_CLEANUP_LOCK = threading.RLock()
_LAST_CLEANUP_AT = 0.0


def _folder_size(path: Path) -> int:
    total = 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                total += item.stat().st_size
    except Exception:
        pass
    return total


def _safe_rmtree(path: Path, *, measure: bool = True) -> int:
    """Best-effort fast delete. Size is optional so cleanup never stalls renders."""
    size = 0
    if measure:
        try:
            size = _folder_size(path)
        except Exception:
            size = 0
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass
    return size


def _copy_or_link(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    try:
        os.link(source, destination)
    except Exception:
        shutil.copy2(source, destination)


class RenderGraph:
    def __init__(
        self,
        *,
        db: IntelligenceDB,
        cache_root: Path,
        job_id: str,
        project_id: str = "",
        max_bytes: int = DEFAULT_MAX_BYTES,
        retention_seconds: int = DEFAULT_RETENTION_SECONDS,
    ):
        self.db = db
        self.cache_root = Path(cache_root)
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.job_id = job_id
        self.project_id = project_id
        self.max_bytes = int(max_bytes)
        self.retention_seconds = int(retention_seconds)
        self.started_at = time.time()
        self.nodes: list[dict[str, Any]] = []
        self.status = "running"
        previous = self.db.latest_graph_run_for_project(project_id) if project_id else None
        self.resuming = bool(previous and str(previous.get("status") or "") in {"failed", "cancelled"})

    def cache_key(self, stage: str, payload: dict[str, Any]) -> str:
        return stable_hash({"graph": GRAPH_VERSION, "stage": stage, "payload": payload})

    def begin(self, stage: str, payload: dict[str, Any], label: str = "") -> tuple[str, dict[str, Any] | None]:
        cache_key = self.cache_key(stage, payload)
        cached = self.db.get_render_node(cache_key)
        if cached:
            artifact_dir = Path(str(cached.get("artifact_dir") or ""))
            manifest = cached.get("manifest") or {}
            artifacts = manifest.get("artifacts") or {}
            artifacts_valid = all(
                (artifact_dir / str(stored_name)).is_file()
                and (artifact_dir / str(stored_name)).stat().st_size > 0
                for stored_name in artifacts.values()
            )
            if artifact_dir.exists() and (artifact_dir / "manifest.json").exists() and artifacts_valid:
                reused_status = "resumed" if self.resuming else "reused"
                node = {
                    "stage": stage,
                    "label": label or stage,
                    "cache_key": cache_key,
                    "status": reused_status,
                    "started_at": time.time(),
                    "finished_at": time.time(),
                    "duration": 0.0,
                    "saved_seconds": float(manifest.get("processing_seconds") or 0.0),
                    "manifest": manifest,
                }
                self.nodes.append(node)
                self._save_run()
                return cache_key, cached
            self.db.delete_render_node(cache_key)
        node = {
            "stage": stage,
            "label": label or stage,
            "cache_key": cache_key,
            "status": "running",
            "started_at": time.time(),
        }
        self.nodes.append(node)
        self._save_run()
        return cache_key, None

    def commit(
        self,
        *,
        stage: str,
        cache_key: str,
        artifacts: dict[str, Path] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        target = self.cache_root / stage / cache_key
        temporary = target.with_name(f".{cache_key}.{uuid.uuid4().hex}.tmp")
        shutil.rmtree(temporary, ignore_errors=True)
        temporary.mkdir(parents=True, exist_ok=True)
        artifact_manifest: dict[str, str] = {}
        for name, source in (artifacts or {}).items():
            if not source or not Path(source).exists():
                continue
            safe_name = Path(name).name
            destination = temporary / safe_name
            _copy_or_link(Path(source), destination)
            artifact_manifest[name] = safe_name
        started_at = next(
            (
                float(node.get("started_at") or time.time())
                for node in reversed(self.nodes)
                if node.get("cache_key") == cache_key
            ),
            time.time(),
        )
        manifest = {
            "graph_version": GRAPH_VERSION,
            "stage": stage,
            "cache_key": cache_key,
            "created_at": time.time(),
            "processing_seconds": round(max(0.0, time.time() - started_at), 4),
            "artifacts": artifact_manifest,
            "metadata": metadata or {},
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(target, ignore_errors=True)
        os.replace(temporary, target)
        size_bytes = _folder_size(target)
        self.db.upsert_render_node(
            cache_key=cache_key,
            stage=stage,
            status="complete",
            artifact_dir=str(target),
            manifest=manifest,
            size_bytes=size_bytes,
            expires_at=time.time() + self.retention_seconds,
        )
        self._finish_node(cache_key, "processed", manifest)
        return manifest

    def record_metadata(
        self,
        *,
        stage: str,
        payload: dict[str, Any],
        metadata: dict[str, Any],
        label: str = "",
    ) -> tuple[dict[str, Any], str]:
        cache_key, cached = self.begin(stage, payload, label)
        if cached:
            return dict((cached.get("manifest") or {}).get("metadata") or {}), "reused"
        manifest = self.commit(stage=stage, cache_key=cache_key, metadata=metadata)
        return dict(manifest.get("metadata") or {}), "processed"

    def restore(self, cached: dict[str, Any], destinations: dict[str, Path]) -> dict[str, Any]:
        artifact_dir = Path(str(cached.get("artifact_dir") or ""))
        manifest = cached.get("manifest") or {}
        artifacts = manifest.get("artifacts") or {}
        for name, destination in destinations.items():
            stored_name = artifacts.get(name)
            if not stored_name:
                continue
            source = artifact_dir / stored_name
            if source.exists():
                _copy_or_link(source, destination)
        return dict(manifest.get("metadata") or {})

    def fail(self, stage: str, cache_key: str, error: str) -> None:
        self._finish_node(cache_key, "failed", {"error": error})
        self.status = "failed"
        self._save_run()

    def fail_running(self, error: str) -> None:
        for node in list(self.nodes):
            if node.get("status") == "running":
                self._finish_node(str(node.get("cache_key") or ""), "failed", {"error": error})
        self.status = "failed"
        self._save_run()

    def finish(self, status: str = "complete") -> dict[str, Any]:
        self.status = status
        payload = self.summary()
        self._save_run()
        return payload

    def summary(self) -> dict[str, Any]:
        return {
            "version": GRAPH_VERSION,
            "job_id": self.job_id,
            "project_id": self.project_id,
            "status": self.status,
            "started_at": self.started_at,
            "updated_at": time.time(),
            "nodes": list(self.nodes),
            "counts": {
                "processed": sum(1 for node in self.nodes if node.get("status") == "processed"),
                "reused": sum(1 for node in self.nodes if node.get("status") == "reused"),
                "resumed": sum(1 for node in self.nodes if node.get("status") == "resumed"),
                "failed": sum(1 for node in self.nodes if node.get("status") == "failed"),
                "running": sum(1 for node in self.nodes if node.get("status") == "running"),
            },
            "saved_seconds": round(
                sum(float(node.get("saved_seconds") or 0.0) for node in self.nodes),
                3,
            ),
        }

    def cleanup(self, force: bool = False) -> dict[str, int | bool]:
        global _LAST_CLEANUP_AT
        with _CLEANUP_LOCK:
            now = time.time()
            if not force and now - _LAST_CLEANUP_AT < 15 * 60:
                return {
                    "removed": 0,
                    "reclaimed_bytes": 0,
                    "remaining_bytes": 0,
                    "skipped": True,
                }
            _LAST_CLEANUP_AT = now
        removed = 0
        orphaned = 0
        reclaimed = 0
        now = time.time()
        rows = self.db.render_nodes_for_cleanup()
        known_dirs = {
            str(Path(str(row.get("artifact_dir") or "")).resolve()).lower()
            for row in rows
            if row.get("artifact_dir")
        }
        if force or len(rows) > 250:
            for stage_dir in list(self.cache_root.iterdir()) if self.cache_root.exists() else []:
                if not stage_dir.is_dir():
                    continue
                for folder in list(stage_dir.iterdir()):
                    if not folder.is_dir():
                        continue
                    resolved = str(folder.resolve()).lower()
                    if resolved in known_dirs:
                        continue
                    _safe_rmtree(folder, measure=False)
                    orphaned += 1
        total = sum(int(row.get("size_bytes") or 0) for row in rows)
        for row in rows:
            expired = float(row.get("expires_at") or 0) < now
            over_budget = total > self.max_bytes
            if not expired and not over_budget:
                continue
            folder = Path(str(row.get("artifact_dir") or ""))
            size = int(row.get("size_bytes") or 0)
            _safe_rmtree(folder, measure=False)
            self.db.delete_render_node(str(row.get("cache_key") or ""))
            total = max(0, total - size)
            reclaimed += size
            removed += 1
        return {"removed": removed, "orphaned": orphaned, "reclaimed_bytes": reclaimed, "remaining_bytes": total}

    def _finish_node(self, cache_key: str, status: str, manifest: dict[str, Any]) -> None:
        now = time.time()
        for node in reversed(self.nodes):
            if node.get("cache_key") != cache_key:
                continue
            node["status"] = status
            node["finished_at"] = now
            node["duration"] = round(max(0.0, now - float(node.get("started_at") or now)), 4)
            node["manifest"] = manifest
            break
        self._save_run()

    def _save_run(self) -> None:
        self.db.save_graph_run(
            self.job_id,
            self.project_id,
            self.status,
            self.summary(),
        )
