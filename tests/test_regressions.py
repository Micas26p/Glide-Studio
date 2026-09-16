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


if __name__ == '__main__':
    unittest.main()
