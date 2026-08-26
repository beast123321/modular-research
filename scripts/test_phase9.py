#!/usr/bin/env python3
"""Phase 9 Douyin Video Intelligence tests."""
from __future__ import annotations

import unittest

from endpoint_registry import EndpointRegistry
from profile_resolver import resolve_profile
from research_request import ResearchRequest
from reference_resolver import resolve_reference_content


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
            {
                "topic": "职场高情商接话",
                "platform": "douyin",
                "research_goals": ["hooks", "creative_patterns", "voc"],
            }
        )
        resolution = resolve_profile(request)
        self.assertEqual(resolution.profile_id, "douyin-video-intelligence-v1")

    def test_lightweight_trend_only_request_preserves_topic_radar(self):
        request = ResearchRequest.from_dict(
            {
                "topic": "职场",
                "platform": "douyin",
                "research_goals": ["trend_discovery"],
            }
        )
        self.assertEqual(resolve_profile(request).profile_id, "douyin-topic-radar-v1")

    def test_ads_goals_do_not_route_to_douyin_video_intelligence_v1(self):
        request = ResearchRequest.from_dict(
            {
                "topic": "职场",
                "platform": "douyin",
                "research_goals": ["ads_analysis"],
            }
        )
        with self.assertRaises(ValueError):
            resolve_profile(request)

    def test_current_douyin_app_v3_endpoint_contracts(self):
        registry = EndpointRegistry()
        expected = {
            "video_search": ("POST", "/api/v1/douyin/search/fetch_video_search_v1", "json"),
            "video_detail": ("GET", "/api/v1/douyin/app/v3/fetch_one_video_v3", "query"),
            "video_detail_by_share_url": ("GET", "/api/v1/douyin/app/v3/fetch_one_video_by_share_url", "query"),
            "video_comments": ("GET", "/api/v1/douyin/app/v3/fetch_video_comments", "query"),
            "creator_posts": ("GET", "/api/v1/douyin/app/v3/fetch_user_post_videos", "query"),
            "user_profile": ("GET", "/api/v1/douyin/app/v3/handler_user_profile", "query"),
            "video_statistics": ("GET", "/api/v1/douyin/app/v3/fetch_video_statistics", "query"),
        }
        for capability, contract in expected.items():
            with self.subTest(capability=capability):
                entry = registry.get("tikhub", "douyin", capability)
                self.assertEqual((entry["method"], entry["path"], entry["request_location"]), contract)
                self.assertEqual(entry["status"], "documented")


if __name__ == "__main__":
    unittest.main()
