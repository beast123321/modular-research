#!/usr/bin/env python3
"""v1.2.1 bounded business pilot controls tests."""
from __future__ import annotations

import unittest

from research_request import ResearchRequest
from stage_planner import build_stage_plan
from run_research import validate_v2_execution_gate


def make_pilot_request() -> ResearchRequest:
    return ResearchRequest.from_dict(
        {
            "topic": "wood bead bracelet",
            "platform": "tiktok",
            "market": "US",
            "language": "en",
            "research_goals": ["hooks", "voc", "ads_analysis"],
            "depth": "quick",
            "sample_size_overrides": {
                "candidate_limit": 10,
                "creator_limit": 1,
                "comment_video_limit": 2,
                "comment_pages": 1,
                "ads_limit": 4,
                "ad_deep_limit": 1,
                "top_contents_detail_limit": 1,
            },
        }
    )


class TikTokSampleOverrideTests(unittest.TestCase):
    def test_tiktok_planner_applies_bounded_pilot_overrides(self):
        plan = build_stage_plan(make_pilot_request())
        tasks = {task.capability: task for stage in plan.stages for task in stage.tasks}

        self.assertEqual(tasks["top_contents_list"].static_calls[0]["limit"], 10)
        self.assertEqual(tasks["top_contents_item_detail"].max_items, 1)
        self.assertEqual(tasks["creator_posts"].max_items, 1)
        self.assertEqual(tasks["video_metrics"].max_items, 2)
        self.assertEqual(tasks["video_comments"].max_items, 2)
        self.assertEqual(tasks["video_comments"].pages_per_item, 1)
        self.assertEqual(tasks["video_comments"].max_requests, 2)
        self.assertEqual(tasks["ads_search"].static_calls[0]["limit"], 4)
        self.assertEqual(tasks["top_ads_spotlight"].static_calls[0]["limit"], 4)
        self.assertEqual(tasks["ads_detail"].max_items, 1)
        self.assertEqual(tasks["ad_percentile"].max_items, 1)
        self.assertEqual(tasks["ad_keyframe_analysis"].max_items, 1)
        self.assertEqual(tasks["ad_interactive_analysis"].max_items, 1)
        self.assertLessEqual(plan.total_max_requests, 20)

    def test_invalid_tiktok_override_is_rejected(self):
        request = make_pilot_request()
        request.sample_size_overrides["creator_limit"] = 0
        with self.assertRaisesRegex(ValueError, "sample_size_overrides.creator_limit"):
            build_stage_plan(request)


class TikTokEvidenceGateTests(unittest.TestCase):
    def test_plan_marks_capability_verification_status(self):
        plan = build_stage_plan(make_pilot_request())
        tasks = {task.capability: task for stage in plan.stages for task in stage.tasks}
        self.assertEqual(tasks["ads_search"].verification_status, "live_verified")
        self.assertEqual(tasks["ad_keyframe_analysis"].verification_status, "documented")
        payload = plan.to_dict()
        serialized = {
            task["capability"]: task["verification_status"]
            for stage in payload["stages"]
            for task in stage["tasks"]
        }
        self.assertEqual(serialized["top_contents_item_detail"], "documented")

    def test_execution_gate_blocks_documented_capabilities_by_default(self):
        plan = build_stage_plan(make_pilot_request())
        ok, reason = validate_v2_execution_gate(
            plan,
            yes=True,
            max_budget_usd=plan.max_cost_usd,
        )
        self.assertFalse(ok)
        self.assertIn("documented", reason.lower())
        self.assertIn("ad_keyframe_analysis", reason)
        self.assertIn("top_contents_item_detail", reason)

    def test_execution_gate_allows_explicit_documented_opt_in(self):
        plan = build_stage_plan(make_pilot_request())
        ok, reason = validate_v2_execution_gate(
            plan,
            yes=True,
            max_budget_usd=plan.max_cost_usd,
            allow_documented_capabilities=True,
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "approved")


if __name__ == "__main__":
    unittest.main()
