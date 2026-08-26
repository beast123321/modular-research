#!/usr/bin/env python3
"""Phase 9 Douyin Video Intelligence tests."""
from __future__ import annotations

import unittest

from endpoint_registry import EndpointRegistry
from profile_resolver import resolve_profile
from research_request import ResearchRequest
from reference_resolver import resolve_reference_content
from stage_planner import build_stage_plan


class ReferenceInputTests(unittest.TestCase):
    def test_research_request_round_trips_reference_content(self):
        url = (
            "https://www.douyin.com/jingxuan/search/%E4%BA%BA%E6%83%85%E4%B8%96%E6%95%85"
            "?modal_id=7667541271225140069&type=general"
        )
        request = ResearchRequest.from_dict(
            {
                "topic": "职场高情商接话",
                "platform": "douyin",
                "research_goals": ["hooks", "voc"],
                "reference_content": [
                    {"platform": "douyin", "url": url, "role": "style_reference"}
                ],
            }
        )
        self.assertEqual(len(request.reference_content), 1)
        self.assertEqual(request.reference_content[0]["platform"], "douyin")
        self.assertEqual(request.reference_content[0]["role"], "style_reference")
        self.assertEqual(request.to_dict()["reference_content"][0]["url"], url)

    def test_modal_id_is_resolved_locally_without_provider_fallback(self):
        resolved = resolve_reference_content(
            {
                "platform": "douyin",
                "url": "https://www.douyin.com/jingxuan/search/x?modal_id=7667541271225140069&type=general",
                "role": "style_reference",
            }
        )
        self.assertEqual(resolved["content_id"], "7667541271225140069")
        self.assertEqual(resolved["resolution_status"], "resolved_local")
        self.assertFalse(resolved["provider_fallback_required"])

    def test_direct_video_path_is_resolved_locally(self):
        resolved = resolve_reference_content(
            {"platform": "douyin", "url": "https://www.douyin.com/video/7592116912205630761"}
        )
        self.assertEqual(resolved["content_id"], "7592116912205630761")
        self.assertFalse(resolved["provider_fallback_required"])

    def test_short_share_url_requires_provider_fallback(self):
        resolved = resolve_reference_content(
            {"platform": "douyin", "url": "https://v.douyin.com/e3x2fjE/"}
        )
        self.assertIsNone(resolved["content_id"])
        self.assertEqual(resolved["resolution_status"], "provider_required")
        self.assertTrue(resolved["provider_fallback_required"])


class DouyinProfileAndEndpointTests(unittest.TestCase):
    def test_creative_goals_route_to_douyin_video_intelligence(self):
        request = ResearchRequest.from_dict(
            {"topic": "职场高情商接话", "platform": "douyin", "research_goals": ["hooks", "creative_patterns", "voc"]}
        )
        self.assertEqual(resolve_profile(request).profile_id, "douyin-video-intelligence-v1")

    def test_reference_content_promotes_douyin_video_intelligence(self):
        request = ResearchRequest.from_dict(
            {
                "topic": "职场",
                "platform": "douyin",
                "research_goals": ["content_opportunities"],
                "reference_content": [{"url": "https://www.douyin.com/video/7592116912205630761", "role": "style_reference"}],
            }
        )
        resolution = resolve_profile(request)
        self.assertEqual(resolution.profile_id, "douyin-video-intelligence-v1")
        self.assertIn("REFERENCE_CONTENT", resolution.reason_codes)

    def test_lightweight_trend_only_request_preserves_topic_radar(self):
        request = ResearchRequest.from_dict({"topic": "职场", "platform": "douyin", "research_goals": ["trend_discovery"]})
        self.assertEqual(resolve_profile(request).profile_id, "douyin-topic-radar-v1")

    def test_ads_goals_do_not_route_to_douyin_video_intelligence_v1(self):
        request = ResearchRequest.from_dict({"topic": "职场", "platform": "douyin", "research_goals": ["ads_analysis"]})
        with self.assertRaises(ValueError):
            resolve_profile(request)

    def test_current_douyin_app_v3_endpoint_contracts(self):
        registry = EndpointRegistry()
        expected = {
            "video_search": ("POST", "/api/v1/douyin/search/fetch_video_search_v1", "json"),
            "video_detail_v3": ("GET", "/api/v1/douyin/app/v3/fetch_one_video_v3", "query"),
            "video_detail_by_share_url_v3": ("GET", "/api/v1/douyin/app/v3/fetch_one_video_by_share_url", "query"),
            "video_comments_v3": ("GET", "/api/v1/douyin/app/v3/fetch_video_comments", "query"),
            "creator_posts_v3": ("GET", "/api/v1/douyin/app/v3/fetch_user_post_videos", "query"),
            "user_profile_v3": ("GET", "/api/v1/douyin/app/v3/handler_user_profile", "query"),
            "video_statistics_v3": ("GET", "/api/v1/douyin/app/v3/fetch_video_statistics", "query"),
        }
        for capability, contract in expected.items():
            with self.subTest(capability=capability):
                entry = registry.get("tikhub", "douyin", capability)
                self.assertEqual((entry["method"], entry["path"], entry["request_location"]), contract)
                if capability != "video_search":
                    self.assertEqual(entry["status"], "documented")


