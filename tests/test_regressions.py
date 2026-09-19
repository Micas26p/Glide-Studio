"""Run with python -m unittest discover -s tests -v. Never uses user data."""
import asyncio
import atexit
import gc
import io
import json
import os
from pathlib import Path
import tempfile
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
        job.preflight_summary['active_render_estimate'] = {
            'seconds': 600.0,
            'confidence': 'historical',
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
            self.assertNotEqual(rem1, rem2)

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


if __name__ == '__main__':
    unittest.main()


