"""Canonical runtime research request model for modular-research.

This module deliberately uses only the Python standard library so the skill
remains portable across agent runtimes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

ALLOWED_DEPTHS = {"quick", "standard", "deep"}
ALLOWED_GOALS = {
    "trend_discovery", "content_opportunities", "low_follower_breakouts", "creative_patterns",
    "hooks", "selling_angles", "formats", "creator_analysis", "ads_analysis", "retention_analysis",
    "voc", "purchase_objections", "competitor_analysis", "product_validation",
}


def normalize_platform(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("platform is required")
    return value.strip().lower()


def _dedupe_strings(values: list[str] | tuple[str, ...] | None) -> list[str]:
    out: list[str] = []; seen: set[str] = set()
    for raw in values or []:
        value = str(raw).strip()
        if value and value not in seen:
            seen.add(value); out.append(value)
    return out


@dataclass
class ResearchRequest:
    topic: str
    platform: str
    research_goals: list[str]
    market: str | None = None
    language: str | None = None
    schema_version: str = "1.0"
    time_range: dict[str, Any] = field(default_factory=dict)
    content_scope: dict[str, Any] = field(default_factory=dict)
    audience: str | None = None
    seed_keywords: list[str] = field(default_factory=list)
    competitors: list[str] = field(default_factory=list)
    brands: list[str] = field(default_factory=list)
    video_filters: dict[str, Any] = field(default_factory=dict)
    sample_size_overrides: dict[str, Any] = field(default_factory=dict)
    output_preferences: dict[str, Any] = field(default_factory=dict)
    depth: str = "standard"
    outputs: list[str] = field(default_factory=lambda: ["evidence", "findings"])
    user_goal_text: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchRequest":
        if not isinstance(data, dict):
            raise ValueError("research request must be an object")
        topic = str(data.get("topic") or "").strip()
        if not topic:
            raise ValueError("topic is required")
        platform = normalize_platform(data.get("platform") or "")
        market_raw = data.get("market")
        market = str(market_raw).strip().upper() if market_raw not in (None, "") else None
        depth = str(data.get("depth") or "standard").strip().lower()
        if depth not in ALLOWED_DEPTHS:
            raise ValueError(f"depth must be one of {sorted(ALLOWED_DEPTHS)}")
        goals = _dedupe_strings(data.get("research_goals"))
        if not goals:
            raise ValueError("research_goals must contain at least one goal")
        unknown = [goal for goal in goals if goal not in ALLOWED_GOALS]
        if unknown:
            raise ValueError(f"research_goals contains unsupported values: {unknown}")
        return cls(
            schema_version=str(data.get("schema_version") or "1.0"), topic=topic, platform=platform, market=market,
            language=(str(data["language"]).strip().lower() if data.get("language") else None), research_goals=goals,
            time_range=dict(data.get("time_range") or {}), content_scope=dict(data.get("content_scope") or {}),
            audience=(str(data["audience"]).strip() if data.get("audience") else None), seed_keywords=_dedupe_strings(data.get("seed_keywords")),
            competitors=_dedupe_strings(data.get("competitors")), brands=_dedupe_strings(data.get("brands")),
            video_filters=dict(data.get("video_filters") or {}), sample_size_overrides=dict(data.get("sample_size_overrides") or {}),
            output_preferences=dict(data.get("output_preferences") or {}), depth=depth,
            outputs=_dedupe_strings(data.get("outputs")) or ["evidence", "findings"],
            user_goal_text=(str(data["user_goal_text"]).strip() if data.get("user_goal_text") else None),
        )

    def validate_material_fields(self) -> list[str]:
        missing: list[str] = []
        if not self.topic.strip(): missing.append("topic")
        if not self.platform.strip(): missing.append("platform")
        if not self.research_goals: missing.append("research_goals")
        market_sensitive_tiktok_goals = {
            "trend_discovery","content_opportunities","creative_patterns","hooks","selling_angles","formats",
            "creator_analysis","ads_analysis","retention_analysis","voc","purchase_objections","competitor_analysis","product_validation",
        }
        if self.platform == "tiktok" and any(goal in market_sensitive_tiktok_goals for goal in self.research_goals) and not self.market:
            missing.append("market")
        return missing

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
