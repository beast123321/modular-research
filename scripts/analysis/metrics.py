"""Transparent deterministic metrics for normalized video evidence."""
from __future__ import annotations

from datetime import datetime
from typing import Any


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ratio(numerator: Any, denominator: Any) -> float | None:
    num = _number(numerator)
    den = _number(denominator)
    if num is None or den is None or den <= 0:
        return None
    return num / den


def compute_rates(snapshot: dict[str, Any]) -> dict[str, float | None]:
    views = _number(snapshot.get("views"))
    likes = _number(snapshot.get("likes")) or 0.0
    comments = _number(snapshot.get("comments")) or 0.0
    shares = _number(snapshot.get("shares")) or 0.0
    engagement = None if views is None or views <= 0 else (likes + comments + shares) / views
    return {"engagement_rate": engagement, "like_rate": _ratio(snapshot.get("likes"), views), "comment_rate": _ratio(snapshot.get("comments"), views), "share_rate": _ratio(snapshot.get("shares"), views), "save_rate": _ratio(snapshot.get("favorites"), views), "follower_leverage": _ratio(views, snapshot.get("author_followers"))}


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def compute_velocity(snapshots: list[dict[str, Any]]) -> dict[str, float | None]:
    empty = {"view_velocity_per_hour": None, "like_velocity_per_hour": None, "comment_velocity_per_hour": None}
    usable = [(dt, row) for row in snapshots if (dt := _parse_dt(row.get("captured_at"))) is not None]
    if len(usable) < 2:
        return empty
    usable.sort(key=lambda x: x[0])
    first_dt, first = usable[0]; last_dt, last = usable[-1]
    elapsed_hours = (last_dt - first_dt).total_seconds() / 3600.0
    if elapsed_hours < 1.0:
        return empty
    def rate(key: str) -> float | None:
        a = _number(first.get(key)); b = _number(last.get(key))
        if a is None or b is None:
            return None
        return (b - a) / elapsed_hours
    return {"view_velocity_per_hour": rate("views"), "like_velocity_per_hour": rate("likes"), "comment_velocity_per_hour": rate("comments")}
