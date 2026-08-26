#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


class Phase8VersionTests(unittest.TestCase):
    def test_version_is_semver_1_0_0(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(version, "1.0.0")
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")


class Phase8EnvironmentTests(unittest.TestCase):
    def test_core_readiness_only_requires_supported_python(self):
        from check_environment import evaluate_readiness
        report = {"python": {"supported": True}, "modules": {}, "commands": {}}
        ready, missing = evaluate_readiness(report, "core")
        self.assertTrue(ready)
        self.assertEqual(missing, [])

    def test_video_readiness_requires_numpy_and_cv2(self):
        from check_environment import evaluate_readiness
        report = {"python": {"supported": True}, "modules": {"numpy": True, "cv2": False}, "commands": {}}
        ready, missing = evaluate_readiness(report, "video")
        self.assertFalse(ready)
        self.assertIn("module:cv2", missing)


class Phase8ReleaseAuditTests(unittest.TestCase):
    def test_release_audit_accepts_repository(self):
        from release_check import audit_repository
        report = audit_repository(ROOT)
        self.assertTrue(report["ok"], report)

    def test_release_audit_rejects_plaintext_config_key(self):
        from release_check import audit_repository
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ["VERSION", "README.md", "SKILL.md", "requirements.txt"]:
                (root / name).write_text("1.0.0" if name == "VERSION" else "x", encoding="utf-8")
            (root / "config.example.json").write_text(json.dumps({"api_key": "secret"}), encoding="utf-8")
            (root / "scripts" / "media").mkdir(parents=True)
            report = audit_repository(root)
            self.assertFalse(report["ok"])
            self.assertTrue(any("api_key" in x for x in report["issues"]))


class Phase8DistributionTests(unittest.TestCase):
    def test_readme_documents_safe_first_run(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for token in ["TIKHUB_API_KEY", "--plan-only", "--max-budget-usd", "ResearchRequest"]:
            self.assertIn(token, text)

    def test_requirements_include_video_dependencies(self):
        text = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
        for dep in ["numpy", "opencv-python-headless", "pillow", "pytesseract", "openpyxl"]:
            self.assertIn(dep, text)

    def test_ci_runs_full_offline_suite_and_never_live_validation_execute(self):
        text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("test_phase8.py", text)
        self.assertIn("test_skill.py", text)
        self.assertIn("release_check.py", text)
        self.assertNotIn("live_validation.py --execute", text)

    def test_gitignore_does_not_hide_source_media_package(self):
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("/media/", text)
        self.assertNotRegex(text, r"(?m)^media/$")
        self.assertTrue((ROOT / "scripts" / "media" / "video.py").exists())


if __name__ == "__main__":
    unittest.main()