class DouyinPlannerTests(unittest.TestCase):
    @staticmethod
    def _request(*, reference_url=None, goals=None, depth="quick"):
        payload = {
            "topic": "职场高情商接话",
            "platform": "douyin",
            "research_goals": goals or ["hooks", "creator_analysis", "voc"],
            "time_range": {"days": 90},
            "seed_keywords": ["人情世故", "职场生存法则"],
            "depth": depth,
        }
        if reference_url:
            payload["reference_content"] = [{"url": reference_url, "role": "style_reference"}]
        return ResearchRequest.from_dict(payload)

    def test_direct_reference_builds_zero_resolution_reference_seed(self):
        request = self._request(reference_url="https://www.douyin.com/jingxuan/search/x?modal_id=7667541271225140069&type=general")
        plan = build_stage_plan(request)
        self.assertEqual(plan.profile_id, "douyin-video-intelligence-v1")
        names = [stage.name for stage in plan.stages]
        self.assertEqual(names[0], "REFERENCE_SEED")
        self.assertIn("ORGANIC_DISCOVERY", names)
        self.assertIn("CREATOR_CONTEXT", names)
        self.assertIn("VOC", names)
        self.assertIn("VIDEO_UNDERSTANDING", names)
        self.assertNotIn("ADS_DISCOVERY", names)
        ref_stage = plan.stages[0]
        detail = next(task for task in ref_stage.tasks if task.capability == "video_detail_v3")
        self.assertEqual(detail.static_calls, [{"aweme_id": "7667541271225140069"}])
        self.assertFalse(any(task.capability == "video_detail_by_share_url_v3" for task in ref_stage.tasks))

    def test_short_share_reference_uses_provider_fallback(self):
        plan = build_stage_plan(self._request(reference_url="https://v.douyin.com/e3x2fjE/"))
        ref_stage = next(stage for stage in plan.stages if stage.name == "REFERENCE_SEED")
        fallback = next(task for task in ref_stage.tasks if task.capability == "video_detail_by_share_url_v3")
        self.assertEqual(fallback.static_calls, [{"share_url": "https://v.douyin.com/e3x2fjE/"}])

    def test_search_contract_uses_douyin_first_page_fields(self):
        plan = build_stage_plan(self._request())
        search = next(task for stage in plan.stages for task in stage.tasks if task.capability == "video_search")
        self.assertEqual(search.method, "POST")
        self.assertEqual(search.request_location, "json")
        self.assertTrue(search.static_calls)
        first = search.static_calls[0]
        self.assertEqual(first["keyword"], "职场高情商接话")
        self.assertEqual(first["cursor"], 0)
        self.assertEqual(first["search_id"], "")
        self.assertEqual(first["backtrace"], "")
        self.assertEqual(first["content_type"], "1")
        self.assertEqual(first["filter_duration"], "0")
        self.assertIn(first["sort_type"], {"0", "1", "2"})
        self.assertEqual(first["publish_time"], "180")

    def test_metrics_enrichment_is_batch_two_and_comments_keep_count_twenty(self):
        plan = build_stage_plan(self._request(depth="standard"))
        stats = next(task for stage in plan.stages for task in stage.tasks if task.capability == "video_statistics_v3")
        comments = next(task for stage in plan.stages for task in stage.tasks if task.capability == "video_comments_v3")
        self.assertEqual(stats.mode, "per_video_batch2")
        self.assertGreater(stats.max_items, 0)
        self.assertEqual(comments.variants, [{"cursor": 0, "count": 20}])
        self.assertEqual(comments.pages_per_item, 3)

    def test_douyin_plan_never_contains_ads_stages(self):
        plan = build_stage_plan(self._request(goals=["hooks", "creative_patterns", "voc"]))
        names = [stage.name for stage in plan.stages]
        self.assertNotIn("ADS_DISCOVERY", names)
        self.assertNotIn("CREATIVE_ANALYSIS", names)
        self.assertIn("PATTERN_MINING", names)
        self.assertIn("HYPOTHESES", names)
        self.assertIn("BRIEFS", names)


if __name__ == "__main__":
    unittest.main()
