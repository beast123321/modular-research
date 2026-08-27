#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
