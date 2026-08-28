#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def _fixture_repo():
    from workbench_test_fixture import build_fixture_run
    from web.backend.run_repository import RunRepository
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    build_fixture_run(root)
    return td, RunRepository(root)


class Phase12FixtureTests(unittest.TestCase):
    def test_requirements_include_web_runtime(self):
        text = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
        for dep in ["fastapi", "uvicorn", "httpx"]:
            self.assertIn(dep, text)

    def test_fixture_builds_complete_read_only_run_shape(self):
        from workbench_test_fixture import build_fixture_run
        with tempfile.TemporaryDirectory() as td:
            run_dir = build_fixture_run(Path(td))
            self.assertTrue((run_dir / "plan.json").exists())
            self.assertTrue((run_dir / "execution.json").exists())
            self.assertTrue((run_dir / "run.sqlite").exists())
            self.assertTrue((run_dir / "raw").is_dir())
            self.assertTrue((run_dir / "reports" / "findings.json").exists())


class Phase12RunRepositoryTests(unittest.TestCase):
    def test_repository_discovers_only_run_directories_and_rejects_traversal(self):
        from workbench_test_fixture import build_fixture_run
        from web.backend.run_repository import RunRepository
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); build_fixture_run(root, "run_fixture"); (root / "notes").mkdir()
            repo = RunRepository(root)
            self.assertEqual(repo.discover_runs(), ["run_fixture"])
            with self.assertRaises(ValueError): repo.run_dir("../escape")

    def test_sqlite_connection_is_query_only(self):
        td, repo = _fixture_repo()
        try:
            conn = repo.open_db("run_fixture")
            try:
                with self.assertRaises(sqlite3.OperationalError): conn.execute("CREATE TABLE forbidden(x INTEGER)")
            finally: conn.close()
        finally: td.cleanup()

    def test_summary_uses_artifacts_and_never_invents_cost(self):
        from web.backend.run_summary import build_run_summary
        td, repo = _fixture_repo()
        try:
            summary = build_run_summary(repo, "run_fixture")
            self.assertEqual(summary.topic, "fixture topic")
            self.assertEqual(summary.video_count, 1)
            self.assertEqual(summary.provider_calls_attempted, 2)
            self.assertIsNone(summary.actual_estimated_cost_usd)
        finally: td.cleanup()


class Phase12FlowTests(unittest.TestCase):
    def test_stage_flow_preserves_execution_basis_and_maps_local_states(self):
        from web.backend.flow_service import build_stage_flow
        td, repo = _fixture_repo()
        try:
            by_name = {row.name: row for row in build_stage_flow(repo, "run_fixture")}
            self.assertEqual(by_name["REFERENCE_SEED"].status, "COMPLETED")
            self.assertEqual(by_name["REFERENCE_SEED"].status_basis, "execution")
            self.assertEqual(by_name["VIDEO_UNDERSTANDING"].status, "PLANNED")
        finally: td.cleanup()

    def test_execution_summary_separates_plan_and_actual(self):
        from web.backend.flow_service import build_execution_summary
        td, repo = _fixture_repo()
        try:
            result = build_execution_summary(repo, "run_fixture")
            self.assertEqual(result.expected_requests, 2)
            self.assertEqual(result.calls_attempted, 2)
            self.assertIsNone(result.actual_estimated_cost_usd)
        finally: td.cleanup()


class Phase12EntityTests(unittest.TestCase):
    def test_videos_are_paginated_and_reject_unknown_sort(self):
        td, repo = _fixture_repo()
        try:
            page = repo.list_videos("run_fixture", page=1, page_size=20, sort="views", order="desc")
            self.assertEqual(page.total, 1)
            self.assertEqual(page.items[0]["video_id"], "video_fixture")
            self.assertEqual(page.items[0]["views"], 10000)
            with self.assertRaises(ValueError): repo.list_videos("run_fixture", page=1, page_size=20, sort="DROP TABLE videos", order="desc")
        finally: td.cleanup()

    def test_voc_uses_real_comment_denominator(self):
        td, repo = _fixture_repo()
        try:
            voc = repo.get_voc("run_fixture")
            self.assertEqual(voc["denominator"], 1)
            labels = {row["label"]: row for row in voc["labels"]}
            self.assertEqual(labels["authenticity"]["count"], 1)
            self.assertEqual(labels["authenticity"]["share"], 1.0)
        finally: td.cleanup()


