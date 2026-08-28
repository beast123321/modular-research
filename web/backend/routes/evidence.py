"""Read-only raw evidence and lineage routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..lineage_service import build_lineage, get_evidence, list_evidence
from ..run_repository import RunRepository


def create_router(repo: RunRepository) -> APIRouter:
    router = APIRouter(prefix="/runs/{run_id}", tags=["evidence"])

    @router.get("/evidence")
    def evidence_list(
        run_id: str,
        page: int = 1,
        page_size: int = Query(50, ge=1, le=200),
        endpoint: str | None = None,
        source_type: str | None = None,
        source_key: str | None = None,
        id: str | None = None,
        query: str | None = None,
    ):
        try:
            return list_evidence(repo, run_id, page=page, page_size=page_size, endpoint=endpoint, source_type=source_type, source_key=source_key, evidence_id=id, query=query)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400 if isinstance(exc, ValueError) else 404, detail=str(exc)) from exc

    @router.get("/evidence/{evidence_id}")
    def evidence_detail(run_id: str, evidence_id: str):
        try:
            return get_evidence(repo, run_id, evidence_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="evidence not found") from exc

    @router.get("/lineage/{evidence_id}")
    def lineage(run_id: str, evidence_id: str):
        try:
            return build_lineage(repo, run_id, evidence_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="evidence not found") from exc

    return router
