"""Build neutral, deterministic observations from derived evidence."""
from __future__ import annotations

from typing import Any


def build_observations(video_rows: list[dict[str, Any]], voc_summary: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    eligible = [row for row in video_rows if row.get("engagement_rate") is not None and row.get("evidence_refs")]
    if eligible:
        top = max(eligible, key=lambda row: float(row["engagement_rate"]))
        findings.append({
            "finding_type": "OBSERVATION",
            "category": "RUN_TOP_ENGAGEMENT",
            "statement": (f"Video {top.get('video_id')} has the highest engagement rate among {len(eligible)} videos with usable engagement evidence in this run."),
            "evidence_refs": list(dict.fromkeys(top.get("evidence_refs") or [])),
            "metrics": {"video_id": top.get("video_id"), "engagement_rate": top.get("engagement_rate"), "engagement_percentile": top.get("engagement_percentile")},
            "support_count": len(eligible),
        })

    for row in video_rows:
        ratio = row.get("creator_overperformance")
        refs = list(dict.fromkeys(row.get("evidence_refs") or []))
        if ratio is None or float(ratio) < 2.0 or not refs:
            continue
        findings.append({
            "finding_type": "OBSERVATION",
            "category": "CREATOR_OVERPERFORMANCE",
            "statement": (f"Video {row.get('video_id')} has {float(ratio):.2f}x the creator's median views within the {int(row.get('creator_baseline_sample') or 0)}-video baseline available in this run."),
            "evidence_refs": refs,
            "metrics": {"video_id": row.get("video_id"), "creator_overperformance": float(ratio), "creator_baseline_views": row.get("creator_baseline_views"), "creator_baseline_sample": row.get("creator_baseline_sample")},
            "support_count": int(row.get("creator_baseline_sample") or 1),
        })

    sample_size = int(voc_summary.get("sample_size") or 0)
    labels = voc_summary.get("labels") or {}
    for label, rec in list(labels.items())[:5]:
        refs = list(dict.fromkeys(rec.get("evidence_refs") or []))
        count = int(rec.get("count") or 0)
        if not refs or count <= 0:
            continue
        findings.append({
            "finding_type": "OBSERVATION",
            "category": "VOC_PREVALENCE",
            "statement": (f"VOC label {label} appears in {count} of {sample_size} sampled comments ({float(rec.get('share') or 0.0):.1%})."),
            "evidence_refs": refs,
            "metrics": {"label": label, "count": count, "sample_size": sample_size, "share": rec.get("share"), "weighted_intensity": rec.get("weighted_intensity")},
            "support_count": count,
        })
    return findings
