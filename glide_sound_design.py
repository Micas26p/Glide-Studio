from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def compact_sound_events(events: list[dict[str, Any]], limit: int = 160) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for event in events[:limit]:
        compact.append({
            "time": event.get("time"),
            "target_time": event.get("target_time"),
            "actual_start": event.get("actual_start"),
            "actual_peak": event.get("actual_peak"),
            "effect": event.get("effect"),
            "reason": event.get("reason"),
            "variant_file": event.get("variant_file"),
            "source": event.get("source"),
            "anchor": event.get("anchor"),
            "offset": event.get("offset"),
            "duration": event.get("duration"),
            "volume_db": event.get("volume_db"),
            "measured_onset_ms": event.get("measured_onset_ms"),
            "rendered_onset_ms": event.get("rendered_onset_ms"),
            "measured_peak_ms": event.get("measured_peak_ms"),
            "sync_deviation_ms": event.get("sync_deviation_ms"),
            "timing_source": event.get("timing_source"),
            "asset_seek_seconds": event.get("asset_seek_seconds"),
            "visual_start_frame": event.get("visual_start_frame"),
            "impact_frame": event.get("impact_frame"),
            "sound_peak_frame": event.get("sound_peak_frame"),
            "subtitle_index": event.get("subtitle_index"),
            "subtitle_animation": event.get("subtitle_animation"),
            "subtitle_variant": event.get("subtitle_variant"),
            "transition_index": event.get("transition_index"),
            "transition_mode": event.get("transition_mode"),
            "tight": event.get("tight"),
        })
    return compact


def write_sound_design_map(export_dir: Path, events: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    export_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": summary,
        "events": compact_sound_events(events),
        "note": "Mapa automatico dos efeitos sonoros usados no render.",
    }
    (export_dir / "sound_design_map.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
