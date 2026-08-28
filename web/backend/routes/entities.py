"""Read-only video, creator, comment and VOC routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..run_repository import RunRepository


def create_router(repo: RunRepository) -> APIRouter:
    router = APIRouter(prefix="/runs/{run_id}", tags=["entities"])

    @router.get("/videos")
    def videos(run_id: str, page: int = 1, page_size: int = Query(50, le=200), sort: str = "views", order: str = "desc", query: str | None = None, creator_id: str | None = None, source_type: str | None = None):
        try:
            return repo.list_videos(run_id, page=page, page_size=page_size, sort=sort, order=order, query=query, creator_id=creator_id, source_type=source_type)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400 if isinstance(exc, ValueError) else 404, detail=str(exc)) from exc

    @router.get("/videos/{video_id}")
    def video(run_id: str, video_id: str):
        result = repo.get_video(run_id, video_id)
        if result is None:
            raise HTTPException(status_code=404, detail="video not found")
        return result

    @router.get("/creators")
    def creators(run_id: str, page: int = 1, page_size: int = Query(50, le=200), sort: str = "followers", order: str = "desc", query: str | None = None):
        return repo.list_creators(run_id, page=page, page_size=page_size, sort=sort, order=order, query=query)

    @router.get("/creators/{creator_id}")
    def creator(run_id: str, creator_id: str):
        result = repo.get_creator(run_id, creator_id)
        if result is None:
            raise HTTPException(status_code=404, detail="creator not found")
        return result

    @router.get("/comments")
    def comments(run_id: str, page: int = 1, page_size: int = Query(50, le=200), sort: str = "likes", order: str = "desc", query: str | None = None, label: str | None = None, video_id: str | None = None):
        return repo.list_comments(run_id, page=page, page_size=page_size, sort=sort, order=order, query=query, label=label, video_id=video_id)

    @router.get("/voc")
    def voc(run_id: str):
        return repo.get_voc(run_id)

    return router
