"""Estabilidade: lista de canais protegida, limpeza sem bloquear, depósito AUTO, perfil de hardware.
Run: python -m unittest tests.test_stability"""
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

_sandbox = tempfile.TemporaryDirectory(prefix="glide-stability-tests-", ignore_cleanup_errors=True)
os.environ.setdefault("GLIDE_ULTRA_DATA_ROOT", _sandbox.name)
import app
from fastapi.testclient import TestClient


class QueueListProtectionTests(unittest.TestCase):
    """Regra: um update ou um ecrã com estado antigo nunca muda a lista de canais."""

    def setUp(self):
        self.client = TestClient(app.app, raise_server_exceptions=False)

    def test_snapshot_never_creates_unknown_project_without_create_flag(self):
        before = [p["id"] for p in app.QUEUE_PROJECTS]
        r = self.client.post("/api/queue/projects/p_stale_tab_1/snapshot", json={"name": "Canal antigo"})
        self.assertEqual(r.status_code, 404)
        self.assertEqual([p["id"] for p in app.QUEUE_PROJECTS], before)

    def test_deleted_project_cannot_be_resurrected(self):
        r = self.client.post("/api/queue/projects/p_tomb_1/snapshot", json={"name": "Novo", "create": True})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.client.delete("/api/queue/projects/p_tomb_1").status_code, 200)
        # debounce/beacon atrasado do ecrã depois de apagar
        r = self.client.post("/api/queue/projects/p_tomb_1/snapshot", json={"name": "Novo", "create": True})
        self.assertEqual(r.status_code, 404)
        self.assertFalse(any(p["id"] == "p_tomb_1" for p in app.QUEUE_PROJECTS))
        saved = json.loads(app.QUEUE_PROJECTS_FILE.read_text(encoding="utf-8"))
        self.assertIn("p_tomb_1", saved["deletedIds"])

    def test_list_change_keeps_dated_backup_of_previous_list(self):
        self.client.post("/api/queue/projects/p_bk_1/snapshot", json={"name": "Canal A", "create": True})
        if app.QUEUE_BACKUP_ROOT.exists():
            for old in app.QUEUE_BACKUP_ROOT.glob("queue_*_before-change.json"):
                old.unlink()
        self.client.post("/api/queue/projects/p_bk_1/snapshot", json={"name": "Canal A renomeado"})
        self.client.post("/api/queue/projects/p_bk_1/snapshot", json={"name": "Canal A outra vez"})
        backups = sorted(app.QUEUE_BACKUP_ROOT.glob("queue_*_before-change.json"))
        self.assertTrue(backups, "renomear devia guardar a lista anterior")
        names = [p["name"] for p in json.loads(backups[0].read_text(encoding="utf-8"))["projects"]]
        self.assertIn("Canal A", names)

    def test_opening_app_does_not_rewrite_queue_file(self):
        app._save_queue_projects(app.QUEUE_PROJECTS)
        stamp = app.QUEUE_PROJECTS_FILE.stat().st_mtime_ns
        app._save_queue_projects(app._load_queue_projects())
        self.assertEqual(app.QUEUE_PROJECTS_FILE.stat().st_mtime_ns, stamp)

    def test_maintenance_never_deletes_active_webview_profile(self):
        self.assertNotIn("webview_profile", app.SAFE_OLD_PROFILE_DIR_NAMES)


