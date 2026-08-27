#!/usr/bin/env python3
"""Regression tests for Modular Research v1.2.0 TikTok provider verification."""
from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import live_validation

ROOT = Path(__file__).resolve().parent.parent


class TikTokProviderVerificationV120Tests(unittest.TestCase):
    @staticmethod
    def _run_plan_only(*extra_args: str):
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "live_validation.py"),
                "--topic",
                "standing desk",
                "--platform",
                "tiktok",
                "--market",
                "US",
                *extra_args,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def _provider_verification(self):
        try:
            return importlib.import_module("provider_verification")
        except ModuleNotFoundError:
            self.fail("provider_verification module must exist for v1.2.0")

    @staticmethod
    def _verification_report() -> dict:
        return {
            "platform": "tiktok",
            "generated_at": "2026-08-27T04:00:00+00:00",
            "status": "COMPLETED_WITH_ERRORS",
            "calls_attempted": 4,
            "calls_succeeded": 2,
            "calls_failed": 2,
            "pricing_basis": "provider_default",
            "results": [
                {
                    "capability": "video_search",
                    "status": "ok",
                    "provider_code": 200,
                    "normalizer_counts": {"videos": 3},
                    "shape": {"keys": ["authentication_token"]},
                    "request_payload": {"token": "must-not-leak"},
                },
                {
                    "capability": "video_detail",
                    "status": "ok",
                    "provider_code": 200,
                    "normalizer_counts": {"videos": 1},
                },
                {
                    "capability": "video_comments",
                    "status": "error",
                    "error_class": "provider",
                },
                {
                    "capability": "ads_search",
                    "status": "error",
                    "error_class": "transport",
                },
            ],
        }

    def test_tiktok_plan_only_defaults_to_twelve_calls(self):
        completed = self._run_plan_only()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        plan = json.loads(completed.stdout)
        self.assertEqual(plan["platform"], "tiktok")
        self.assertEqual(plan["call_ceiling"], 12)
        self.assertEqual(plan["estimated_max_cost_usd"], 0.012)

    def test_tiktok_cli_never_expands_above_twelve_calls(self):
        completed = self._run_plan_only("--max-calls", "99")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        plan = json.loads(completed.stdout)
        self.assertEqual(plan["call_ceiling"], 12)
        self.assertEqual(plan["estimated_max_cost_usd"], 0.012)

    def test_programmatic_runner_never_expands_above_twelve_calls(self):
        probes = [
            live_validation.ProbeSpec(
                "video_search",
                {
                    "keyword": f"standing desk {index}",
                    "offset": 0,
                    "count": 3,
                    "sort_type": 0,
                    "publish_time": 30,
                    "region": "US",
                },
            )
            for index in range(20)
        ]

        def transport(**kwargs):
            return {"code": 200, "data": {"items": []}}

        runner = live_validation.LiveValidationRunner(transport=transport)
        with tempfile.TemporaryDirectory() as td:
            result = runner.run(
                probes,
                platform="tiktok",
                api_key="secret",
                base_url="https://example.invalid",
                output_dir=Path(td),
                max_calls=99,
                max_budget_usd=1.0,
                unit_price_usd=0.001,
                skip_dns_check=True,
            )

        self.assertEqual(result["call_ceiling"], 12)
        self.assertEqual(result["calls_attempted"], 12)

    def test_call_ceiling_preserves_controlled_error_for_unsupported_platform(self):
        with self.assertRaisesRegex(ValueError, "unsupported live-validation platform: instagram"):
            live_validation.clamp_call_ceiling("instagram", 3)

    def test_live_report_carries_explicit_pricing_provenance(self):
        parameters = inspect.signature(live_validation.LiveValidationRunner.run).parameters
        self.assertIn("pricing_basis", parameters)

        runner = live_validation.LiveValidationRunner(
            transport=lambda **kwargs: {"code": 200, "data": {"items": []}}
        )
        with tempfile.TemporaryDirectory() as td:
            result = runner.run(
                [live_validation.ProbeSpec("video_search", {"keyword": "standing desk"})],
                platform="tiktok",
                api_key="secret",
                base_url="https://example.invalid",
                output_dir=Path(td),
                max_calls=1,
                max_budget_usd=0.001,
                unit_price_usd=0.001,
                pricing_basis="provider_default",
                skip_dns_check=True,
            )
        self.assertEqual(result["pricing_basis"], "provider_default")

    def test_normalizer_failure_is_not_counted_as_provider_success(self):
        def broken_normalizer(*args, **kwargs):
            raise ValueError("fixture normalizer failure")

        runner = live_validation.LiveValidationRunner(
            transport=lambda **kwargs: {"code": 200, "data": {"items": []}}
        )
        with tempfile.TemporaryDirectory() as td, mock.patch.object(
            live_validation, "_normalizer_for", return_value=broken_normalizer
        ):
            result = runner.run(
                [live_validation.ProbeSpec("video_search", {"keyword": "standing desk"})],
                platform="tiktok",
                api_key="secret",
                base_url="https://example.invalid",
                output_dir=Path(td),
                max_calls=1,
                max_budget_usd=0.001,
                unit_price_usd=0.001,
                skip_dns_check=True,
            )

        self.assertEqual(result["calls_attempted"], 1)
        self.assertEqual(result["calls_succeeded"], 0)
        self.assertEqual(result["calls_failed"], 1)
        self.assertEqual(result["results"][0]["error_class"], "normalizer")

    def test_manifest_promotes_only_successful_provider_and_normalizer_results(self):
        module = self._provider_verification()
        manifest = module.build_verification_manifest(
            self._verification_report(), platform="tiktok"
        )
        self.assertEqual(manifest["schema_version"], "1.0")
        self.assertEqual(manifest["platform"], "tiktok")
        self.assertEqual(manifest["verified_at"], "2026-08-27")
        self.assertEqual(
            manifest["validation_calls"],
            {"attempted": 4, "succeeded": 2, "failed": 2},
        )
        self.assertEqual(manifest["pricing_basis"], "provider_default")
        self.assertEqual(
            manifest["promoted_capabilities"], ["video_detail", "video_search"]
        )
        self.assertEqual(
            manifest["non_promoted_capabilities"],
            [
                {"capability": "ads_search", "reason": "transport_error"},
                {"capability": "video_comments", "reason": "provider_error"},
            ],
        )
        serialized = json.dumps(manifest, sort_keys=True)
        self.assertNotIn("authentication_token", serialized)
        self.assertNotIn("must-not-leak", serialized)
        self.assertNotIn('"shape"', serialized)
        self.assertNotIn('"request_payload"', serialized)

    def test_manifest_rejects_inconsistent_call_counts(self):
        module = self._provider_verification()
        report = self._verification_report()
        report["calls_succeeded"] = 3
        with self.assertRaisesRegex(ValueError, "validation call counts are inconsistent"):
            module.build_verification_manifest(report, platform="tiktok")

    def test_registry_promotion_preserves_contract_pricing_and_douyin_entries(self):
        module = self._provider_verification()
        with tempfile.TemporaryDirectory() as td:
            registry_path = Path(td) / "endpoints.json"
            shutil.copyfile(ROOT / "references" / "endpoints.json", registry_path)
            before = json.loads(registry_path.read_text(encoding="utf-8"))
            manifest = module.apply_registry_promotions(
                self._verification_report(), registry_path, platform="tiktok"
            )
            after = json.loads(registry_path.read_text(encoding="utf-8"))

        def by_key(payload, platform, capability):
            return next(
                row
                for row in payload["endpoints"]
                if row["provider"] == "tikhub"
                and row["platform"] == platform
                and row["capability"] == capability
            )

        for capability in manifest["promoted_capabilities"]:
            old = by_key(before, "tiktok", capability)
            new = by_key(after, "tiktok", capability)
            self.assertEqual(new["status"], "live_verified")
            self.assertEqual(new["verified_at"], "2026-08-27")
            self.assertEqual(new["verification_basis"], "real_provider_response")
            self.assertEqual(new["normalizer_validation"], "PASS")
            self.assertEqual(
                new["validation_calls"],
                {"attempted": 4, "succeeded": 2, "failed": 2},
            )
            for field in (
                "method",
                "path",
                "request_location",
                "unit_price_usd",
                "defaults",
                "limits",
            ):
                self.assertEqual(new.get(field), old.get(field), field)

        for capability in ("video_comments", "ads_search"):
            self.assertEqual(
                by_key(after, "tiktok", capability)["status"],
                by_key(before, "tiktok", capability)["status"],
            )

        before_douyin = [row for row in before["endpoints"] if row["platform"] == "douyin"]
        after_douyin = [row for row in after["endpoints"] if row["platform"] == "douyin"]
        self.assertEqual(after_douyin, before_douyin)

    def test_provider_verification_cli_is_dry_run_by_default_and_apply_is_sanitized(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report_path = root / "report.json"
            registry_path = root / "endpoints.json"
            manifest_path = root / "manifest.json"
            report_path.write_text(
                json.dumps(self._verification_report()), encoding="utf-8"
            )
            shutil.copyfile(ROOT / "references" / "endpoints.json", registry_path)
            original_registry = registry_path.read_bytes()

            dry = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "provider_verification.py"),
                    "--report",
                    str(report_path),
                    "--platform",
                    "tiktok",
                    "--registry",
                    str(registry_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(dry.returncode, 0, dry.stderr)
            dry_manifest = json.loads(dry.stdout)
            self.assertEqual(
                dry_manifest["promoted_capabilities"], ["video_detail", "video_search"]
            )
            self.assertEqual(registry_path.read_bytes(), original_registry)

            applied = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "provider_verification.py"),
                    "--report",
                    str(report_path),
                    "--platform",
                    "tiktok",
                    "--registry",
                    str(registry_path),
                    "--manifest-out",
                    str(manifest_path),
                    "--apply",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertNotEqual(registry_path.read_bytes(), original_registry)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            serialized = json.dumps(manifest, sort_keys=True)
            self.assertNotIn("authentication_token", serialized)
            self.assertNotIn("must-not-leak", serialized)


if __name__ == "__main__":
    unittest.main()
