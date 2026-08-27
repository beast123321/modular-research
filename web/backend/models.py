"""Typed read models exposed by the Research Workbench backend."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ArtifactAvailability(BaseModel):
    plan: bool = False
    execution: bool = False
    database: bool = False
    raw: bool = False
    reports: bool = False
    media: bool = False


class Page(BaseModel):
    items: list[Any] = Field(default_factory=list)
    page: int = 1
    page_size: int = 50
    total: int = 0


class StageState(BaseModel):
    name: str
    status: Literal["COMPLETED", "RUNNING", "SKIPPED", "FAILED", "PLANNED", "UNAVAILABLE"]
    status_basis: Literal["execution", "artifact", "inferred", "unavailable"]
    calls_attempted: int | None = None
    calls_succeeded: int | None = None
    calls_failed: int | None = None
    summary: dict[str, Any] | None = None


class ExecutionSummary(BaseModel):
    expected_requests: int | None = None
    max_requests: int | None = None
    expected_cost_usd: float | None = None
    max_cost_usd: float | None = None
    calls_attempted: int | None = None
    calls_succeeded: int | None = None
    calls_failed: int | None = None
    actual_estimated_cost_usd: float | None = None
    stages: list[StageState] = Field(default_factory=list)


class RunSummary(BaseModel):
    run_id: str
    status: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    topic: str | None = None
    platform: str | None = None
    market: str | None = None
    depth: str | None = None
    profile_id: str | None = None
    provider: str | None = None
    video_count: int | None = None
    creator_count: int | None = None
    comment_count: int | None = None
    raw_evidence_count: int | None = None
    provider_calls_attempted: int | None = None
    provider_calls_succeeded: int | None = None
    provider_calls_failed: int | None = None
    expected_cost_usd: float | None = None
    max_cost_usd: float | None = None
    actual_estimated_cost_usd: float | None = None
    stage_summary: list[dict[str, Any]] = Field(default_factory=list)
    artifact_availability: ArtifactAvailability = Field(default_factory=ArtifactAvailability)