class NonBlockingClearTests(unittest.TestCase):
    def test_clear_moves_media_out_instantly_and_purges_later(self):
        project_id = "p_clear_fast"
        folder = app._project_media_dir(project_id)
        folder.mkdir(parents=True, exist_ok=True)
        for i in range(50):
            (folder / f"clip_{i}.mp4").write_bytes(b"x" * 2048)
        project = {"id": project_id, "jobId": None}
        started = time.perf_counter()
        result = app._clear_queue_project_storage(project)
        self.assertLess(time.perf_counter() - started, 2.0)
        self.assertFalse(folder.exists())
        self.assertEqual(result["removed"], 1)
        self.assertGreater(result["bytes_recovered"], 0)
        self.assertEqual(app._purge_trash_once(), 0)
        self.assertFalse(any(app.TRASH_ROOT.iterdir()))

    def test_locked_file_does_not_abort_clear(self):
        project_id = "p_clear_locked"
        folder = app._project_media_dir(project_id)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "a.mp4").write_bytes(b"1" * 100)
        (folder / "b.mp4").write_bytes(b"2" * 100)
        real_replace = os.replace

        def flaky_replace(src, dst):
            if Path(src) == folder or Path(src).name == "b.mp4":
                raise PermissionError("em uso")
            return real_replace(src, dst)

        with patch.object(app.os, "replace", side_effect=flaky_replace):
            result = app._clear_queue_project_storage({"id": project_id})
        self.assertTrue(any("b.mp4" in err for err in result["errors"]))
        self.assertFalse((folder / "a.mp4").exists())


class AutomatorPoolTests(unittest.TestCase):
    """O rascunho AUTO sobe cada ficheiro uma vez; a confirmação só move (sem reenvio)."""

    def setUp(self):
        self.client = TestClient(app.app, raise_server_exceptions=False)

    def _project(self, pid):
        r = self.client.post(f"/api/queue/projects/{pid}/snapshot", json={"name": pid, "create": True})
        self.assertEqual(r.status_code, 200, r.text)

    def test_pool_upload_then_commit_moves_without_reupload(self):
        pid = "p_pool_commit"
        self._project(pid)
        payload = {
            "voz.wav": b"RIFF" + b"\0" * 400,
            "texto.srt": b"1\n00:00:00,000 --> 00:00:01,000\nOla\n",
            "clip.mp4": b"\0" * 900,
        }
        keys = {name: f"{name}|{len(data)}|1700000000000" for name, data in payload.items()}
        files = [("files", (name, data)) for name, data in payload.items()]
        r = self.client.post("/api/queue/automator/pool", files=files, data={"keys": json.dumps(list(keys.values()))})
        self.assertEqual(sorted(r.json()["stored"]), sorted(keys.values()))
        present = self.client.post("/api/queue/automator/pool/check", json={"keys": list(keys.values()) + ["x|1|1"]}).json()["present"]
        self.assertEqual(sorted(present), sorted(keys.values()))

        specs = [
            {"slot": "p0_audio_0", "projectId": pid, "kind": "audio", "lane": "audio", "rel": "voz.wav", "name": "voz.wav", "size": len(payload["voz.wav"]), "duration": 1},
            {"slot": "p0_srt_0", "projectId": pid, "kind": "subtitle", "lane": "srt", "rel": "texto.srt", "name": "texto.srt", "size": len(payload["texto.srt"]), "duration": 0},
            {"slot": "p0_folder_0", "projectId": pid, "kind": "video", "lane": "folder", "rel": "pasta/clip.mp4", "name": "clip.mp4", "size": len(payload["clip.mp4"]), "duration": 5},
        ]
        created = self.client.post("/api/queue/automator/sessions", json={"rows": [{"projectId": pid, "projectName": pid}], "files": specs}).json()
        sid = created["sessionId"]
        slot_keys = {"p0_audio_0": keys["voz.wav"], "p0_srt_0": keys["texto.srt"], "p0_folder_0": keys["clip.mp4"]}
        r = self.client.post(f"/api/queue/automator/sessions/{sid}/from-pool",
                             json={"items": [{"slot": s, "key": k} for s, k in slot_keys.items()]}).json()
        self.assertEqual(sorted(r["registered"]), sorted(slot_keys))
        self.assertEqual(r["missing"], [])
        # o depósito ficou vazio: os ficheiros foram MOVIDOS (sem cópia extra no disco)
        self.assertEqual(self.client.post("/api/queue/automator/pool/check", json={"keys": list(keys.values())}).json()["present"], [])
        commit = self.client.post(f"/api/queue/automator/sessions/{sid}/commit")
        self.assertEqual(commit.status_code, 200, commit.text)
        counts = commit.json()["projects"][0]["counts"]
        self.assertEqual(counts, {"videos": 1, "audios": 1, "texts": 1})

    def test_cancel_returns_files_to_pool(self):
        pid = "p_pool_cancel"
        self._project(pid)
        data = {"voz.wav": b"RIFF" + b"\1" * 300, "t.srt": b"1\n00:00:00,000 --> 00:00:01,000\nA\n", "c.mp4": b"\1" * 700}
        keys = {n: f"{n}|{len(d)}|1700000000001" for n, d in data.items()}
        self.client.post("/api/queue/automator/pool", files=[("files", (n, d)) for n, d in data.items()],
                         data={"keys": json.dumps(list(keys.values()))})
        specs = [
            {"slot": "a", "projectId": pid, "kind": "audio", "rel": "voz.wav", "size": len(data["voz.wav"])},
            {"slot": "s", "projectId": pid, "kind": "subtitle", "rel": "t.srt", "size": len(data["t.srt"])},
            {"slot": "v", "projectId": pid, "kind": "video", "rel": "p/c.mp4", "size": len(data["c.mp4"])},
        ]
        sid = self.client.post("/api/queue/automator/sessions", json={"rows": [{"projectId": pid}], "files": specs}).json()["sessionId"]
        self.client.post(f"/api/queue/automator/sessions/{sid}/from-pool",
                         json={"items": [{"slot": "a", "key": keys["voz.wav"]}, {"slot": "s", "key": keys["t.srt"]}, {"slot": "v", "key": keys["c.mp4"]}]})
        self.client.delete(f"/api/queue/automator/sessions/{sid}")
        present = self.client.post("/api/queue/automator/pool/check", json={"keys": list(keys.values())}).json()["present"]
        self.assertEqual(sorted(present), sorted(keys.values()), "cancelar não pode perder ficheiros do rascunho")

    def test_release_keeps_only_requested_keys(self):
        keys = ["k1.mp4|5|1", "k2.mp4|5|1"]
        self.client.post("/api/queue/automator/pool", files=[("files", ("k1.mp4", b"12345")), ("files", ("k2.mp4", b"12345"))],
                         data={"keys": json.dumps(keys)})
        self.client.post("/api/queue/automator/pool/release", json={"keep": ["k2.mp4|5|1"]})
        present = self.client.post("/api/queue/automator/pool/check", json={"keys": keys}).json()["present"]
        self.assertEqual(present, ["k2.mp4|5|1"])

    def test_pool_rejects_truncated_upload(self):
        r = self.client.post("/api/queue/automator/pool", files=[("files", ("cut.mp4", b"123"))],
                             data={"keys": json.dumps(["cut.mp4|999|1"])})
        self.assertEqual(r.json()["stored"], [])


