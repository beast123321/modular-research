"""Deterministic mapping from ResearchRequest semantics to a research profile."""

from __future__ import annotations

from dataclasses import dataclass, field

from profile_loader import load_profiles
from research_request import ResearchRequest


@dataclass
class ProfileResolution:
    profile_id: str
    reason_codes: list[str]
    confidence: float
    warnings: list[str] = field(default_factory=list)


def resolve_profile(
    request: ResearchRequest,
    profiles: dict[str, dict] | None = None,
) -> ProfileResolution:
    available = profiles if profiles is not None else load_profiles()
    candidates: list[tuple[int, str, list[str]]] = []

    for profile_id, profile in available.items():
        if str(profile.get("platform", "")).lower() != request.platform:
            continue
        supported = set(profile.get("supported_goals") or [])
        matched = [goal for goal in request.research_goals if goal in supported]
        if not matched:
            continue
        reasons = [f"PLATFORM_{request.platform.upper()}"]
        reasons.extend(f"GOAL_{goal.upper()}" for goal in matched)
        candidates.append((len(matched), profile_id, reasons))

    if not candidates:
        raise ValueError(
            f"no compatible research profile for platform={request.platform} "
            f"goals={request.research_goals}"
        )

    candidates.sort(key=lambda row: (-row[0], row[1]))
    best_score, best_id, reasons = candidates[0]
    warnings: list[str] = []
    if len(candidates) > 1 and candidates[1][0] == best_score:
        warnings.append("multiple profiles matched equally; deterministic id order used")
        confidence = 0.8
    else:
        confidence = 0.98

    return ProfileResolution(
        profile_id=best_id,
        reason_codes=reasons,
        confidence=confidence,
        warnings=warnings,
    )
