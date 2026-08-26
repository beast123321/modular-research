from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any
ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = sorted((ROOT / "migrations").glob("*.sql"))
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
def _stable_id(*parts: Any) -> str:
    raw = "\x1f".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
