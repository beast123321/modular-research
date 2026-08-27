"""Safe local-media resolution for Research Workbench."""
from __future__ import annotations

from pathlib import Path

from .run_repository import RunRepository


def resolve_keyframe_path(repo: RunRepository, run_id: str, video_id: str, frame_id: str) -> Path:
    """Resolve one stored keyframe by IDs only and enforce run-directory containment."""
    conn = repo.open_db(run_id)
    try:
        row = conn.execute(
            "SELECT local_path FROM media_keyframes WHERE run_id=? AND video_id=? AND id=?",
            (run_id, video_id, frame_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise FileNotFoundError(frame_id)
    path = Path(str(row["local_path"])).resolve()
    run_root = repo.run_dir(run_id).resolve()
    try:
        path.relative_to(run_root)
    except ValueError as exc:
        raise ValueError("media path escapes run directory") from exc
    if not path.is_file():
        raise FileNotFoundError(path)
    return path
