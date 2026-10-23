from __future__ import annotations

import gc
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

logger = logging.getLogger("glide_intelligence_db")

SCHEMA_VERSION = 1

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS render_nodes (
    cache_key TEXT PRIMARY KEY,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    artifact_dir TEXT,
    manifest_json TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    accessed_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_render_nodes_accessed
    ON render_nodes(accessed_at);
CREATE INDEX IF NOT EXISTS idx_render_nodes_stage
    ON render_nodes(stage);

CREATE TABLE IF NOT EXISTS graph_runs (
    job_id TEXT PRIMARY KEY,
    project_id TEXT,
    status TEXT NOT NULL,
    run_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS media_index (
    signature TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    modified_ns INTEGER NOT NULL DEFAULT 0,
    full_hash TEXT,
    categories_json TEXT NOT NULL,
    features_json TEXT NOT NULL,
    fingerprint TEXT,
    model_version TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_media_index_path
    ON media_index(path);

CREATE TABLE IF NOT EXISTS correction_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    project_id TEXT,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_correction_channel
    ON correction_events(channel, event_type, created_at);

CREATE TABLE IF NOT EXISTS channel_preferences (
    channel TEXT NOT NULL,
    preference_key TEXT NOT NULL,
    value_json TEXT NOT NULL,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    weight REAL NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL,
    PRIMARY KEY(channel, preference_key)
);

CREATE TABLE IF NOT EXISTS visual_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    project_id TEXT,
    job_id TEXT,
    fingerprint TEXT NOT NULL,
    path TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_visual_usage_channel
    ON visual_usage(channel, created_at);
"""

T = TypeVar("T")


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8", errors="ignore")).hexdigest()


def _is_corrupt_error(exc: Exception) -> bool:
    if isinstance(exc, sqlite3.DatabaseError):
        msg = str(exc).lower()
        return any(term in msg for term in ("malformed", "corrupt", "not a database", "disk i/o error"))
    return False


class IntelligenceDB:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._write_lock = threading.RLock()
        self._initialize_schema()

    def _connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "connection", None)
        if conn is not None:
            return conn
        conn = None
        try:
            conn = sqlite3.connect(self.path, timeout=5, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
            self._local.connection = conn
            return conn
        except Exception as exc:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
                conn = None
            self._local.connection = None
            gc.collect()
            if _is_corrupt_error(exc):
                self._recover_from_corruption()
                conn = sqlite3.connect(self.path, timeout=5, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA busy_timeout=5000")
                self._local.connection = conn
                return conn
            raise

    def close(self) -> None:
        conn = getattr(self._local, "connection", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._local.connection = None
        gc.collect()

    def _initialize_schema(self) -> None:
        try:
            with sqlite3.connect(self.path, timeout=10) as c:
                c.executescript(SCHEMA_DDL)
                c.execute(
                    "INSERT OR REPLACE INTO metadata(key, value) VALUES('schema_version', ?)",
                    (str(SCHEMA_VERSION),),
                )
                c.commit()
        except sqlite3.DatabaseError as exc:
            if _is_corrupt_error(exc):
                self._recover_from_corruption()
            else:
                raise

    def _recover_from_corruption(self) -> None:
        """Autocura de banco: recupera tabelas intactas ou recria banco limpo em milissegundos."""
        with self._write_lock:
            self.close()
            ts = int(time.time() * 1000)
            corrupt_bak = self.path.with_name(f"{self.path.stem}_corrupt_{ts}.sqlite3")
            temp_fixed = self.path.with_name(f"{self.path.stem}_salvaged_{ts}.sqlite3")

            # 1. Tentar salvar tabelas intactas se o arquivo ainda existir
            salvaged = False
            if self.path.exists() and self.path.stat().st_size > 0:
                try:
                    src_conn = sqlite3.connect(f"file:{self.path.resolve()}?mode=ro", uri=True, timeout=5)
                    src_conn.row_factory = sqlite3.Row
                    dst_conn = sqlite3.connect(temp_fixed, timeout=10)
                    dst_conn.executescript(SCHEMA_DDL)
                    tables = [
                        "metadata", "render_nodes", "graph_runs",
                        "channel_preferences", "correction_events",
                        "visual_usage", "media_index"
                    ]
                    for tbl in tables:
                        try:
                            cursor = src_conn.execute(f"SELECT * FROM {tbl}")
                            cols = [d[0] for d in cursor.description]
                            placeholders = ",".join("?" * len(cols))
                            col_str = ",".join(cols)
                            while True:
                                try:
                                    row = cursor.fetchone()
                                    if row is None:
                                        break
                                    dst_conn.execute(
                                        f"INSERT OR IGNORE INTO {tbl}({col_str}) VALUES({placeholders})",
                                        tuple(row),
                                    )
                                except Exception:
                                    break
                            dst_conn.commit()
                        except Exception:
                            pass
                    src_conn.close()
                    dst_conn.close()
                    salvaged = temp_fixed.exists() and temp_fixed.stat().st_size > 0
                except Exception:
                    salvaged = False

            # 2. Fazer backup do corrupto
            try:
                shutil.copy2(self.path, corrupt_bak)
            except Exception:
                pass

            # 3. Substituir ou remover
            replaced = False
            if salvaged:
                try:
                    shutil.copy2(temp_fixed, self.path)
                    temp_fixed.unlink(missing_ok=True)
                    replaced = True
                except Exception:
                    self.path = temp_fixed
                    replaced = True

            if not replaced:
                try:
                    self.path.unlink(missing_ok=True)
                except Exception:
                    self.path = self.path.with_name(f"{self.path.stem}_{ts}.sqlite3")

            # 4. Limpar WAL e SHM
            for ext in (".sqlite3-wal", ".sqlite3-shm", "-wal", "-shm"):
                p = self.path.with_suffix(ext) if ext.startswith(".") else Path(str(self.path) + ext)
                if p.exists():
                    try:
                        p.unlink(missing_ok=True)
                    except Exception:
                        pass

            # 5. Inicializar esquema limpo
            self.close()
            try:
                with sqlite3.connect(self.path, timeout=10) as c:
                    c.executescript(SCHEMA_DDL)
                    c.execute(
                        "INSERT OR REPLACE INTO metadata(key, value) VALUES('schema_version', ?)",
                        (str(SCHEMA_VERSION),),
                    )
                    c.commit()
                logger.info("IntelligenceDB autocura concluída com sucesso em %s", self.path)
            except Exception as e:
                logger.error("Falha ao inicializar banco após recuperação: %s", e)

    def _run_safe(self, action_fn: Callable[[], T], fallback_val: T) -> T:
        try:
            return action_fn()
        except sqlite3.DatabaseError as exc:
            if _is_corrupt_error(exc):
                logger.warning("Corrupção detectada no IntelligenceDB (%s). Executando autocura...", exc)
                try:
                    self._recover_from_corruption()
                    return action_fn()
                except Exception as retry_exc:
                    logger.error("Falha após autocura: %s", retry_exc)
                    return fallback_val
            logger.warning("DatabaseError no IntelligenceDB: %s", exc)
            return fallback_val
        except Exception as exc:
            logger.warning("Exceção no IntelligenceDB: %s", exc)
            return fallback_val

    def upsert_render_node(
        self,
        *,
        cache_key: str,
        stage: str,
        status: str,
        artifact_dir: str,
        manifest: dict[str, Any],
        size_bytes: int,
        expires_at: float,
    ) -> None:
        def _op() -> None:
            now = time.time()
            with self._write_lock:
                connection = self._connection()
                connection.execute(
                    """
                    INSERT INTO render_nodes(
                        cache_key, stage, status, artifact_dir, manifest_json,
                        size_bytes, created_at, accessed_at, expires_at
                    ) VALUES(?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(cache_key) DO UPDATE SET
                        stage=excluded.stage,
                        status=excluded.status,
                        artifact_dir=excluded.artifact_dir,
                        manifest_json=excluded.manifest_json,
                        size_bytes=excluded.size_bytes,
                        accessed_at=excluded.accessed_at,
                        expires_at=excluded.expires_at
                    """,
                    (
                        cache_key,
                        stage,
                        status,
                        artifact_dir,
                        stable_json(manifest),
                        int(size_bytes),
                        now,
                        now,
                        float(expires_at),
                    ),
                )
                connection.commit()

        self._run_safe(_op, None)

    def get_render_node(self, cache_key: str) -> dict[str, Any] | None:
        def _op() -> dict[str, Any] | None:
            connection = self._connection()
            row = connection.execute(
                "SELECT * FROM render_nodes WHERE cache_key=?",
                (cache_key,),
            ).fetchone()
            if not row:
                return None
            if float(row["expires_at"] or 0) < time.time():
                return None
            with self._write_lock:
                connection.execute(
                    "UPDATE render_nodes SET accessed_at=? WHERE cache_key=?",
                    (time.time(), cache_key),
                )
                connection.commit()
            result = dict(row)
            try:
                result["manifest"] = json.loads(result.pop("manifest_json"))
            except Exception:
                result["manifest"] = {}
            return result

        return self._run_safe(_op, None)

    def delete_render_node(self, cache_key: str) -> None:
        def _op() -> None:
            with self._write_lock:
                connection = self._connection()
                connection.execute("DELETE FROM render_nodes WHERE cache_key=?", (cache_key,))
                connection.commit()

        self._run_safe(_op, None)

    def render_nodes_for_cleanup(self) -> list[dict[str, Any]]:
        def _op() -> list[dict[str, Any]]:
            rows = self._connection().execute(
                "SELECT * FROM render_nodes ORDER BY accessed_at ASC"
            ).fetchall()
            return [dict(row) for row in rows]

        return self._run_safe(_op, [])

    def render_cache_stats(self) -> dict[str, Any]:
        def _op() -> dict[str, Any]:
            row = self._connection().execute(
                """
                SELECT COUNT(*) AS total_nodes, COALESCE(SUM(size_bytes), 0) AS total_bytes,
                       MIN(created_at) AS oldest, MAX(accessed_at) AS latest
                FROM render_nodes
                """
            ).fetchone()
            return dict(row) if row else {"total_nodes": 0, "total_bytes": 0}

        return self._run_safe(_op, {"total_nodes": 0, "total_bytes": 0})

    def clear_render_nodes(self) -> list[dict[str, Any]]:
        def _op() -> list[dict[str, Any]]:
            rows = self.render_nodes_for_cleanup()
            with self._write_lock:
                connection = self._connection()
                connection.execute("DELETE FROM render_nodes")
                connection.commit()
            return rows

        return self._run_safe(_op, [])

    def save_graph_run(
        self,
        job_id: str,
        project_id: str,
        status: str,
        payload: dict[str, Any],
    ) -> None:
        def _op() -> None:
            now = time.time()
            with self._write_lock:
                connection = self._connection()
                connection.execute(
                    """
                    INSERT INTO graph_runs(job_id, project_id, status, run_json, created_at, updated_at)
                    VALUES(?,?,?,?,?,?)
                    ON CONFLICT(job_id) DO UPDATE SET
                        project_id=excluded.project_id,
                        status=excluded.status,
                        run_json=excluded.run_json,
                        updated_at=excluded.updated_at
                    """,
                    (job_id, project_id, status, stable_json(payload), now, now),
                )
                connection.commit()

        self._run_safe(_op, None)

    def get_graph_run(self, job_id: str) -> dict[str, Any] | None:
        def _op() -> dict[str, Any] | None:
            row = self._connection().execute(
                "SELECT * FROM graph_runs WHERE job_id=?",
                (job_id,),
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            try:
                result["run"] = json.loads(result.pop("run_json"))
            except Exception:
                result["run"] = {}
            return result

        return self._run_safe(_op, None)

    def latest_graph_run_for_project(self, project_id: str) -> dict[str, Any] | None:
        if not project_id:
            return None

        def _op() -> dict[str, Any] | None:
            row = self._connection().execute(
                """
                SELECT * FROM graph_runs
                WHERE project_id=?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            try:
                result["run"] = json.loads(result.pop("run_json"))
            except Exception:
                result["run"] = {}
            return result

        return self._run_safe(_op, None)

    def upsert_media_index(
        self,
        *,
        signature: str,
        path: str,
        size_bytes: int,
        modified_ns: int,
        categories: list[dict[str, Any]],
        features: dict[str, Any],
        fingerprint: str,
        model_version: str,
        full_hash: str | None = None,
    ) -> None:
        def _op() -> None:
            now = time.time()
            with self._write_lock:
                connection = self._connection()
                connection.execute(
                    """
                    INSERT INTO media_index(
                        signature, path, size_bytes, modified_ns, full_hash,
                        categories_json, features_json, fingerprint, model_version,
                        created_at, updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(signature) DO UPDATE SET
                        path=excluded.path,
                        size_bytes=excluded.size_bytes,
                        modified_ns=excluded.modified_ns,
                        full_hash=COALESCE(excluded.full_hash, media_index.full_hash),
                        categories_json=excluded.categories_json,
                        features_json=excluded.features_json,
                        fingerprint=excluded.fingerprint,
                        model_version=excluded.model_version,
                        updated_at=excluded.updated_at
                    """,
                    (
                        signature,
                        path,
                        int(size_bytes),
                        int(modified_ns),
                        full_hash,
                        stable_json(categories),
                        stable_json(features),
                        fingerprint,
                        model_version,
                        now,
                        now,
                    ),
                )
                connection.commit()

        self._run_safe(_op, None)

    def get_media_index(self, signature: str) -> dict[str, Any] | None:
        def _op() -> dict[str, Any] | None:
            row = self._connection().execute(
                "SELECT * FROM media_index WHERE signature=?",
                (signature,),
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            for source, target, fallback in (
                ("categories_json", "categories", []),
                ("features_json", "features", {}),
            ):
                try:
                    result[target] = json.loads(result.pop(source))
                except Exception:
                    result[target] = fallback
            return result

        return self._run_safe(_op, None)

    def update_media_full_hash(self, signature: str, full_hash: str) -> None:
        if not signature or not full_hash:
            return

        def _op() -> None:
            with self._write_lock:
                connection = self._connection()
                connection.execute(
                    "UPDATE media_index SET full_hash=?, updated_at=? WHERE signature=?",
                    (full_hash, time.time(), signature),
                )
                connection.commit()

        self._run_safe(_op, None)

    def record_correction(
        self,
        *,
        channel: str,
        project_id: str,
        event_type: str,
        payload: dict[str, Any],
        source: str = "user",
    ) -> dict[str, Any]:
        channel_key = (channel or "default").strip().lower()[:120]
        event_key = (event_type or "unknown").strip().lower()[:80]

        def _op() -> dict[str, Any]:
            now = time.time()
            with self._write_lock:
                connection = self._connection()
                connection.execute(
                    """
                    INSERT INTO correction_events(
                        channel, project_id, event_type, payload_json, source, created_at
                    ) VALUES(?,?,?,?,?,?)
                    """,
                    (channel_key, project_id, event_key, stable_json(payload), source, now),
                )
                evidence = connection.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM correction_events
                    WHERE channel=? AND event_type=? AND source='user'
                    """,
                    (channel_key, event_key),
                ).fetchone()
                count = int(evidence["total"] or 0)
                if count >= 3:
                    connection.execute(
                        """
                        INSERT INTO channel_preferences(
                            channel, preference_key, value_json, evidence_count, weight, updated_at
                        ) VALUES(?,?,?,?,?,?)
                        ON CONFLICT(channel, preference_key) DO UPDATE SET
                            value_json=excluded.value_json,
                            evidence_count=excluded.evidence_count,
                            weight=excluded.weight,
                            updated_at=excluded.updated_at
                        """,
                        (
                            channel_key,
                            event_key,
                            stable_json(payload),
                            count,
                            min(1.0, 0.35 + count * 0.1),
                            now,
                        ),
                    )
                connection.commit()
            return {"channel": channel_key, "event": event_key, "evidence": count, "active": count >= 3}

        return self._run_safe(_op, {"channel": channel_key, "event": event_key, "evidence": 0, "active": False})

    def preferences(self, channel: str) -> list[dict[str, Any]]:
        channel_key = (channel or "default").strip().lower()[:120]

        def _op() -> list[dict[str, Any]]:
            rows = self._connection().execute(
                """
                SELECT preference_key, value_json, evidence_count, weight, updated_at
                FROM channel_preferences WHERE channel=?
                ORDER BY weight DESC, updated_at DESC
                """,
                (channel_key,),
            ).fetchall()
            result: list[dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                try:
                    item["value"] = json.loads(item.pop("value_json"))
                except Exception:
                    item["value"] = {}
                result.append(item)
            return result

        return self._run_safe(_op, [])

    def reset_preferences(self, channel: str) -> None:
        channel_key = (channel or "default").strip().lower()[:120]

        def _op() -> None:
            with self._write_lock:
                connection = self._connection()
                connection.execute("DELETE FROM correction_events WHERE channel=?", (channel_key,))
                connection.execute("DELETE FROM channel_preferences WHERE channel=?", (channel_key,))
                connection.commit()

        self._run_safe(_op, None)

    def record_visual_usage(
        self,
        *,
        channel: str,
        project_id: str,
        job_id: str,
        items: list[dict[str, Any]],
    ) -> None:
        now = time.time()
        rows = [
            (
                (channel or "default").strip().lower()[:120],
                project_id,
                job_id,
                str(item.get("fingerprint") or ""),
                str(item.get("path") or ""),
                now,
            )
            for item in items
            if item.get("fingerprint")
        ]
        if not rows:
            return

        def _op() -> None:
            with self._write_lock:
                connection = self._connection()
                connection.executemany(
                    """
                    INSERT INTO visual_usage(
                        channel, project_id, job_id, fingerprint, path, created_at
                    ) VALUES(?,?,?,?,?,?)
                    """,
                    rows,
                )
                connection.commit()

        self._run_safe(_op, None)

    def recent_visual_fingerprints(self, channel: str, limit_jobs: int = 5) -> set[str]:
        channel_key = (channel or "default").strip().lower()[:120]

        def _op() -> set[str]:
            rows = self._connection().execute(
                """
                SELECT fingerprint FROM visual_usage
                WHERE channel=? AND job_id IN (
                    SELECT job_id FROM visual_usage
                    WHERE channel=?
                    GROUP BY job_id
                    ORDER BY MAX(created_at) DESC
                    LIMIT ?
                )
                """,
                (channel_key, channel_key, int(limit_jobs)),
            ).fetchall()
            return {str(row["fingerprint"]) for row in rows if row["fingerprint"]}

        return self._run_safe(_op, set())

    def prune_dead_media(self, limit: int = 500) -> int:
        """Removes entries from media_index whose files no longer exist on disk."""
        def _op() -> int:
            with self._write_lock:
                connection = self._connection()
                rows = connection.execute(
                    "SELECT signature, path FROM media_index ORDER BY updated_at ASC LIMIT ?",
                    (int(limit),),
                ).fetchall()
                dead = [
                    row["signature"] for row in rows
                    if row["path"] and not Path(str(row["path"])).exists()
                ]
                if dead:
                    connection.executemany(
                        "DELETE FROM media_index WHERE signature=?",
                        [(sig,) for sig in dead],
                    )
                    connection.commit()
                return len(dead)

        return self._run_safe(_op, 0)
