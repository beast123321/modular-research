#!/usr/bin/env python3
"""Phase 9 CLI ergonomics and release-version tests."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest

import run_research

ROOT = Path(__file__).resolve().parent.parent


class Phase9ReleaseVersionTests(unittest.TestCase):
    def test_phase9_release_candidate_is_1_1_0(self):
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), "1.1.0")


class ReferenceUrlCliTests(unittest.TestCase):
    def test_reference_url_becomes_canonical_reference_content(self):
        url = "https://www.douyin.com/jingxuan/search/x?modal_id=7667541271225140069&type=general"
        args = SimpleNamespace(
            request=None,
            topic="职场高情商接话",
            platform="douyin",
            market=None,
            research_goal=["hooks", "voc"],
            depth="quick",
            reference_url=[url],
            goal=None,
        )
        request = run_research.load_research_request_from_args(args)
        self.assertIsNotNone(request)
        self.assertEqual(
            request.reference_content,
            [{"platform": "douyin", "url": url, "content_id": None, "role": "style_reference"}],
        )
        plan = run_research.build_v2_stage_plan(request)
        self.assertEqual(plan.profile_id, "douyin-video-intelligence-v1")
        detail = next(
            task
            for stage in plan.stages
            for task in stage.tasks
            if task.capability == "video_detail_v3"
        )
        self.assertEqual(detail.static_calls, [{"aweme_id": "7667541271225140069"}])

    def test_request_file_cannot_be_mixed_with_reference_url(self):
        args = SimpleNamespace(
            request="request.json",
            topic=None,
            platform=None,
            market=None,
            research_goal=[],
            depth="standard",
            reference_url=["https://v.douyin.com/example/"],
            goal=None,
        )
        with self.assertRaisesRegex(ValueError, "cannot mix --request"):
            run_research.load_research_request_from_args(args)


if __name__ == "__main__":
    unittest.main()
