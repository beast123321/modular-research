#!/usr/bin/env python3
"""Regression tests for Douyin provider live-verification metadata."""
from __future__ import annotations

from pathlib import Path
import unittest

from endpoint_registry import EndpointRegistry

ROOT = Path(__file__).resolve().parent.parent

LIVE_VERIFIED_CAPABILITIES = {
    "video_detail_v3",
    "video_search",
    "video_comments_v3",
    "user_profile_v3",
    "creator_posts_v3",
    "video_statistics_v3",
}


class DouyinProviderVerificationTests(unittest.TestCase):
    def test_release_candidate_is_1_1_3(self):
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), "1.1.3")

    def test_six_real_provider_contracts_are_live_verified_with_run_metadata(self):
        registry = EndpointRegistry()
        for capability in sorted(LIVE_VERIFIED_CAPABILITIES):
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

    def test_live_verification_does_not_promote_provider_default_price_to_exact_endpoint_price(self):
        registry = EndpointRegistry()
        provider_default_capabilities = LIVE_VERIFIED_CAPABILITIES - {"video_search"}
        for capability in sorted(provider_default_capabilities):
            entry = registry.get("tikhub", "douyin", capability)
            with self.subTest(capability=capability):
                self.assertIsNone(entry.get("unit_price_usd"))
                pricing = registry.get_pricing("tikhub", "douyin", capability)
                self.assertFalse(pricing["is_endpoint_exact"])
                self.assertEqual(pricing["price_source"], "provider_default")


if __name__ == "__main__":
    unittest.main()
