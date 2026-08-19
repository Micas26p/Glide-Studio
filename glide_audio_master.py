from __future__ import annotations

import json
import re
from typing import Any


MASTER_PROFILES = {
    "youtube_long": {
        "label": "YouTube longo",
        "target_i": -14.0,
        "target_tp": -1.0,
        "target_lra": 9.0,
        "standard": "YouTube",
    },
    "shorts": {
        "label": "Shorts",
        "target_i": -13.0,
        "target_tp": -1.0,
        "target_lra": 7.0,
        "standard": "Shorts",
    },
    "documentary": {
        "label": "Documentario",
        "target_i": -16.0,
        "target_tp": -1.2,
        "target_lra": 11.0,
        "standard": "Documentario",
    },
    "clean_voice": {
        "label": "Narracao limpa",
        "target_i": -15.0,
        "target_tp": -1.0,
        "target_lra": 8.0,
        "standard": "Narracao limpa",
    },
}


def profile_settings(profile: str | None = None) -> dict[str, Any]:
    key = str(profile or "youtube_long").strip().lower()
    if key not in MASTER_PROFILES:
        key = "youtube_long"
    settings = dict(MASTER_PROFILES[key])
    settings["key"] = key
    return settings


def first_pass_filter(profile: str | None = None) -> str:
    settings = profile_settings(profile)
    return (
        f"loudnorm=I={settings['target_i']}:TP={settings['target_tp']}:"
        f"LRA={settings['target_lra']}:print_format=json"
    )


def parse_loudnorm_output(text: str) -> dict[str, Any]:
    candidates = re.findall(r"\{[\s\S]*?\}", text or "")
    for candidate in reversed(candidates):
        try:
            payload = json.loads(candidate)
        except Exception:
            continue
        if "input_i" in payload:
            return payload
    return {}


def second_pass_filter(measurement: dict[str, Any], profile: str | None = None) -> str:
    settings = profile_settings(profile)
    required = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
    if not all(key in measurement for key in required):
        return first_pass_filter(settings["key"]) + ":linear=true"
    return (
        f"loudnorm=I={settings['target_i']}:TP={settings['target_tp']}:LRA={settings['target_lra']}:"
        f"measured_I={measurement['input_i']}:"
        f"measured_TP={measurement['input_tp']}:"
        f"measured_LRA={measurement['input_lra']}:"
        f"measured_thresh={measurement['input_thresh']}:"
        f"offset={measurement['target_offset']}:"
        "linear=true:print_format=json"
    )


def limiter_value(profile: str | None = None) -> float:
    settings = profile_settings(profile)
    try:
        return round(10 ** (float(settings["target_tp"]) / 20.0), 4)
    except Exception:
        return 0.891


def summary(measurement: dict[str, Any], output_measurement: dict[str, Any] | None = None, profile: str | None = None) -> dict[str, Any]:
    settings = profile_settings(profile)
    output = output_measurement or {}
    return {
        "enabled": True,
        "profile": settings["key"],
        "profile_label": settings["label"],
        "target_lufs": settings["target_i"],
        "target_true_peak_dbtp": settings["target_tp"],
        "target_lra": settings["target_lra"],
        "input_lufs": _number(measurement.get("input_i")),
        "input_true_peak_dbtp": _number(measurement.get("input_tp")),
        "input_lra": _number(measurement.get("input_lra")),
        "output_lufs": _number(output.get("output_i"), settings["target_i"]),
        "output_true_peak_dbtp": _number(output.get("output_tp"), settings["target_tp"]),
        "output_lra": _number(output.get("output_lra"), settings["target_lra"]),
        "standard": settings["standard"],
        "passes": 2,
    }


def _number(value: Any, fallback: float | None = None) -> float | None:
    try:
        return round(float(value), 2)
    except Exception:
        return fallback
