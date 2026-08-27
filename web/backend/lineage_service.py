"""Evidence Explorer and stored-reference lineage for Research Workbench."""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from api_research_core import redact_payload

from .models import Page
from .run_repository import RunRepository


class LineageEdge(BaseModel):
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    relation: str


class LineageGraph(BaseModel):
    root_id: str
    edges: list[LineageEdge] = Field(default_factory=list)


_DIRECT_REFS: tuple[tuple[str, str, str], ...] = (
    ("creators", "creator", "creator_id"),
    ("videos", "video", "video_id"),
    ("video_snapshots", "video_snapshot", "id"),
    ("discoveries", "discovery", "id"),
    ("comments", "comment", "comment_id"),
    ("ads", "ad", "material_id"),
    ("ad_timeseries", "ad_timeseries", "id"),
    ("search_insights", "search_insight", "id"),
)

_DERIVED_REFS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("video_metrics_derived", "video_metric", ("video_id",)),
    ("creator_metrics_derived", "creator_metric", ("creator_id",)),
    ("comment_labels", "comment_label", ("comment_id",)),
    ("findings", "finding", ("id",)),
    ("media_keyframes", "keyframe", ("id",)),
    ("transcript_segments", "transcript", ("id",)),
    ("creative_analysis", "creative_analysis", ("video_id", "analyzer_name")),
    ("creative_patterns", "pattern", ("id",)),
    ("insights", "insight", ("id",)),
    ("creative_hypotheses", "hypothesis", ("id",)),
    ("media_briefs", "brief", ("id",)),
)


def _decode_json(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _columns(conn, table: str) -> set[str]:
    return {str(row["name"]) for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


def _target_id(row: Any, columns: tuple[str, ...]) -> str:
    return ":".join(str(row[column]) for column in columns)


def _direct_entities(conn, evidence_id: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for table, entity_type, id_column in _DIRECT_REFS:
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is None:
            continue
        cols = _columns(conn, table)
        if "raw_evidence_id" not in cols or id_column not in cols:
            continue
        for row in conn.execute(
            f'SELECT "{id_column}" AS entity_id FROM "{table}" WHERE raw_evidence_id=?',
            (evidence_id,),
        ).fetchall():
            result.append({"type": entity_type, "id": str(row["entity_id"])})
    return result


def get_evidence(repo: RunRepository, run_id: str, evidence_id: str) -> dict[str, Any]:
    """Return one raw evidence record with defense-in-depth redaction."""
    conn = repo.open_db(run_id)
    try:
        row = conn.execute(
            "SELECT * FROM raw_evidence WHERE run_id=? AND id=?",
            (run_id, evidence_id),
        ).fetchone()
        if row is None:
            raise FileNotFoundError(evidence_id)
        return {
            "id": str(row["id"]),
            "run_id": str(row["run_id"]),
            "endpoint": row["endpoint"],
            "method": row["method"],
            "source_type": row["source_type"],
            "source_key": row["source_key"],
            "fetched_at": row["fetched_at"],
            "request": redact_payload(_decode_json(row["request_json"], {})),
            "response": redact_payload(_decode_json(row["response_json"], {})),
            "normalized_entities": _direct_entities(conn, evidence_id),
        }
    finally:
        conn.close()


def list_evidence(
    repo: RunRepository,
    run_id: str,
    *,
    page: int = 1,
    page_size: int = 50,
    endpoint: str | None = None,
    source_type: str | None = None,
    source_key: str | None = None,
    evidence_id: str | None = None,
    query: str | None = None,
) -> Page:
    limit, offset, _ = repo._paging(page, page_size, "desc")
    conn = repo.open_db(run_id)
    try:
        where = ["run_id=?"]
        params: list[Any] = [run_id]
        for column, value in (("endpoint", endpoint), ("source_type", source_type), ("source_key", source_key), ("id", evidence_id)):
            if value:
                where.append(f'"{column}"=?')
                params.append(value)
        if query:
            where.append("(id LIKE ? OR endpoint LIKE ? OR source_key LIKE ?)")
            needle = f"%{query}%"
            params.extend([needle, needle, needle])
        clause = " AND ".join(where)
        total = int(conn.execute(f"SELECT COUNT(*) AS n FROM raw_evidence WHERE {clause}", params).fetchone()["n"])
        rows = [
            dict(row)
            for row in conn.execute(
                f"SELECT id,endpoint,method,source_type,source_key,fetched_at FROM raw_evidence WHERE {clause} ORDER BY fetched_at DESC,id DESC LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()
        ]
        return Page(items=rows, page=page, page_size=page_size, total=total)
    finally:
        conn.close()


def build_lineage(repo: RunRepository, run_id: str, evidence_id: str) -> LineageGraph:
    """Build only lineage edges supported by stored IDs and evidence refs."""
    conn = repo.open_db(run_id)
    try:
        exists = conn.execute("SELECT 1 FROM raw_evidence WHERE run_id=? AND id=?", (run_id, evidence_id)).fetchone()
        if exists is None:
            raise FileNotFoundError(evidence_id)
        edges: list[LineageEdge] = []
        seen: set[tuple[str, str, str, str, str]] = set()

        def add(target_type: str, target_id: str, relation: str) -> None:
            key = ("raw_evidence", evidence_id, target_type, target_id, relation)
            if key in seen:
                return
            seen.add(key)
            edges.append(LineageEdge(source_type="raw_evidence", source_id=evidence_id, target_type=target_type, target_id=target_id, relation=relation))

        for entity in _direct_entities(conn, evidence_id):
            add(entity["type"], entity["id"], "normalized_as")

        for table, target_type, id_columns in _DERIVED_REFS:
            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is None:
                continue
            cols = _columns(conn, table)
            if "evidence_refs_json" not in cols or any(column not in cols for column in id_columns):
                continue
            selected = ",".join(f'"{column}"' for column in id_columns) + ',"evidence_refs_json"'
            if "run_id" in cols:
                rows = conn.execute(f'SELECT {selected} FROM "{table}" WHERE run_id=?', (run_id,)).fetchall()
            else:
                rows = conn.execute(f'SELECT {selected} FROM "{table}"').fetchall()
            for row in rows:
                refs = _decode_json(row["evidence_refs_json"], [])
                if isinstance(refs, list) and evidence_id in {str(ref) for ref in refs}:
                    add(target_type, _target_id(row, id_columns), "supports")
        return LineageGraph(root_id=evidence_id, edges=edges)
    finally:
        conn.close()
