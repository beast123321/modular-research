"""Conservative stage-flow and plan-vs-actual execution read models."""
from __future__ import annotations

from typing import Any

from .models import ExecutionSummary, StageState
from .run_repository import RunRepository

EXECUTION_STATUS_MAP = {
    "completed": "COMPLETED",
    "completed_local": "COMPLETED",
    "prepared_local": "PLANNED",
    "awaiting_host_agent": "PLANNED",
    "skipped_no_inputs": "SKIPPED",
    "skipped_insufficient_evidence": "SKIPPED",
    "partial_failed": "FAILED",
    "local_pending": "PLANNED",
    "running": "RUNNING",
}

_ARTIFACTS = {
    "CHEAP_RANKING": "reports/rankings.json",
    "VOC": "reports/voc.json",
    "FINDINGS": "reports/findings.json",
    "PATTERN_MINING": "reports/pattern_report.json",
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _number(mapping: dict[str, Any], key: str) -> float | None:
    value = mapping.get(key)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _integer(mapping: dict[str, Any], key: str) -> int | None:
    value = mapping.get(key)
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else None


def build_stage_flow(repo: RunRepository, run_id: str) -> list[StageState]:
    plan = _mapping(repo.load_json(run_id, "plan.json"))
    execution = _mapping(repo.load_json(run_id, "execution.json"))
    planned = [row for row in (plan.get("stages") or []) if isinstance(row, dict)]
    executed = [row for row in (execution.get("stages") or []) if isinstance(row, dict)]
    by_name = {str(row.get("stage")): row for row in executed if row.get("stage")}
    names = [str(row.get("name") or row.get("stage")) for row in planned if row.get("name") or row.get("stage")]
    if not names:
        names = [str(row.get("stage")) for row in executed if row.get("stage")]

    result: list[StageState] = []
    for name in names:
        row = by_name.get(name)
        if row is not None:
            raw_status = str(row.get("status") or "")
            status = EXECUTION_STATUS_MAP.get(raw_status, "UNAVAILABLE")
            result.append(
                StageState(
                    name=name,
                    status=status,
                    status_basis="execution" if status != "UNAVAILABLE" else "unavailable",
                    calls_attempted=_integer(row, "calls_attempted"),
                    calls_succeeded=_integer(row, "calls_succeeded"),
                    calls_failed=_integer(row, "calls_failed"),
                    summary=row.get("summary") if isinstance(row.get("summary"), dict) else None,
                )
            )
            continue
        artifact = _ARTIFACTS.get(name)
        if artifact and repo.artifact_path(run_id, artifact).is_file():
            result.append(StageState(name=name, status="COMPLETED", status_basis="inferred"))
        else:
            result.append(StageState(name=name, status="UNAVAILABLE", status_basis="unavailable"))
    return result


def build_execution_summary(repo: RunRepository, run_id: str) -> ExecutionSummary:
    plan = _mapping(repo.load_json(run_id, "plan.json"))
    execution = _mapping(repo.load_json(run_id, "execution.json"))
    actual = _number(execution, "actual_estimated_cost_usd")
    if actual is None:
        actual = _number(execution, "estimated_actual_cost_usd")
    return ExecutionSummary(
        expected_requests=_integer(plan, "expected_requests"),
        max_requests=_integer(plan, "max_requests"),
        expected_cost_usd=_number(plan, "expected_cost_usd"),
        max_cost_usd=_number(plan, "max_cost_usd"),
        calls_attempted=_integer(execution, "calls_attempted"),
        calls_succeeded=_integer(execution, "calls_succeeded"),
        calls_failed=_integer(execution, "calls_failed"),
        actual_estimated_cost_usd=actual,
        stages=build_stage_flow(repo, run_id),
    )
