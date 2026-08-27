#!/usr/bin/env python3
"""Integrity gates for v1.2.0 provider verification evidence."""
from __future__ import annotations

import unittest

import provider_verification


class ProviderVerificationIntegrityTests(unittest.TestCase):
    @staticmethod
    def _report() -> dict:
        return {
            "platform": "tiktok",
            "generated_at": "2026-08-27T04:00:00+00:00",
            "status": "COMPLETED",
            "calls_attempted": 1,
            "calls_succeeded": 1,
            "calls_failed": 0,
            "pricing_basis": "provider_default",
            "results": [
                {
                    "capability": "video_search",
                    "status": "ok",
                    "provider_code": 200,
                    "normalizer_counts": {"videos": 1},
                }
            ],
        }

    def test_blocked_or_nonterminal_report_cannot_promote(self):
        report = self._report()
        report["status"] = "BLOCKED_BUDGET"
        with self.assertRaisesRegex(ValueError, "source status is not promotable"):
            provider_verification.build_verification_manifest(report, platform="tiktok")

    def test_attempted_call_count_must_match_result_rows(self):
        report = self._report()
        report["calls_attempted"] = 2
        report["calls_failed"] = 1
        with self.assertRaisesRegex(ValueError, "result count does not match calls_attempted"):
            provider_verification.build_verification_manifest(report, platform="tiktok")


if __name__ == "__main__":
    unittest.main()
