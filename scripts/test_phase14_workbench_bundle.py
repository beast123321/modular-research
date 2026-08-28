#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


class Phase14WorkbenchBundleTests(unittest.TestCase):
    def test_committed_frontend_bundle_serves_spa_and_api_without_node_runtime(self):
        from workbench_test_fixture import build_fixture_run
        from web.backend.app import create_app

        dist = ROOT / "web" / "frontend" / "dist"
        self.assertTrue((dist / "index.html").is_file(), "committed Workbench dist/index.html is required")
        assets = dist / "assets"
        self.assertTrue(assets.is_dir(), "committed Workbench dist/assets is required")
        self.assertTrue(any(path.is_file() for path in assets.rglob("*")), "committed Workbench assets must not be empty")

        with tempfile.TemporaryDirectory() as td:
            runs_root = Path(td) / "runs"
            build_fixture_run(runs_root)
            client = TestClient(create_app(runs_root, frontend_dist=dist))
            root = client.get("/")
            self.assertEqual(root.status_code, 200)
            self.assertIn("id=\"root\"", root.text)
            self.assertEqual(client.get("/api/health").status_code, 200)
            self.assertEqual(client.get("/api/runs").json()[0]["run_id"], "run_fixture")
            fallback = client.get("/runs/run_fixture/execution")
            self.assertEqual(fallback.status_code, 200)
            self.assertIn("id=\"root\"", fallback.text)

    def test_python_launcher_does_not_start_node_or_npm(self):
        launcher = (ROOT / "scripts" / "research_web.py").read_text(encoding="utf-8")
        self.assertNotIn("subprocess", launcher)
        self.assertNotIn("npm run", launcher)
        self.assertNotIn("node ", launcher)
        self.assertIn('host="127.0.0.1"', launcher)


if __name__ == "__main__":
    unittest.main()
