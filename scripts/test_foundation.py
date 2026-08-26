#!/usr/bin/env python3
"""Modular Research V2 Phase 1 foundation tests (stdlib unittest, offline)."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))


class ResearchRequestTests(unittest.TestCase):
    def setUp(self):
        from research_request import ResearchRequest
        self.ResearchRequest = ResearchRequest

    def test_valid_request_round_trip(self):
        data = {
            "schema_version": "1.0",
            "topic": "standing desk",
            "platform": "tiktok",
            "market": "US",
            "language": "en",
            "research_goals": ["creative_patterns", "voc"],
            "time_range": {"days": 90},
            "content_scope": {"organic": True, "ads": True, "comments": True},
            "depth": "standard",
            "outputs": ["evidence", "findings"],
            "user_goal_text": "ç ”ç©µç¾Žå›½ TikTok standing desk è§†é¢‘",
        }
        req = self.ResearchRequest.from_dict(data)
        self.assertEqual(req.to_dict()["topic"], "standing desk")
        self.assertEqual(req.to_dict()["research_goals"], ["creative_patterns", "voc"])
        self.assertEqual(req.to_dict()["user_goal_text"], data["user_goal_text"])

    def test_platform_is_normalized(self):
        req = self.ResearchRequest.from_dict({
            "topic": "desk", "platform": "TikTok", "market": "us",
            "research_goals": ["hooks"],
        })
        self.assertEqual(req.platform, "tiktok")
        self.assertEqual(req.market, "US")

    def test_depth_defaults_to_standard(self):
        req = self.ResearchRequest.from_dict({
            "topic": "desk", "platform": "tiktok", "market": "US",
            "research_goals": ["hooks"],
        })
        self.assertEqual(req.depth, "standard")

    def test_empty_topic_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "topic"):
            self.ResearchRequest.from_dict({
                "topic": " ", "platform": "tiktok", "market": "US",
                "research_goals": ["hooks"],
            })

    def test_invalid_depth_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "depth"):
            self.ResearchRequest.from_dict({
                "topic": "desk", "platform": "tiktok", "market": "US",
                "research_goals": ["hooks"], "depth": "huge",
            })

    def test_unknown_goal_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "research_goals"):
            self.ResearchRequest.from_dict({
                "topic": "desk", "platform": "tiktok", "market": "US",
                "research_goals": ["make_me_viral"],
            })

    def test_tiktok_request_without_market_reports_material_missing(self):
        req = self.ResearchRequest.from_dict({
            "topic": "desk", "platform": "tiktok",
            "research_goals": ["creative_patterns"],
        })
        self.assertIn("market", req.validate_material_fields())

    def test_douyin_topic_radar_does_not_require_market(self):
        req = self.ResearchRequest.from_dict({
            "topic": "å® ç‰©ç”¨å“", "platform": "douyin",
            "research_goals": ["low_follower_breakouts"],
        })
        self.assertNotIn("market", req.validate_material_fields())

    def test_filters_and_optional_lists_round_trip(self):
        req = self.ResearchRequest.from_dict({
            "topic": "desk", "platform": "tiktok", "market": "GB",
            "research_goals": ["creative_patterns"],
            "audience": "remote workers",
            "seed_keywords": ["standing desk", "desk setup"],
            "competitors": ["brand-a"],
            "video_filters": {
                "content_types": ["ugc"],
                "duration_sec": {"min": 5, "max": 30},
                "creator_followers": {"min": None, "max": 50000},
                "minimum_views": 10000,
                "include_ads": True,
                "include_organic": True,
            },
        })
        out = req.to_dict()
        self.assertEqual(out["audience"], "remote workers")
        self.assertEqual(out["video_filters"]["creator_followers"]["max"], 50000)
        self.assertEqual(out["seed_keywords"], ["standing desk", "desk setup"])

    def test_duplicate_goals_are_deduplicated_preserving_order(self):
        req = self.ResearchRequest.from_dict({
            "topic": "desk", "platform": "tiktok", "market": "US",
            "research_goals": ["hooks", "voc", "hooks"],
        })
        self.assertEqual(req.research_goals, ["hooks", "voc"])

    def test_schema_version_defaults_to_1_0(self):
        req = self.ResearchRequest.from_dict({
            "topic": "desk", "platform": "tiktok", "market": "US",
            "research_goals": ["hooks"],
        })
        self.assertEqual(req.schema_version, "1.0")

    def test_schema_file_exists_and_has_no_business_defaults(self):
        path = ROOT / "references" / "schemas" / "research-request.schema.json"
        obj = json.loads(path.read_text(encoding="utf-8"))
        text = json.dumps(obj, ensure_ascii=False).lower()
        self.assertEqual(obj["title"], "Modular Research ResearchRequest")
        self.assertNotIn("wood bead bracelet", text)
        self.assertNotIn('"default": "us"', text)


class ProfileResolutionTests(unittest.TestCase):
    def _request(self, **overrides):
        from research_request import ResearchRequest
        data = {
            "topic": "generic topic",
            "platform": "tiktok",
            "market": "CA",
            "research_goals": ["creative_patterns"],
        }
        data.update(overrides)
        return ResearchRequest.from_dict(data)

    def test_profiles_load_from_canonical_directory(self):
        from profile_loader import load_profiles
        profiles = load_profiles()
        self.assertIn("tiktok-video-intelligence-v1", profiles)
        self.assertIn("douyin-topic-radar-v1", profiles)

    def test_tiktok_creative_goal_resolves_video_intelligence(self):
        from profile_resolver import resolve_profile
        result = resolve_profile(self._request())
        self.assertEqual(result.profile_id, "tiktok-video-intelligence-v1")
        self.assertIn("PLATFORM_TIKTOK", result.reason_codes)
        self.assertGreaterEqual(result.confidence, 0.9)

    def test_tiktok_voc_goal_resolves_video_intelligence(self):
        from profile_resolver import resolve_profile
        result = resolve_profile(self._request(research_goals=["voc"]))
        self.assertEqual(result.profile_id, "tiktok-video-intelligence-v1")
        self.assertIn("GOAL_VOC", result.reason_codes)

    def test_douyin_low_follower_resolves_topic_radar(self):
        from profile_resolver import resolve_profile
        req = self._request(
            platform="douyin", market=None,
            research_goals=["low_follower_breakouts"],
        )
        result = resolve_profile(req)
        self.assertEqual(result.profile_id, "douyin-topic-radar-v1")
        self.assertIn("PLATFORM_DOUYIN", result.reason_codes)

    def test_unknown_platform_has_no_silent_fallback(self):
        from profile_resolver import resolve_profile
        req = self._request(platform="youtube")
        with self.assertRaisesRegex(ValueError, "profile"):
            resolve_profile(req)

    def test_profile_files_do_not_hardcode_topic_or_market(self):
      ²È="24Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡•Ál‰µ•Ñ¡½‰t°€‰Pˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡•Ál‰Á…Ñ ‰t°€ˆ½…Á¤½ØÄ½‘½Õå¥¸½Ý•ˆ½™•Ñ¡}½¹•}Ù¥‘•¼ˆ¤((€€€‘•˜Ñ•ÍÑ}É•¥ÍÑÉå}±½…‘Í}Ñ¥­Ñ½­}Ù¥‘•½}Í•…É ¡Í•±˜¤è(€€€€€€€™É½´•¹‘Á½¥¹Ñ}É•¥ÍÑÉä¥µÁ½ÉÐ¹‘Á½¥¹ÑI•¥ÍÑÉä(€€€€€€€•À€ô¹‘Á½¥¹ÑI•¥ÍÑÉä ¤¹•Ð ‰Ñ¥­¡Õˆˆ°€‰Ñ¥­Ñ½¬ˆ°€‰Ù¥‘•½}Í•…É ˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡•Ál‰µ•Ñ¡½‰t°€‰Pˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡•Ál‰Á…Ñ ‰t°€ˆ½…Á¤½ØÄ½Ñ¥­Ñ½¬½…ÁÀ½ØÌ½™•Ñ¡}Ù¥‘•½}Í•…É¡}É•ÍÕ±Ðˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡•Ál‰ÍÑ…ÑÕÌ‰t°€‰‘½Õµ•¹Ñ•ˆ¤((€€€‘•˜Ñ•ÍÑ}É•¥ÍÑÉå}±½…‘Í}Ñ¥­Ñ½­}É•…Ñ½É}Í•…É¡}¥¹Í¥¡ÑÌ¡Í•±˜¤è(€€€€€€€™É½´•¹‘Á½¥¹Ñ}É•¥ÍÑÉä¥µÁ½ÉÐ¹‘Á½¥¹ÑI•¥ÍÑÉä(€€€€€€€•À€ô¹‘Á½¥¹ÑI•¥ÍÑÉä ¤¹•Ð ‰Ñ¥­¡Õˆˆ°€‰Ñ¥­Ñ½¬ˆ°€‰É•…Ñ½É}Í•…É¡}¥¹Í¥¡ÑÌˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡•Ál‰µ•Ñ¡½‰t°€‰Pˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰™•Ñ¡}É•…Ñ½É}Í•…É¡}¥¹Í¥¡ÑÌˆ°•Ál‰Á…Ñ ‰t¤((€€€‘•˜Ñ•ÍÑ}É•¥ÍÑÉå}±½…‘Í}Ñ¥­Ñ½­}…‘}­•å™É…µ•}µ•Ñ¡½‘}¥¹‘¥Ù¥‘Õ…±±ä¡Í•±˜¤è(€€€€€€€™É½´•¹‘Á½¥¹Ñ}É•¥ÍÑÉä¥µÁ½ÉÐ¹‘Á½¥¹ÑI•¥ÍÑÉä(€€€€€€€•À€ô¹‘Á½¥¹ÑI•¥ÍÑÉä ¤¹•Ð ‰Ñ¥­¡Õˆˆ°€‰Ñ¥­Ñ½¬ˆ°€‰…‘}­•å™É…µ•}…¹…±åÍ¥Ìˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡•Ál‰µ•Ñ¡½‰t°€‰A=MPˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡•Ál‰É•ÅÕ•ÍÑ}±½…Ñ¥½¸‰t°€‰©Í½¸ˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡•Ál‰Á…Ñ ‰t°€ˆ½…Á¤½ØÄ½Ñ¥­Ñ½¬½…‘Ì½•Ñ}…‘}­•å™É…µ•}…¹…±åÍ¥Ìˆ¤((€€€‘•˜Ñ•ÍÑ}É•¥ÍÑÉå}Õ¹­¹½Ý¹}…Á…‰¥±¥Ñå}±¥ÍÑÍ}…Ù…¥±…‰±”¡Í•±˜¤è(€€€€€€€™É½´•¹‘Á½¥¹Ñ}É•¥ÍÑÉä¥µÁ½ÉÐ¹‘Á½¥¹ÑI•¥ÍÑÉä(€€€€€€€Ý¥Ñ Í•±˜¹…ÍÍ•ÉÑI…¥Í•ÍI••à¡-•åÉÉ½È°€‹–ÞËšr$ˆ¤è(€€€€€€€€€€€¹‘Á½¥¹ÑI•¥ÍÑÉä ¤¹•Ð ‰Ñ¥­¡Õˆˆ°€‰Ñ¥­Ñ½¬ˆ°€‰‘½•Í}¹½Ñ}•á¥ÍÐˆ¤((€€€‘•˜Ñ•ÍÑ}É•¥ÍÑÉå}…Á…‰¥±¥Ñå}±¥ÍÑ¥¹}¥Í}Í½ÉÑ•¡Í•±˜¤è(€€€€€€€™É½´•¹‘Á½¥¹Ñ}É•¥ÍÑÉä¥µÁ½ÉÐ¹‘Á½¥¹ÑI•¥ÍÑÉä(€€€€€€€…ÁÌ€ô¹‘Á½¥¹ÑI•¥ÍÑÉä ¤¹±¥ÍÑ}…Á…‰¥±¥Ñ¥•Ì ‰Ñ¥­¡Õˆˆ°€‰Ñ¥­Ñ½¬ˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡…ÁÌ°Í½ÉÑ•¡…ÁÌ¤¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰Ù¥‘•½}µ•ÑÉ¥Ìˆ°…ÁÌ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰Ù¥‘•½}½µµ•¹ÑÌˆ°…ÁÌ¤((€€€‘•˜Ñ•ÍÑ}±•…å}Á±…¹¹•É}É•Í½±Ù•}•¹‘Á½¥¹Ñ}­••ÁÍ}‘•¥µ…±}ÁÉ¥”¡Í•±˜¤è(€€€€€€€™É½´‘•¥µ…°¥µÁ½ÉÐ•¥µ…°(€€€€€€€¥µÁ½ÉÐÉ•Í•…É¡}Á±…¹¹•È…ÌÁ±…¹¹•È(€€€€€€€•À€ôÁ±…¹¹•È¹É•Í½±Ù•}•¹‘Á½¥¹Ð ‰Ñ¥­¡Õˆˆ°€‰‘½Õå¥¸ˆ°€‰Ù¥‘•½}‘•Ñ…¥°ˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%Í%¹ÍÑ…¹”¡•Ál‰Õ¹¥Ñ}ÁÉ¥”‰t°•¥µ…°¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡•Ál‰Õ¹¥Ñ}ÁÉ¥”‰t°•¥µ…° ˆÀ¸ÀÀÄˆ¤¤((€€€‘•˜Ñ•ÍÑ}É•Í•…É¡}Á±…¹¹•É}¡…Í}¹½}•µ‰•‘‘•‘}É½ÕÑ¥¹}Ñ…‰±•}…ÕÑ¡½É¥Ñä¡Í•±˜¤è(€€€€€€€Ñ•áÐ€ô€¡I==P€¼€‰ÍÉ¥ÁÑÌˆ€¼€‰É•Í•…É¡}Á±…¹¹•È¹Áäˆ¤¹É•…‘}Ñ•áÐ¡•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ9½Ñ%¸ ‰I=UQ%9}Q	1è‘¥Ð€ôˆ°Ñ•áÐ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰¹‘Á½¥¹ÑI•¥ÍÑÉäˆ°Ñ•áÐ¤(()±…ÍÌI•ÅÕ•ÍÑ±¥½µÁ…Ñ¥‰¥±¥ÑåQ•ÍÑÌ¡Õ¹¥ÑÑ•ÍÐ¹Q•ÍÑ…Í”¤è(€€€‘•˜}…ÉÌ¡Í•±˜°€¨©½Ù•ÉÉ¥‘•Ì¤è(€€€€€€€‰…Í”€ô‘¥Ð (€€€€€€€€€€€É•ÅÕ•ÍÐõ9½¹”°Ñ½Á¥Œõ9½¹”°Á±…Ñ™½É´õ9½¹”°µ…É­•Ðõ9½¹”°(€€€€€€€€€€€É•Í•…É¡}½…°õmt°‘•ÁÑ ô‰ÍÑ…¹‘…Éˆ°½…°õ9½¹”°(€€€€€€€€¤(€€€€€€€‰…Í”¹ÕÁ‘…Ñ”¡½Ù•ÉÉ¥‘•Ì¤(€€€€€€€É•ÑÕÉ¸…ÉÁ…ÉÍ”¹9…µ•ÍÁ…” ¨©‰…Í”¤((€€€‘•˜Ñ•ÍÑ}±½…‘}É•ÅÕ•ÍÑ}©Í½¸¡Í•±˜¤è(€€€€€€€¥µÁ½ÉÐÉÕ¹}É•Í•…É (€€€€€€€Ý¥Ñ Ñ•µÁ™¥±”¹Q•µÁ½É…Éå¥É•Ñ½Éä ¤…ÌÑè(€€€€€€€€€€€Á…Ñ €ôA…Ñ ¡Ñ¤€¼€‰É•ÅÕ•ÍÐ¹©Í½¸ˆ(€€€€€€€€€€€Á…Ñ ¹ÝÉ¥Ñ•}Ñ•áÐ¡©Í½¸¹‘ÕµÁÌ¡ì(€€€€€€€€€€€€€€€€‰Ñ½Á¥Œˆè€‰½™™•”µ…¡¥¹”ˆ°(€€€€€€€€€€€€€€€€‰Á±…Ñ™½É´ˆè€‰Ñ¥­Ñ½¬ˆ°(€€€€€€€€€€€€€€€€‰µ…É­•Ðˆè€‰ˆ°(€€€€€€€€€€€€€€€€‰É•Í•…É¡}½…±Ìˆèl‰Ù½Œ‰t(€€€€€€€€€€€ô¤°•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€€€€€É•Ä€ôÉÕ¹}É•Í•…É ¹±½…‘}É•Í•…É¡}É•ÅÕ•ÍÑ}™É½µ}…ÉÌ¡Í•±˜¹}…ÉÌ¡É•ÅÕ•ÍÐõÍÑÈ¡Á…Ñ ¤¤¤(€€€€€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡É•Ä¹Ñ½Á¥Œ°€‰½™™•”µ…¡¥¹”ˆ¤(€€€€€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡É•Ä¹µ…É­•Ð°€‰ˆ¤((€€€‘•˜Ñ•ÍÑ}±½…‘}½¹Ù•¹¥•¹•}…ÉÌ¡Í•±˜¤è(€€€€€€€¥µÁ½ÉÐÉÕ¹}É•Í•…É (€€€€€€€É•Ä€ôÉÕ¹}É•Í•…É ¹±½…‘}É•Í•…É¡}É•ÅÕ•ÍÑ}™É½µ}…ÉÌ¡Í•±˜¹}…ÉÌ (€€€€€€€€€€€Ñ½Á¥Œô‰ÍÑ…¹‘¥¹œ‘•Í¬ˆ°Á±…Ñ™½É´ô‰Q¥­Q½¬ˆ°µ…É­•Ðô‰ÕÌˆ°(€€€€€€€€€€€É•Í•…É¡}½…°õl‰¡½½­Ìˆ°€‰Ù½Œ‰t°‘•ÁÑ ô‰‘••Àˆ°(€€€€€€€€¤¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡É•Ä¹Á±…Ñ™½É´°€‰Ñ¥­Ñ½¬ˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡É•Ä¹É•Í•…É¡}½…±Ì°l‰¡½½­Ìˆ°€‰Ù½Œ‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡É•Ä¹‘•ÁÑ °€‰‘••Àˆ¤((€€€‘•˜Ñ•ÍÑ}±•…å}½…±}Ý¥Ñ¡½ÕÑ}¹•Ý}É•ÅÕ•ÍÑ}É•ÑÕÉ¹Í}¹½¹”¡Í•±˜¤è(€€€€€€€¥µÁ½ÉÐÉÕ¹}É•Í•…É (€€€€€€€É•Ä€ôÉÕ¹}É•Í•…É ¹±½…‘}É•Í•…É¡}É•ÅÕ•ÍÑ}™É½µ}…ÉÌ¡Í•±˜¹}…ÉÌ¡½…°ô‹š^œ½Õå¥¸ƒ¢Âž‚Pˆ¤¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%Í9½¹”¡É•Ä¤((€€€‘•˜Ñ•ÍÑ}É•ÅÕ•ÍÑ}™¥±•}…¹‘}½¹Ù•¹¥•¹•}…ÉÍ}…¹¹½Ñ}‰•}µ¥á•¡Í•±˜¤è(€€€€€€€¥µÁ½ÉÐÉÕ¹}É•Í•…É (€€€€€€€Ý¥Ñ Ñ•µÁ™¥±”¹Q•µÁ½É…Éå¥É•Ñ½Éä ¤…ÌÑè(€€€€€€€€€€€Á…Ñ €ôA…Ñ ¡Ñ¤€¼€‰É•ÅÕ•ÍÐ¹©Í½¸ˆ(€€€€€€€€€€€Á…Ñ ¹ÝÉ¥Ñ•}Ñ•áÐ¡©Í½¸¹‘ÕµÁÌ¡ì(€€€€€€€€€€€€€€€€‰Ñ½Á¥Œˆè€‰àˆ°€‰Á±…Ñ™½É´ˆè€‰Ñ¥­Ñ½¬ˆ°€‰µ…É­•Ðˆè€‰ULˆ°(€€€€€€€€€€€€€€€€‰É•Í•…É¡}½…±Ìˆèl‰¡½½­Ì‰t(€€€€€€€€€€€ô¤°•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€€€€€Ý¥Ñ Í•±˜¹…ÍÍ•ÉÑI…¥Í•ÍI••à¡Y…±Õ•ÉÉ½È°€‰…¹¹½Ðµ¥àˆ¤è(€€€€€€€€€€€€€€€ÉÕ¹}É•Í•…É ¹±½…‘}É•Í•…É¡}É•ÅÕ•ÍÑ}™É½µ}…ÉÌ¡Í•±˜¹}…ÉÌ (€€€€€€€€€€€€€€€€€€€É•ÅÕ•ÍÐõÍÑÈ¡Á…Ñ ¤°Ñ½Á¥Œô‰½Ñ¡•Èˆ°(€€€€€€€€€€€€€€€€¤¤((€€€‘•˜Ñ•ÍÑ}¹•Ý}É•ÅÕ•ÍÑ}Á…ÉÍ•É}‘½•Í}¹½Ñ}É•ÅÕ¥É•}¥¹Ñ•É¹…±}ÁÉ½™¥±•}½É}•¹‘Á½¥¹Ð¡Í•±˜¤è(€€€€€€€Ñ•áÐ€ô€¡I==P€¼€‰ÍÉ¥ÁÑÌˆ€¼€‰ÉÕ¹}É•Í•…É ¹Áäˆ¤¹É•…‘}Ñ•áÐ¡•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ œ´µÉ•ÅÕ•ÍÐœ°Ñ•áÐ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ œ´µÉ•Í•…É µ½…°œ°Ñ•áÐ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ9½Ñ%¸ œ´µÁÉ½™¥±”œ°Ñ•áÐ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ9½Ñ%¸ œ´µ•¹‘Á½¥¹Ðœ°Ñ•áÐ¤((€€€‘•˜Ñ•ÍÑ}¹•Ý}É•ÅÕ•ÍÑ}É•ÅÕ¥É•Í}Á±…¹}½¹±å}¥¹}Á¡…Í”Ä¡Í•±˜¤è(€€€€€€€¥µÁ½ÉÐÉÕ¹}É•Í•…É (€€€€€€€É•Ä€ôÉÕ¹}É•Í•…É ¹±½…‘}É•Í•…É¡}É•ÅÕ•ÍÑ}™É½µ}…ÉÌ¡Í•±˜¹}…ÉÌ (€€€€€€€€€€€Ñ½Á¥Œô‰‘•Í¬ˆ°Á±…Ñ™½É´ô‰Ñ¥­Ñ½¬ˆ°µ…É­•Ðô‰ULˆ°É•Í•…É¡}½…°õl‰¡½½­Ì‰t(€€€€€€€€¤¤(€€€€€€€É•ÍÕ±Ð€ôÉÕ¹}É•Í•…É ¹‰Õ¥±‘}¥¹Ñ…­•}Á±…¸ ¡É•Ä¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡É•ÍÕ±Ñl‰ÁÉ½™¥±”‰ul‰ÁÉ½™¥±•}¥‰t°€‰Ñ¥­Ñ½¬µÙ¥‘•¼µ¥¹Ñ•±±¥•¹”µØÄˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡É•ÍÕ±Ñl‰•á•ÕÑ¥½¹}ÍÑ…ÑÕÌ‰t°€‰A19}=91e}=U9Q%=8ˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡É•ÍÕ±Ñl‰µ¥ÍÍ¥¹}µ…Ñ•É¥…±}™¥•±‘Ì‰t°mt¤(()±…ÍÌA½ÉÑ…‰¥±¥Ñå¹‘½ÍQ•ÍÑÌ¡Õ¹¥ÑÑ•ÍÐ¹Q•ÍÑ…Í”¤è(€€€‘•˜Ñ•ÍÑ}™½Õ¹‘…Ñ¥½¹}µ½‘Õ±•Í}¡…Ù•}¹½}¡½ÍÑ}ÁÉ½©•Ñ}¥µÁ½ÉÑÌ¡Í•±˜¤è(€€€€€€€¹…µ•Ì€ôl(€€€€€€€€€€€€‰É•Í•…É¡}É•ÅÕ•ÍÐ¹Áäˆ°€‰ÁÉ½™¥±•}±½…‘•È¹Áäˆ°€‰ÁÉ½™¥±•}É•Í½±Ù•È¹Áäˆ°(€€€€€€€€€€€€‰•¹‘Á½¥¹Ñ}É•¥ÍÑÉä¹Áäˆ°€‰É•Í•…É¡}Á±…¹¹•È¹Áäˆ°(€€€€€€€t(€€€€€€€Ñ•áÐ€ô€‰q¸ˆ¹©½¥¸ ¡I==P€¼€‰ÍÉ¥ÁÑÌˆ€¼¹…µ”¤¹É•…‘}Ñ•áÐ¡•¹½‘¥¹œô‰ÕÑ˜´àˆ¤™½È¹…µ”¥¸¹…µ•Ì¤¹±½Ý•È ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ9½Ñ%¸ ‰¥µÁ½ÉÐ¡¼ˆ°Ñ•áÐ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ9½Ñ%¸ ‰¥µÁ½ÉÐ¡•Éµ•Ìˆ°Ñ•áÐ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ9½Ñ%¸ ‰¥µÁ½ÉÐÍ¡½Á¥™äˆ°Ñ•áÐ¤((€€€‘•˜Ñ•ÍÑ}¥Ñ¥¹½É•}•á±Õ‘•Í}Á±…¥¹Ñ•áÑ}½¹™¥}…¹‘}ÉÕ¹Ñ¥µ•}½ÕÑÁÕÑÌ¡Í•±˜¤è(€€€€€€€Ñ•áÐ€ô€¡I==P€¼€ˆ¹¥Ñ¥¹½É”ˆ¤¹É•…‘}Ñ•áÐ¡•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰½¹™¥œ¹©Í½¸ˆ°Ñ•áÐ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰}}Áå…¡•}|¼ˆ°Ñ•áÐ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰Í½¥…°µÉ•Í•…É ¼ˆ°Ñ•áÐ¤((€€€‘•˜Ñ•ÍÑ}Í­¥±±}‘•™¥¹•Í}ÉÕ¹Ñ¥µ•}¥¹Ñ…­•}¹½Ñ}™¥á•‘}‰ÕÍ¥¹•ÍÍ}É•ÅÕ•ÍÐ¡Í•±˜¤è(€€€€€€€Ñ•áÐ€ô€¡I==P€¼€‰M-%10¹µˆ¤¹É•…‘}Ñ•áÐ¡•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€±½Ý•É•€ôÑ•áÐ¹±½Ý•È ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰É•Í•…É¡É•ÅÕ•ÍÐˆ°±½Ý•É•¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰É•Í•…É ¥¹Ñ…­”ˆ°±½Ý•É•¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰ÁÉ½™¥±”É•Í½±Ù•Èˆ°±½Ý•É•¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ9½Ñ%¸‹’ú,ëšÆž&šv¿–.oœîs–.g–êPˆ°±½Ý•É•¤((€€€‘•˜Ñ•ÍÑ}Í­¥±±}Í…åÍ}ÕÍ•É}¹••‘}¹½Ñ}ÁÉ½Ù¥‘•}¥¹Ñ•É¹…±}ÁÉ½™¥±•}½É}•¹‘Á½¥¹Ð¡Í•±˜¤è(€€€€€€€Ñ•áÐ€ô€¡I==P€¼€‰M-%10¹µˆ¤¹É•…‘}Ñ•áÐ¡•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‹’â7–ú_¢ššÆžR£š"ßš>C’úlˆ°Ñ•áÐ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰•¹‘Á½¥¹Ðˆ°Ñ•áÐ¹±½Ý•È ¤¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰ÁÉ½™¥±”ˆ°Ñ•áÐ¹±½Ý•È ¤¤((€€€‘•˜Ñ•ÍÑ}É½ÕÑ¥¹}Ñ…‰±•}µ…É­Í}•¹‘Á½¥¹ÑÍ}©Í½¹}…Í}µ…¡¥¹•}…ÕÑ¡½É¥Ñä¡Í•±˜¤è(€€€€€€€Ñ•áÐ€ô€¡I==P€¼€‰É•™•É•¹•Ìˆ€¼€‰É½ÕÑ¥¹œµÑ…‰±”¹µˆ¤¹É•…‘}Ñ•áÐ¡•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰•¹‘Á½¥¹ÑÌ¹©Í½¸ˆ°Ñ•áÐ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‹–R¿’âšrë–f£šv–¢ˆ°Ñ•áÐ¤((€€€‘•˜Ñ•ÍÑ}‘¥ÍÑÉ¥‰ÕÑ•‘}ÁÉ½™¥±•Í}½¹Ñ…¥¹}¹½}…Á¥}­•ä¡Í•±˜¤è(€€€€€€€Ñ•áÐ€ô€‰q¸ˆ¹©½¥¸¡À¹É•…‘}Ñ•áÐ¡•¹½‘¥¹œô‰ÕÑ˜´àˆ¤™½ÈÀ¥¸€¡I==P€¼€‰É•™•É•¹•Ìˆ€¼€‰ÁÉ½™¥±•Ìˆ¤¹±½ˆ ˆ¨¹©Í½¸ˆ¤¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ9½Ñ%¸ ‰…Á¥}­•äˆ°Ñ•áÐ¹±½Ý•È ¤¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ9½Ñ%¸ ‰‰•…É•È€ˆ°Ñ•áÐ¹±½Ý•È ¤¤(()¥˜}}¹…µ•}|€ôô€‰}}µ…¥¹}|ˆè(€€€Õ¹¥ÑÑ•ÍÐ¹µ…¥¸ ¤(