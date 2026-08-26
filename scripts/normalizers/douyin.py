"""Douyin/TikHub response normalization for Video Intelligence V1.

The module emits the same evidence bundle contract as the TikTok normalizer.
It performs deterministic field extraction only; no observations, insights, or
hypotheses are generated here.
"""
from __future__ import annotations

from typing import Any

from normalizers.tiktok import normalize_capability as normalize_tiktok_shape


def _empty_bundle() -> dict[str, list[dict[str, Any]]]:
    return {
        "videos": [],
        "video_snapshots": [],
        "creators": [],
        "comments": [],
        "ads": [],
        "ad_timeseries": [],
        "search_insights": [],
        "discoveries": [],
    }


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _first(mapping: dict[str, Any] | None, *keys: str) -> Any:
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


def _as_text(value: Any) -> str | None:
    return None if value in (None, "") else str(value)


def _as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _normalize_profile(payload: Any, raw_evidence_id: str | None) -> dict[str, list[dict[str, Any]]]:
    out = _empty_bundle()
    seen: set[str] = set()
    for node in _walk(payload):
        if not isinstance(node, dict):
            continue
        uid = _as_text(_first(node, "uid", "user_id", "id"))
        sec = _as_text(_first(node, "sec_uid", "sec_user_id"))
        unique = _as_text(_first(node, "unique_id"))
        if not (uid or sec or unique):
            continue
        if not any(key in node for key in ("nickname", "signature", "follower_count", "aweme_count", "following_count")):
            continue
        creator_id = uid or sec or unique
        if creator_id in seen:
            continue
        seen.add(creator_id)
        out["creators"].append({
            "creator_id": creator_id,
            "sec_user_id": sec,
            "unique_id": unique,
            "nickname": _as_text(_first(node, "nickname", "nick_name")),
            "bio": _as_text(_first(node, "signature", "bio")),
            "region": _as_text(_first(node, "region", "ip_location")),
            "verified": 1 if bool(_first(node, "verified", "is_verified")) else 0,
            "followers": _as_int(_first(node, "follower_count", "followers")),
            "following": _as_int(_first(node, "following_count", "following")),
            "total_likes": _as_int(_first(node, "total_favorited", "favoriting_count", "total_likes")),
            "video_count": _as_int(_first(node, "aweme_count", "video_count")),
            "raw_evidence_id": raw_evidence_id,
        })
    return out


def _normalize_statistics(payload: Any, raw_evidence_id: str | None) -> dict[str, list[dict[str, Any]]]:
    out = _empty_bundle()
    seen: set[str] = set()
    for node in _walk(payload):
        if not isinstance(node, dict):
            continue
        video_id = _as_text(_first(node, "aweme_id", "item_id"))
        if not video_id or video_id in seen:
            continue
        stats = node.get("statistics") if isinstance(node.get("statistics"), dict) else node.get("stats") if isinstance(node.get("stats"), dict) else node
        if not isinstance(stats, dict):
            continue
        metrics = {
            "views": _as_int(_first(stats, "play_count", "view_count", "views")),
            "likes": _as_int(_first(stats, "digg_count", "like_count", "likes")),
            "comments": _as_int(_first(stats, "comment_count", "comments")),
            "shares": _as_int(_first(stats, "share_count", "shares")),
            "favorites": _as_int(_first(stats, "collect_count", "favorite_count", "favorites")),
            "author_followers": None,
        }
        if not any(value is not None for value in metrics.values()):
            continue
        seen.add(video_id)
        out["video_snapshots"].append({
            "video_id": video_id,
            **metrics,
            "raw_evidence_id": raw_evidence_id,
        })
    return out


def normalize_capability(
    capability: str,
    payload: Any,
    *,
    raw_evidence_id: str | None = None,
    request_payload: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    request = dict(request_payload or {})
    if capability == "video_statistics_v3":
        return _normalize_statistics(payload, raw_evidence_id)
    if capability == "user_profile_v3":
        return _normalize_profile(payload, raw_evidence_id)

    aliases = {
        "video_search": "video_search",
        "video_detail_v3": "video_detail",
        "video_detail_by_share_url_v3": "video_detail",
        "creator_posts_v3": "creator_posts",
        "video_comments_v3": "video_comments",
    }
    target = aliases.get(capability)
    if target:
        return normalize_tiktok_shape(
            target,
            payload,
            raw_evidence_id=raw_evidence_id,
            request_payload=request,
        )
    return _empty_bundle()
