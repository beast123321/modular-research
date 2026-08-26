#!/usr/bin/env python3
"""Regression tests for bounded Douyin live provider validation."""
from __future__ import annotations

import inspect
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import live_validation

ROOT = Path(__file__).resolve().parent.parent


class DouyinLiveValidationTests(unittest.TestCase):
    def test_release_candidate_is_1_1_2(self):
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), "1.1.2")

    def test_douyin_probe_builder_is_bounded_and_starts_from_reference_and_search(self):
        builder = getattr(live_validation, "build_douyin_probes", None)
        self.assertTrue(callable(builder), "live_validation must expose build_douyin_probes")
        probes = builder(topic="职场高情商接话", reference_aweme_id="7667541271225140069")
        self.assertEqual([p.capability for p in probes], ["video_detail_v3", "video_search"])
        self.assertEqual(probes[0].payload, {"aweme_id": "7667541271225140069"})
        self.assertEqual(probes[1].payload["keyword"], "职场高情商接话")
        self.assertEqual(probes[1].payload["cursor"], 0)
        self.assertEqual(probes[1].payload["search_id"], "")

    def test_plan_only_cli_defaults_douyin_to_six_calls_without_api_key(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "live_validation.py"),
                "--topic",
                "职场高情商接话",
                "--platform",
                "douyin",
                "--reference-aweme-id",
                "7667541271225140069",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        plan = json.loads(completed.stdout)
        self.assertEqual(plan["execution_status"], "PLAN_ONLY")
        self.assertEqual(plan["platform"], "douyin")
        self.assertEqual(plan["call_ceiling"], 6)
        self.assertEqual(plan["estimated_max_cost_usd"], 0.006)
        self.assertEqual(
            plan["initial_capabilities"],
            ["video_detail_v3", "video_search"],
        )

    def test_runner_accepts_platform_and_douyin_expands_to_six_contract_probes(self):
        parameters = inspect.signature(live_validation.LiveValidationRunner.run).parameters
        self.assertIn("platform", parameters, "runner must select registry/normalizer by platform")

        seen = []

        def transport(**kwargs):
            seen.append(kwargs)
            path = kwargs["path"]
            if path.endswith("fetch_one_video_v3"):
                return {
                    "code": 200,
                    "data": {
                        "aweme_id": "7667541271225140069",
                        "desc": "参考视频",
                        "author": {"uid": "U1", "sec_uid": "SEC1", "nickname": "作者"},
                        "video": {},
                    },
                }
            if path.endswith("fetch_video_search_v1"):
                return {
                    "code": 200,
                    "data": {
                        "items": [
                            {
                                "aweme_id": "V2",
                                "desc": "候选视频",
                                "author": {"uid": "U2", "sec_uid": "SEC2", "nickname": "候选作者"},
                                "video": {},
                            }
                        ]
                    },
                }
            if path.endswith("fetch_video_statistics"):
                ids = kwargs["params"]["aweme_ids"].split(",")
                return {"code": 200, "data": [{"aweme_id": item, "statistics": {"play_count": 100}} for item in ids]}
            if path.endswith("fetch_video_comments"):
                return {"code": 200, "data": {"comments": []}}
            if path.endswith("handler_user_profile"):
                return {"code": 200, "data": {"user": {"uid": "U1", "sec_uid": "SEC1", "nickname": "作者"}}}
            if path.endswith("fetch_user_post_videos"):
                return {"code": 200, "data": {"aweme_list": []}}
            return {"code": 200, "data": {}}

        probes = live_validation.build_douyin_probes(
            topic="职场高情商接话",
            reference_aweme_id="7667541271225140069",
        )
        runner = live_validation.LiveValidationRunner(transport=transport)
        with tempfile.TemporaryDirectory() as td:
            result = runner.run(
                probes,
                platform="douyin",
                api_key="secret",
                base_url="https://example.invalid",
                output_dir=Path(td),
                max_calls=6,
                max_budget_usd=0.006,
                unit_price_usd=0.001,
                skip_dns_check=True,
            )

        caps = [row["capability"] for row in result["results"]]
        self.assertEqual(result["platform"], "douyin")
        self.assertEqual(result["calls_attempted"], 6)
        self.assertEqual(result["calls_failed"], 0)
        self.assertEqual(
            set(caps),
            {"video_detail_v3", "video_search", "video_statistics_v3", "video_comments_v3", "user_profile_v3", "creator_posts_v3"},
        )
        self.assertTrue(all("/api/v1/douyin/" in call["path"] for call in seen))
        stats_call = next(call for call in seen if call["path"].endswith("fetch_video_statistics"))
        self.assertEqual(stats_call["params"]["aweme_ids"], "7667541271225140069,V2")
        comments_call = next(call for call in seen if call["path"].endswith("fetch_video_comments"))
        self.assertEqual(comments_call["params"]["count"], 20)
        profile_call = next(call for call in seen if call["path"].endswith("handler_user_profile"))
        self.assertEqual(profile_call["params"]["sec_user_id"], "SEC1")


if __name__ == "__main__":
    unittest.main()
