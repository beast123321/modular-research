"""Configurable deterministic Voice-of-Customer classification."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TAXONOMY = ROOT / "references" / "taxonomies" / "voc-general-v1.json"


def load_taxonomy(path: str | Path | None = None) -> dict[str, Any]:
    return json.loads(Path(path or DEFAULT_TAXONOMY).read_text(encoding="utf-8"))


def classify_comment(text: str, taxonomy: dict[str, Any]) -> dict[str, Any]:
    raw = str(text or ""); lowered = raw.casefold(); labels: list[str] = []; matches: dict[str, list[str]] = {}
    for label, terms in (taxonomy.get("labels") or {}).items():
        found = [str(term) for term in terms if str(term).casefold() and str(term).casefold() in lowered]
        if found:
            labels.append(str(label)); matches[str(label)] = list(dict.fromkeys(found))
    return {"labels": labels, "matched_terms": matches, "classifier_version": str(taxonomy.get("version") or "unknown")}


def comment_weight(like_count: Any) -> float:
    try: likes = max(0.0, float(like_count or 0))
    except (TypeError, ValueError): likes = 0.0
    return 1.0 + math.log1p(likes)


def summarize_voc(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sample_size = len(rows); summary: dict[str, dict[str, Any]] = {}
    for row in rows:
        weight = comment_weight(row.get("like_count"))
        for label in row.get("labels") or []:
            rec = summary.setdefault(str(label), {"count":0,"share":0.0,"weighted_intensity":0.0,"evidence_refs":[],"comment_ids":[]})
            rec["count"] += 1; rec["weighted_intensity"] += weight; rec["comment_ids"].append(str(row.get("comment_id")))
            for ref in row.get("evidence_refs") or []:
                if ref and ref not in rec["evidence_refs"]: rec["evidence_refs"].append(ref)
    for rec in summary.values():
        rec["share"] = rec["count"] / sample_size if sample_size else 0.0; rec["weighted_intensity"] = round(rec["weighted_intensity"], 6)
    return {"sample_size": sample_size, "labels": dict(sorted(summary.items(), key=lambda item: (-item[1]["weighted_intensity"], item[0])))}
