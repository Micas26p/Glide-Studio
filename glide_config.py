from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def load_config_bundle(assets_root: Path, app_version: str) -> dict[str, Any]:
    config_root = assets_root / "config"
    return {
        "version": app_version,
        "export_presets": load_json(config_root / "export_presets.json", {}),
        "workflow_presets": load_json(config_root / "workflow_presets.json", {}),
        "sound_design": load_json(config_root / "sound_design.json", {}),
        "ui": load_json(config_root / "ui.json", {}),
    }
