"""Read-only deterministic and semantic intelligence/report routes."""
from __future__ import annotations

from fastapi import APIRouter

from ..run_repository import RunRepository


def create_router(repo: RunRepository) -> APIRouter:
    router = APIRouter(prefix="/runs/{run_id}", tags=["intelligence"])

    @router.get("/findings")
    def findings(run_id: str):
        return repo.list_findings(run_id)

    @router.get("/patterns")
    def patterns(run_id: str):
        return repo.list_patterns(run_id)

    @router.get("/insights")
    def insights(run_id: str):
        return repo.list_insights(run_id)

    @router.get("/hypotheses")
    def hypotheses(run_id: str):
        return repo.list_hypotheses(run_id)

    @router.get("/briefs")
    def briefs(run_id: str):
        return repo.list_briefs(run_id)

    @router.get("/report")
    def report(run_id: str):
        return repo.get_report(run_id)

    return router