class OpeningProtocolTests(unittest.TestCase):
    """O protocolo de abertura escolhe os primeiros slots mas nunca remove clipes do projeto."""

    def test_never_drops_clips_kept_by_the_visual_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            pairs, verdicts = [], {}
            for i in range(40):
                path = work / f"clip_{i:02d}.mp4"
                path.write_bytes(bytes([i]) * 64)
                pairs.append((path, 6.0))
                # 30 clipes "mantidos pelo teto de 30%" (apresentador parcial / estático), 10 limpos
                if i % 4 == 0:
                    verdicts[path.name] = {"category": "clean", "action": "keep", "metrics": {"mean": 90, "frame_diff": 9, "stdev": 40, "edge_density": 0.08, "quality_score": 0.9}}
                else:
                    verdicts[path.name] = {"category": "presenter", "action": "keep", "metrics": {}}

            def fake_probe(path, duration, level, cwd=None, context=None, media_kind="video"):
                return dict(verdicts[Path(path).name])

            job = app.Job(id="opening", work=work)
            job.options = {"visualCleanFilter": True}
            with patch.object(app, "probe_visual_clean_health", side_effect=fake_probe),                  patch.object(app, "probe_media_dimensions", return_value=(1920, 1080)),                  patch.object(app, "visual_clean_cache_key", side_effect=lambda p, d, w: f"k-{Path(p).name}"):
                result, summary = app.enforce_clean_opening_protocol(job, pairs, work, max_opening_slots=10)
            self.assertEqual(len(result), 40)
            self.assertEqual({p.name for p, _ in result}, {p.name for p, _ in pairs})
            self.assertEqual(summary["purged"], 0)
            # a abertura usa só clipes elegíveis (limpos)
            for path, _dur in result[:5]:
                self.assertEqual(verdicts[path.name]["category"], "clean")


