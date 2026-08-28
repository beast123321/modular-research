#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


class Phase12HttpTests(unittest.TestCase):
    def _app_fixture(self, frontend_dist=None):
        from workbench_test_fixture import build_fixture_run
        from web.backend.app import create_app
        td = tempfile.TemporaryDirectory()
        runs_root = Path(td.name) / "runs"
        build_fixture_run(runs_root)
        app = create_app(runs_root, frontend_dist=frontend_dist)
        return td, app

    def test_health_and_runs_api_are_local_read_models(self):
        td, app = self._app_fixture(frontend_dist=None)
        try:
            client = TestClient(app)
            self.assertEqual(client.get("/api/health").status_code, 200)
            payload = client.get("/api/runs").json()
            self.assertEqual(payload[0]["run_id"], "run_fixture")
            self.assertEqual(payload[0]["video_count"], 1)
        finally:
            td.cleanup()

    def test_all_full_chain_routes_are_mounted(self):
        td, app = self._app_fixture(frontend_dist=None)
        try:
            client = TestClient(app)
            paths = [
                "/api/runs/run_fixture/flow",
                "/api/runs/run_fixture/videos",
                "/api/runs/run_fixture/creators",
                "/api/runs/run_fixture/comments",
                "/api/runs/run_fixture/voc",
                "/api/runs/run_fixture/evidence",
                "/api/runs/run_fixture/evidence/raw:fixture:0001",
                "/api/runs/run_fixture/lineage/raw:fixture:0001",
                "/api/runs/run_fixture/media",
                "/api/runs/run_fixture/findings",
                "/api/runs/run_fixture/patterns",
                "/api/runs/run_fixture/insights",
                "/api/runs/run_fixture/hypotheses",
                "/api/runs/run_fixture/briefs",
                "/api/runs/run_fixture/report",
                "/api/runs/run_fixture/execution",
            ]
            for path in paths:
                response = client.get(path)
                self.assertEqual(response.status_code, 200, (path, response.text))
        finally:
            td.cleanup()

    def test_api_404_is_not_swallowed_by_spa_fallback(self):
        from workbench_test_fixture import build_fixture_run
        from web.backend.app import create_app
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runs_root = root / "runs"
            build_fixture_run(runs_root)
            dist = root / "dist"
            dist.mkdir()
            (dist / "index.html").write_text("<html>Workbench</html>", encoding="utf-8")
            app = create_app(runs_root, frontend_dist=dist)
            client = TestClient(app)
            self.assertEqual(client.get("/api/does-not-exist").status_code, 404)
            spa = client.get("/runs/run_fixture")
            self.assertEqual(spa.status_code, 200)
            self.assertIn("Workbench", spa.text)

    def test_launcher_has_no_host_option_and_binds_loopback(self):
        text = (ROOT / "scripts" / "research_web.py").read_text(encoding="utf-8")
        self.assertNotIn('add_argument("--host"', text)
        self.assertIn('host="127.0.0.1"', text)


if __name__ == "__main__":
    unittest.main()
