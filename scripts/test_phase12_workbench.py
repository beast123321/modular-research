#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


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
            root = Path(td)
            build_fixture_run(root, "run_fixture")
            (root / "notes").mkdir()
            repo = RunRepository(root)
            self.assertEqual(repo.discover_runs(), ["run_fixture"])
            with self.assertRaises(ValueError):
                repo.run_dir("../escape")

    def test_sqlite_connection_is_query_only(self):
        from workbench_test_fixture import build_fixture_run
        from web.backend.run_repository import RunRepository

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            build_fixture_run(root)
            repo = RunRepository(root)
            conn = repo.open_db("run_fixture")
            try:
                with self.assertRaises(sqlite3.OperationalError):
                    conn.execute("CREATE TABLE forbidden(x INTEGER)")
            finally:
                conn.close()

    def test_summary_uses_artifacts_and_never_invents_cost(self):
        from workbench_test_fixture import build_fixture_run
        from web.backend.run_repository import RunRepository
        from web.backend.run_summary import build_run_summary

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            build_fixture_run(root)
            summary = build_run_summary(RunRepository(root), "run_fixture")
            self.assertEqual(summary.topic, "fixture topic")
            self.assertEqual(summary.video_count, 1)
            self.assertEqual(summary.provider_calls_attempted, 2)
            self.assertIsNone(summary.actual_estimated_cost_usd)


if __name__ == "__main__":
    unittest.main()
