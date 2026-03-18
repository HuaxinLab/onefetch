from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _builtin_preset_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "plugin_presets"


def _local_preset_dir() -> Path:
    custom = os.getenv("ONEFETCH_PLUGIN_PRESET_DIR", "").strip()
    if custom:
        return Path(custom).expanduser()

    project_root = os.getenv("ONEFETCH_PROJECT_ROOT", "").strip()
    root = Path(project_root).expanduser() if project_root else Path.cwd()
    return root / ".secrets" / "plugin_presets"


def _preset_candidates(name: str) -> list[Path]:
    filename = f"{name}.json"
    return [
        _local_preset_dir() / filename,
        _builtin_preset_dir() / filename,
    ]


def load_preset(name: str, *, plugin_id: str) -> dict[str, Any]:
    preset_path = next((path for path in _preset_candidates(name) if path.exists()), None)
    if preset_path is None:
        raise ValueError(f"preset not found: {name}")

    payload = json.loads(preset_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid preset format: {name}")

    expected_plugin = str(payload.get("plugin_id", "")).strip()
    if expected_plugin and expected_plugin != plugin_id:
        raise ValueError(
            f"preset '{name}' is for plugin '{expected_plugin}', not '{plugin_id}'"
        )

    options = payload.get("options", {})
    if not isinstance(options, dict):
        raise ValueError(f"invalid preset options: {name}")
    return options
