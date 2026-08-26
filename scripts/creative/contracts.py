"""Creative analysis request/response contract validation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TAXONOMY_PATH = ROOT / "references" / "taxonomies" / "creative-v1.json"
SCHEMA_PATH = ROOT / "references" / "schemas" / "creative-analysis.schema.json"


def load_taxonomy() -> dict[str, Any]:
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))


def _number_or_none(value: Any, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number or null")
    if float(value) < 0:
        raise ValueError(f"{name} must be >= 0")
    return float(value)


def _validate_confidence(mapping: Any) -> dict[str, float]:
    if mapping is None:
        return {}
    if not isinstance(mapping, dict):
        raise ValueError("confidence must be an object")
    out: dict[str, float] = {}
    for key, value in mapping.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"confidence.{key} must be numeric")
        number = float(value)
        if not 0.0 <= number <= 1.0:
            raise ValueError(f"confidence.{key} must be between 0 and 1")
        out[str(key)] = number
    return out


def validate_analysis_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize one host/backend semantic analysis response."""
    if not isinstance(payload, dict):
        raise ValueError("analysis response must be an object")
    out = dict(payload)
    if str(out.get("schema_version")) != "1.0":
        raise ValueError("schema_version must be 1.0")
    if not str(out.get("video_id") or "").strip():
        raise ValueError("video_id is required")
    analyzer = out.get("analyzer")
    if not isinstance(analyzer, dict) or not str(analyzer.get("name") or "").strip() or not str(analyzer.get("mode") or "").strip():
        raise ValueError("analyzer.name and analyzer.mode are required")

    taxonomy = load_taxonomy()
    for field in ("hook_type", "format", "selling_angle", "proof_type"):
        value = out.get(field)
        if value is None:
            continue
        if value not in taxonomy[field]:
            raise ValueError(f"invalid {field}: {value}")
    out["product_visible_at"] = _number_or_none(out.get("product_visible_at"), "product_visible_at")
    out["cta_at"] = _number_or_none(out.get("cta_at"), "cta_at")
    if out.get("shot_count") is not None and (isinstance(out["shot_count"], bool) or not isinstance(out["shot_count"], int) or out["shot_count"] < 0):
        raise ValueError("shot_count must be a non-negative integer or null")
    out["avg_shot_length"] = _number_or_none(out.get("avg_shot_length"), "avg_shot_length")
    out["confidence"] = _validate_confidence(out.get("confidence"))

    timeline = out.get("timeline") or []
    if not isinstance(timeline, list):
        raise ValueError("timeline must be an array")
    normalized_timeline: list[dict[str, Any]] = []
    previous_end = -1.0
    for index, event in enumerate(timeline):
        if not isinstance(event, dict):
            raise ValueError(f"timeline[{index}] must be an object")
        start = _number_or_none(event.get("start_sec"), f"timeline[{index}].start_sec")
        end = _number_or_none(event.get("end_sec"), f"timeline[{index}].end_sec")
        if start is None or end is None or end < start:
            raise ValueError(f"timeline[{index}] has invalid time range")
        if start < previous_end:
            raise ValueError("timeline must be ordered and non-overlapping")
        event_type = event.get("event_type")
        if event_type not in taxonomy["event_type"]:
            raise ValueError(f"invalid timeline event_type: {event_type}")
        confidence = event.get("confidence")
        if confidence is not None:
            confidence = _validate_confidence({"value": confidence})["value"]
        refs = event.get("evidence_refs") or []
        if not isinstance(refs, list) or not all(isinstance(x, str) for x in refs):
            raise ValueError("timeline evidence_refs must be an array of strings")
        normalized = dict(event)
        normalized["start_sec"] = start
        normalized["end_sec"] = end
        normalized["confidence"] = confidence
        normalized["evidence_refs"] = refs
        normalized_timeline.append(normalized)
        previous_end = end
    out["timeline"] = normalized_timeline
    refs = out.get("evidence_refs") or []
    if not isinstance(refs, list) or not all(isinstance(x, str) for x in refs):
        raise ValueError("evidence_refs must be an array of strings")
    out["evidence_refs"] = list(dict.fromkeys(refs))
    return out
