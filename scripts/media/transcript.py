"""Transcript sidecar parsing.

Phase 5 does not bundle a heavyweight ASR model. If the host agent/runtime has
ASR, its transcript can be supplied as SRT/VTT/TXT and normalized here.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_TIME_RE = re.compile(r"(?P<h>\d{1,2}):(?P<m>\d{2}):(?P<s>\d{2})(?P<frac>[,.]\d{1,3})?")


def _time(value: str) -> float:
    m = _TIME_RE.fullmatch(value.strip())
    if not m:
        raise ValueError(f"invalid transcript timestamp: {value}")
    frac = (m.group("frac") or "").replace(",", ".")
    return int(m.group("h")) * 3600 + int(m.group("m")) * 60 + int(m.group("s")) + (float(frac) if frac else 0.0)


def load_sidecar_transcript(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    text = p.read_text(encoding="utf-8-sig")
    suffix = p.suffix.lower()
    if suffix == ".txt":
        stripped = text.strip()
        return [] if not stripped else [{"start_sec": None, "end_sec": None, "text": stripped, "source": "sidecar_txt", "confidence": None}]
    if suffix not in {".srt", ".vtt"}:
        raise ValueError("supported transcript formats: .srt, .vtt, .txt")
    if suffix == ".vtt" and text.lstrip().startswith("WEBVTT"):
        text = text.lstrip()[6:].lstrip("\r\n")
    blocks = re.split(r"\r?\n\s*\r?\n", text.strip())
    rows: list[dict[str, Any]] = []
    for block in blocks:
        lines = [line.strip("\ufeff") for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        timing_idx = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_idx is None:
            continue
        start_raw, end_raw = [x.strip().split()[0] for x in lines[timing_idx].split("-->", 1)]
        body = " ".join(lines[timing_idx + 1:]).strip()
        if not body:
            continue
        rows.append({"start_sec": round(_time(start_raw), 3), "end_sec": round(_time(end_raw), 3), "text": body, "source": "sidecar_vtt" if suffix == ".vtt" else "sidecar_srt", "confidence": None})
    return rows
