"""Read-only filesystem and SQLite access for Research Workbench runs."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sqlite3
from typing import Any

RUN_ID_RE = re.compile(r"^run_[A-Za-z0-9._-]+$")


class RunRepository:
    def __init__(self, runs_root: Path):
        self.runs_root = Path(runs_root).resolve()

    def discover_runs(self) -> list[str]:
        if not self.runs_root.exists():
            return []
        return sorted(
            p.name
            for p in self.runs_root.iterdir()
            if p.is_dir() and RUN_ID_RE.fullmatch(p.name)
        )

    def run_dir(self, run_id: str) -> Path:
        if not RUN_ID_RE.fullmatch(str(run_id)):
            raise ValueError("invalid run id")
        candidate = (self.runs_root / run_id).resolve()
        if candidate.parent != self.runs_root:
            raise ValueError("run path escapes runs root")
        if not candidate.is_dir():
            raise FileNotFoundError(run_id)
        return candidate

    def artifact_path(self, run_id: str, relative: str) -> Path:
        base = self.run_dir(run_id)
        candidate = (base / relative).resolve()
        try:
            candidate.relative_to(base)
        except ValueError as exc:
            raise ValueError("artifact path escapes run directory") from exc
        return candidate

    def load_json(self, run_id: str, relative: str) -> Any | None:
        path = self.artifact_path(run_id, relative)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def open_db(self, run_id: str) -> sqlite3.Connection:
        db = self.artifact_path(run_id, "run.sqlite")
        if not db.is_file():
            raise FileNotFoundError(db)
        conn = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        return conn

    @staticmethod
    def table_exists(conn: sqlite3.Connection, table: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        return row is not None

    def count_table(self, run_id: str, table: str, *, run_scoped: bool = False) -> int | None:
        try:
            conn = self.open_db(run_id)
        except FileNotFoundError:
            return None
        try:
            if not self.table_exists(conn, table):
                return None
            if run_scoped:
                row = conn.execute(f'SELECT COUNT(*) AS n FROM "{table}" WHERE run_id=?', (run_id,)).fetchone()
            else:
                row = conn.execute(f'SELECT COUNT(*) AS n FROM "{table}"').fetchone()
            return int(row["n"])
        finally:
            conn.close()

    def research_run_row(self, run_id: str) -> dict[str, Any] | None:
        try:
            conn = self.open_db(run_id)
        except FileNotFoundError:
            return None
        try:
            if not self.table_exists(conn, "research_runs"):
                return None
            row = conn.execute("SELECT * FROM research_runs WHERE id=?", (run_id,)).fetchone()
            return dict(row) if row is not None else None
        finally:
            conn.close()
