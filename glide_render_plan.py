from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def media_names(paths: list[Path], limit: int = 14) -> list[str]:
    return [Path(path).name for path in paths[:limit]]


def int_option(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(float(value))
    except Exception:
        parsed = default
    return max(minimum, min(maximum, parsed))


def build_render_plan(
    *,
    app_version: str,
    job_id: str,
    options: dict[str, Any],
    videos: list[Path],
    audios: list[Path],
    background_tracks: list[Path],
    subtitles: list[Path],
    captions: list[Path] | None = None,
    preflight: dict[str, Any] | None = None,
    timeline: dict[str, Any] | None = None,
    output: str | None = None,
) -> dict[str, Any]:
    return {
        "version": app_version,
        "job_id": job_id,
        "policy": {
            "duration": options.get("durationPolicy", "smart_fit_reuse"),
            "cta": "director_contextual_max_2",
            "music": options.get("backgroundMusicPolicy", "fit_voiceover_random_reuse"),
            "sound_fx": "automatic_mapped_events" if options.get("autoSoundFx", True) else "disabled",
            "emotion": options.get("projectTone", "auto"),
            "ducking": "adaptive" if options.get("adaptiveDucking", True) else "fixed",
            "dynamic_pauses": "enabled" if options.get("dynamicPauses", False) else "disabled",
            "recovery": "enabled" if options.get("renderRecovery", True) else "disabled",
            "render_graph": "selective_cached_nodes_v2",
            "director": "smart_scene_fit" if options.get("smartVisualDirector", True) else "manual_timeline",
            "semantic_index": "optional_local_onnx" if options.get("semanticVisualIndex", True) else "filename_heuristics",
            "channel_learning": "local_after_three_signals" if options.get("channelLearning", True) else "disabled",
            "anti_repeat": "channel_recent_five" if options.get("antiRepeat", True) else "disabled",
            "continuity": "neighbor_match" if options.get("continuityMatch", True) else "disabled",
            "audio_master": "youtube_loudnorm_two_pass" if options.get("audioMastering", True) else "disabled",
            "reference_style": (
                "inspiration_guide"
                if options.get("referenceStyleMode") != "reference"
                else "precise_reference_guide"
            ) if options.get("referenceStyleEnabled") else "glide_package",
        },
        "inputs": {
            "videos": {"count": len(videos), "samples": media_names(videos)},
            "voiceover": {"count": len(audios), "samples": media_names(audios)},
            "background_music": {"count": len(background_tracks), "samples": media_names(background_tracks)},
            "texts": {"count": len(subtitles), "samples": media_names(subtitles)},
            "captions": {"count": len(captions or []), "samples": media_names(captions or [])},
        },
        "options": {
            "mode": options.get("mode"),
            "ratio": options.get("ratio"),
            "codec": options.get("codec"),
            "export_profile": options.get("exportProfile"),
            "transitions": options.get("transitions"),
            "intro_mode": options.get("introMode", "standard"),
            "quality_boost": bool(options.get("qualityBoost", True)),
            "cta_language": options.get("ctaLanguage"),
            "cta_max_occurrences": int_option(options.get("ctaMaxOccurrences"), 2, 1, 2),
            "smart_subtitle_placement": bool(options.get("smartSubtitlePlacement", True)),
            "smart_cta_placement": bool(options.get("smartCtaPlacement", True)),
            "music_genre": options.get("backgroundMusicGenre"),
            "project_tone": options.get("projectTone", "auto"),
            "adaptive_ducking": bool(options.get("adaptiveDucking", True)),
            "dynamic_pauses": bool(options.get("dynamicPauses", False)),
            "strong_moment_enhance": bool(options.get("strongMomentEnhance", True)),
            "render_recovery": bool(options.get("renderRecovery", True)),
            "render_priority": options.get("renderPriority", "balanced"),
            "turbo_policy": options.get("turboPolicy", "production_max") if options.get("renderPriority") == "max" else "disabled",
            "auto_director": bool(options.get("autoDirector", True)),
            "semantic_visual_index": bool(options.get("semanticVisualIndex", True)),
            "channel_learning": bool(options.get("channelLearning", True)),
            "energy_editing": bool(options.get("energyEditing", True)),
            "anti_repeat": bool(options.get("antiRepeat", True)),
            "continuity_match": bool(options.get("continuityMatch", True)),
            "audio_mastering": bool(options.get("audioMastering", True)),
            "reference_style_enabled": bool(options.get("referenceStyleEnabled", False)),
            "reference_style_mode": "reference" if options.get("referenceStyleMode") == "reference" else "inspiration",
        },
        "preflight": preflight or {},
        "turbo_summary": (preflight or {}).get("turbo_summary") or {},
        "confidence_summary": (preflight or {}).get("confidence") or {},
        "intelligence": (preflight or {}).get("intelligence") or {},
        "timeline": timeline or {},
        "output": output,
    }


def write_render_plan(export_dir: Path, plan: dict[str, Any]) -> None:
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "render_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
