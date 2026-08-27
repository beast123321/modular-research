#!/usr/bin/env python3
"""Deterministic, offline run fixture for Research Workbench tests."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "migrations"


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _apply_migrations(conn: sqlite3.Connection) -> None:
    for path in sorted(MIGRATIONS.glob("*.sql")):
        conn.executescript(path.read_text(encoding="utf-8"))


def build_fixture_run(root: Path, run_id: str = "run_fixture") -> Path:
    """Create one complete, synthetic v1.1.x-compatible run without network I/O."""
    root = Path(root)
    run_dir = root / run_id
    raw_dir = run_dir / "raw"
    reports_dir = run_dir / "reports"
    media_dir = run_dir / "media" / "video_fixture" / "frames"
    raw_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)

    request = {
        "topic": "fixture topic",
        "platform": "douyin",
        "market": "CN",
        "language": "zh",
        "research_goals": ["voc", "creative_patterns"],
        "depth": "standard",
    }
    stages = [
        {"name": "REFERENCE_SEED", "local_only": False, "tasks": []},
        {"name": "ORGANIC_DISCOVERY", "local_only": False, "tasks": []},
        {"name": "CHEAP_RANKING", "local_only": True, "tasks": []},
        {"name": "VOC", "local_only": True, "tasks": []},
        {"name": "VIDEO_UNDERSTANDING", "local_only": True, "tasks": []},
        {"name": "PATTERN_MINING", "local_only": True, "tasks": []},
        {"name": "FINDINGS", "local_only": True, "tasks": []},
        {"name": "HYPOTHESES", "local_only": True, "tasks": []},
        {"name": "BRIEFS", "local_only": True, "tasks": []},
    ]
    _write_json(
        run_dir / "plan.json",
        {
            "request": request,
            "profile_id": "douyin-video-intelligence-v1",
            "provider": "tikhub",
            "stages": stages,
            "expected_requests": 2,
            "max_requests": 4,
            "expected_cost_usd": 0.002,
            "max_cost_usd": 0.004,
        },
    )
    _write_json(
        run_dir / "execution.json",
        {
            "status": "completed",
            "run_id": run_id,
            "calls_attempted": 2,
            "calls_succeeded": 2,
            "calls_failed": 0,
            "stages": [
                {"stage": "REFERENCE_SEED", "status": "completed", "calls_attempted": 1, "calls_succeeded": 1, "calls_failed": 0},
                {"stage": "ORGANIC_DISCOVERY", "status": "completed", "calls_attempted": 1, "calls_succeeded": 1, "calls_failed": 0},
                {"stage": "CHEAP_RANKING", "status": "completed_local", "calls_attempted": 0, "calls_succeeded": 0, "calls_failed": 0},
                {"stage": "VOC", "status": "completed_local", "calls_attempted": 0, "calls_succeeded": 0, "calls_failed": 0},
                {"stage": "VIDEO_UNDERSTANDING", "status": "prepared_local", "calls_attempted": 0, "calls_succeeded": 0, "calls_failed": 0},
                {"stage": "PATTERN_MINING", "status": "completed_local", "calls_attempted": 0, "calls_succeeded": 0, "calls_failed": 0},
                {"stage": "FINDINGS", "status": "completed_local", "calls_attempted": 0, "calls_succeeded": 0, "calls_failed": 0},
                {"stage": "HYPOTHESES", "status": "awaiting_host_agent", "calls_attempted": 0, "calls_succeeded": 0, "calls_failed": 0},
                {"stage": "BRIEFS", "status": "awaiting_host_agent", "calls_attempted": 0, "calls_succeeded": 0, "calls_failed": 0},
            ],
            "output_dir": str(run_dir),
        },
    )

    raw_payload = {
        "raw_evidence_id": "raw:fixture:0001",
        "stage": "REFERENCE_SEED",
        "capability": "video_detail_v3",
        "request": {"aweme_id": "video_fixture", "api_key": "fixture-api-key-must-redact"},
        "response": {
            "Authorization": "Bearer fixture-secret-must-redact",
            "data": {"aweme_detail": {"aweme_id": "video_fixture", "desc": "fixture video"}},
        },
    }
    _write_json(raw_dir / "0001_reference_seed_video_detail_v3.json", raw_payload)

    db_path = run_dir / "run.sqlite"
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    try:
        _apply_migrations(conn)
        now = "2026-08-27T00:00:00+00:00"
        conn.execute(
            "INSERT INTO research_runs(id,request_json,profile_id,provider,status,started_at,completed_at) VALUES(?,?,?,?,?,?,?)",
            (run_id, json.dumps(request), "douyin-video-intelligence-v1", "tikhub", "completed", now, now),
        )
        conn.execute(
            "INSERT INTO raw_evidence(id,run_id,endpoint,method,request_json,response_json,source_type,source_key,fetched_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                "raw:fixture:0001",
                run_id,
                "/api/v1/douyin/app/v3/fetch_one_video_v3",
                "GET",
                json.dumps(raw_payload["request"]),
                json.dumps(raw_payload["response"]),
                "video_detail_v3",
                "video_fixture",
                now,
            ),
        )
        conn.execute(
            "INSERT INTO creators(creator_id,sec_user_id,unique_id,nickname,bio,region,verified,followers,following,total_likes,video_count,last_seen_at,raw_evidence_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("creator_fixture", "sec_fixture", "fixture_user", "Fixture Creator", "fixture bio", "CN", 0, 1234, 100, 8888, 12, now, "raw:fixture:0001"),
        )
        conn.execute(
            "INSERT INTO videos(video_id,creator_id,caption,create_time,duration_sec,region,cover_url,video_url,music_id,music_title,hashtags_json,first_seen_at,last_seen_at,raw_evidence_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("video_fixture", "creator_fixture", "fixture video caption", now, 24.0, "CN", "https://example.invalid/cover.jpg", "https://example.invalid/video.mp4", "music_fixture", "Fixture Music", json.dumps(["职场", "真实"]), now, now, "raw:fixture:0001"),
        )
        conn.execute(
            "INSERT INTO video_snapshots(run_id,video_id,views,likes,comments,shares,favorites,author_followers,captured_at,raw_evidence_id) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (run_id, "video_fixture", 10000, 600, 50, 20, 30, 1234, now, "raw:fixture:0001"),
        )
        conn.execute(
            "INSERT INTO discoveries(id,run_id,video_id,source_type,query_text,source_rank,sort_type,time_window,discovered_at,raw_evidence_id) VALUES(?,?,?,?,?,?,?,?,?,?)",
            ("discovery_fixture", run_id, "video_fixture", "search", "fixture topic", 1, "0", "180", now, "raw:fixture:0001"),
        )
        conn.execute(
            "INSERT INTO comments(comment_id,video_id,author_id,text,like_count,reply_count,language,created_at,raw_evidence_id) VALUES(?,?,?,?,?,?,?,?,?)",
            ("comment_fixture", "video_fixture", "viewer_fixture", "这个场景太真实了，应该怎么回？", 12, 1, "zh", now, "raw:fixture:0001"),
        )
        conn.execute(
            "INSERT INTO video_metrics_derived(run_id,video_id,engagement_rate,like_rate,comment_rate,share_rate,save_rate,follower_leverage,views_percentile,engagement_percentile,share_rate_percentile,follower_leverage_percentile,creator_overperformance,creator_baseline_views,creator_baseline_sample,cohort_json,evidence_refs_json,computed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, "video_fixture", 0.067, 0.06, 0.005, 0.002, 0.003, 8.1037, 1.0, 1.0, 1.0, 1.0, 2.0, 5000.0, 3, json.dumps({"platform": "douyin"}), json.dumps(["raw:fixture:0001"]), now),
        )
        conn.execute(
            "INSERT INTO creator_metrics_derived(run_id,creator_id,baseline_views,sample_size,median_engagement_rate,evidence_refs_json,computed_at) VALUES(?,?,?,?,?,?,?)",
            (run_id, "creator_fixture", 5000.0, 3, 0.05, json.dumps(["raw:fixture:0001"]), now),
        )
        conn.execute(
            "INSERT INTO comment_labels(run_id,comment_id,labels_json,matched_terms_json,weighted_intensity,classifier_version,evidence_refs_json,computed_at) VALUES(?,?,?,?,?,?,?,?)",
            (run_id, "comment_fixture", json.dumps(["authenticity", "question"]), json.dumps(["真实", "怎么"]), 1.0, "fixture-v1", json.dumps(["raw:fixture:0001"]), now),
        )
        conn.execute(
            "INSERT INTO findings(id,run_id,finding_type,category,statement,evidence_refs_json,metrics_json,support_count,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            ("finding_fixture", run_id, "OBSERVATION", "engagement", "Fixture video is the top engagement sample.", json.dumps(["raw:fixture:0001"]), json.dumps({"engagement_rate": 0.067}), 1, now),
        )
        conn.execute(
            "INSERT INTO media_assets(run_id,video_id,source_url,local_path,sha256,byte_size,duration_sec,width,height,fps,status,error,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, "video_fixture", "https://example.invalid/video.mp4", None, None, None, 24.0, 1080, 1920, 30.0, "not_downloaded", "fixture media intentionally unavailable", now),
        )
        frame_path = media_dir / "frame_000.jpg"
        frame_path.write_bytes(b"fixture-keyframe")
        conn.execute(
            "INSERT INTO media_keyframes(id,run_id,video_id,timestamp_sec,local_path,scene_index,ocr_text,ocr_confidence,evidence_refs_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            ("frame:video_fixture:000", run_id, "video_fixture", 0.0, str(frame_path), 0, "领导说方案不行", 0.9, json.dumps(["frame:video_fixture:000"]), now),
        )
        conn.execute(
            "INSERT INTO transcript_segments(id,run_id,video_id,start_sec,end_sec,text,source,confidence,evidence_refs_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            ("transcript:video_fixture:000", run_id, "video_fixture", 0.0, 3.0, "领导说方案不行", "sidecar_txt", None, json.dumps(["transcript:video_fixture:000"]), now),
        )
        conn.execute(
            "INSERT INTO creative_analysis(run_id,video_id,schema_version,analyzer_name,analyzer_version,analyzer_mode,hook_type,hook_text,product_visible_at,format,selling_angle,proof_type,cta_text,cta_at,shot_count,avg_shot_length,visual_style,timeline_json,confidence_json,evidence_refs_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, "video_fixture", "1.0", "fixture-agent", "1", "multimodal", None, "fixture hook", None, None, None, None, "comment", 20.0, 4, 6.0, "talking_head", json.dumps([]), json.dumps({"hook": 0.8}), json.dumps(["frame:video_fixture:000", "raw:fixture:0001"]), now),
        )
        conn.execute(
            "INSERT INTO creative_patterns(id,run_id,performance_metric,pattern_field,pattern_value,top_cohort_size,baseline_size,top_support,baseline_support,top_share,baseline_share,lift,creator_support,organic_support,ad_support,evidence_refs_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("pattern_fixture", run_id, "engagement_rate", "hook_type", "scenario", 1, 1, 1, 1, 1.0, 1.0, 1.0, 1, 1, 0, json.dumps(["raw:fixture:0001"]), now),
        )
        conn.execute(
            "INSERT INTO insights(id,run_id,statement,evidence_refs_json,confidence,analyzer_name,analyzer_version,analyzer_mode,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            ("insight_fixture", run_id, "Scenario-specific language may improve perceived usefulness.", json.dumps(["raw:fixture:0001"]), 0.7, "fixture-agent", "1", "semantic", now),
        )
        conn.execute(
            "INSERT INTO creative_hypotheses(id,run_id,statement,objective,hook_type,format,selling_angle,proof_type,evidence_refs_json,confidence,status,analyzer_name,analyzer_version,analyzer_mode,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("hypothesis_fixture", run_id, "Test a concrete workplace scenario hook.", "engagement", None, None, None, None, json.dumps(["raw:fixture:0001"]), 0.6, "PROPOSED", "fixture-agent", "1", "semantic", now),
        )
        conn.execute(
            "INSERT INTO media_briefs(id,run_id,hypothesis_id,objective,target_audience,duration_target_sec,timeline_json,cta,evidence_refs_json,confidence,analyzer_name,analyzer_version,analyzer_mode,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("brief_fixture", run_id, "hypothesis_fixture", "engagement", "职场新人", 30.0, json.dumps([{"start": 0, "end": 3, "purpose": "hook"}]), "评论你的场景", json.dumps(["raw:fixture:0001"]), 0.6, "fixture-agent", "1", "semantic", now),
        )
        conn.commit()
    finally:
        conn.close()

    _write_json(reports_dir / "metrics.json", {"video_count": 1, "creator_count": 1, "comment_count": 1})
    _write_json(reports_dir / "rankings.json", [{"video_id": "video_fixture", "engagement_rate": 0.067, "rank": 1}])
    _write_json(reports_dir / "voc.json", {"denominator": 1, "labels": [{"label": "authenticity", "count": 1, "share": 1.0}]})
    _write_json(reports_dir / "findings.json", [{"id": "finding_fixture", "statement": "Fixture video is the top engagement sample.", "evidence_refs": ["raw:fixture:0001"]}])
    _write_json(reports_dir / "pattern_report.json", {"patterns": [{"id": "pattern_fixture", "evidence_refs": ["raw:fixture:0001"]}]})
    _write_json(reports_dir / "synthesis_request.json", {"run_id": run_id, "pattern_ids": ["pattern_fixture"]})
    (reports_dir / "final_report.md").write_text("# Fixture Research Report\n\nEvidence-backed fixture report.\n", encoding="utf-8")
    return run_dir


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        print(build_fixture_run(Path(td)))
