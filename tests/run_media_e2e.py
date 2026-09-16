"""Real FFmpeg regression scenario against an isolated running Glide server."""
import json
from pathlib import Path
import subprocess
import sys
import time
import httpx

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else ROOT / 'scratch' / 'qa_demo'
FIXTURES.mkdir(parents=True, exist_ok=True)


def ffmpeg(*args):
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *map(str, args)], check=True)


def main():
    if not (FIXTURES / 'narração.wav').exists():
        ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=220:sample_rate=48000:duration=24',
               '-af', 'volume=0.7+0.3*sin(2*PI*t):eval=frame', FIXTURES / 'narração.wav')
        ffmpeg('-f', 'lavfi', '-i', 'testsrc2=size=640x360:rate=24:duration=12',
               '-c:v', 'libx264', '-pix_fmt', 'yuv420p', FIXTURES / 'cena 01.mp4')
        ffmpeg('-f', 'lavfi', '-i', 'smptebars=size=640x360:rate=24:duration=8',
               '-c:v', 'libx264', FIXTURES / 'cena 02.mp4')
        ffmpeg('-i', FIXTURES / 'cena 01.mp4', '-frames:v', '1', FIXTURES / 'foto ação.png')
        ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=24', FIXTURES / 'música.wav')
        (FIXTURES / 'textos.srt').write_text('1\n00:00:00,000 --> 00:00:06,000\nUma viagem começa aqui.\n\n2\n00:00:06,000 --> 00:00:12,000\nCada cena conta uma história.\n\n3\n00:00:12,000 --> 00:00:18,000\nImagens, ritmo e emoção.\n\n4\n00:00:18,000 --> 00:00:24,000\nAté à próxima aventura!\n', encoding='utf-8')
    files = [('cena 01.mp4','video'), ('cena 02.mp4','video'), ('foto ação.png','image'),
             ('narração.wav','audio'), ('música.wav','background_music'), ('textos.srt','subtitle')]
    options = dict(mode='fast', codec='h264', gpu=False, ctaLanguage='english',
                   finalOutputMode='browser_download', backgroundMusicUseLibrary=False,
                   renderBudgetEnabled=False, renderRecovery=False, visualCleanFilter=False,
                   estimatedDurationSeconds=24, outputName='QA ciclo completo', dualExportShorts=True,
                   forceShortRender=True)
    client = httpx.Client(base_url=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8793', timeout=120)
    manifest = [{'rel': name, 'name': name, 'kind': kind} for name,kind in files]
    start = time.perf_counter()
    result = client.post('/api/create-render-job', data={'manifest':json.dumps(manifest), 'options':json.dumps(options)})
    result.raise_for_status()
    job_id = result.json()['job_id']
    print('JOB',job_id,flush=True)
    for i,(name,kind) in enumerate(files):
        with (FIXTURES/name).open('rb') as handle:
            response=client.post(f'/api/upload-file/{job_id}', data={'rel':name,'kind':kind,'index':i}, files={'file':(name,handle)})
            response.raise_for_status()
    client.post(f'/api/launch-render/{job_id}').raise_for_status()
    last_stage = None
    deadline=time.monotonic()+1200
    while time.monotonic()<deadline:
        result=client.get(f'/api/status/{job_id}').json()
        if result.get('stage')!=last_stage:
            last_stage=result.get('stage')
            print(result.get('status'), last_stage, result.get('message'),flush=True)
        if result.get('status') in ('done','error','cancelled','recovered'):
            break
        time.sleep(1)
    result['qa_elapsed_seconds']=round(time.perf_counter()-start,3)
    (FIXTURES/f'{job_id}_status.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({key:result.get(key) for key in ('status','error','output','output_dir','qa_elapsed_seconds')},ensure_ascii=True),flush=True)
    if result.get('status')!='done':
        print(str(result.get('log',''))[-4000:])
        return 1
    output=Path(result['output'])
    probe=subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(output)],capture_output=True,text=True,check=True)
    metadata=json.loads(probe.stdout)
    (FIXTURES/f'{job_id}_probe.json').write_text(probe.stdout,encoding='utf-8')
    assert any(s['codec_type']=='audio' for s in metadata['streams'])
    assert any(s['codec_type']=='video' for s in metadata['streams'])
    assert 23 <= float(metadata['format']['duration']) <= 35, metadata['format']['duration']
    ffmpeg('-i',output,'-f','null','-')
    print('OUTPUT DECODE OK',flush=True)
    return 0


if __name__=='__main__':
    sys.exit(main())
