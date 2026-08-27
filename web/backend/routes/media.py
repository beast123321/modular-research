"""Read-only media, keyframe, OCR, transcript and creative-analysis routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..media_service import resolve_keyframe_path
from ..run_repository import RunRepository


def create_router(repo: RunRepository) -> APIRouter:
    router = APIRouter(prefix="/runs/{run_id}/media", tags=["media"])

    @router.get("")
    def media_list(run_id: str):
        return repo.list_media(run_id)

    @router.get("/{video_id}")
    def media_detail(run_id: str, video_id: str):
        return repo.get_media(run_id, video_id)

    @router.get("/{video_id}/keyframes/{frame_id}/content")
    def keyframe_content(run_id: str, video_id: str, frame_id: str):
        try:
            path = resolve_keyframe_path(repo, run_id, video_id, frame_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="keyframe not found") from exc
        return FileResponse(path)

    return router
