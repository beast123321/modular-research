"""Deterministic creative pattern lift mining.

Pattern lift is association evidence only. It does not establish causality.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

PERFORMANCE_METRICS = (
    "engagement_percentile",
    "share_rate_percentile",
    "follower_leverage_percentile",
    "views_percentile",
)
PATTERN_FIELDS = ("hook_type", "format", "selling_angle", "proof_type")


def _stable_id(run_id: str, metric: str, field: str, value: str) -> str:
    raw = "\x1f".join([run_id, metric, field, value])
    return "pat_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _load_rows(db_path: str | Path, run_id: str) -> list[dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT ca.video_id,v.creator_id,ca.hook_type,ca.format,ca.selling_angle,ca.proof_type,
                      ca.evidence_refs_json AS creative_refs,
                      m.engagement_percentile,m.share_rate_percentile,m.follower_leverage_percentile,m.views_percentile,
                      m.evidence_refs_json AS metric_refs,
                      CASE WHEN EXISTS(SELECT 1 FROM ads a WHERE a.video_id=ca.video_id) THEN 1 ELSE 0 END AS has_ad
               FROM creative_analysis ca
               JOIN video_metrics_derived m ON m.run_id=ca.run_id AND m.video_id=ca.video_id
               LEFT JOIN videos v ON v.video_id=ca.video_id
               WHERE ca.run_id=?
               ORDER BY ca.video_id""",
            (run_id,),
        ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            refs: list[str] = []
            for key in ("creative_refs", "metric_refs"):
                try:
                    values = json.loads(item.pop(key) or "[]")
                except json.JSONDecodeError:
                    values = []
                for ref in values:
                    if isinstance(ref, str) and ref and ref not in refs:
                        refs.append(ref)
            item["evidence_refs"] = refs
            out.append(item)
        return out
    finally:
        conn.close()


def mine_patterns(
    db_path: str | Path,
    run_id: str,
    *,
    top_threshold: float = 0.75,
    min_baseline_size: int = 8,
    min_top_support: int = 2,
    min_creator_support: int = 2,
) -> list[dict[str, Any]]:
    rows = _load_rows(db_path, run_id)
    if len(rows) < min_baseline_size:
        return []
    patterns: list[dict[str, Any]] = []
    for metric in PERFORMANCE_METRICS:
        eligible = [r for r in rows if r.get(metric) is not None]
        if len(eligible) < min_baseline_size:
            continue
        top = [r for r in eligible if float(r[metric]) >= top_threshold]
        if len(top) < min_top_support:
            continue
        for field in PATTERN_FIELDS:
            values = sorted({str(r[field]) for r in eligible if r.get(field) not in (None, "", "UNKNOWN")})
            for value in values:
                top_rows = [r for r in top if r.get(field) == value]
                baseline_rows = [r for r in eligible if r.get(field) == value]
                top_support = len(top_rows)
                baseline_support = len(baseline_rows)
                creators = {str(r["creator_id"]) for r in top_rows if r.get("creator_id")}
                if top_support < min_top_support or len(creators) < min_creator_support:
                    continue
                top_share = top_support / len(top)
                baseline_share = baseline_support / len(eligible)
                lift = (top_share / baseline_share) if baseline_share > 0 else None
                refs: list[str] = []
                for row in top_rows:
                    for ref in row.get("evidence_refs") or []:
                        if ref not in refs:
                            refs.append(ref)
                pattern_id = _stable_id(run_id, metric, field, value)
                patterns.append({
                    "id": pattern_id,
                    "performance_metric": metric,
                    "pattern_field": field,
                    "pattern_value": value,
                    "top_cohort_size": len(top),
                    "baseline_size": len(eligible),
                    "top_support": top_support,
                    "baseline_support": baseline_support,
                    "top_share": top_share,
                    "baseline_share": baseline_share,
                    "lift": lift,
                    "creator_support": len(creators),
                    "organic_support": top_support,
                    "ad_support": sum(1 for r in top_rows if int(r.get("has_ad") or 0) == 1),
                    "evidence_refs": refs,
                })
    return sorted(
        patterns,
        key=lambda p: (
            p.get("lift") is not None,
            float(p.get("lift") or 0.0),
            p["creator_support"],
            p["top_support"],
            p["performance_metric"],
            p["pattern_field"],
            p["pattern_value"],
        ),
        reverse=True,
    )
