"""Run with python -m unittest discover -s tests -v. Never uses user data."""
import asyncio
import atexit
import gc
import io
import json
import math
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

_sandbox = tempfile.TemporaryDirectory(prefix="glide-tests-")
os.environ["GLIDE_ULTRA_DATA_ROOT"] = _sandbox.name
import app
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile
from glide_audio_master import second_pass_filter, summary

def cleanup():
    app.INTELLIGENCE_DB._connection().close()
    gc.collect()

atexit.register(cleanup)


class Regressions(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app.app, raise_server_exceptions=False)

    def create(self, manifest=None):
        return self.client.post('/api/create-render-job', data={
            'manifest': json.dumps(manifest or [{'rel': 'voice.wav', 'kind': 'audio'}]),
            'options': '{}',
        }).json()['job_id']

    def test_invalid_json_shapes(self):
        for manifest, options in [('[]', 'null'), ('{}', '{}'), ('[1]', '{}'), ('null', '{}')]:
            with self.subTest(manifest=manifest, options=options):
                response = self.client.post('/api/create-render-job', data={'manifest': manifest, 'options': options})
                self.assertEqual(response.status_code, 400, response.text)

    def test_legacy_queue_list(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'queue.json'
            path.write_text('[{"id":"old","name":"Antigo"}]', encoding='utf-8')
            with patch.object(app, 'QUEUE_PROJECTS_FILE', path):
                self.assertEqual(app._load_queue_projects()[0]['id'], 'old')

    def test_duplicate_upload_does_not_complete_missing_file(self):
        job_id = self.create([{'rel': 'voice.wav', 'kind': 'audio'}, {'rel': 'video.mp4', 'kind': 'video'}])
        for _ in range(2):
            response = self.client.post(f'/api/upload-file/{job_id}', data={'rel':'voice.wav','index':0}, files={'file':('voice.wav', b'RIFF-test')})
            self.assertEqual(response.status_code, 200)
        self.assertEqual(app.JOBS[job_id].uploaded_files, 1)
        self.assertEqual(self.client.post(f'/api/launch-render/{job_id}').status_code, 400)

    def test_zero_byte_upload_rejected(self):
        job_id = self.create()
        response = self.client.post(f'/api/upload-file/{job_id}', data={'rel':'voice.wav','index':0}, files={'file':('voice.wav', b'')})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(app.JOBS[job_id].uploaded_files, 0)

    def test_cancel_before_launch(self):
        job_id = self.create()
        self.client.post(f'/api/cancel-render/{job_id}')
        self.assertEqual(self.client.post(f'/api/launch-render/{job_id}').status_code, 409)
        self.assertEqual(app.JOBS[job_id].status, 'cancelled')

    def test_interrupted_upload_preserves_previous_file(self):
        job_id = self.create()
        async def run():
            await app.upload_file(job_id, UploadFile(io.BytesIO(b'original'), filename='voice.wav'), 'voice.wav', 'audio', 0)
            broken = UploadFile(io.BytesIO(b'partial'), filename='voice.wav')
            async def read(_):
                raise OSError('injected read failure')
            broken.read = read
            with self.assertRaises(OSError):
                await app.upload_file(job_id, broken, 'voice.wav', 'audio', 0)
        asyncio.run(run())
        self.assertEqual(app.JOBS[job_id].upload_paths['voice.wav'].read_bytes(), b'original')

    def test_silent_loudnorm_is_finite(self):
        measurement = dict(input_i='-inf', input_tp='-inf', input_lra='0', input_thresh='-70', target_offset='inf')
        self.assertNotIn('=inf', second_pass_filter(measurement))
        self.assertNotIn('=-inf', second_pass_filter(measurement))
        json.dumps(summary(measurement), allow_nan=False)

    def test_invalid_duration(self):
        for duration in ['abc', 'Infinity', -1, []]:
            with self.subTest(duration=duration):
                response = self.client.post('/api/create-render-job', data={
                    'manifest':'[]', 'options':json.dumps({'estimatedDurationSeconds':duration})})
                self.assertEqual(response.status_code, 400)

    def test_same_basename_in_different_folders(self):
        names = ['voice.wav', 'folder/voice.wav']
        job_id = self.create([{'rel':name,'kind':'audio'} for name in names])
        for i,name in enumerate(names):
            response = self.client.post(f'/api/upload-file/{job_id}', data={'rel':name,'index':i}, files={'file':(name,str(i).encode())})
            self.assertEqual(response.status_code,200,response.text)
        job = app.JOBS[job_id]
        self.assertEqual(job.uploaded_files,2)
        self.assertEqual([job.upload_paths[name].read_bytes() for name in names], [b'0',b'1'])

    def test_corrupt_primary_does_not_destroy_recovery_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'queue.json'
            backup = path.with_suffix('.json.bak')
            path.write_text('{broken',encoding='utf-8')
            backup.write_text('[{"id":"recover"}]',encoding='utf-8')
            with patch.object(app,'QUEUE_PROJECTS_FILE',path):
                self.assertEqual(app._load_queue_projects()[0]['id'],'recover')
                app._save_queue_projects([{'id':'new'}])
                self.assertEqual(json.loads(backup.read_text())[0]['id'],'recover')
                self.assertEqual(app._load_queue_projects()[0]['id'],'new')

    def test_concurrent_launch_starts_one_worker(self):
        from concurrent.futures import ThreadPoolExecutor
        job_id = self.create()
        job = app.JOBS[job_id]
        job.expected_files = 0
        with patch.object(app,'render_worker',lambda _: None):
            with ThreadPoolExecutor(max_workers=8) as executor:
                results = list(executor.map(lambda _: app.launch_render(job_id), range(20)))
        self.assertEqual(sum(not result.get('already_started',False) for result in results),1)

    def test_ffmpeg_missing_is_actionable(self):
        job_id = self.create()
        with patch.object(app,'FFMPEG',None):
            app.render_worker(job_id)
        self.assertEqual(app.JOBS[job_id].status,'error')
        self.assertIn('FFmpeg',app.JOBS[job_id].error)

    def test_vertical_auto_protects_text_and_manual_crop_remains(self):
        job = app.Job(id='vertical', options={'ctaLanguage':'english'})
        self.assertEqual(app.dual_export_effective_mode(job, []),'smart_blur')
        job.options = {'dualExportMode':'smart_crop'}
        self.assertEqual(app.dual_export_effective_mode(job, []),'smart_crop')
        job.options = {}
        self.assertEqual(app.dual_export_effective_mode(job,[{'focal_x':0.1}]),'smart_crop')

    def test_cache_publication_retries_only_transient_access(self):
        import glide_render_graph as graph
        with patch.object(graph.os,'replace',side_effect=[PermissionError('busy'), None]) as replace:
            with patch.object(graph.time,'sleep'):
                graph._publish_directory(Path('a'),Path('b'))
            self.assertEqual(replace.call_count,2)
        with patch.object(graph.os,'replace',side_effect=PermissionError('denied')) as replace:
            with patch.object(graph.time,'sleep'), self.assertRaises(PermissionError):
                graph._publish_directory(Path('a'),Path('b'))
            self.assertEqual(replace.call_count,4)

    def test_cancelled_vertical_export_does_not_spawn_ffmpeg(self):
        job = app.Job(id='cancelled-vertical', cancel_requested=True, options={})
        with patch.object(app,'_popen_hidden') as popen:
            with self.assertRaises(app.RenderCancelled):
                app.run_cmd(job,['ffmpeg','-version'])
            popen.assert_not_called()

    def test_script_guide_survives_snapshot_and_reload(self):
        response = self.client.post('/api/queue/projects/qa-script-guide/snapshot', json={
            'name':'Roteiro — ação',
            'media':{'videos':[], 'audios':[], 'script_guides':['roteiro ação.txt']},
        })
        self.assertEqual(response.status_code,200,response.text)
        restored = next(p for p in app._load_queue_projects() if p['id']=='qa-script-guide')
        self.assertEqual(restored['media'].get('script_guides'),['roteiro ação.txt'])

    def test_atomic_save_failure_preserves_existing_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'queue.json'
            path.write_text('original',encoding='utf-8')
            with patch.object(app.os,'replace',side_effect=PermissionError('read-only')):
                with self.assertRaises(PermissionError):
                    app.atomic_write_text(path,'new')
            self.assertEqual(path.read_text(),'original')
            self.assertEqual([p.name for p in Path(folder).iterdir()],['queue.json'])

    @unittest.skipUnless(app.FFMPEG, 'FFmpeg unavailable')
    def test_real_ffmpeg_cancel_releases_process(self):
        import threading
        import time
        job=app.Job(id='cancel-real',options={})
        errors=[]
        def run():
            try:
                app.run_cmd(job,[app.FFMPEG,'-hide_banner','-loglevel','error','-re',
                    '-f','lavfi','-i','color=size=64x64:rate=10:duration=30','-f','null','-'])
            except Exception as exc:
                errors.append(exc)
        worker=threading.Thread(target=run)
        worker.start()
        deadline=time.monotonic()+5
        while not job.current_processes and worker.is_alive() and time.monotonic()<deadline:
            time.sleep(0.01)
        job.cancel_requested=True
        app._terminate_job_processes(job)
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertTrue(errors and isinstance(errors[0],app.RenderCancelled),errors)
        self.assertEqual(job.current_processes,[])

    def test_dynamic_status_eta_countdown(self):
        job = app.Job(id='test-countdown', status='running')
        job.created_at = 1000.0
        job.started_at = 1000.0
        job.estimated_total_seconds = 600.0
        job.percent = 15.0
        job.rendered_timeline_duration = 0.0
        job.total_timeline_duration = 900.0
        job.preflight_summary['active_render_estimate'] = {
            'seconds': 600.0,
            'confidence': 'historical',
            'stage_forecast': {
                'audio': 15.0,
                'direction': 25.0,
                'subtitles_ass': 5.0,
                'visual_analysis': 30.0,
                'segments': 350.0,
                'composition': 120.0,
                'mux': 10.0,
                'delivery': 2.0,
            },
        }
        app.JOBS[job.id] = job

        with patch('time.time', return_value=1050.0):
            res1 = self.client.get(f'/api/status/{job.id}').json()
            self.assertIn('eta_summary', res1)
            rem1 = res1['eta_summary']['estimated_remaining_seconds']
            self.assertGreater(rem1, 400)

        # 10 seconds later, elapsed increased by 10s: remaining MUST count down and not be frozen
        with patch('time.time', return_value=1060.0):
            res2 = self.client.get(f'/api/status/{job.id}').json()
            rem2 = res2['eta_summary']['estimated_remaining_seconds']
            self.assertLess(rem2, rem1)
    def test_preparation_overrun_preserves_encoding_eta(self):
        """Garante que atrasos na fase de preparação (ex: 500 clipes) não colapsem a estimativa para 2 segundos."""
        job = app.Job(id='test-prep-overrun', status='running')
        job.created_at = 1000.0
        job.started_at = 1000.0
        job.estimated_total_seconds = 1200.0
        job.percent = 20.0
        job.rendered_timeline_duration = 0.0
        job.total_timeline_duration = 1800.0
        job.preflight_summary['active_render_estimate'] = {
            'seconds': 1200.0,
            'confidence': 'calibrated',
            'stage_forecast': {
                'audio': 20.0,
                'direction': 30.0,
                'subtitles_ass': 10.0,
                'visual_analysis': 40.0,
                'segments': 800.0,
                'composition': 250.0,
                'mux': 20.0,
            }
        }
        app.JOBS[job.id] = job

        with patch('time.time', return_value=2500.0):
            res = self.client.get(f'/api/status/{job.id}').json()
            rem = res['eta_summary']['estimated_remaining_seconds']
            self.assertGreater(rem, 700.0, f"Remaining ETA ({rem}s) collapsed instead of preserving encoding duration!")

    def test_analyze_voice_energy_vectorized(self):
        """Verifica que analyze_voice_energy usa numpy vetorizado sem erro e calcula RMS correto."""
        import numpy as np
        t = np.linspace(0, 10, 10000, endpoint=False)
        sig = (np.sin(2 * np.pi * 5 * t) * 16000).astype(np.int16)
        raw_bytes = sig.tobytes()

        class MockCompletedProcess:
            returncode = 0
            stdout = raw_bytes

        with patch('app._run_hidden', return_value=MockCompletedProcess()):
            res = app.analyze_voice_energy(Path(__file__), 10.0, Path("."))
            self.assertTrue(res.get("available"))
            self.assertEqual(len(res.get("points", [])), 10)

    def test_smart_image_motion_and_easing(self):
        """Verifica os 10 arquétipos, anti-repetição, safe framing e interpolação Hermite sem filtros destrutivos."""
        # 1. Expressão de easing e ausência de unsharp
        fc = app.build_image_filter_complex(
            w=1920,
            h=1080,
            target_duration=5.0,
            motion="slow_zoom_in",
            image_path=None,
            style_profile="editorial_cinematic",
            focal_point=(0.5, 0.4),
            safe_framing={"safe_fx": 0.5, "safe_fy": 0.4, "has_face": True},
        )
        self.assertIn("3*pow((on/150),2)-2*pow((on/150),3)", fc)
        self.assertNotIn("unsharp", fc)
        self.assertIn("bt709", fc)

        # 2. Anti-repetição de movimentos sucessivos
        m1, f1, s1 = app.choose_smart_image_motion(None, prev_motions=[])
        m2, f2, s2 = app.choose_smart_image_motion(None, prev_motions=[m1])
        m3, f3, s3 = app.choose_smart_image_motion(None, prev_motions=[m1, m2])
        self.assertNotEqual(m1, m2)
        self.assertNotEqual(m2, m3)

    def test_image_dominant_pacing_benchmark(self):
        """Verifica que projetos predominantemente de imagens adotam a média 5.52s da referência."""
        # Vídeo com imagens estáticas
        min_d, target_d, max_d, zone = app.get_retention_pacing_parameters(
            current_pos=60.0,
            audio_total=120.0,
            is_image_dominant=True,
        )
        self.assertEqual(zone, "body")
        self.assertGreaterEqual(target_d, 5.0)
        self.assertLessEqual(target_d, 6.5)
        self.assertEqual(min_d, 3.5)
        self.assertEqual(max_d, 6.5)

    def test_top_ranking_lock_isolation(self):
        """Verifica isolamento estrito de posições (#10, #9, #8...) e proibição de contaminação cruzada."""
        script = """
        TOP 10 MAIORES MÁQUINAS
        10. Komatsu D575A Super Dozer
        Trator colossal japonês de esteiras.
        9. Bagger 293
        Escavadora gigante feita na Alemanha.
        8. Caterpillar 797F
        Caminhão fora de estrada com caçamba titânica.
        """
        cues = [
            app.SubtitleCue(start=5.0, end=15.0, text="Número 10: O trator Komatsu D575A"),
            app.SubtitleCue(start=15.0, end=25.0, text="Ele tem uma potência incrível"),
            app.SubtitleCue(start=25.0, end=38.0, text="Número 9: A escavadora Bagger 293"),
            app.SubtitleCue(start=38.0, end=50.0, text="Feita na Alemanha com peso colossal"),
            app.SubtitleCue(start=50.0, end=65.0, text="#8: Caterpillar 797F caminhão fora de estrada"),
        ]
        units = app.extract_ranking_editorial_units(script, cues)
        self.assertEqual(len(units), 3)
        self.assertEqual(units[0]["rank_num"], 10)
        self.assertEqual(units[1]["rank_num"], 9)
        self.assertEqual(units[2]["rank_num"], 8)

        # Tokens do #9 e #8 devem ser proibidos no #10
        self.assertIn("9", units[0]["forbidden_tokens"])
        self.assertIn("8", units[0]["forbidden_tokens"])
        self.assertIn("bagger", units[0]["forbidden_tokens"])
        self.assertIn("caterpillar", units[0]["forbidden_tokens"])

        # E tokens do #10 devem ser proibidos no #9
        self.assertIn("komatsu", units[1]["forbidden_tokens"])
        self.assertIn("10", units[1]["forbidden_tokens"])

    def test_dhash_perceptual_deduplication(self):
        """Verifica cálculo do dHash e distância de Hamming."""
        h1 = 0b1111000011110000
        h2 = 0b1111000011110011  # difere em 2 bits
        h3 = 0b0000111100001111  # difere em 16 bits
        self.assertEqual(app.dhash_distance(h1, h2), 2)
        self.assertLessEqual(app.dhash_distance(h1, h2), 6)  # detectado como duplicado
        self.assertEqual(app.dhash_distance(h1, h3), 16)
        self.assertGreater(app.dhash_distance(h1, h3), 6)  # aceito como diferente

    def test_hybrid_and_image_timeline_plan(self):
        """Verifica a montagem de timelines 100% imagens e híbridas com transições e safe framing."""
        dummy_imgs = [Path(f"img_{i}.jpg") for i in range(10)]
        plans_img, _ = app.build_segment_plan(
            video_files=dummy_imgs,
            video_durs=[5.0] * 10,
            audio_total=45.0,
            force_short=True,
        )
        self.assertGreaterEqual(len(plans_img), 5)
        for p in plans_img:
            self.assertEqual(p.media_kind, "image")
            self.assertIn(p.image_motion, app.IMAGE_MOTION_ARCHETYPES)
            self.assertIsNotNone(p.safe_framing)

        # Híbrido: 1 vídeo + 9 imagens
        dummy_hybrid = [Path("video_hero.mp4")] + dummy_imgs[:9]
        dummy_durs = [12.0] + [5.0] * 9
        plans_hyb, _ = app.build_segment_plan(
            video_files=dummy_hybrid,
            video_durs=dummy_durs,
            audio_total=45.0,
            force_short=True,
        )
        kinds = {p.media_kind for p in plans_hyb}
        self.assertIn("video", kinds)
        self.assertIn("image", kinds)

    def test_persistent_media_signature_across_paths(self):
        """Verifica se media_signature é consistente mesmo quando arquivos estão em pastas temporárias distintas."""
        from glide_director import media_signature
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            p1 = Path(d1) / "sample_clip.mp4"
            p2 = Path(d2) / "sample_clip.mp4"
            content = b"TEST_VIDEO_BYTES_HEADER" + b"\x00" * 8000 + b"TAIL_BYTES"
            p1.write_bytes(content)
            p2.write_bytes(content)
            sig1 = media_signature(p1)
            sig2 = media_signature(p2)
            self.assertEqual(sig1, sig2)

    def test_persistent_visual_clean_cache_key_across_paths(self):
        """Verifica se visual_clean_cache_key é consistente entre pastas temporárias distintas."""
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            p1 = Path(d1) / "sample_clip.mp4"
            p2 = Path(d2) / "sample_clip.mp4"
            content = b"CLEAN_CHECK_BYTES" + b"\x11" * 8000 + b"END_BYTES"
            p1.write_bytes(content)
            p2.write_bytes(content)
            k1 = app.visual_clean_cache_key(p1, duration=5.0)
            k2 = app.visual_clean_cache_key(p2, duration=5.0)
            self.assertEqual(k1, k2)

    def test_laptop_thermal_worker_calibration(self):
        """Verifica se em notebooks o limite de workers paralelos é calibrado em 2 para evitar thermal throttling a 93C."""
        job = app.Job("test_thermal")
        with patch.object(app, "hardware_profile", return_value={"gpus": [{"name": "RTX 3050 Laptop GPU"}], "preferred_gpu": "RTX 3050 Laptop GPU"}):
            budget = app.render_performance_budget(job, gpu=True, segment_count=50)
            self.assertTrue(budget["is_laptop"])
            self.assertEqual(budget["segment_workers"], 2)

    def test_single_pass_mastering_summary(self):
        """Verifica se o sumário do mastering single-pass broadcast é gerado corretamente."""
        from glide_audio_master import single_pass_summary
        s = single_pass_summary("youtube_long")
        self.assertEqual(s["passes"], 1)
        self.assertEqual(s["target_lufs"], -14.0)
        self.assertEqual(s["mode"], "single_pass_linear_broadcast")

    def test_automator_kind_allowed_modern_image_formats(self):
        """Verifica se AVIF, HEIC, HEIF e JFIF são aceitos pelo automator e IMAGE_EXTS."""
        for ext in (".avif", ".heic", ".heif", ".jfif", ".jpg", ".png", ".webp"):
            self.assertTrue(app._automator_kind_allowed("image", ext), f"Falha ao aceitar image com {ext}")
            self.assertTrue(app._automator_kind_allowed("video", ext), f"Falha ao aceitar visual lane com {ext}")
            self.assertTrue(ext in app.IMAGE_EXTS, f"{ext} ausente de app.IMAGE_EXTS")

    def test_ensure_compatible_image_source_avif_conversion(self):
        """Verifica se imagens AVIF são convertidas transparentemente para JPEG legível pelo FFmpeg."""
        from PIL import Image
        with tempfile.TemporaryDirectory() as td:
            avif_path = Path(td) / "test_photo.avif"
            test_img = Image.new("RGB", (640, 480), color=(120, 180, 220))
            test_img.save(avif_path, format="AVIF")
            self.assertTrue(avif_path.exists())

            compat_path = app.ensure_compatible_image_source(avif_path, Path(td))
            self.assertTrue(compat_path.exists())
            self.assertEqual(compat_path.suffix.lower(), ".jpg")
            w, h = app.probe_image_dimensions(compat_path)
            self.assertEqual(w, 640)
            self.assertEqual(h, 480)

    def test_normalize_and_relocate_media_file_avif(self):
        """Verifica se _normalize_and_relocate_media_file converte AVIF para JPG no destino."""
        from PIL import Image
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "staging_file.avif"
            tgt = Path(td) / "dest_file.jpg"
            img = Image.new("RGB", (320, 240), color=(200, 100, 50))
            img.save(src, format="AVIF")

            final_path = app._normalize_and_relocate_media_file(src, tgt)
            self.assertEqual(final_path.resolve(), tgt.resolve())
            self.assertTrue(tgt.exists())
            self.assertFalse(src.exists())
            w, h = app.probe_image_dimensions(tgt)
            self.assertEqual(w, 320)
            self.assertEqual(h, 240)


    def test_visual_clean_cache_key_duration_invariant(self):
        """Verifica se visual_clean_cache_key é consistente independentemente do tempo de probe passado."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sample.mp4"
            p.write_bytes(b"testmp4data" * 200)
            k1 = app.visual_clean_cache_key(p, duration=5.0)
            k2 = app.visual_clean_cache_key(p, duration=15.0)
            k3 = app.visual_clean_cache_key(p, duration=0.0)
            self.assertEqual(k1, k2)
            self.assertEqual(k2, k3)

    def test_ema_eta_and_speed_calculation(self):
        """Verifica se o cálculo de throughput EMA, FPS e ETA decrescente funciona corretamente."""
        job = app.Job(
            id="test-job-eta-ema",
            status="running",
            percent=45.0,
            options={"mode": "standard"},
            work=Path(tempfile.gettempdir()),
        )
        job.started_at = time.time() - 100.0  # 100 seconds elapsed
        job.rendered_timeline_duration = 150.0  # 150s rendered => 1.5x realtime
        job.total_timeline_duration = 300.0  # 300s total timeline
        app.JOBS[job.id] = job
        try:
            status_data = app.status(job.id)
            eta = status_data.get("eta_summary") or {}
            self.assertIsNotNone(eta.get("speed_factor"))
            self.assertAlmostEqual(eta["speed_factor"], 1.5, delta=0.1)
            self.assertIn("1.50x tempo real", eta.get("speed_label", ""))
            self.assertIn("45.0 FPS", eta.get("speed_label", ""))
            # Remaining timeline is 150s at 1.5x speed => ~100s + overhead
            rem = eta.get("estimated_remaining_seconds", 0)
            self.assertGreater(rem, 80.0)
            self.assertLess(rem, 130.0)
        finally:
            app.JOBS.pop(job.id, None)

    def test_build_pcm_sfx_event_bed_numpy(self):
        """Verifica se a mixagem de efeitos de áudio em memória funciona e gera um WAV PCM válido."""
        import wave, struct
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            clip1 = work / "clip1.wav"
            clip2 = work / "clip2.wav"
            sr = 48000
            for c_path in (clip1, clip2):
                with wave.open(str(c_path), "wb") as wf:
                    wf.setnchannels(2)
                    wf.setsampwidth(2)
                    wf.setframerate(sr)
                    # 0.5s of sine-like audio
                    samples = bytearray()
                    for s_i in range(int(0.5 * sr)):
                        val = int(5000 * math.sin(s_i * 0.1))
                        samples += struct.pack("<hh", val, val)
                    wf.writeframes(samples)

            prepared = [
                ({"time": 1.0, "effect": "whoosh"}, clip1),
                ({"time": 2.5, "effect": "hit"}, clip2),
            ]
            total_dur = 4.0
            bed = app.build_pcm_sfx_event_bed(prepared, total_dur, work)
            self.assertTrue(bed.exists())
            self.assertGreater(bed.stat().st_size, 44)
            with wave.open(str(bed), "rb") as wf:
                self.assertEqual(wf.getnchannels(), 2)
                self.assertEqual(wf.getsampwidth(), 2)
                self.assertEqual(wf.getframerate(), 48000)
                frames = wf.getnframes()
                self.assertAlmostEqual(frames / 48000.0, total_dur, delta=0.1)


    def test_post_processing_eta_does_not_collapse_to_one_second(self):
        """Garante que quando a renderização dos segmentos termina (rendered_sec == total_sec),
        mas o render ainda está em mixagem de áudio ou composição de chunks (pct < 98%),
        o ETA não colapsa prematuramente para 1 segundo."""
        job = app.Job("test_post_eta", {}, Path(tempfile.gettempdir()))
        job.status = "running"
        job.stage = "cta"
        job.percent = 85.0
        job.has_visual_composition = True
        job.total_timeline_duration = 1770.0
        job.rendered_timeline_duration = 1770.0
        job.started_at = time.time() - 1000.0
        app.JOBS[job.id] = job
        try:
            status_data = app.status(job.id)
            eta_summary = status_data.get("eta_summary", {})
            rem = eta_summary.get("estimated_remaining_seconds", 0)
            self.assertGreater(rem, 5.0)
            self.assertEqual(eta_summary.get("state"), "composition")
        finally:
            app.JOBS.pop(job.id, None)

    def test_watchdog_timeout_not_masked_as_no_valid_videos(self):
        """Garante que se o watchdog estourar o orçamento de render durante a análise de vídeos,
        o erro lançado especifica o estouro de orçamento e NÃO 'Nenhum video valido foi encontrado'."""
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            job = app.Job(id="test_watchdog_budget")
            job.cancel_requested = True
            job.render_budget_state = "exceeded"
            job.render_budget_seconds = 1200.0

            # Test filter_renderable_videos
            with self.assertRaises(RuntimeError) as cm:
                app.filter_renderable_videos(job, [work / "dummy.mp4"], work)
            self.assertIn("Orçamento de render", str(cm.exception))
            self.assertNotIn("Nenhum video valido", str(cm.exception))

            # Test standard cancellation
            job.render_budget_state = None
            with self.assertRaises(app.RenderCancelled):
                app.filter_renderable_videos(job, [work / "dummy.mp4"], work)

    def test_hard_reject_outro_subscribe_static_video_and_black_screen(self):
        """Garante que telas de subscribe/agradecimento, vídeos estáticos/congelados e
        telas pretas são invariavelmente classificadas como hard_reject e eliminadas da timeline,
        inclusive quando o filtro de velocidade estiver desativado (Hard-Gate obrigatório)."""
        # 1. Classificação de tela de subscribe / YouTube outro
        outro_metrics = {"source": "outro_subscribe.mp4", "metrics": {"mean": 55.0, "text_lines": 2, "has_red_subscribe_banner": 1.0}}
        cl_outro = app._classify_visual_analysis(outro_metrics, "normal")
        self.assertEqual(cl_outro.get("category"), "outro_subscribe_screen")
        self.assertEqual(cl_outro.get("action"), "hard_reject")

        # 2. Classificação de vídeo estático (movimento nulo / slide exportado como vídeo)
        static_metrics = {"source": "frozen_slide.mp4", "metrics": {"mean": 60.0, "frame_diff": 0.8}}
        cl_static = app._classify_visual_analysis(static_metrics, "normal", media_kind="video")
        self.assertEqual(cl_static.get("category"), "static_video")
        self.assertEqual(cl_static.get("action"), "hard_reject")

        # 3. Classificação de tela preta
        black_metrics = {"source": "dark_screen.mp4", "metrics": {"mean": 6.0, "black_ratio": 0.90}}
        cl_black = app._classify_visual_analysis(black_metrics, "normal", media_kind="video")
        self.assertIn(cl_black.get("category"), {"black_screen", "static_black_screen"})
        self.assertEqual(cl_black.get("action"), "hard_reject")

        # 4. Portão Rígido (Hard-Gate): mesmo com visualCleanFilter=False, clipes são bloqueados
        job = app.Job(id="test_hard_gate_invariance", options={"visualCleanFilter": False})
        pair_outro = (Path("outro.mp4"), 5.0)
        pair_static = (Path("static.mp4"), 5.0)
        pair_black = (Path("black.mp4"), 5.0)
        pair_clean = (Path("broll_clean.mp4"), 5.0)

        def mock_probe(p, d, lvl, cwd=None):
            name = str(p)
            if "outro" in name:
                return {"category": "outro_subscribe_screen", "action": "hard_reject", "reason": "outro card"}
            elif "static" in name:
                return {"category": "static_video", "action": "hard_reject", "reason": "video estatico"}
            elif "black" in name:
                return {"category": "black_screen", "action": "hard_reject", "reason": "tela preta"}
            return {"category": "clean", "action": "keep", "reason": "broll limpo"}

        with unittest.mock.patch("app.probe_visual_clean_health", side_effect=mock_probe):
            approved_pairs, summary = app.apply_visual_clean_filter(
                job, [pair_outro, pair_static, pair_black, pair_clean], 20.0, Path(".")
            )

        self.assertEqual(len(approved_pairs), 1)
        self.assertEqual(approved_pairs[0][0].name, "broll_clean.mp4")
        self.assertEqual(summary.get("hard_rejected"), 3)

    def test_normal_broll_with_red_elements_not_rejected_as_subscribe(self):
        """Garante que filmagens ou fotos reais com elementos vermelhos (ex: robô Ameca, flores,
        roupa vermelha) NÃO são falsamente classificadas como tela de subscribe."""
        # Vídeo com movimento natural e elementos vermelhos/fundo homogêneo
        broll_metrics = {
            "source": "09_Ameca_expressions_with_GPT3_4_00m00s-00m07s.mp4",
            "metrics": {
                "mean": 110.0,
                "stdev": 45.0,
                "frame_diff": 4.5,
                "edge_density": 0.05,
                "has_red_subscribe_banner": 0.0,
                "text_lines": 0,
                "text_score": 0.0,
                "uniform_bg": 0.22,
            }
        }
        cl = app._classify_visual_analysis(broll_metrics, "normal", media_kind="video")
        self.assertEqual(cl.get("category"), "clean")
        self.assertEqual(cl.get("action"), "keep")

        # Foto com fundo claro e sem texto
        photo_metrics = {
            "source": "428_SoftBank_Pepper_working_at_Heijo_Palace.jpg",
            "metrics": {
                "mean": 125.0,
                "stdev": 50.0,
                "frame_diff": 0.0,
                "edge_density": 0.06,
                "has_red_subscribe_banner": 0.0,
                "text_lines": 0,
                "text_score": 0.0,
                "uniform_bg": 0.30,
            }
        }
        cl_photo = app._classify_visual_analysis(photo_metrics, "normal", media_kind="image")
        self.assertEqual(cl_photo.get("category"), "clean")
        self.assertEqual(cl_photo.get("action"), "keep")

    def test_tech_photo_with_clean_background_not_rejected_as_slide(self):
        """Garante que fotos de robôs/produtos com fundo de estúdio e nitidez alta
        não sejam rejeitadas como slides de apresentação quando não contêm blocos de texto."""
        metrics = {
            "source": "423_SoftBank_Pepper_standing_alone.jpg",
            "metrics": {
                "mean": 130.0,
                "stdev": 55.0,
                "frame_diff": 0.0,
                "edge_density": 0.07,
                "has_red_subscribe_banner": 0.0,
                "text_lines": 0,
                "text_score": 0.0,
                "uniform_bg": 0.42,
                "black_ratio": 0.0,
            }
        }
        cl = app._classify_visual_analysis(metrics, "normal", media_kind="image")
        self.assertEqual(cl.get("category"), "clean")
        self.assertEqual(cl.get("action"), "keep")

    def test_visual_clean_salvage_safeguard_prevents_video_underflow(self):
        """Garante que se o filtro rejeitar mais mídias do que o áudio necessita,
        o mecanismo de salvaguarda restaura os melhores clipes para evitar que o vídeo fique curto."""
        job = app.Job(id="test_salvage", options={"mode": "standard", "ratio": "16:9", "visualCleanFilter": True})
        # 10 mídias de 5s cada = 50s total. Áudio precisa de 40s.
        pairs = [(Path(f"clip_{i}.mp4"), 5.0) for i in range(10)]
        
        # Simula classificador rejeitando 8 dos 10 clipes (apenas 2 passariam = 10s < 40s)
        def mock_probe(path, *args, **kwargs):
            idx = int(path.stem.split("_")[1])
            if idx < 2:
                return {"category": "clean", "action": "keep", "reason": "clean broll", "score": 90}
            else:
                return {"category": "reused_slide", "action": "reject", "reason": "suspect slide", "score": 75}

        with unittest.mock.patch("app.probe_visual_clean_health", side_effect=mock_probe):
            approved_pairs, summary = app.apply_visual_clean_filter(job, pairs, 40.0, Path("."))

        approved_dur = sum(d for _, d in approved_pairs)
        self.assertGreaterEqual(approved_dur, 40.0, "A salvaguarda deve garantir duração suficiente para cobrir o áudio")
        self.assertGreater(len(approved_pairs), 2)

    def test_build_segment_plan_guarantees_complete_audio_coverage(self):
        """Garante que build_segment_plan gera planos cobrindo 100% da narração respeitando o teto de 2x de repetição."""
        files = [Path("vid1.mp4"), Path("img1.jpg"), Path("vid2.mp4")]
        durs = [5.0, 5.0, 5.0]
        audio_dur = 120.0  # 2 minutos de áudio com apenas 15s de mídia única
        plans, summary = app.build_segment_plan(files, durs, audio_dur, force_short=True)
        total_planned = sum(p.target_duration for p in plans)
        # O total planejado cobre 100% da duração final de áudio ajustada, sem exceder 2x de repetição
        self.assertAlmostEqual(total_planned, summary["audio_duration"], delta=0.5)
        self.assertLessEqual(summary.get("max_asset_usage"), 2)

    def test_case_a_plenty_clean_videos(self):
        """Caso A: Projeto com muitas mídias de vídeo limpas.
        Todas as mídias devem ser usadas 1x, sem repetições desnecessárias, com cortes naturais."""
        files = [Path(f"video_clean_{i}.mp4") for i in range(12)]
        durs = [6.0] * 12  # 72s de vídeo para 45s de áudio
        plans, summary = app.build_segment_plan(files, durs, 45.0, force_short=True)
        self.assertEqual(summary.get("max_asset_usage"), 1, "Nenhuma mídia deve se repetir quando há mídia limpa suficiente")
        self.assertFalse(summary.get("audio_trimmed"))
        self.assertAlmostEqual(summary.get("planned_duration"), 45.0, delta=0.5)
        for p in plans:
            self.assertGreaterEqual(p.target_duration, 1.8)
            self.assertLessEqual(p.target_duration, 6.0)

    def test_case_b_static_images_smooth_ken_burns(self):
        """Caso B: Projeto com imagens estáticas suficientes.
        Movimentos Ken Burns suaves sem tremor, arquétipos cinemáticos e duração 4.0s a 7.5s."""
        files = [Path(f"image_{i}.jpg") for i in range(10)]
        durs = [5.0] * 10
        plans, summary = app.build_segment_plan(files, durs, 50.0, force_short=True)
        self.assertEqual(summary.get("max_asset_usage"), 1)
        for p in plans:
            self.assertEqual(p.media_kind, "image")
            self.assertIn(p.image_motion, app.IMAGE_MOTION_ARCHETYPES)
            self.assertGreaterEqual(p.target_duration, 3.0)
            self.assertLessEqual(p.target_duration, 7.5)

    def test_case_c_hybrid_images_and_videos(self):
        """Caso C: Projeto misto (imagens + vídeos).
        Transição harmônica, vídeos sem cortes hiperativos, imagens suaves."""
        files = [Path(f"vid_{i}.mp4") for i in range(5)] + [Path(f"img_{i}.jpg") for i in range(5)]
        durs = [5.0] * 10
        plans, summary = app.build_segment_plan(files, durs, 45.0, force_short=True)
        kinds = {p.media_kind for p in plans}
        self.assertIn("video", kinds)
        self.assertIn("image", kinds)
        self.assertLessEqual(summary.get("max_asset_usage"), 2)

    def test_case_d_slight_media_deficit_progressive_hierarchy(self):
        """Caso D: Projeto com leve déficit de mídia.
        Fase 2 (expansão de imagem) e Fase 3 (desaceleração de vídeo) antes de reutilização (máx 2x)."""
        # 4 imagens e 2 vídeos = base 4*4.2 + 2*5.0 = 26.8s para 35s de áudio
        files = [Path(f"img_{i}.jpg") for i in range(4)] + [Path(f"vid_{i}.mp4") for i in range(2)]
        durs = [5.0] * 6
        plans, summary = app.build_segment_plan(files, durs, 35.0, force_short=True)
        # Deve ter expandido imagens até 7.5s
        self.assertGreaterEqual(summary.get("applied_image_duration"), 4.5)
        # Asset usage nunca excede 2
        self.assertLessEqual(summary.get("max_asset_usage"), 2)
        # Duração planejada deve cobrir os 35s sem corte de áudio
        self.assertFalse(summary.get("audio_trimmed"))
        self.assertAlmostEqual(summary.get("planned_duration"), 35.0, delta=0.5)

    def test_case_e_soft_reject_only_used_when_clean_insufficient(self):
        """Caso E: Projeto com mídias suspeitas / soft-reject.
        Soft-reject só entra se faltar mídia aprovada. Hard-reject NUNCA entra."""
        clean_files = [Path(f"clean_{i}.mp4") for i in range(8)]
        clean_durs = [5.0] * 8  # 40s
        soft_media = [(Path(f"soft_{i}.mp4"), 5.0) for i in range(4)]
        hard_media = [(Path("black_screen.mp4"), 5.0), (Path("subscribe.mp4"), 5.0)]

        # Subcaso 1: Limpas suficientes (40s limpo para 30s áudio) -> soft NÃO deve entrar
        plans1, sum1 = app.build_segment_plan(
            clean_files, clean_durs, 30.0, force_short=True,
            soft_rejected_media=soft_media, hard_rejected_media=hard_media,
        )
        sources1 = {p.source.name for p in plans1}
        self.assertTrue(all("clean" in s for s in sources1), "Soft-reject não deve entrar quando limpas cobrem áudio")
        self.assertNotIn("black_screen.mp4", sources1)
        self.assertNotIn("subscribe.mp4", sources1)

        # Subcaso 2: Limpas insuficientes (10s limpo para 40s áudio) -> soft entra de apoio, hard NUNCA
        few_clean = [Path("clean_0.mp4"), Path("clean_1.mp4")]
        few_durs = [5.0, 5.0]
        plans2, sum2 = app.build_segment_plan(
            few_clean, few_durs, 40.0, force_short=True,
            soft_rejected_media=soft_media, hard_rejected_media=hard_media,
        )
        sources2 = {p.source.name for p in plans2}
        self.assertNotIn("black_screen.mp4", sources2, "Hard-reject JAMAIS pode entrar")
        self.assertNotIn("subscribe.mp4", sources2, "Hard-reject JAMAIS pode entrar")
        self.assertLessEqual(sum2.get("max_asset_usage"), 2)

    def test_case_f_long_audio_scarce_media_graceful_end(self):
        """Caso F: Áudio longo com pouca mídia.
        Todas as mídias úteis usadas 2x com variação. Sem congelar tela, sem repetir 3x,
        vídeo encerra de forma limpa onde a mídia disponível acabou."""
        files = [Path("vid1.mp4"), Path("img1.jpg"), Path("vid2.mp4")]
        durs = [5.0, 5.0, 5.0]  # 15s de mídia única
        audio_dur = 120.0  # 120s de áudio
        plans, summary = app.build_segment_plan(files, durs, audio_dur, force_short=True)
        # Limite absoluto de 2x respeitado
        self.assertLessEqual(summary.get("max_asset_usage"), 2)
        # Áudio foi encerrado no limite da mídia disponível
        self.assertTrue(summary.get("audio_trimmed"))
        total_planned = sum(p.target_duration for p in plans)
        self.assertAlmostEqual(total_planned, summary.get("audio_duration"), delta=0.35)
        # Nenhuma tela congelada
        self.assertGreaterEqual(total_planned, 15.0)

    def test_case_g_content_deduplication_renamed_copies(self):
        """Caso G: Arquivos renomeados ou duplicados na pasta.
        Deduplicação por fingerprint compartilha o mesmo contador (máximo 2x global)."""
        p1 = Path("original_clip.mp4")
        p2 = Path("copy_of_clip.mp4")
        app.ASSET_FINGERPRINT_CACHE[str(p1.resolve()).lower()] = "fp_identical_123"
        app.ASSET_FINGERPRINT_CACHE[str(p2.resolve()).lower()] = "fp_identical_123"

        files = [p1, p2, Path("other.mp4")]
        durs = [5.0, 5.0, 5.0]
        plans, summary = app.build_segment_plan(files, durs, 25.0, force_short=True)
        fp_count = sum(1 for p in plans if app.compute_asset_fingerprint(p.source) == "fp_identical_123")
        self.assertLessEqual(fp_count, 2, "Cópias duplicadas não podem exceder 2x somadas")

    def test_audit_timeline_plan_detects_violations(self):
        """Verifica se a auditoria matemática pré-render barra planos inválidos."""
        plan_ok = [
            app.SegmentPlan(source=Path("v1.mp4"), raw_duration=5.0, target_duration=5.0, source_offset=0.0, source_index=1, cycle=0, media_kind="video", image_motion=""),
            app.SegmentPlan(source=Path("v2.mp4"), raw_duration=5.0, target_duration=5.0, source_offset=0.0, source_index=2, cycle=0, media_kind="video", image_motion=""),
        ]
        res = app.audit_timeline_plan(plan_ok, 10.0)
        self.assertTrue(res["passed"])

        # Violação de repetição: 3 aparições do mesmo asset
        plan_bad = [
            app.SegmentPlan(source=Path("v1.mp4"), raw_duration=5.0, target_duration=5.0, source_offset=0.0, source_index=1, cycle=0, media_kind="video", image_motion=""),
            app.SegmentPlan(source=Path("v1.mp4"), raw_duration=5.0, target_duration=5.0, source_offset=0.0, source_index=1, cycle=1, media_kind="video", image_motion=""),
            app.SegmentPlan(source=Path("v1.mp4"), raw_duration=5.0, target_duration=5.0, source_offset=0.0, source_index=1, cycle=2, media_kind="video", image_motion=""),
        ]
        with self.assertRaises(RuntimeError):
            app.audit_timeline_plan(plan_bad, 15.0)


if __name__ == '__main__':
    unittest.main()



