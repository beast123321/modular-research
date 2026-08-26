"""Run deterministic intelligence over one Phase 3 Evidence Store."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from evidence_store import EvidenceStore
from analysis.findings import build_observations
from analysis.metrics import compute_rates, compute_velocity
from analysis.ranking import build_creator_baselines, build_video_rankings
from analysis.voc import classify_comment, comment_weight, load_taxonomy, summarize_voc


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _stable_finding_id(run_id: str, finding: dict[str, Any], index: int) -> str:
    raw = json.dumps([run_id, index, finding.get("category"), finding.get("metrics")], sort_keys=True, ensure_ascii=False)
    return "obs_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _video_records(store: EvidenceStore, run_id: str) -> list[dict[str, Any]]:
    conn = store.conn
    latest_rows = conn.execute(
        """SELECT v.video_id,v.creator_id,v.create_time,v.raw_evidence_id AS video_raw,
                  c.followers AS creator_followers,
                  s.views,s.likes,s.comments,s.shares,s.favorites,s.author_followers,s.captured_at,s.raw_evidence_id AS snapshot_raw
           FROM videos v
           JOIN video_snapshots s ON s.id=(
               SELECT s2.id FROM video_snapshots s2
               WHERE s2.run_id=? AND s2.video_id=v.video_id
               ORDER BY s2.captured_at DESC, s2.id DESC LIMIT 1
           )
           LEFT JOIN creators c ON c.creator_id=v.creator_id
           ORDER BY v.video_id""",
        (run_id,),
    ).fetchall()
    cols = [d[0] for d in conn.execute("SELECT v.video_id,v.creator_id,v.create_time,v.raw_evidence_id AS video_raw,c.followers AS creator_followers,s.views,s.likes,s.comments,s.shares,s.favorites,s.author_followers,s.captured_at,s.raw_evidence_id AS snapshot_raw FROM videos v JOIN video_snapshots s ON 1=0 LEFT JOIN creators c ON 1=0").description]

    all_snapshots: dict[str, list[dict[str, Any]]] = {}
    for row in conn.execute(
        "SELECT video_id,views,likes,comments,shares,favorites,author_followers,captured_at,raw_evidence_id FROM video_snapshots WHERE run_id=? ORDER BY captured_at,id",
        (run_id,),
    ):
        item = dict(zip(["video_id","views","likes","comments","shares","favorites","author_followers","captured_at","raw_evidence_id"], row))
        all_snapshots.setdefault(str(item["video_id"]), []).append(item)

    discoveries: dict[str, dict[str, list[str]]] = {}
    for video_id, query_text, raw_id in conn.execute(
        "SELECT video_id,query_text,raw_evidence_id FROM discoveries WHERE run_id=? ORDER BY discovered_at",
        (run_id,),
    ):
        entry = discoveries.setdefault(str(video_id), {"keywords": [], "refs": []})
        if query_text and query_text not in entry["keywords"]:
            entry["keywords"].append(str(query_text))
        if raw_id and raw_id not in entry["refs"]:
            entry["refs"].append(str(raw_id))

    records: list[dict[str, Any]] = []
    for raw in latest_rows:
        row = dict(zip(cols, raw))
        video_id = str(row["video_id"])
        snapshots = all_snapshots.get(video_id, [])
        followers = row.get("author_followers") if row.get("author_followers") is not None else row.get("creator_followers")
        snapshot = {
            "views": row.get("views"), "likes": row.get("likes"), "comments": row.get("comments"),
            "shares": row.get("shares"), "favorites": row.get("favorites"), "author_followers": followers,
        }
        refs = []
        for ref in [row.get("video_raw"), row.get("snapshot_raw"), *[s.get("raw_evidence_id") for s in snapshots], *discoveries.get(video_id, {}).get("refs", [])]:
            if ref and ref not in refs:
                refs.append(str(ref))
        records.append({
            "video_id": video_id,
            "creator_id": row.get("creator_id"),
            "create_time": row.get("create_time"),
            "captured_at": row.get("captured_at"),
            "views": row.get("views"),
            "likes": row.get("likes"),
            "comments": row.get("comments"),
            "shares": row.get("shares"),
            "favorites": row.get("favorites"),
            "author_followers": followers,
            "keywords": discoveries.get(video_id, {}).get("keywords", []),
            "evidence_refs": refs,
            **compute_rates(snapshot),
            **compute_velocity(snapshots),
        })
    return records


def _comment_records(store: EvidenceStore, run_id: str) -> list[dict[str, Any]]:
    taxonomy = load_taxonomy()
    rows: list[dict[str, Any]] = []
    for comment_id, text, like_count, raw_id in store.conn.execute(
        """SELECT c.comment_id,c.text,c.like_count,c.raw_evidence_id
           FROM comments c JOIN raw_evidence r ON r.id=c.raw_evidence_id
           WHERE r.run_id=? ORDER BY c.comment_id""",
        (run_id,),
    ):
        classified = classify_comment(str(text), taxonomy)
        rows.append({
            "comment_id": str(comment_id),
            "text": str(text),
            "like_count": like_count,
            "evidence_refs": [str(raw_id)] if raw_id else [],
            "weighted_intensity": comment_weight(like_count),
            **classified,
        })
    return rows


def run_deterministic_intelligence(db_path: str | Path, reports_dir: str | Path, run_id: str) -> dict[str, Any]:
    store = EvidenceStore(db_path)
    try:
        base_records = _video_records(store, run_id)
        ranked = build_video_rankings(base_records)
        creators = list(build_creator_baselines(ranked).values())
        comments = _comment_records(store, run_id)
        voc = summarize_voc(comments)
        observations = build_observations(ranked, voc)
        for index, finding in enumerate(observations, 1):
            finding["id"] = _stable_finding_id(run_id, finding, index)
        store.replace_intelligence(
            run_id=run_id, video_rows=ranked, creator_rows=creators,
            comment_rows=comments, findings=observations,
        )
        metrics_fields = [
            "video_id", "views", "likes", "comments", "shares", "favorites", "author_followers",
            "engagement_rate", "like_rate", "comment_rate", "share_rate", "save_rate", "follower_leverage",
            "view_velocity_per_hour", "like_velocity_per_hour", "comment_velocity_per_hour", "evidence_refs",
        ]
        metrics = [{key: row.get(key) for key in metrics_fields} for row in ranked]
        report_dir = Path(reports_dir)
        _write_json(report_dir / "metrics.json", metrics)
        _write_json(report_dir / "rankings.json", ranked)
        _write_json(report_dir / "voc.json", {"summary": voc, "comments": comments})
        _write_json(report_dir / "findings.json", observations)
        summary = {
            "run_id": run_id,
            "video_count": len(ranked),
            "creator_baseline_count": len(creators),
            "comment_count": len(comments),
            "finding_count": len(observations),
            "finding_types": sorted(set(row["finding_type"] for row in observations)),
            "analysis_mode": "deterministic",
            "insights_generated": 0,
            "hypotheses_generated": 0,
        }
        _write_json(report_dir / "deterministic_summary.json", summary)
        return summary
    finally:
        store.close()
