"""Prepare media evidence and host-agent creative analysis requests."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from creative.agent_bridge import build_analysis_request
from creative.shortlist import select_creative_shortlist
from evidence_store import EvidenceStore
from media.assets import download_media
from media.ocr import ocr_keyframes
from media.transcript import load_sidecar_transcript
from media.video import extract_keyframes, probe_video


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _sidecar(video_dir: Path) -> Path | None:
    for name in ("transcript.srt", "transcript.vtt", "transcript.txt"):
        p = video_dir / name
        if p.exists():
            return p
    return None


def run_video_understanding(
    db_path: str | Path,
    run_dir: str | Path,
    run_id: str,
    *,
    limit: int,
    download: bool = False,
    max_bytes_per_video: int = 100 * 1024 * 1024,
    max_keyframes: int = 12,
    ocr_engine: str = "auto",
    video_filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Prepare expensive-analysis shortlist and portable multimodal requests.

    With ``download=False`` this is metadata-only and performs no network I/O.
    With ``download=True`` it downloads public media, extracts keyframes/OCR and
    normalizes any host-provided transcript sidecar already in the video folder.
    """
    run_root = Path(run_dir)
    report_dir = run_root / "reports"
    media_root = run_root / "media"
    shortlist = select_creative_shortlist(db_path, run_id, limit, video_filters=video_filters)
    _write(report_dir / "creative_shortlist.json", shortlist)

    store = EvidenceStore(db_path)
    analysis_requests: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    downloaded = failed = 0
    try:
        for video in shortlist:
            video_id = str(video["video_id"])
            video_dir = media_root / video_id
            asset: dict[str, Any] = {
                "source_url": video.get("video_url"),
                "local_path": None,
                "status": "not_downloaded",
            }
            keyframes: list[dict[str, Any]] = []
            transcripts: list[dict[str, Any]] = []
            if download:
                try:
                    source = str(video.get("video_url") or "")
                    destination = video_dir / "source.mp4"
                    asset = download_media(source, destination, max_bytes=max_bytes_per_video)
                    asset.update(probe_video(destination))
                    frames = extract_keyframes(destination, video_dir / "frames", max_frames=max_keyframes)
                    ocr = ocr_keyframes(frames, engine=ocr_engine)
                    ocr_by_id = {str(x.get("id")): x for x in ocr.get("items", [])}
                    for frame in frames:
                        item = dict(frame)
                        o = ocr_by_id.get(str(frame.get("id")))
                        if o:
                            item["ocr_text"] = o.get("text")
                            item["ocr_confidence"] = o.get("confidence")
                        item["evidence_refs"] = [str(frame.get("id"))]
                        keyframes.append(item)
                    sidecar = _sidecar(video_dir)
                    if sidecar:
                        transcripts = load_sidecar_transcript(sidecar)
                        for index, seg in enumerate(transcripts):
                            seg["id"] = f"transcript:{video_id}:{index:03d}"
                            seg["evidence_refs"] = [seg["id"]]
                    downloaded += 1
                except Exception as exc:
                    failed += 1
                    asset = {
                        "source_url": video.get("video_url"), "local_path": None,
                        "status": "failed", "error": str(exc),
                    }
            store.replace_media_analysis(
                run_id=run_id, video_id=video_id, asset=asset,
                keyframes=keyframes, transcripts=transcripts,
            )
            request = build_analysis_request(
                video=video, asset=asset, keyframes=keyframes, transcript=transcripts
            )
            analysis_requests.append(request)
            manifest.append({
                "video_id": video_id,
                "asset_status": asset.get("status"),
                "local_path": asset.get("local_path"),
                "keyframe_count": len(keyframes),
                "transcript_segment_count": len(transcripts),
                "ocr_status": "not_run" if not download else ("available" if keyframes else "unavailable"),
            })
        semantic_count = int(store.conn.execute(
            "SELECT COUNT(*) FROM creative_analysis WHERE run_id=?", (run_id,)
        ).fetchone()[0])
    finally:
        store.close()

    _write(report_dir / "creative_analysis_requests.json", analysis_requests)
    _write(report_dir / "media_manifest.json", manifest)
    return {
        "run_id": run_id,
        "shortlist_count": len(shortlist),
        "analysis_request_count": len(analysis_requests),
        "media_downloaded": downloaded,
        "media_failed": failed,
        "semantic_analysis_count": semantic_count,
        "download_enabled": bool(download),
    }
