"""Load reusable research profiles from references/profiles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROFILE_DIR = ROOT / "references" / "profiles"
_REQUIRED_KEYS = {
    "id", "version", "platform", "default_provider", "supported_goals",
    "required_capabilities", "default_content_scope", "depth_presets",
    "stages", "analysis_modules", "output_contracts",
}


def load_profiles(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    directory = Path(path) if path is not None else DEFAULT_PROFILE_DIR
    profiles: dict[str, dict[str, Any]] = {}
    if not directory.exists():
        return profiles

    for file_path in sorted(directory.glob("*.json")):
        data = json.loads(file_path.read_text(encoding="utf-8"))
        missing = sorted(_REQUIRED_KEYS - set(data))
        if missing:
            raise ValueError(f"profile {file_path.name} missing keys: {missing}")
        profile_id = str(data["id"])
        if profile_id in profiles:
            raise ValueError(f"duplicate profile id: {profile_id}")
        profiles[profile_id] = data
    return profiles
