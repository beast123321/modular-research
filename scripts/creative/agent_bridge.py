"""Provider-neutral bridge between prepared media evidence and a host multimodal agent."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from creative.contracts import SCHEMA_PATH, load_taxonomy, validate_analysis_response


def build_analysis_request(*, video: dict[str, Any], asset: dict[str, Any] | None, keyframes: list[dict[str, Any]], transcript: list[dict[str, Any]]) -> dict[str, Any]:
    video_id = str(video.get("video_id") or "").strip()
    if not video_id:
        raise ValueError("video.video_id is required")
    return {
        "request_version": "1.0",
        "video_id": video_id,
        "task": "Describe only observable creative structure from the supplied video/frame/text evidence. Use UNKNOWN/null when evidence is insufficient.",
        "video": {
            "caption": video.get("caption"),
            "duration_sec": video.get("duration_sec"),
            "video_url": video.get("video_url"),
        },
        "asset": asset,
        "keyframes": keyframes,
        "transcript": transcript,
        "controlled_taxonomy": load_taxonomy(),
        "required_output_schema": str(SCHEMA_PATH),
        "rules": [
            "Do not infer sales, conversion, market demand, or causality from visual content.",
            "Every timeline event should cite frame/transcript evidence when available.",
            "Use UNKNOWN or null rather than inventing unobserved properties.",
        ],
    }


def write_analysis_request(path: str | Path, payload: dict[str, Any]) -> None:
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def import_analysis_response(path: str | Path, store, run_id: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    valid = validate_analysis_response(payload)
    store.upsert_creative_analysis(run_id, valid)
    return valid
