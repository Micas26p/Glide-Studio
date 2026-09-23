"""Regressões do modo AUTO, progresso e Ken Burns. Run: python -m unittest tests.test_auto_mode"""
import os
from pathlib import Path
import tempfile
import time
import unittest

_sandbox = tempfile.TemporaryDirectory(prefix="glide-auto-tests-", ignore_cleanup_errors=True)
os.environ.setdefault("GLIDE_ULTRA_DATA_ROOT", _sandbox.name)
import app
from fastapi.testclient import TestClient


def _new_project(client) -> str:
    response = client.post("/api/queue/projects", json={"name": f"AUTO {time.time_ns()}"})
    if response.status_code == 200 and response.json().get("project", {}).get("id"):
        return response.json()["project"]["id"]
    project = {"id": f"p_test_{time.time_ns()}", "name": "AUTO test", "media": {}, "options": {}, "status": "draft"}
    with app.QUEUE_LOCK:
        app.QUEUE_PROJECTS.append(project)
    return project["id"]


class AutoModeRegressions(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app.app, raise_server_exceptions=False)

    def _session(self, project_id, files):
        return self.client.post("/api/queue/automator/sessions", json={"rows": [{"projectId": project_id}], "files": files})

    def test_unsupported_media_in_folder_is_skipped_not_fatal(self):
        pid = _new_project(self.client)
        files = [
            {"slot": "v0", "projectId": pid, "kind": "image", "lane": "folder", "rel": "104_VIZAN/29_diagram.svg", "size": 10},
            {"slot": "v1", "projectId": pid, "kind": "image", "lane": "folder", "rel": "104_VIZAN/01.png", "size": 10},
            {"slot": "a0", "projectId": pid, "kind": "audio", "lane": "audio", "rel": "a.wav", "size": 10},
            {"slot": "s0", "projectId": pid, "kind": "subtitle", "lane": "srt", "rel": "a.srt", "size": 10},
        ]
        response = self._session(pid, files)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["skippedSlots"], ["v0"])
        self.assertEqual(body["expectedFiles"], 3)
        upload = self.client.post(
            f"/api/queue/automator/sessions/{body['sessionId']}/file",
            data={"slot": "v0"}, files={"file": ("29_diagram.svg", b"<svg/>")},
        )
        self.assertEqual(upload.status_code, 200)
        self.assertTrue(upload.json().get("skipped"))
        self.client.delete(f"/api/queue/automator/sessions/{body['sessionId']}")

    def test_invalid_narration_is_still_fatal(self):
        pid = _new_project(self.client)
        files = [
            {"slot": "v1", "projectId": pid, "kind": "image", "lane": "folder", "rel": "f/01.png", "size": 10},
            {"slot": "a0", "projectId": pid, "kind": "audio", "lane": "audio", "rel": "a.svg", "size": 10},
            {"slot": "s0", "projectId": pid, "kind": "subtitle", "lane": "srt", "rel": "a.srt", "size": 10},
        ]
        self.assertEqual(self._session(pid, files).status_code, 400)

    def test_commit_does_not_wait_on_itself(self):
        pid = _new_project(self.client)
        files = [
            {"slot": "v1", "projectId": pid, "kind": "image", "lane": "folder", "rel": "f/01.png", "size": 10},
            {"slot": "a0", "projectId": pid, "kind": "audio", "lane": "audio", "rel": "a.wav", "size": 10},
            {"slot": "s0", "projectId": pid, "kind": "subtitle", "lane": "srt", "rel": "a.srt", "size": 10},
        ]
        session = self._session(pid, files).json()["sessionId"]
        payloads = {"v1": ("01.png", b"\x89PNG fake"), "a0": ("a.wav", b"RIFF fake"), "s0": ("a.srt", b"1\n00:00:00,000 --> 00:00:02,000\nOla\n")}
        for slot, (name, content) in payloads.items():
            r = self.client.post(f"/api/queue/automator/sessions/{session}/file", data={"slot": slot}, files={"file": (name, content)})
            self.assertEqual(r.status_code, 200, r.text)
        started = time.perf_counter()
        commit = self.client.post(f"/api/queue/automator/sessions/{session}/commit")
        self.assertEqual(commit.status_code, 200, commit.text)
        self.assertLess(time.perf_counter() - started, 10.0, "commit voltou a esperar por si próprio")

    def test_detect_text_language(self):
        self.assertEqual(app.detect_text_language("Isso não é uma coisa que você vê, mas também é muito importante para nós."), "pt")
        self.assertEqual(app.detect_text_language("The battery was the thing that would change what they could do with their cars."), "en")
        self.assertEqual(app.detect_text_language("La batería es una de las cosas más importantes porque también hay muchos."), "es")
        self.assertEqual(app.detect_text_language(""), "pt")

    def test_stage_never_regresses_within_job(self):
        job = app.Job(id="stage_test", work=Path(_sandbox.name)) if "work" in app.Job.__dataclass_fields__ else None
        if job is None:
            self.skipTest("Job exige outros campos")
        app.set_stage(job, "rendering", "r")
        app.set_stage(job, "cta", "c")
        app.set_stage(job, "audio", "a", "mixando")
        self.assertEqual(job.stage, "cta")
        self.assertEqual(job.message, "mixando")
        app.set_stage(job, "muxing", "m")
        self.assertEqual(job.stage, "muxing")
        app.set_stage(job, "error", "e")
        self.assertEqual(job.stage, "error")

    def test_image_motion_is_continuous(self):
        for kind in ("zoom_in", "zoom_out", "pan"):
            spec = {"frames": 150, "kind": kind, "safe_fx": 0.5, "safe_fy": 0.4, "pan_x0": 0.3, "pan_x1": 0.7}
            states = [app.image_motion_state(spec, n) for n in range(150)]
            for a, b in zip(states, states[1:]):
                self.assertLess(abs(b[0] - a[0]), 0.002)
                self.assertLess(abs(b[1] - a[1]), 0.01)
            zooms = [s[0] for s in states]
            self.assertTrue(all(1.0 <= z <= app.IMAGE_MOTION_ZMAX for z in zooms))


if __name__ == "__main__":
    unittest.main()
