"""Run history, overview, flow and execution routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..flow_service import build_execution_summary, build_stage_flow
from ..run_repository import RunRepository
from ..run_summary import build_run_summary


def create_router(repo: RunRepository) -> APIRouter:
    router = APIRouter(prefix="/runs", tags=["runs"])

    @router.get("")
    def list_runs():
        return [build_run_summary(repo, run_id) for run_id in reversed(repo.discover_runs())]

    @router.get("/{run_id}")
    def get_run(run_id: str):
        try:
            return build_run_summary(repo, run_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc

    @router.get("/{run_id}/flow")
    def flow(run_id: str):
        return build_stage_flow(repo, run_id)

    @router.get("/{run_id}/execution")
    def execution(run_id: str):
        return build_execution_summary(repo, run_id)

    return router
