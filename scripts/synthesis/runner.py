"""Phase 6 deterministic pattern preparation and host-agent synthesis request generation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from analysis.patterns import mine_patterns
from evidence_store import EvidenceStore
from synthesis.agent_bridge import build_synthesis_request


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_context(store: EvidenceStore, run_id: str) -> tuple[str | None, list[dict[str, Any]], dict[str, Any]]:
    row = store.conn.execute("SELECT request_json FROM research_runs WHERE id=?", (run_id,)).fetchone()
    topic = None
    if row:
        try: topic = (json.loads(row[0]) or {}).get("topic")
        except Exception: topic = None
    observations = []
    for rec in store.conn.execute("SELECT id,category,statement,evidence_refs_json,metrics_json,support_count FROM findings WHERE run_id=? ORDER BY id", (run_id,)):
        observations.append({"id":rec[0],"finding_type":"OBSERVATION","category":rec[1],"statement":rec[2],"evidence_refs":json.loads(rec[3] or "[]"),"metrics":json.loads(rec[4] or "{}"),"support_count":rec[5]})
    labels: dict[str, dict[str, Any]] = {}
    sample_size = store.conn.execute("SELECT COUNT(*) FROM comment_labels WHERE run_id=?", (run_id,)).fetchone()[0]
    for labels_json, intensity, refs_json in store.conn.execute("SELECT labels_json,weighted_intensity,evidence_refs_json FROM comment_labels WHERE run_id=?", (run_id,)):
        try: row_labels = json.loads(labels_json or "[]"); refs = json.loads(refs_json or "[]")
        except json.JSONDecodeError: continue
        for label in row_labels:
            rec = labels.setdefault(str(label), {"count":0,"weighted_intensity":0.0,"evidence_refs":[]}); rec["count"] += 1; rec["weighted_intensity"] += float(intensity or 0.0)
            for ref in refs:
                if ref not in rec["evidence_refs"]: rec["evidence_refs"].append(ref)
    for rec in labels.values(): rec["share"] = rec["count"] / sample_size if sample_size else 0.0
    return topic, observations, {"sample_size":sample_size,"labels":labels}


def prepare_synthesis(db_path: str | Path, run_dir: str | Path, run_id: str) -> dict[str, Any]:
    run_dir = Path(run_dir); patterns = mine_patterns(db_path, run_id); store = EvidenceStore(db_path)
    try:
        store.replace_patterns(run_id, patterns); topic, observations, voc_summary = _load_context(store, run_id)
    finally: store.close()
    pattern_report = {"run_id":run_id,"analysis_mode":"deterministic_association","causality_note":"Pattern lift measures association within the observed sample; it does not prove causality.","patterns":[{**row,"reference":f"pattern:{row['id']}"} for row in patterns]}
    request = build_synthesis_request(run_id=run_id, patterns=pattern_report["patterns"], observations=observations, voc_summary=voc_summary, topic=topic)
    reports = run_dir / "reports"; _write(reports / "pattern_report.json", pattern_report); _write(reports / "synthesis_request.json", request)
    return {"run_id":run_id,"pattern_count":len(patterns),"insights_generated":0,"hypotheses_generated":0,"media_briefs_generated":0,"semantic_status":"awaiting_host_agent"}
