#!/usr/bin/env python3
"""Regression tests for Modular Research v1.2.0 TikTok provider verification."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
