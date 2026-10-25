from __future__ import annotations

import array
import math
import struct
import sys
import wave
from pathlib import Path
from typing import Any


def make_sfx_wav_header(total_frames: int, sample_rate: int = 48000, channels: int = 2, sample_width: int = 2) -> bytes:
    """Gera cabeçalho canônico RIFF/WAVE PCM de 44 bytes para buffer de áudio."""
    frame_bytes = channels * sample_width
    data_size = total_frames * frame_bytes
    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        channels,
        sample_rate,
        sample_rate * frame_bytes,
        frame_bytes,
        sample_width * 8,
        b"data",
        data_size,
    )


def build_pcm_sfx_event_bed(
    prepared: list[tuple[dict[str, Any], Path]],
    audio_total: float,
    work: Path,
) -> Path:
    """Mix short PCM effects into one sample-accurate bed in memory for ultra-fast performance."""
    sample_rate = 48000
    channels = 2
    sample_width = 2
    frame_bytes = channels * sample_width
    total_frames = max(1, int(math.ceil(max(0.1, audio_total) * sample_rate)))
    data_size = total_frames * frame_bytes
    if data_size >= 0xFFFFFFFF - 44:
        raise RuntimeError("Faixa de efeitos excede o limite WAV PCM.")

    bed = work / "glide_sfx_event_bed.wav"
    header = make_sfx_wav_header(total_frames, sample_rate, channels, sample_width)

    try:
        import numpy as np

        def _load_and_normalize_clip(clip_path: Path) -> np.ndarray | None:
            try:
                with wave.open(str(clip_path), "rb") as source:
                    channels_in = source.getnchannels()
                    framerate = source.getframerate()
                    sampwidth = source.getsampwidth()
                    raw = source.readframes(source.getnframes())
                    if not raw:
                        return None
                    if sampwidth == 2:
                        clip_arr = np.frombuffer(raw, dtype=np.int16).astype(np.int32)
                    elif sampwidth == 1:
                        clip_arr = (np.frombuffer(raw, dtype=np.uint8).astype(np.int32) - 128) * 256
                    else:
                        return None

                    if channels_in == 1:
                        clip_arr = np.repeat(clip_arr, 2)
                    elif channels_in > 2:
                        # Se multicanal (>2), extrair os dois primeiros canais
                        frames_cnt = len(clip_arr) // channels_in
                        clip_arr = clip_arr.reshape(frames_cnt, channels_in)[:, :2].flatten()

                    if framerate != sample_rate and len(clip_arr) > 0:
                        actual_frames = len(clip_arr) // channels
                        target_frames_clip = int(round(actual_frames * sample_rate / framerate))
                        if target_frames_clip > 0:
                            old_x = np.linspace(0, actual_frames, actual_frames, endpoint=False)
                            new_x = np.linspace(0, actual_frames, target_frames_clip, endpoint=False)
                            left = np.interp(new_x, old_x, clip_arr[0::2])
                            right = np.interp(new_x, old_x, clip_arr[1::2])
                            resampled = np.empty(target_frames_clip * 2, dtype=np.int32)
                            resampled[0::2] = left.astype(np.int32)
                            resampled[1::2] = right.astype(np.int32)
                            clip_arr = resampled

                    return clip_arr
            except Exception:
                return None

        # Otimização em memória contígua direta quando cabe confortavelmente na RAM (<300MB)
        if total_frames <= 35_000_000:
            bed_arr = np.zeros(total_frames * channels, dtype=np.int32)
            for event, clip in prepared:
                start_frame = max(0, int(round(float(event.get("time") or 0.0) * sample_rate)))
                if start_frame >= total_frames:
                    continue
                clip_arr = _load_and_normalize_clip(clip)
                if clip_arr is None or len(clip_arr) == 0:
                    continue
                dst_s = start_frame * channels
                dst_e = dst_s + min(len(clip_arr), (total_frames - start_frame) * channels)
                src_len = dst_e - dst_s
                bed_arr[dst_s:dst_e] += clip_arr[:src_len]

            with bed.open("wb") as target:
                target.write(header)
                np.clip(bed_arr, -32768, 32767, out=bed_arr)
                target.write(bed_arr.astype(np.int16).tobytes())
            return bed

        # Process in chunks (48000 frames) as fallback for ultra-long timelines (>40 min)
        chunk_frames = 48000
        total_chunks = int(math.ceil(total_frames / chunk_frames))

        loaded_events = []
        for event, clip in prepared:
            start_frame = max(0, int(round(float(event.get("time") or 0.0) * sample_rate)))
            if start_frame >= total_frames:
                continue
            clip_arr = _load_and_normalize_clip(clip)
            if clip_arr is None or len(clip_arr) == 0:
                continue
            frames_in_clip = len(clip_arr) // channels
            loaded_events.append((start_frame, start_frame + frames_in_clip, clip_arr))

        with bed.open("wb") as target:
            target.write(header)
            for chunk_idx in range(total_chunks):
                c_start = chunk_idx * chunk_frames
                c_end = min(total_frames, c_start + chunk_frames)
                c_len = c_end - c_start
                chunk_arr = np.zeros(c_len * channels, dtype=np.int32)

                for ev_start, ev_end, ev_data in loaded_events:
                    if ev_end <= c_start or ev_start >= c_end:
                        continue
                    overlap_start = max(c_start, ev_start)
                    overlap_end = min(c_end, ev_end)
                    src_offset = (overlap_start - ev_start) * channels
                    src_count = (overlap_end - overlap_start) * channels
                    dst_offset = (overlap_start - c_start) * channels
                    chunk_arr[dst_offset : dst_offset + src_count] += ev_data[src_offset : src_offset + src_count]

                np.clip(chunk_arr, -32768, 32767, out=chunk_arr)
                target.write(chunk_arr.astype(np.int16).tobytes())

        return bed
    except Exception:
        # Fallback robusto em Python puro
        chunk_frames = 16384
        total_chunks = int(math.ceil(total_frames / chunk_frames))
        loaded_events_pure = []
        for event, clip in prepared:
            start_frame = max(0, int(round(float(event.get("time") or 0.0) * sample_rate)))
            if start_frame >= total_frames:
                continue
            try:
                with wave.open(str(clip), "rb") as source:
                    channels_in = source.getnchannels()
                    n_frames = min(source.getnframes(), total_frames - start_frame)
                    if n_frames <= 0:
                        continue
                    raw = source.readframes(n_frames)
                    if not raw:
                        continue
                    arr = array.array("h")
                    arr.frombytes(raw)
                    if sys.byteorder != "little":
                        arr.byteswap()
                    if channels_in == 1:
                        stereo_arr = array.array("h")
                        for s in arr:
                            stereo_arr.append(s)
                            stereo_arr.append(s)
                        arr = stereo_arr
                    loaded_events_pure.append((start_frame, start_frame + (len(arr) // 2), arr))
            except Exception:
                continue

        with bed.open("wb") as target:
            target.write(header)
            for c_idx in range(total_chunks):
                c_start = c_idx * chunk_frames
                c_end = min(total_frames, (c_idx + 1) * chunk_frames)
                c_len = c_end - c_start
                chunk_buf = [0] * (c_len * channels)

                for ev_start, ev_end, arr in loaded_events_pure:
                    if ev_end <= c_start or ev_start >= c_end:
                        continue
                    overlap_start = max(c_start, ev_start)
                    overlap_end = min(c_end, ev_end)
                    src_s = (overlap_start - ev_start) * channels
                    src_e = (overlap_end - ev_start) * channels
                    dst_s = (overlap_start - c_start) * channels
                    for k in range(src_e - src_s):
                        chunk_buf[dst_s + k] += arr[src_s + k]

                out_arr = array.array("h", (max(-32768, min(32767, val)) for val in chunk_buf))
                if sys.byteorder != "little":
                    out_arr.byteswap()
                target.write(out_arr.tobytes())
        return bed
