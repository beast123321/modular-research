"""Optional OCR adapter for extracted keyframes."""
from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any


def ocr_keyframes(frames: list[dict[str, Any]], *, engine: str = "auto", language: str | None = None) -> dict[str, Any]:
    if engine == "none":
        return {"status": "unavailable", "engine": "none", "items": [], "reason": "disabled"}
    if engine not in {"auto", "tesseract"}:
        raise ValueError(f"unsupported OCR engine: {engine}")
    if shutil.which("tesseract") is None:
        return {"status": "unavailable", "engine": "tesseract", "items": [], "reason": "tesseract_not_found"}
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return {"status": "unavailable", "engine": "tesseract", "items": [], "reason": "python_dependencies_missing"}

    items: list[dict[str, Any]] = []
    failures = 0
    for frame in frames:
        path = Path(str(frame.get("path") or ""))
        try:
            data = pytesseract.image_to_data(
                Image.open(path),
                lang=language or None,
                output_type=pytesseract.Output.DICT,
                config="--psm 6",
            )
            texts: list[str] = []
            confidences: list[float] = []
            for text, conf in zip(data.get("text", []), data.get("conf", [])):
                text = str(text).strip()
                try:
                    c = float(conf)
                except (TypeError, ValueError):
                    c = -1
                if text and c >= 0:
                    texts.append(text)
                    confidences.append(c / 100.0)
            joined = " ".join(texts).strip()
            items.append({
                "id": frame.get("id"),
                "timestamp_sec": frame.get("timestamp_sec"),
                "path": str(path),
                "text": joined or None,
                "confidence": (sum(confidences) / len(confidences)) if confidences else None,
            })
        except Exception as exc:
            failures += 1
            items.append({"id": frame.get("id"), "timestamp_sec": frame.get("timestamp_sec"), "path": str(path), "text": None, "confidence": None, "error": str(exc)})
    status = "complete" if failures == 0 else ("partial" if items else "failed")
    return {"status": status, "engine": "tesseract", "items": items}
