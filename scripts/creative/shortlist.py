"""Transparent shortlist selection for expensive media analysis.

No composite/viral score is calculated. Candidates are selected round-robin
from auditable ranking dimensions so one metric cannot dominate the shortlist.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

_BUCKETS = [
    ("views_percentile", "top_views_percentile"),
    ("engagement_percentile", "top_engagement_percentile"),
    ("share_rate_percentile", "top_share_rate_percentile"),
    ("follower_leverage_percentile", "top_follower_leverage_percentile"),
    ("creator_overperformance", "top_creator_overperformance"),
]


def _rows(db_path: str | Path, run_id: str) -> list[dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT v.video_id,v.creator_id,v.caption,v.duration_sec,v.video_url,v.cover_url,v.raw_evidence_id,
                      m.views_percentile,m.engagement_percentile,m.share_rate_percentile,
                      m.follower_leverage_percentile,m.creator_overperformance,m.evidence_refs_json,
                      (SELECT s.views FROM video_snapshots s WHERE s.run_id=m.run_id AND s.video_id=v.video_id ORDER BY s.captured_at DESC,s.id DESC LIMIT 1) AS views,
                      (SELECT s.author_followers FROM video_snapshots s WHERE s.run_id=m.run_id AND s.video_id=v.video_id ORDER BY s.captured_at DESC,s.id DESC LIMIT 1) AS author_followers
               FROM video_metrics_derived m
               JOIN videos v ON v.video_id=m.video_id
               WHERE m.run_id=? AND v.video_url IS NOT NULL AND TRIM(v.video_url)<>''
               ORDER BY v.video_id""",
            (run_id,),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                refs = json.loads(item.pop("evidence_refs_json") or "[]")
            except json.JSONDecodeError:
                refs = []
            if item.get("raw_evidence_id") and item["raw_evidence_id"] not in refs:
                refs.append(item["raw_evidence_id"])
            item["evidence_refs"] = refs
            item["selection_reasons"] = []
            out.append(item)
        return out
    finally:
        conn.close()



def _matches_filters(row: dict[str, Any], video_filters: dict[str, Any] | None) -> bool:
    filters = video_filters or {}
    duration = filters.get("duration") if isinstance(filters.get("duration"), dict) else {}
    value = row.get("duration_sec")
    if duration.get("min") is not None and (value is None or float(value) < float(duration["min"])):
        return False
    if duration.get("max") is not None and (value is None or float(value) > float(duration["max"])):
        return False
    creator = filters.get("creator_size") if isinstance(filters.get("creator_size"), dict) else {}
    followers = row.get("author_followers")
    if creator.get("min_followers") is not None and (followers is None or int(followers) < int(creator["min_followers"])):
        return False
    if creator.get("max_followers") is not None and (followers is None or int(followers) > int(creator["max_followers"])):
        return False
    minimum_views = filters.get("minimum_views")
    if minimum_views is not None and (row.get("views") is None or int(row["views"]) < int(minimum_views)):
        return False
    return True


def select_creative_shortlist(db_path: str | Path, run_id: str, limit: int, *, video_filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Select at most ``limit`` videos with explainable round-robin ranking."""
    if limit <= 0:
        return []
    candidates = [row for row in _rows(db_path, run_id) if _matches_filters(row, video_filters)]
    if not candidates:
        return []

    by_id = {str(row["video_id"]): row for row in candidates}
    ordered_buckets: list[tuple[str, list[str]]] = []
    for field, reason in _BUCKETS:
        ranked = sorted(
            candidates,
            key=lambda r: (
                r.get(field) is not None,
                float(r.get(field)) if r.get(field) is not None else float("-inf"),
                str(r.get("video_id")),
            ),
            reverse=True,
        )
        ids = [str(r["video_id"]) for r in ranked if r.get(field) is not None]
        ordered_buckets.append((reason, ids))

    selected: list[str] = []
    seen: set[str] = set()
    while len(selected) < min(limit, len(candidates)):
        progressed = False
        for reason, ids in ordered_buckets:
            choice = next((vid for vid in ids if vid not in seen), None)
            if choice is None:
                continue
            seen.add(choice)
            selected.append(choice)
            by_id[choice]["selection_reasons"].append(reason)
            progressed = True
            if len(selected) >= min(limit, len(candidates)):
                break
        if not progressed:
            break
    for reason, ids in ordered_buckets:
        if not ids:
            continue
        top_value = by_id[ids[0]].get(next(field for field, r in _BUCKETS if r == reason))
        for vid in selected:
            field = next(field for field, r in _BUCKETS if r == reason)
            if by_id[vid].get(field) == top_value and reason not in by_id[vid]["selection_reasons"]:
                by_id[vid]["selection_reasons"].append(reason)
    return [by_id[vid] for vid in selected]
