import atexit
import gc
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

_sandbox = tempfile.TemporaryDirectory(prefix="glide-queue-tests-")
os.environ["GLIDE_ULTRA_DATA_ROOT"] = _sandbox.name
os.environ["GLIDE_TEST_MODE"] = "1"

import app
from app import (
    BACKEND_QUEUE_MANAGER,
    QUEUE_PROJECTS,
    QUEUE_LOCK,
    _save_queue_projects,
    _find_queue_project,
    choose_video_args,
    Job,
)
from fastapi.testclient import TestClient


def cleanup():
    try:
        app.INTELLIGENCE_DB._connection().close()
    except Exception:
        pass
    gc.collect()

atexit.register(cleanup)


class TestQueueDeterministic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app.app, raise_server_exceptions=False)

    def setUp(self):
        with BACKEND_QUEUE_MANAGER.lock:
            BACKEND_QUEUE_MANAGER.running = False
            BACKEND_QUEUE_MANAGER.paused = False
            BACKEND_QUEUE_MANAGER.stop_requested = False
            BACKEND_QUEUE_MANAGER.pause_requested = False
            BACKEND_QUEUE_MANAGER.current_project_id = None
            BACKEND_QUEUE_MANAGER.current_job_id = None
            BACKEND_QUEUE_MANAGER.queue_items = []
            BACKEND_QUEUE_MANAGER.completed_count = 0
            BACKEND_QUEUE_MANAGER.failed_count = 0

    def test_nvenc_encoder_args_optimized(self):
        """Verify choose_video_args uses -preset p2 and eliminates spatial/temporal AQ throttle."""
        dummy_job = Job(id="test_opt", status="ready", options={"mode": "standard", "gpu": True})
        dummy_job.timeline_summary = {}
        args = choose_video_args("standard", "h264", True, dummy_job)
        
        hw = app.best_hardware_encoder("h264")
        if hw and hw.endswith("_nvenc"):
            self.assertIn("-preset", args)
            idx = args.index("-preset")
            self.assertEqual(args[idx + 1], "p2", "NVENC preset must be p2 for maximum throughput on laptop GPU")
            self.assertNotIn("-spatial-aq", args, "spatial-aq must be removed to avoid CUDA kernel memory throttling")
            self.assertNotIn("-temporal-aq", args, "temporal-aq must be removed to avoid CUDA kernel memory throttling")

    def test_deterministic_10_projects_queue(self):
        """Verify a 10-project queue runs with strict concurrency=1 and completes 10/10 without skipping."""
        project_ids = []
        execution_log = []
        active_concurrency = []
        concurrency_lock = threading.Lock()
        current_active = 0

        with QUEUE_LOCK:
            QUEUE_PROJECTS.clear()
            for i in range(1, 11):
                pid = f"proj_test_{i:02d}"
                project_ids.append(pid)
                QUEUE_PROJECTS.append({
                    "id": pid,
                    "name": f"Projeto {i}",
                    "status": "ready",
                    "options": {"mode": "standard", "selectedCta": "es"},
                    "media": {
                        "videos": [f"v{i}.mp4"],
                        "audios": [f"a{i}.mp3"],
                        "texts": [f"s{i}.srt"],
                    }
                })
            _save_queue_projects(QUEUE_PROJECTS)

        def mock_render_worker(job_id: str):
            nonlocal current_active
            with concurrency_lock:
                current_active += 1
                active_concurrency.append(current_active)
            try:
                job = app.JOBS[job_id]
                pid = job.options.get("queueProjectId")
                execution_log.append(pid)
                time.sleep(0.01)
                job.status = "done"
                job.output = f"/fake/exports/{pid}.mp4"
                job.output_dir = "/fake/exports"
            finally:
                with concurrency_lock:
                    current_active -= 1

        with patch("app._queue_project_missing_requirements", return_value=[]):
            with patch("app.render_worker", side_effect=mock_render_worker):
                resp = self.client.post("/api/queue/start", json={
                    "projectIds": project_ids,
                    "batchId": "batch_test_10",
                })
                self.assertEqual(resp.status_code, 200)
                self.assertTrue(resp.json().get("ok"))

                # Wait for queue manager worker thread to finish
                timeout = 10.0
                t0 = time.time()
                while time.time() - t0 < timeout:
                    status = BACKEND_QUEUE_MANAGER.status()
                    if not status["running"]:
                        break
                    time.sleep(0.02)

                self.assertFalse(BACKEND_QUEUE_MANAGER.status()["running"])
                self.assertEqual(BACKEND_QUEUE_MANAGER.status()["completed_count"], 10)
                self.assertEqual(BACKEND_QUEUE_MANAGER.status()["failed_count"], 0)

        # Assert all 10 projects were executed in exact sequential order
        self.assertEqual(execution_log, project_ids, "All 10 projects must execute in exact specified order")
        # Assert strict concurrency = 1 at all times
        self.assertTrue(all(c == 1 for c in active_concurrency), f"Concurrency exceeded 1: {active_concurrency}")

        # Verify all projects in QUEUE_PROJECTS are marked done
        with QUEUE_LOCK:
            for pid in project_ids:
                p = _find_queue_project(pid)
                self.assertIsNotNone(p)
                self.assertEqual(p.get("status"), "done", f"Project {pid} should be 'done', got {p.get('status')}")

    def test_resilience_to_mid_queue_failure(self):
        """Verify that when Project 3 fails, Project 1, 2, 4, 5 complete successfully and 0 are skipped."""
        project_ids = []
        execution_log = []

        with QUEUE_LOCK:
            QUEUE_PROJECTS.clear()
            for i in range(1, 6):
                pid = f"proj_fail_test_{i}"
                project_ids.append(pid)
                QUEUE_PROJECTS.append({
                    "id": pid,
                    "name": f"Projeto {i}",
                    "status": "ready",
                    "options": {"mode": "standard", "selectedCta": "es"},
                    "media": {
                        "videos": [f"v{i}.mp4"],
                        "audios": [f"a{i}.mp3"],
                        "texts": [f"s{i}.srt"],
                    }
                })
            _save_queue_projects(QUEUE_PROJECTS)

        def mock_render_worker_with_failure(job_id: str):
            job = app.JOBS[job_id]
            pid = job.options.get("queueProjectId")
            execution_log.append(pid)
            if pid == "proj_fail_test_3":
                job.status = "error"
                job.error = "Simulated render failure on project 3"
                raise RuntimeError("Simulated render failure on project 3")
            else:
                job.status = "done"
                job.output = f"/fake/exports/{pid}.mp4"
                job.output_dir = "/fake/exports"

        with patch("app._queue_project_missing_requirements", return_value=[]):
            with patch("app.render_worker", side_effect=mock_render_worker_with_failure):
                resp = self.client.post("/api/queue/start", json={
                    "projectIds": project_ids,
                    "batchId": "batch_test_fail",
                })
                self.assertEqual(resp.status_code, 200)
                self.assertTrue(resp.json().get("ok"))

                # Wait for queue worker to finish
                timeout = 10.0
                t0 = time.time()
                while time.time() - t0 < timeout:
                    status = BACKEND_QUEUE_MANAGER.status()
                    if not status["running"]:
                        break
                    time.sleep(0.02)

                self.assertFalse(BACKEND_QUEUE_MANAGER.status()["running"])
                self.assertEqual(BACKEND_QUEUE_MANAGER.status()["completed_count"], 4)
                self.assertEqual(BACKEND_QUEUE_MANAGER.status()["failed_count"], 1)

        # Assert all 5 projects were processed!
        self.assertEqual(execution_log, project_ids, "All 5 projects must be processed, none skipped!")

        # Verify status of each project
        with QUEUE_LOCK:
            p1 = _find_queue_project("proj_fail_test_1")
            p2 = _find_queue_project("proj_fail_test_2")
            p3 = _find_queue_project("proj_fail_test_3")
            p4 = _find_queue_project("proj_fail_test_4")
            p5 = _find_queue_project("proj_fail_test_5")

            self.assertEqual(p1["status"], "done")
            self.assertEqual(p2["status"], "done")
            self.assertEqual(p3["status"], "error")
            self.assertIn("Simulated render failure", p3["error"])
            self.assertEqual(p4["status"], "done")
            self.assertEqual(p5["status"], "done")


if __name__ == "__main__":
    unittest.main()
