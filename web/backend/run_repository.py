"""Read-only filesystem and SQLite access for Research Workbench runs."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from .models import Page

RUN_ID_RE = re.compile(r"^run_[A-Za-z0-9._-]+$")
VIDEO_SORTS = {
    "views": "s.views",
    "engagement_rate": "m.engagement_rate",
    "follower_leverage": "m.follower_leverage",
    "captured_at": "s.captured_at",
}
CREATOR_SORTS = {"followers": "c.followers", "baseline_views": "m.baseline_views", "nickname": "c.nickname"}
COMMENT_SORTS = {"likes": "cm.like_count", "created_at": "cm.created_at", "intensity": "l.weighted_intensity"}


class RunRepository:
    def __init__(self, runs_root: Path):
        self.runs_root = Path(runs_root).resolve()

    def discover_runs(self) -> list[str]:
        if not self.runs_root.exists():
            return []
        return sorted(p.name for p in self.runs_root.iterdir() if p.is_dir() and RUN_ID_RE.fullmatch(p.name))

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
        return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None

    @staticmethod
    def _paging(page: int, page_size: int, order: str) -> tuple[int, int, str]:
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1 or page_size > 200:
            raise ValueError("page_size must be between 1 and 200")
        normalized_order = str(order or "desc").lower()
        if normalized_order not in {"asc", "desc"}:
            raise ValueError("order must be asc or desc")
        return page_size, (page - 1) * page_size, normalized_order.upper()

    @staticmethod
    def _decode_json(value: Any, fallback):
        if value in (None, ""):
            return fallback
        try:
            return json.loads(str(value))
        except (TypeError, ValueError, json.JSONDecodeError):
            return fallback

    @classmethod
    def _decode_row_json(cls, row: dict[str, Any]) -> dict[str, Any]:
        out = dict(row)
        mappings = {
            "evidence_refs_json": ("evidence_refs", []),
            "metrics_json": ("metrics", {}),
            "timeline_json": ("timeline", []),
            "confidence_json": ("confidence", {}),
            "cohort_json": ("cohort", {}),
            "labels_json": ("labels", []),
            "matched_terms_json": ("matched_terms", []),
        }
        for source, (target, fallback) in mappings.items():
            if source in out:
                out[target] = cls._decode_json(out.pop(source), fallback)
        return out

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

    def list_videos(self, run_id: str, *, page: int = 1, page_size: int = 50, sort: str = "views", order: str = "desc", query: str | None = None, creator_id: str | None = None, source_type: str | None = None) -> Page:
        limit, offset, direction = self._paging(page, page_size, order)
        column = VIDEO_SORTS.get(sort or "views")
        if column is None:
            raise ValueError("unsupported video sort")
        conn = self.open_db(run_id)
        try:
            where = ["1=1"]
            params: list[Any] = [run_id, run_id]
            if query:
                where.append("(v.caption LIKE ? OR c.nickname LIKE ? OR v.video_id LIKE ?)")
                needle = f"%{query}%"; params.extend([needle, needle, needle])
            if creator_id:
                where.append("v.creator_id=?"); params.append(creator_id)
            if source_type:
                where.append("EXISTS(SELECT 1 FROM discoveries dx WHERE dx.run_id=? AND dx.video_id=v.video_id AND dx.source_type=?)")
                params.extend([run_id, source_type])
            clause = " AND ".join(where)
            count_params = params[2:]
            count_sql = f"SELECT COUNT(*) AS n FROM videos v LEFT JOIN creators c ON c.creator_id=v.creator_id WHERE {clause}"
            total = int(conn.execute(count_sql, count_params).fetchone()["n"])
            sql = f"""
                WITH latest_snapshot AS (
                    SELECT s.* FROM video_snapshots s
                    JOIN (SELECT video_id, MAX(id) AS max_id FROM video_snapshots WHERE run_id=? GROUP BY video_id) x ON x.max_id=s.id
                )
                SELECT v.video_id,v.creator_id,v.caption,v.create_time,v.duration_sec,v.region,v.cover_url,v.video_url,v.hashtags_json,v.raw_evidence_id,
                       c.nickname AS creator_nickname,c.followers,
                       s.views,s.likes,s.comments,s.shares,s.favorites,s.author_followers,s.captured_at,s.raw_evidence_id AS snapshot_evidence_id,
                       m.engagement_rate,m.like_rate,m.comment_rate,m.share_rate,m.save_rate,m.follower_leverage,m.creator_overperformance,m.evidence_refs_json,
                       (SELECT d.source_type FROM discoveries d WHERE d.run_id=? AND d.video_id=v.video_id ORDER BY COALESCE(d.source_rank,999999),d.id LIMIT 1) AS discovery_source
                FROM videos v
                LEFT JOIN creators c ON c.creator_id=v.creator_id
                LEFT JOIN latest_snapshot s ON s.video_id=v.video_id
                LEFT JOIN video_metrics_derived m ON m.run_id=? AND m.video_id=v.video_id
                WHERE {clause}
                ORDER BY ({column} IS NULL) ASC, {column} {direction}
                LIMIT ? OFFSET ?
            """
            query_params = [run_id, run_id, run_id] + params[2:] + [limit, offset]
            rows = [dict(row) for row in conn.execute(sql, query_params).fetchall()]
            for row in rows:
                row["hashtags"] = self._decode_json(row.pop("hashtags_json", None), [])
                row["evidence_refs"] = self._decode_json(row.pop("evidence_refs_json", None), [])
            return Page(items=rows, page=page, page_size=page_size, total=total)
        finally:
            conn.close()

    def get_video(self, run_id: str, video_id: str) -> dict[str, Any] | None:
        page = self.list_videos(run_id, page=1, page_size=200, sort="views", order="desc", query=video_id)
        base = next((row for row in page.items if row.get("video_id") == video_id), None)
        if base is None:
            return None
        conn = self.open_db(run_id)
        try:
            base = dict(base)
            base["snapshots"] = [dict(r) for r in conn.execute("SELECT * FROM video_snapshots WHERE run_id=? AND video_id=? ORDER BY captured_at", (run_id, video_id)).fetchall()]
            base["discoveries"] = [dict(r) for r in conn.execute("SELECT * FROM discoveries WHERE run_id=? AND video_id=? ORDER BY source_rank", (run_id, video_id)).fetchall()]
            base["comments"] = [dict(r) for r in conn.execute("SELECT * FROM comments WHERE video_id=? ORDER BY like_count DESC", (video_id,)).fetchall()]
            return base
        finally:
            conn.close()

    def list_creators(self, run_id: str, *, page: int = 1, page_size: int = 50, sort: str = "followers", order: str = "desc", query: str | None = None) -> Page:
        limit, offset, direction = self._paging(page, page_size, order)
        column = CREATOR_SORTS.get(sort or "followers")
        if column is None:
            raise ValueError("unsupported creator sort")
        conn = self.open_db(run_id)
        try:
            where = ["1=1"]; params: list[Any] = []
            if query:
                where.append("(c.nickname LIKE ? OR c.unique_id LIKE ? OR c.creator_id LIKE ?)")
                needle=f"%{query}%"; params.extend([needle, needle, needle])
            clause=" AND ".join(where)
            total=int(conn.execute(f"SELECT COUNT(*) AS n FROM creators c WHERE {clause}", params).fetchone()["n"])
            sql=f"""SELECT c.*,m.baseline_views,m.sample_size,m.median_engagement_rate,m.evidence_refs_json,
                    (SELECT COUNT(*) FROM videos v WHERE v.creator_id=c.creator_id) AS run_video_count
                    FROM creators c LEFT JOIN creator_metrics_derived m ON m.run_id=? AND m.creator_id=c.creator_id
                    WHERE {clause} ORDER BY ({column} IS NULL) ASC,{column} {direction} LIMIT ? OFFSET ?"""
            rows=[dict(r) for r in conn.execute(sql,[run_id]+params+[limit,offset]).fetchall()]
            for row in rows:
                row["evidence_refs"] = self._decode_json(row.pop("evidence_refs_json", None), [])
            return Page(items=rows,page=page,page_size=page_size,total=total)
        finally:
            conn.close()

    def get_creator(self, run_id: str, creator_id: str) -> dict[str, Any] | None:
        conn=self.open_db(run_id)
        try:
            row=conn.execute("SELECT * FROM creators WHERE creator_id=?",(creator_id,)).fetchone()
            if row is None: return None
            result=dict(row)
            result["videos"]=[dict(r) for r in conn.execute("SELECT video_id,caption,create_time,raw_evidence_id FROM videos WHERE creator_id=? ORDER BY create_time DESC",(creator_id,)).fetchall()]
            return result
        finally: conn.close()

    def list_comments(self, run_id: str, *, page: int = 1, page_size: int = 50, sort: str = "likes", order: str = "desc", query: str | None = None, label: str | None = None, video_id: str | None = None) -> Page:
        limit,offset,direction=self._paging(page,page_size,order)
        column=COMMENT_SORTS.get(sort or "likes")
        if column is None: raise ValueError("unsupported comment sort")
        conn=self.open_db(run_id)
        try:
            where=["1=1"]; params:list[Any]=[run_id]
            if query:
                where.append("cm.text LIKE ?"); params.append(f"%{query}%")
            if video_id:
                where.append("cm.video_id=?"); params.append(video_id)
            if label:
                where.append("l.labels_json LIKE ?"); params.append(f'%"{label}"%')
            clause=" AND ".join(where)
            count_sql=f"SELECT COUNT(*) AS n FROM comments cm LEFT JOIN comment_labels l ON l.run_id=? AND l.comment_id=cm.comment_id WHERE {clause}"
            total=int(conn.execute(count_sql,params).fetchone()["n"])
            sql=f"""SELECT cm.*,l.labels_json,l.matched_terms_json,l.weighted_intensity,l.classifier_version,l.evidence_refs_json
                    FROM comments cm LEFT JOIN comment_labels l ON l.run_id=? AND l.comment_id=cm.comment_id
                    WHERE {clause} ORDER BY ({column} IS NULL) ASC,{column} {direction} LIMIT ? OFFSET ?"""
            rows=[dict(r) for r in conn.execute(sql,params+[limit,offset]).fetchall()]
            for row in rows:
                row["labels"]=self._decode_json(row.pop("labels_json",None),[])
                row["matched_terms"]=self._decode_json(row.pop("matched_terms_json",None),[])
                row["evidence_refs"]=self._decode_json(row.pop("evidence_refs_json",None),[])
            return Page(items=rows,page=page,page_size=page_size,total=total)
        finally: conn.close()

    def get_voc(self, run_id: str) -> dict[str, Any]:
        conn=self.open_db(run_id)
        try:
            denominator=int(conn.execute("SELECT COUNT(*) AS n FROM comments").fetchone()["n"]) if self.table_exists(conn,"comments") else 0
            if not self.table_exists(conn,"comment_labels"):
                return {"denominator":denominator,"labels":[]}
            rows=conn.execute("SELECT labels_json FROM comment_labels WHERE run_id=?",(run_id,)).fetchall()
            counter:Counter[str]=Counter()
            for row in rows:
                labels=self._decode_json(row["labels_json"],[])
                if isinstance(labels,list): counter.update(str(x) for x in labels)
            labels=[{"label":label,"count":count,"share":(count/denominator if denominator else None)} for label,count in sorted(counter.items(),key=lambda x:(-x[1],x[0]))]
            return {"denominator":denominator,"labels":labels}
        finally: conn.close()

    def list_media(self, run_id: str) -> list[dict[str, Any]]:
        conn = self.open_db(run_id)
        try:
            if not self.table_exists(conn, "media_assets"):
                return []
            rows = conn.execute(
                """SELECT a.*,
                    (SELECT COUNT(*) FROM media_keyframes k WHERE k.run_id=a.run_id AND k.video_id=a.video_id) AS keyframe_count,
                    (SELECT COUNT(*) FROM transcript_segments t WHERE t.run_id=a.run_id AND t.video_id=a.video_id) AS transcript_count,
                    (SELECT COUNT(*) FROM creative_analysis c WHERE c.run_id=a.run_id AND c.video_id=a.video_id) AS creative_analysis_count
                    FROM media_assets a WHERE a.run_id=? ORDER BY a.video_id""",
                (run_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_media(self, run_id: str, video_id: str) -> dict[str, Any]:
        conn = self.open_db(run_id)
        try:
            asset = None
            if self.table_exists(conn, "media_assets"):
                row = conn.execute("SELECT * FROM media_assets WHERE run_id=? AND video_id=?", (run_id, video_id)).fetchone()
                asset = dict(row) if row is not None else None
            keyframes: list[dict[str, Any]] = []
            if self.table_exists(conn, "media_keyframes"):
                keyframes = [self._decode_row_json(dict(row)) for row in conn.execute("SELECT * FROM media_keyframes WHERE run_id=? AND video_id=? ORDER BY timestamp_sec,id", (run_id, video_id)).fetchall()]
            transcripts: list[dict[str, Any]] = []
            if self.table_exists(conn, "transcript_segments"):
                transcripts = [self._decode_row_json(dict(row)) for row in conn.execute("SELECT * FROM transcript_segments WHERE run_id=? AND video_id=? ORDER BY COALESCE(start_sec,0),id", (run_id, video_id)).fetchall()]
            creative: list[dict[str, Any]] = []
            if self.table_exists(conn, "creative_analysis"):
                creative = [self._decode_row_json(dict(row)) for row in conn.execute("SELECT * FROM creative_analysis WHERE run_id=? AND video_id=? ORDER BY analyzer_name", (run_id, video_id)).fetchall()]
            return {"video_id": video_id, "asset": asset, "keyframes": keyframes, "transcripts": transcripts, "creative_analysis": creative}
        finally:
            conn.close()

    def _list_run_table(self, run_id: str, table: str, order_column: str) -> list[dict[str, Any]]:
        conn = self.open_db(run_id)
        try:
            if not self.table_exists(conn, table):
                return []
            rows = conn.execute(f'SELECT * FROM "{table}" WHERE run_id=? ORDER BY "{order_column}"', (run_id,)).fetchall()
            return [self._decode_row_json(dict(row)) for row in rows]
        finally:
            conn.close()

    def list_findings(self, run_id: str) -> list[dict[str, Any]]:
        return self._list_run_table(run_id, "findings", "created_at")

    def list_patterns(self, run_id: str) -> list[dict[str, Any]]:
        return self._list_run_table(run_id, "creative_patterns", "created_at")

    def list_insights(self, run_id: str) -> list[dict[str, Any]]:
        return self._list_run_table(run_id, "insights", "created_at")

    def list_hypotheses(self, run_id: str) -> list[dict[str, Any]]:
        return self._list_run_table(run_id, "creative_hypotheses", "created_at")

    def list_briefs(self, run_id: str) -> list[dict[str, Any]]:
        return self._list_run_table(run_id, "media_briefs", "created_at")

    def get_report(self, run_id: str) -> dict[str, Any]:
        reports_dir = self.artifact_path(run_id, "reports")
        for name in ("final_report.md", "research_report.md", "report.md"):
            path = (reports_dir / name).resolve()
            if path.is_file():
                return {
                    "persisted_final_report": True,
                    "artifact": name,
                    "markdown": path.read_text(encoding="utf-8"),
                    "notice": None,
                }
        known = [name for name in ("metrics.json", "rankings.json", "voc.json", "findings.json", "pattern_report.json", "synthesis_request.json") if (reports_dir / name).is_file()]
        return {
            "persisted_final_report": False,
            "artifact": None,
            "markdown": None,
            "notice": "Final report not persisted for this run",
            "available_structured_artifacts": known,
        }