class Phase12EvidenceTests(unittest.TestCase):
    def test_evidence_detail_redacts_stored_secret_fields_again(self):
        from web.backend.lineage_service import get_evidence
        td, repo = _fixture_repo()
        try:
            detail = get_evidence(repo, "run_fixture", "raw:fixture:0001")
            serialized = json.dumps(detail)
            self.assertNotIn("Bearer fixture-secret-must-redact", serialized)
            self.assertNotIn("fixture-api-key-must-redact", serialized)
        finally: td.cleanup()

    def test_lineage_contains_only_stored_references(self):
        from web.backend.lineage_service import build_lineage
        td, repo = _fixture_repo()
        try:
            graph = build_lineage(repo, "run_fixture", "raw:fixture:0001")
            relations = {(e.source_type, e.target_type, e.relation) for e in graph.edges}
            self.assertIn(("raw_evidence", "video", "normalized_as"), relations)
            self.assertFalse(any(e.target_id == "invented" for e in graph.edges))
        finally: td.cleanup()


class Phase12MediaIntelligenceTests(unittest.TestCase):
    def test_keyframe_resolver_rejects_path_outside_run(self):
        from web.backend.media_service import resolve_keyframe_path
        td, repo = _fixture_repo()
        try:
            db = repo.run_dir("run_fixture") / "run.sqlite"
            outside = repo.runs_root.parent / "outside.jpg"
            conn = sqlite3.connect(db)
            try:
                conn.execute(
                    "INSERT INTO media_keyframes(id,run_id,video_id,timestamp_sec,local_path,scene_index,ocr_text,ocr_confidence,evidence_refs_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("frame-outside", "run_fixture", "video_fixture", 1.0, str(outside), 1, None, None, "[]", "2026-08-27T00:00:00+00:00"),
                )
                conn.commit()
            finally:
                conn.close()
            with self.assertRaises(ValueError):
                resolve_keyframe_path(repo, "run_fixture", "video_fixture", "frame-outside")
        finally: td.cleanup()

    def test_media_detail_includes_keyframes_transcript_and_creative_analysis(self):
        td, repo = _fixture_repo()
        try:
            media = repo.get_media("run_fixture", "video_fixture")
            self.assertEqual(media["asset"]["status"], "not_downloaded")
            self.assertEqual(media["keyframes"][0]["ocr_text"], "领导说方案不行")
            self.assertEqual(media["transcripts"][0]["text"], "领导说方案不行")
            self.assertEqual(media["creative_analysis"][0]["analyzer_name"], "fixture-agent")
        finally: td.cleanup()

    def test_report_does_not_fabricate_missing_final_report(self):
        td, repo = _fixture_repo()
        try:
            (repo.run_dir("run_fixture") / "reports" / "final_report.md").unlink()
            report = repo.get_report("run_fixture")
            self.assertFalse(report["persisted_final_report"])
            self.assertIn("Final report not persisted", report["notice"])
        finally: td.cleanup()

    def test_persisted_final_report_is_returned_verbatim(self):
        td, repo = _fixture_repo()
        try:
            report = repo.get_report("run_fixture")
            self.assertTrue(report["persisted_final_report"])
            self.assertEqual(report["artifact"], "final_report.md")
            self.assertIn("Fixture Research Report", report["markdown"])
        finally: td.cleanup()

    def test_intelligence_preserves_evidence_refs(self):
        td, repo = _fixture_repo()
        try:
            findings = repo.list_findings("run_fixture")
            self.assertEqual(findings[0]["evidence_refs"], ["raw:fixture:0001"])
            hypotheses = repo.list_hypotheses("run_fixture")
            self.assertEqual(hypotheses[0]["status"], "PROPOSED")
            self.assertEqual(hypotheses[0]["evidence_refs"], ["raw:fixture:0001"])
        finally: td.cleanup()


if __name__ == "__main__":
    unittest.main()
