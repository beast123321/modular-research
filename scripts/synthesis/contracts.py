"""Validation for evidence-backed insight, hypothesis and media brief responses."""
from __future__ import annotations

from typing import Any
from creative.contracts import load_taxonomy


def _confidence(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path} must be numeric")
    value = float(value)
    if not 0 <= value <= 1:
        raise ValueError(f"{path} must be between 0 and 1")
    return value


def _refs(value: Any, path: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(x, str) and x.strip() for x in value):
        raise ValueError(f"{path} must be a non-empty array of strings")
    return list(dict.fromkeys(value))


def _analyzer(payload: dict[str, Any]) -> dict[str, Any]:
    analyzer = payload.get("analyzer")
    if not isinstance(analyzer, dict) or not str(analyzer.get("name") or "").strip() or not str(analyzer.get("mode") or "").strip():
        raise ValueError("analyzer.name and analyzer.mode are required")
    return dict(analyzer)


def validate_synthesis_response(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or str(payload.get("schema_version")) != "1.0":
        raise ValueError("schema_version must be 1.0")
    analyzer = _analyzer(payload)
    taxonomy = load_taxonomy()
    out = {"schema_version": "1.0", "analyzer": analyzer, "insights": [], "hypotheses": [], "media_briefs": []}
    for index, item in enumerate(payload.get("insights") or []):
        if not isinstance(item, dict) or not str(item.get("id") or "").strip() or not str(item.get("statement") or "").strip():
            raise ValueError(f"insights[{index}] requires id and statement")
        row = dict(item); row["evidence_refs"] = _refs(row.get("evidence_refs"), f"insights[{index}].evidence_refs"); row["confidence"] = _confidence(row.get("confidence"), f"insights[{index}].confidence"); out["insights"].append(row)
    for index, item in enumerate(payload.get("hypotheses") or []):
        if not isinstance(item, dict) or not str(item.get("id") or "").strip() or not str(item.get("statement") or "").strip() or not str(item.get("objective") or "").strip():
            raise ValueError(f"hypotheses[{index}] requires id, statement and objective")
        row = dict(item)
        for field in ("hook_type", "format", "selling_angle", "proof_type"):
            value = row.get(field)
            if value is not None and value not in taxonomy[field]:
                raise ValueError(f"invalid hypotheses[{index}].{field}: {value}")
        row["evidence_refs"] = _refs(row.get("evidence_refs"), f"hypotheses[{index}].evidence_refs"); row["confidence"] = _confidence(row.get("confidence"), f"hypotheses[{index}].confidence"); out["hypotheses"].append(row)
    hypothesis_ids = {str(h["id"]) for h in out["hypotheses"]}
    for index, item in enumerate(payload.get("media_briefs") or []):
        if not isinstance(item, dict) or not str(item.get("id") or "").strip() or not str(item.get("hypothesis_id") or "").strip() or not str(item.get("objective") or "").strip():
            raise ValueError(f"media_briefs[{index}] requires id, hypothesis_id and objective")
        row = dict(item)
        if hypothesis_ids and row["hypothesis_id"] not in hypothesis_ids:
            raise ValueError(f"media_briefs[{index}].hypothesis_id must reference a hypothesis in the same response")
        duration = row.get("duration_target_sec")
        if duration is not None and (isinstance(duration, bool) or not isinstance(duration, (int, float)) or float(duration) <= 0):
            raise ValueError(f"media_briefs[{index}].duration_target_sec must be > 0 or null")
        timeline = row.get("timeline") or []
        if not isinstance(timeline, list):
            raise ValueError(f"media_briefs[{index}].timeline must be an array")
        previous_end = -1.0; normalized = []
        for j, event in enumerate(timeline):
            if not isinstance(event, dict) or not str(event.get("event") or "").strip() or not str(event.get("instruction") or "").strip():
                raise ValueError(f"media_briefs[{index}].timeline[{j}] requires event and instruction")
            start = float(event.get("start_sec")); end = float(event.get("end_sec"))
            if start < 0 or end <= start or start < previous_end:
                raise ValueError(f"media_briefs[{index}].timeline must be ordered and non-overlapping")
            normalized.append({**event, "start_sec": start, "end_sec": end}); previous_end = end
        row["timeline"] = normalized; row["evidence_refs"] = _refs(row.get("evidence_refs"), f"media_briefs[{index}].evidence_refs"); row["confidence"] = _confidence(row.get("confidence"), f"media_briefs[{index}].confidence"); out["media_briefs"].append(row)
    return out