class TextDensityTests(unittest.TestCase):
    def _ass(self, cues, total):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            def ts(x):
                return f"{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:{int(x % 60):02d},{int(round((x % 1) * 1000)):03d}"
            srt = work / "t.srt"
            blocks = [f"{i + 1}" + chr(10) + f"{ts(a)} --> {ts(b)}" + chr(10) + text + chr(10) for i, (a, b, text) in enumerate(cues)]
            srt.write_text(chr(10).join(blocks), encoding="utf-8")
            job = app.Job(id="dens", work=work)
            job.options = {}
            job.preflight_summary = {}
            ass = app.build_ass_file(job, srt, total, 1920, 1080, work)
            return ass.read_text(encoding="utf-8"), job

    def test_full_narration_srt_uses_plain_subtitles(self):
        cues = [(i * 3.4, i * 3.4 + 3.0, f"Frase numero {i} da narracao completa") for i in range(60)]
        text, job = self._ass(cues, 204.0)
        self.assertNotIn(",Card,", text)
        self.assertTrue(job.subtitle_summary["dense_track"]["dense"])
        self.assertTrue(job.preflight_summary.get("warnings"))

    def test_sparse_highlights_keep_the_card(self):
        cues = [(20 + i * 60.0, 24 + i * 60.0, f"Destaque {i} com 163 kW") for i in range(6)]
        text, job = self._ass(cues, 400.0)
        self.assertIn(",Card,", text)
        self.assertFalse(job.subtitle_summary["dense_track"]["dense"])


class FootageSyncFileTests(unittest.TestCase):
    def test_link_list_srt_is_not_rendered_as_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            blocks = []
            for i in range(10):
                blocks.append(f"{i + 1}" + chr(10) + f"00:00:{i * 4:02d},000 --> 00:00:{i * 4 + 3:02d},000" + chr(10)
                              + f"https://youtube.com/watch?v=abc{i} *** 03:41-03:45" + chr(10))
            srt = work / "sync.srt"
            srt.write_text(chr(10).join(blocks), encoding="utf-8")
            job = app.Job(id="links", work=work)
            job.options = {}
            cues, summary, _caps = app.resolve_effective_subtitle_cues(job, srt, 60.0)
            self.assertEqual(cues, [])
            self.assertEqual(summary.get("ignored"), "footage_sync_links")


class DeliveryTests(unittest.TestCase):
    def test_delivery_links_instead_of_rewriting_final_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source = work / "final.mp4"
            source.write_bytes(b"v" * 4096)
            job = app.Job(id="deliver", work=work)
            job.options = {"finalOutputMode": "custom", "finalOutputFolder": str(work / "saida")}
            out = app.deliver_final_video(job, source)
            self.assertEqual(job.delivery_summary.get("delivery_method"), "hardlink")
            source.unlink()  # o render apaga o intermediário a seguir
            self.assertEqual(out.read_bytes(), b"v" * 4096)


class HardwareProfileCacheTests(unittest.TestCase):
    def test_profile_is_detected_once_per_session(self):
        calls = []
        real = app._compute_hardware_profile

        def counting():
            calls.append(1)
            return real()

        with patch.object(app, "_HARDWARE_PROFILE_CACHE", {}), patch.object(app, "_compute_hardware_profile", side_effect=counting), \
             patch.object(app, "_detect_windows_gpus", return_value=[]), patch.object(app, "encoder_available", return_value=False):
            threads = [threading.Thread(target=app.hardware_profile) for _ in range(6)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            with patch.object(app.time, "monotonic", return_value=time.monotonic() + 3600):
                app.hardware_profile()
        self.assertEqual(len(calls), 1, "deteção repetida trava o render (~11-14 s por vez)")


if __name__ == "__main__":
    unittest.main()
