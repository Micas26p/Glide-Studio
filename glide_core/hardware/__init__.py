from __future__ import annotations

from glide_core.hardware.thermal_governor import (
    HardwareThermalGovernor,
    HARDWARE_THERMAL_GOVERNOR,
    THERMAL_GOVERNOR,
    _NvencGate,
    NVENC_GATE,
    gpu_free_vram_mb,
    uses_nvenc,
    nvenc_slot,
)

__all__ = [
    "HardwareThermalGovernor",
    "HARDWARE_THERMAL_GOVERNOR",
    "THERMAL_GOVERNOR",
    "_NvencGate",
    "NVENC_GATE",
    "gpu_free_vram_mb",
    "uses_nvenc",
    "nvenc_slot",
]
