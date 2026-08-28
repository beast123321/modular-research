"""Derive backwards-compatible run summaries from existing run artifacts."""
from __future__ import annotations

import json
from typing import Any

from .models import ArtifactAvailability, RunSummary
from .run_repository import RunRepository


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _number(mapping: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def build_run_summary(repo: RunRepository, run_id: str) -> RunSummary:
    run_dir = repo.run_dir(run_id)
    plan = _mapping(repo.load_json(run_id, "plan.json"))
    execution = _mapping(repo.load_json(run_id, "execution.json"))
    row = repo.research_run_row(run_id) or {}
    request = _mapping(plan.get("request"))
    if not request and row.get("request_json"):
        try:
            request = _mapping(json.loads(str(row["request_json"])))
        except (TypeError, ValueError, json.JSONDecodeError):
            request = {}
    return RunSummary(
        run_id=run_id,
        status=execution.get("status") or row.get("status"),
        started_at=row.get("started_at"),
        completed_at=row.get("completed_at"),
        topic=request.get("topic"),
        platform=request.get("platform"),
        market=request.get("market"),
        depth=request.get("depth"),
        profile_id=plan.get("profile_id") or row.get("profile_id"),
        provider=plan.get("provider") or row.get("provider"),
        video_count=repo.count_table(run_id, "videos"),
        creator_count=repo.count_table(run_id, "creators"),
        comment_count=repo.count_table(run_id, "comments"),
        raw_evidence_count=repo.count_table(run_id, "raw_evidence", run_scoped=True),
        provider_calls_attempted=execution.get("calls_attempted") if isinstance(execution.get("calls_attempted"), int) else None,
        provider_calls_succeeded=execution.get("calls_succeeded") if isinstance(execution.get("calls_succeeded"), int) else None,
        provider_calls_failed=execution.get("calls_failed") if isinstance(execution.get("calls_failed"), int) else None,
        expected_cost_usd=_number(plan, "expected_cost_usd"),
        max_cost_usd=_number(plan, "max_cost_usd"),
        actual_estimated_cost_usd=_number(execution, "actual_estimated_cost_usd", "estimated_actual_cost_usd"),
        stage_summary=list(execution.get("stages") or []),
        artifact_availability=ArtifactAvailability(
            plan=(run_dir / "plan.json").is_file(),
            execution=(run_dir / "execution.json").is_file(),
            database=(run_dir / "run.sqlite").is_file(),
            raw=(run_dir / "raw").is_dir(),
            reports=(run_dir / "reports").is_dir(),
            media=(run_dir / "media").is_dir(),
        ),
    )
