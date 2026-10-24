"""
Glide Core - Pacote de Arquitetura Modularizada do Glide Studio Ultra 2.0
Submódulos organizados para hardware, legendas, áudio, pipeline visual e motor de render.
"""

from __future__ import annotations

from glide_core.hardware import (
    HardwareThermalGovernor,
    HARDWARE_THERMAL_GOVERNOR,
    THERMAL_GOVERNOR,
    _NvencGate,
    NVENC_GATE,
    gpu_free_vram_mb,
    uses_nvenc,
    nvenc_slot,
)
from glide_core.subtitles import (
    srt_time_to_seconds,
    seconds_to_ass_time,
    ass_escape,
    ass_color,
)
from glide_core.audio import (
    build_pcm_sfx_event_bed,
    make_sfx_wav_header,
)

__version__ = "2.0.0"

__all__ = [
    "HardwareThermalGovernor",
    "HARDWARE_THERMAL_GOVERNOR",
    "THERMAL_GOVERNOR",
    "_NvencGate",
    "NVENC_GATE",
    "gpu_free_vram_mb",
    "uses_nvenc",
    "nvenc_slot",
    "srt_time_to_seconds",
    "seconds_to_ass_time",
    "ass_escape",
    "ass_color",
    "build_pcm_sfx_event_bed",
    "make_sfx_wav_header",
]
