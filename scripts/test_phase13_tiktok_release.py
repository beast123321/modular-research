#!/usr/bin/env python3
"""Release assertions for v1.2.0 TikTok Provider Verification."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from endpoint_registry import EndpointRegistry

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "references" / "verifications" / "tiktok-provider-verification-v1.2.0.json"

LIVE_VERIFIED_CAPABILITIES = {
    "ad_percentile",
    "ads_detail",
    "ads_search",
    "creator_posts",
    "creator_search_insights",
    "creator_search_insights_trend",
    "top_ads_spotlight",
    "top_contents_list",
    "video_comments",
    "video_detail",
    "video_metrics",
    "video_search",
}

DOUYIN_V1_1_3_CAPABILITIES = {
    "video_detail_v3",
    "video_search",
    "video_comments_v3",
    "user_profile_v3",
    "creator_posts_v3",
    "video_statistics_v3",
}

EXPECTED_CALLS = {"attempted": 12, "succeeded": 12, "failed": 0}


class TikTokProviderReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        if version != "1.2.0":
            raise AssertionError(
                f"v1.2.0 release guard requires VERSION=1.2.0, got {version}"
            )

    def test_manifest_is_sanitized_and_matches_real_provider_run(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            set(manifest),
            {
                "schema_version",
                "platform",
                "verified_at",
                "source_status",
                "validation_calls",
                "pricing_basis",
                "promoted_capabilities",
                "non_promoted_capabilities",
            },
        )
        self.assertEqual(manifest["schema_version"], "1.0")
        self.assertEqual(manifest["platform"], "tiktok")
        self.assertEqual(manifest["verified_at"], "2026-08-27")
        self.assertEqual(manifest["source_status"], "COMPLETED")
        self.assertEqual(manifest["validation_calls"], EXPECTED_CALLS)
        self.assertEqual(manifest["pricing_basis"], "provider_default")
        self.assertEqual(set(manifest["promoted_capabilities"]), LIVE_VERIFIED_CAPABILITIES)
        self.assertEqual(manifest["non_promoted_capabilities"], [])

    def test_registry_promotes_exactly_the_twelve_evidence_backed_tiktok_capabilities(self):
        registry = EndpointRegistry()
        raw_registry = json.loads((ROOT / "references" / "endpoints.json").read_text(encoding="utf-8"))
        tiktok_entries = [
            row
            for row in raw_registry["endpoints"]
            if row.get("provider") == "tikhub" and row.get("platform") == "tiktok"
        ]
        self.assertGreater(len(tiktok_entries), len(LIVE_VERIFIED_CAPABILITIES))

        for entry in tiktok_entries:
            capability = entry["capability"]
            with self.subTest(capability=capability):
                if capability in LIVE_VERIFIED_CAPABILITIES:
                    self.assertEqual(entry["status"], "live_verified")
                    self.assertEqual(entry["verified_at"], "2026-08-27")
                    self.assertEqual(entry["verification_basis"], "real_provider_response")
                    self.assertEqual(entry["validation_calls"], EXPECTED_CALLS)
                    self.assertEqual(entry["normalizer_validation"], "PASS")
                    self.assertIsNone(entry.get("unit_price_usd"))
                    pricing = registry.get_pricing("tikhub", "tiktok", capability)
                    self.assertFalse(pricing["is_endpoint_exact"])
                    self.assertEqual(pricing["price_source"], "provider_default")
                else:
                    self.assertEqual(entry["status"], "documented")

    def test_douyin_v1_1_3_verification_metadata_is_unchanged(self):
        registry = EndpointRegistry()
        for capability in sorted(DOUYIN_V1_1_3_CAPABILITIES):
            entry = registry.get("tikhub", "douyin", capability)
            with self.subTest(capability=capability):
                self.assertEqual(entry["status"], "live_verified")
                self.assertEqual(entry["verified_at"], "2026-08-26")
                self.assertEqual(entry["verification_basis"], "real_provider_response")
                self.assertEqual(
                    entry["validation_calls"],
                    {"attempted": 6, "succeeded": 6, "failed": 0},
                )
                self.assertEqual(entry["normalizer_validation"], "PASS")

    def test_public_release_keeps_paid_execution_and_raw_evidence_out_of_ci(self):
        self.assertFalse(
            (ROOT / ".github" / "workflows" / "v1.2.0-tiktok-provider-verification.yml").exists()
        )
        self.assertFalse((ROOT / ".github" / "v1.2.0-live-validation-trigger").exists())
        self.assertFalse((ROOT / "references" / "verifications" / "live-validation.json").exists())

    def test_public_docs_identify_v1_2_0_and_pricing_boundary(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        release = (ROOT / "docs" / "RELEASE.md").read_text(encoding="utf-8")
        self.assertIn("当前版本：`1.2.0`", readme)
        self.assertIn("# Modular Research v1.2.0 发布说明", release)
        self.assertIn("provider-default", readme)
        self.assertIn("provider-default", release)


if __name__ == "__main__":
    unittest.main()
