"""Sincronia e precisão: grelha de frames, alinhamento de callouts, cartão, blocos e filtro.
Run: python -m unittest tests.test_sync_precision"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

_sandbox = tempfile.TemporaryDirectory(prefix="glide-sync-tests-", ignore_cleanup_errors=True)
os.environ.setdefault("GLIDE_ULTRA_DATA_ROOT", _sandbox.name)
import app
import glide_align


class FrameGridTests(unittest.TestCase):
    def test_plans_snap_to_frames_without_cumulative_drift(self):
        durations = [5.217, 4.004, 7.04, 3.333, 5.2, 2.911] * 60
        plans = [app.SegmentPlan(source=Path("x.mp4"), raw_duration=d, target_duration=d, source_index=i, cycle=0)
                 for i, d in enumerate(durations)]
        summary = app.quantize_plans_to_frame_grid(plans)
        self.assertEqual(summary["total_frames"], round(sum(durations) * 30))
        elapsed = 0.0
        for plan, original in zip(plans, durations):
            self.assertEqual(plan.frame_count, round(plan.target_duration * 30))
            self.assertAlmostEqual(plan.target_duration * 30, plan.frame_count, places=6)
            elapsed += plan.target_duration
        self.assertLess(abs(elapsed - sum(durations)), 0.5 / 30 + 1e-9)


class CalloutAlignmentTests(unittest.TestCase):
    def _speech(self, cues, scale=1.05, lead=2.0):
        words = []
        filler = ["the", "narrator", "keeps", "talking", "about", "motors", "and", "materials"]
        t = 0.0
        for start, _end, text in cues:
            spoken_at = start * scale + lead
            while t < spoken_at - 0.5:
                words.append((t, glide_align.stem(glide_align.norm_token(filler[int(t) % len(filler)]))))
                t += 0.4
            for tok in text.split():
                words.append((t, glide_align.stem(glide_align.norm_token(tok))))
                t += 0.35
        return words

    def test_callouts_follow_the_narration(self):
        texts = ["Tesla says the Cybercab", "EPA evidence 163 kilowatt motor", "Hard target remove rare earths",
                 "Ferrite magnets are cheaper", "Synchronous reluctance rotor design", "Supply chain in China 2024",
                 "Efficiency map and thermal limits", "Demand grows fifty percent by 2035"]
        cues = [(20.0 + i * 60.0, 24.0 + i * 60.0, text) for i, text in enumerate(texts)]
        words = self._speech(cues)
        new, stats = glide_align.align_callouts(cues, words)
        self.assertTrue(stats["applied"])
        for (start, _end, _t), (ns, _ne) in zip(cues, new):
            self.assertLess(abs(ns - (start * 1.05 + 2.0)), 1.0)

    def test_without_matches_times_are_kept(self):
        cues = [(10.0, 14.0, "Completely unrelated words"), (40.0, 44.0, "Nothing spoken here")]
        words = [(float(i), "zzz") for i in range(100)]
        new, stats = glide_align.align_callouts(cues, words)
        self.assertFalse(stats["applied"])
        self.assertEqual(new, [(10.0, 14.0), (40.0, 44.0)])

    def test_accents_and_numbers_normalize(self):
        self.assertEqual(glide_align.norm_token("Três"), "3")
        self.assertEqual(glide_align.norm_token("Energía"), "energia")
        self.assertIn("163", glide_align.keywords("163 kW permanent-magnet"))


class CalloutCardTests(unittest.TestCase):
    def test_card_uses_box_style_and_same_layout_as_text(self):
        style = app.subtitle_style_from_options({})
        box, text = app.callout_card_dialogues("Tesla says", "0:00:01.00", "0:00:04.00", 960, 900, style, 48)
        self.assertIn(",Card,", box)
        self.assertIn("\\move(", box)
        self.assertIn("\\fad(200,180)", text)
        # a barra existe nas duas camadas (visível na caixa, transparente no texto) => alinhados
        self.assertEqual(box.count("\\p1"), text.count("\\p1"))
        self.assertIn("Style: Card,", app.callout_card_style_line(style, 48, 120))

    def test_chunk_continuation_does_not_replay_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "all.ass"
            src.write_text(
                "[Events]\nDialogue: 2,0:02:28.00,0:02:34.00,Default,,0,0,0,,{\\an2\\move(930,900,960,900,0,240)\\fad(200,180)}texto\n",
                encoding="utf-8",
            )
            first = app.slice_ass_for_chunk(src, 0.0, 150.0, Path(tmp) / "a.ass").read_text(encoding="utf-8")
            second = app.slice_ass_for_chunk(src, 150.0, 150.0, Path(tmp) / "b.ass").read_text(encoding="utf-8")
            self.assertIn("\\fad(200,0)", first)
            self.assertIn("\\pos(960,900)", second)
            self.assertIn("\\fad(0,180)", second)
            self.assertNotIn("\\move", second)


class StrictVisualFilterTests(unittest.TestCase):
    def test_rejected_clips_never_return_to_timeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            clean = [work / f"clean_{i}.mp4" for i in range(2)]
            dirty = [work / f"presenter_{i}.mp4" for i in range(6)]
            for path in clean + dirty:
                path.write_bytes(b"x" * 64)

            def fake_probe(path, duration, level, cwd=None, context=None, media_kind="video"):
                if "presenter" in Path(path).name:
                    return {"category": "presenter", "action": "hard_reject", "reason": "apresentador", "confidence": 0.9, "metrics": {}}
                return {"category": "clean", "action": "keep", "reason": "limpo", "confidence": 0.9, "metrics": {}}

            job = app.Job(id="strict", work=work)
            job.options = {}
            pairs = [(p, 8.0) for p in clean + dirty]
            with patch.object(app, "probe_visual_clean_health", side_effect=fake_probe):
                selected, summary = app.apply_visual_clean_filter(job, pairs, 300.0, work)
            names = {Path(p).name for p, _ in selected}
            self.assertFalse(any(n.startswith("presenter") for n in names), names)
            self.assertEqual(summary.get("fallback_used", 0), 0)
            self.assertTrue(summary.get("insufficient_clean_media"))


class TailPadTests(unittest.TestCase):
    def test_short_video_is_extended_without_frozen_gap(self):
        if not app.FFMPEG:
            self.skipTest("sem FFmpeg")
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            src = work / "composed.mp4"
            subprocess.run([app.FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=30:d=3",
                            "-f", "lavfi", "-i", "sine=d=5", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                            str(src)], check=True)
            job = app.Job(id="tail", work=work)
            job.options = {"gpu": False, "codec": "h264"}
            out = app.ensure_video_duration(job, src, 5.0, work)
            pts = subprocess.run([app.FFPROBE, "-v", "error", "-select_streams", "v", "-show_entries", "packet=pts_time",
                                  "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.split()
            times = sorted(float(x) for x in pts if x.strip() and x != "N/A")
            gaps = [b - a for a, b in zip(times, times[1:])]
            self.assertLess(max(gaps), 0.1, "buraco (imagem congelada) na junção")
            self.assertGreaterEqual(times[-1], 4.8)


if __name__ == "__main__":
    unittest.main()
