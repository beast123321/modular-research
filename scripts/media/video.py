"""Deterministic video probing and keyframe extraction using OpenCV."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _cv2():
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("OpenCV is required for video preprocessing") from exc
    return cv2


def probe_video(path: str | Path) -> dict[str, Any]:
    cv2 = _cv2()
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"cannot open video: {path}")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        duration = (frame_count / fps) if fps > 0 else None
        return {"fps": round(fps, 6) if fps > 0 else None, "frame_count": frame_count, "width": width, "height": height, "duration_sec": round(duration, 3) if duration is not None else None}
    finally:
        cap.release()


def _difference(gray_a, gray_b) -> float:
    import numpy as np
    return float(np.mean(np.abs(gray_a.astype("float32") - gray_b.astype("float32"))) / 255.0)


def extract_keyframes(path: str | Path, out_dir: str | Path, *, max_frames: int = 12, sample_fps: float = 2.0, scene_threshold: float = 0.22) -> list[dict[str, Any]]:
    if max_frames <= 0:
        return []
    cv2 = _cv2()
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"cannot open video: {path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if fps <= 0 or total <= 0:
        cap.release()
        raise ValueError("video has invalid fps/frame count")
    stride = max(1, int(round(fps / max(sample_fps, 0.1))))
    sampled: list[tuple[int, Any, Any]] = []
    idx = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % stride == 0 or idx == total - 1:
                small = cv2.resize(frame, (64, 64), interpolation=cv2.INTER_AREA)
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                sampled.append((idx, frame.copy(), gray))
            idx += 1
    finally:
        cap.release()
    if not sampled:
        return []
    chosen: list[tuple[int, Any, int]] = []
    scene_index = 0
    chosen.append((sampled[0][0], sampled[0][1], scene_index))
    prev_gray = sampled[0][2]
    for frame_idx, frame, gray in sampled[1:]:
        diff = _difference(prev_gray, gray)
        if diff >= scene_threshold:
            scene_index += 1
            chosen.append((frame_idx, frame, scene_index))
        prev_gray = gray
    if len(chosen) < min(max_frames, len(sampled)):
        chosen_ids = {x[0] for x in chosen}
        need = min(max_frames, len(sampled)) - len(chosen)
        candidates = [x for x in sampled if x[0] not in chosen_ids]
        if candidates and need > 0:
            positions = [round(i * (len(candidates) - 1) / max(need - 1, 1)) for i in range(need)]
            for pos in positions:
                frame_idx, frame, _ = candidates[pos]
                chosen.append((frame_idx, frame, -1))
    chosen = sorted({frame_idx: (frame_idx, frame, scene) for frame_idx, frame, scene in chosen}.values(), key=lambda x: x[0])[:max_frames]
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for order, (frame_idx, frame, scene) in enumerate(chosen):
        ts = round(frame_idx / fps, 3)
        output = target / f"frame_{order:03d}_{ts:08.3f}.jpg"
        if not cv2.imwrite(str(output), frame):
            raise RuntimeError(f"failed to write keyframe: {output}")
        rows.append({"id": f"frame:{Path(path).stem}:{order:03d}", "timestamp_sec": ts, "path": str(output), "scene_index": scene if scene >= 0 else None})
    return rows
