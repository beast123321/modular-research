"""Deterministic cohort ranking and creator-relative baselines."""
from __future__ import annotations

from datetime import datetime, timezone
from statistics import median
from typing import Any


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def percentile_rank(values: list[Any], value: Any) -> float | None:
    target = _num(value)
    usable = [x for raw in values if (x := _num(raw)) is not None]
    if target is None or not usable:
        return None
    return sum(1 for item in usable if item <= target) / len(usable)


def creator_size_bucket(followers: Any) -> str:
    value = _num(followers)
    if value is None or value < 0:
        return "unknown"
    if value < 10_000:
        return "micro_0_10k"
    if value < 50_000:
        return "small_10k_50k"
    if value < 250_000:
        return "mid_50k_250k"
    if value < 1_000_000:
        return "large_250k_1m"
    return "mega_1m_plus"


def _dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    try:
        if text.replace(".", "", 1).isdigit():
            return datetime.fromtimestamp(float(text), tz=timezone.utc)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


def video_age_bucket(create_time: Any, captured_at: Any) -> str | None:
    created = _dt(create_time)
    captured = _dt(captured_at)
    if created is None or captured is None:
        return None
    days = max(0.0, (captured - created).total_seconds() / 86400.0)
    if days <= 7:
        return "age_0_7d"
    if days <= 30:
        return "age_8_30d"
    if days <= 90:
        return "age_31_90d"
    if days <= 180:
        return "age_91_180d"
    return "age_180d_plus"


def build_creator_baselines(records: list[dict[str, Any]], min_samples: int = 3) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        creator_id = row.get("creator_id")
        if not creator_id or _num(row.get("views")) is None:
            continue
        groups.setdefault(str(creator_id), []).append(row)
    out: dict[str, dict[str, Any]] = {}
    for creator_id, rows in groups.items():
        views = [float(row["views"]) for row in rows if _num(row.get("views")) is not None]
        if len(views) < min_samples:
            continue
        engagements = [float(row["engagement_rate"]) for row in rows if _num(row.get("engagement_rate")) is not None]
        refs = list(dict.fromkeys(ref for row in rows for ref in row.get("evidence_refs", []) if ref))
        out[creator_id] = {
            "creator_id": creator_id,
            "baseline_views": float(median(views)),
            "sample_size": len(views),
            "median_engagement_rate": float(median(engagements)) if engagements else None,
            "evidence_refs": refs,
        }
    return out


def _cohort_keys(row: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    size = creator_size_bucket(row.get("author_followers"))
    keys.append(f"creator_size:{size}")
    age = video_age_bucket(row.get("create_time"), row.get("captured_at"))
    if age:
        keys.append(f"age:{age}")
    for keyword in row.get("keywords") or []:
        if str(keyword).strip():
            keys.append(f"keyword:{str(keyword).strip().casefold()}")
    return list(dict.fromkeys(keys))


def _metric_percentiles(rows: list[dict[str, Any]], row: dict[str, Any]) -> dict[str, Any]:
    metrics = {
        "views_percentile": "views",
        "engagement_percentile": "engagement_rate",
        "share_rate_percentile": "share_rate",
        "follower_leverage_percentile": "follower_leverage",
    }
    return {
        out_key: percentile_rank([x.get(source_key) for x in rows], row.get(source_key))
        for out_key, source_key in metrics.items()
    }


def build_video_rankings(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [dict(row) for row in records]
    baselines = build_creator_baselines(rows)
    cohort_members: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        for key in _cohort_keys(row):
            cohort_members.setdefault(key, []).append(row)

    for row in rows:
        row.update(_metric_percentiles(rows, row))
        creator_id = str(row.get("creator_id")) if row.get("creator_id") else None
        baseline = baselines.get(creator_id) if creator_id else None
        views = _num(row.get("views"))
        if baseline and views is not None and baseline["baseline_views"] > 0:
            row["creator_overperformance"] = views / baseline["baseline_views"]
            row["creator_baseline_views"] = baseline["baseline_views"]
            row["creator_baseline_sample"] = baseline["sample_size"]
        else:
            row["creator_overperformance"] = None
            row["creator_baseline_views"] = None
            row["creator_baseline_sample"] = 0 if not baseline else baseline["sample_size"]
        age = video_age_bucket(row.get("create_time"), row.get("captured_at"))
        row["cohorts"] = {
            "creator_size": creator_size_bucket(row.get("author_followers")),
            "age": age,
            "keywords": list(row.get("keywords") or []),
        }
        row["cohort_percentiles"] = {}
        for key in _cohort_keys(row):
            members = cohort_members[key]
            row["cohort_percentiles"][key] = {
                "support_count": len(members),
                **_metric_percentiles(members, row),
            }
    return rows
