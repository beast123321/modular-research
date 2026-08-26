#!/usr/bin/env python3
"""Regression tests for bounded Douyin Video Intelligence sampling."""
from __future__ import annotations

from pathlib import Path
import unittest

from research_request import ResearchRequest
from stage_planner import build_stage_plan

ROOT = Path(__file__).resolve().parent.parent


class DouyinBudgetPlannerTests(unittest.TestCase):
    @staticmethod
    def _request(overrides=None):
        payload = {
            "topic": "职场高情商接话",
            "platform": "douyin",
            "research_goals": [
                "low_follower_breakouts",
                "trend_discovery",
                "hooks",
                "creative_patterns",
                "selling_angles",
                "formats",
                "creator_analysis",
                "voc",
                "content_opportunities",
            ],
            "time_range": {"days": 90},
            "reference_content": [
                {
                    "url": "https://www.douyin.com/jingxuan/search/x?modal_id=7667541271225140069&type=general",
                    "role": "style_reference",
                }
            ],
            "depth": "standard",
        }
        if overrides is not None:
            payload["sample_size_overrides"] = overrides
        return ResearchRequest.from_dict(payload)

    @staticmethod
    def _task(plan, capability):
        return next(
            task
            for stage in plan.stages
            for task in stage.tasks
            if task.capability == capability
        )

    def test_patch_release_version_is_1_1_1(self):
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), "1.1.1")

    def test_standard_single_topic_plan_bounds_paid_enrichment(self):
        plan = build_stage_plan(self._request())
        stats = self._task(plan, "video_statistics_v3")
        posts = self._task(plan, "creator_posts_v3")
        profile = self._task(plan, "user_profile_v3")
        comments = self._task(plan, "video_comments_v3")

        self.assertEqual(stats.max_items, 20)
        self.assertEqual(stats.expected_requests, 10)
        self.assertEqual(posts.max_items, 6)
        self.assertEqual(len(posts.variants), 2)
        self.assertEqual(profile.max_items, 6)
        self.assertEqual(comments.max_items, 6)
        self.assertEqual(comments.pages_per_item, 3)
        self.assertEqual(plan.total_expected_requests, 38)
        self.assertEqual(plan.total_max_requests, 50)
        self.assertLessEqual(plan.max_cost_usd, 0.05)

    def test_sample_size_overrides_drive_network_sampling_and_stats_are_capped_by_candidate_pool(self):
        plan = build_stage_plan(
            self._request(
                {
                    "candidate_limit": 9,
                    "statistics_video_limit": 20,
                    "creator_limit": 2,
                    "comment_video_limit": 3,
                    "comment_pages": 2,
                }
            )
        )
        stats = self._task(plan, "video_statistics_v3")
        posts = self._task(plan, "creator_posts_v3")
        profile = self._task(plan, "user_profile_v3")
        comments = self._task(plan, "video_comments_v3")

        self.assertEqual(stats.max_items, 9)
        self.assertEqual(stats.expected_requests, 5)
        self.assertEqual(posts.max_items, 2)
        self.assertEqual(profile.max_items, 2)
        self.assertEqual(comments.max_items, 3)
        self.assertEqual(comments.pages_per_item, 2)
        self.assertEqual(comments.expected_requests, 3)
        self.assertEqual(comments.max_requests, 6)


if __name__ == "__main__":
    unittest.main()
