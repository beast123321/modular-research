"""FastAPI assembly for the bundled local Research Workbench."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .run_repository import RunRepository
from .routes import health
from .routes.entities import create_router as create_entities_router
from .routes.evidence import create_router as create_evidence_router
from .routes.intelligence import create_router as create_intelligence_router
from .routes.media import create_router as create_media_router
from .routes.runs import create_router as create_runs_router


def create_app(runs_root: Path, frontend_dist: Path | None = None) -> FastAPI:
    repo = RunRepository(Path(runs_root))
    app = FastAPI(title="modular-research Workbench", version="1.2.0")
    app.state.run_repository = repo

    app.include_router(health.router, prefix="/api")
    app.include_router(create_runs_router(repo), prefix="/api")
    app.include_router(create_entities_router(repo), prefix="/api")
    app.include_router(create_evidence_router(repo), prefix="/api")
    app.include_router(create_media_router(repo), prefix="/api")
    app.include_router(create_intelligence_router(repo), prefix="/api")

    if frontend_dist is not None:
        dist = Path(frontend_dist).resolve()
        index = dist / "index.html"
        if not index.is_file():
            raise ValueError(f"frontend build missing index.html: {dist}")
        assets = dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            if full_path == "api" or full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="API route not found")
            requested = (dist / full_path).resolve()
            try:
                requested.relative_to(dist)
            except ValueError as exc:
                raise HTTPException(status_code=404, detail="not found") from exc
            if requested.is_file():
                return FileResponse(requested)
            return FileResponse(index)

    return app
