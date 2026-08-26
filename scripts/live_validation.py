"""Bounded TikHub live-validation harness.

This module validates provider contracts; it is not a research workflow. It is
provider-neutral at the semantic layer and never turns live probe results into
Insights or Hypotheses.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
from typing import Any, Callable
from urllib.parse import urlparse

import api_research_core as core
from endpoint_registry import EndpointRegistry
from normalizers.douyin import normalize_capability as normalize_douyin_capability
from normalizers.tiktok import normalize_capability as normalize_tiktok_capability
from research_executor_v2 import (
    extract_ad_ids,
    extract_creator_ids,
    extract_search_insights,
    extract_top_content_ids,
    extract_video_ids,
)


@dataclass(frozen=True)
class ProbeSpec:
    capability: str
    payload: dict[str, Any]


def summarize_shape(value: Any, *, depth: int = 0, max_depth: int = 5) -> dict[str, Any]:
    if depth >= max_depth:
        return {"type": type(value).__name__}
    if isinstance(value, dict):
        return {
            "type": "dict",
            "keys": sorted(str(key) for key in value.keys()),
            "children": {
                str(key): summarize_shape(child, depth=depth + 1, max_depth=max_depth)
                for key, child in value.items()
            },
        }
    if isinstance(value, list):
        result: dict[str, Any] = {"type": "list", "length": len(value)}
        if value:
            result["item_shape"] = summarize_shape(value[0], depth=depth + 1, max_depth=max_depth)
        return result
    if value is None:
        return {"type": "null"}
    return {"type": type(value).__name__}


def build_default_probes(*, topic: str, market: str = "US") -> list[ProbeSpec]:
    """Build the legacy bounded TikTok contract probes."""
    period_end = int(
        datetime.now(timezone.utc)
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .timestamp()
    )
    return [
        ProbeSpec(
            "creator_search_insights",
            {
                "offset": 0,
                "limit": 5,
                "tab": "content_gap",
                "creator_source": "general_search",
                "force_refresh": False,
                "language_filters": "en",
            },
        ),
        ProbeSpec(
            "video_search",
            {
                "keyword": topic,
                "offset": 0,
                "count": 3,
                "sort_type": 0,
                "publish_time": 30,
                "region": market,
            },
        ),
        ProbeSpec(
            "top_contents_list",
            {
                "period_end_timestamp": period_end,
                "period_dimension": 1,
                "country_code": market,
                "order_by_metric": 1,
                "organic_only": True,
                "page": 1,
                "limit": 3,
            },
        ),
        ProbeSpec(
            "ads_search",
            {
                "keyword": topic,
                "period": 30,
                "page": 1,
                "limit": 3,
                "country_code": market,
                "ad_language": "en",
            },
        ),
        ProbeSpec("top_ads_spotlight", {"page": 1, "limit": 3}),
    ]


def build_douyin_probes(*, topic: str, reference_aweme_id: str) -> list[ProbeSpec]:
    """Start a Douyin validation from one known reference and one search probe.

    The remaining App V3 probes are discovered dynamically from these responses,
    keeping the live contract validation useful without asking the user for a
    creator identifier.
    """
    aweme_id = str(reference_aweme_id).strip()
    if not aweme_id:
        raise ValueError("reference_aweme_id is required for Douyin live validation")
    keyword = str(topic).strip()
    if not keyword:
        raise ValueError("topic is required for Douyin live validation")
    return [
        ProbeSpec("video_detail_v3", {"aweme_id": aweme_id}),
        ProbeSpec(
            "video_search",
            {
                "keyword": keyword,
                "cursor": 0,
                "sort_type": "0",
                "publish_time": "180",
                "filter_duration": "0",
                "content_type": "1",
                "search_id": "",
                "backtrace": "",
            },
        ),
    ]


def _host_resolves(base_url: str) -> tuple[bool, str | None]:
    host = urlparse(base_url).hostname
    if not host:
        return False, "invalid_base_url"
    try:
        socket.getaddrinfo(host, None)
    except OSError as exc:
        return False, f"dns:{type(exc).__name__}"
    return True, None


def _normalizer_for(platform: str):
    if platform == "douyin":
        return normalize_douyin_capability
    if platform == "tiktok":
        return normalize_tiktok_capability
    raise ValueError(f"unsupported live-validation platform: {platform}")


class LiveValidationRunner:
    def __init__(
        self,
        transport: Callable[..., Any] | None = None,
        registry: EndpointRegistry | None = None,
    ):
        self.transport = transport or core.request_json
        self.registry = registry or EndpointRegistry()

    def run(
        self,
        probes: list[ProbeSpec],
        *,
        platform: str = "tiktok",
        api_key: str,
        base_url: str,
        output_dir: Path,
        max_calls: int,
        max_budget_usd: float,
        unit_price_usd: float = 0.001,
        skip_dns_check: bool = False,
    ) -> dict[str, Any]:
        platform = str(platform).strip().lower()
        normalizer = _normalizer_for(platform)
        output_dir = Path(output_dir)
        raw_dir = output_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        max_calls = max(0, int(max_calls))
        estimated = round(max_calls * float(unit_price_usd), 6)
        base_report: dict[str, Any] = {
            "schema_version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "platform": platform,
            "initial_probes": len(probes),
            "call_ceiling": max_calls,
            "estimated_max_cost_usd": estimated,
            "unit_price_basis_usd": float(unit_price_usd),
            "results": [],
        }
        if estimated > float(max_budget_usd):
            base_report.update(
                {
                    "status": "BLOCKED_BUDGET",
                    "calls_attempted": 0,
                    "calls_succeeded": 0,
                    "calls_failed": 0,
                }
            )
            (output_dir / "live-validation.json").write_text(
                json.dumps(base_report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return base_report
        if not skip_dns_check:
            ok, reason = _host_resolves(base_url)
            if not ok:
                base_report.update(
                    {
                        "status": "BLOCKED_ENVIRONMENT",
                        "block_reason": reason,
                        "calls_attempted": 0,
                        "calls_succeeded": 0,
                        "calls_failed": 0,
                    }
                )
                (output_dir / "live-validation.json").write_text(
                    json.dumps(base_report, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                return base_report

        queue = list(probes)
        queued_caps = {probe.capability for probe in queue}
        attempted = succeeded = failed = 0
        results: list[dict[str, Any]] = []
        discovered_video_ids: list[str] = []
        discovered_creators: list[dict[str, str | None]] = []

        def remember_videos(values: list[str]) -> None:
            for value in values:
                if value not in discovered_video_ids:
                    discovered_video_ids.append(value)

        def remember_creators(values: list[dict[str, str | None]]) -> None:
            known = {
                (row.get("sec_user_id"), row.get("unique_id"))
                for row in discovered_creators
            }
            for value in values:
                key = (value.get("sec_user_id"), value.get("unique_id"))
                if key not in known:
                    known.add(key)
                    discovered_creators.append(value)

        def enqueue(capability: str, payload: dict[str, Any]) -> None:
            if capability in queued_caps or len(queue) >= max_calls * 3:
                return
            queued_caps.add(capability)
            queue.append(ProbeSpec(capability, payload))

        index = 0
        while index < len(queue) and attempted < max_calls:
            probe = queue[index]
            index += 1
            entry = self.registry.get("tikhub", platform, probe.capability)
            attempted += 1
            kwargs: dict[str, Any] = {
                "base_url": base_url,
                "api_key": api_key,
                "method": entry["method"],
                "path": entry["path"],
                "params": None,
                "body": None,
            }
            location = entry.get(
                "request_location", "query" if entry["method"] == "GET" else "json"
            )
            kwargs["body" if location == "json" else "params"] = dict(probe.payload)
            try:
                response = self.transport(**kwargs)
                safe = core.redact_payload(response)
                (raw_dir / f"{attempted:02d}_{probe.capability}.json").write_text(
                    json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                provider_code = response.get("code") if isinstance(response, dict) else None
                if provider_code not in (None, 200):
                    failed += 1
                    results.append(
                        {
                            "capability": probe.capability,
                            "method": entry["method"],
                            "request_location": location,
                            "path": entry["path"],
                            "provider_code": provider_code,
                            "shape": summarize_shape(response),
                            "status": "error",
                            "error_class": "provider",
                        }
                    )
                    continue

                succeeded += 1
                bundle = normalizer(
                    probe.capability,
                    safe,
                    raw_evidence_id=f"live:{attempted:02d}",
                    request_payload=probe.payload,
                )
                results.append(
                    {
                        "capability": probe.capability,
                        "method": entry["method"],
                        "request_location": location,
                        "path": entry["path"],
                        "provider_code": provider_code,
                        "shape": summarize_shape(response),
                        "normalizer_counts": {key: len(value) for key, value in bundle.items()},
                        "status": "ok",
                    }
                )

                if platform == "douyin":
                    remember_videos(extract_video_ids(response))
                    remember_creators(extract_creator_ids(response))
                    if probe.capability == "video_detail_v3":
                        reference_id = str(probe.payload.get("aweme_id") or "").strip()
                        if reference_id:
                            remember_videos([reference_id])
                            enqueue(
                                "video_comments_v3",
                                {"aweme_id": reference_id, "cursor": 0, "count": 20},
                            )
                        creator = next(
                            (row for row in discovered_creators if row.get("sec_user_id")),
                            None,
                        )
                        if creator:
                            sec_user_id = str(creator["sec_user_id"])
                            enqueue("user_profile_v3", {"sec_user_id": sec_user_id})
                            enqueue(
                                "creator_posts_v3",
                                {
                                    "sec_user_id": sec_user_id,
                                    "max_cursor": 0,
                                    "count": 20,
                                    "sort_type": 0,
                                    "channel": "normal",
                                },
                            )
                    elif probe.capability == "video_search" and discovered_video_ids:
                        enqueue(
                            "video_statistics_v3",
                            {"aweme_ids": ",".join(discovered_video_ids[:2])},
                        )
                    continue

                if probe.capability == "video_search":
                    videos = extract_video_ids(response)
                    creators = extract_creator_ids(response)
                    if videos:
                        video_id = videos[0]
                        enqueue(
                            "video_detail",
                            {
                                "aweme_id": video_id,
                                "region": probe.payload.get("region", "US"),
                            },
                        )
                        enqueue("video_metrics", {"item_id": video_id})
                        enqueue(
                            "video_comments",
                            {"aweme_id": video_id, "cursor": 0, "count": 3},
                        )
                    if creators:
                        creator = creators[0]
                        creator_payload: dict[str, Any] = {
                            "max_cursor": 0,
                            "count": 3,
                            "sort_type": 0,
                        }
                        if creator.get("sec_user_id"):
                            creator_payload["sec_user_id"] = creator["sec_user_id"]
                        elif creator.get("unique_id"):
                            creator_payload["unique_id"] = creator["unique_id"]
                        enqueue("creator_posts", creator_payload)
                elif probe.capability == "creator_search_insights":
                    rows = extract_search_insights(response)
                    if rows:
                        row = rows[0]
                        query_id = row.get("query_id")
                        keyword = row.get("keyword")
                        if query_id:
                            enqueue(
                                "creator_search_insights_trend",
                                {
                                    "query_id_str": query_id,
                                    "from_tab_path": "TRENDING,TOPICS",
                                    "query_analysis_required": True,
                                },
                            )
                        if keyword:
                            enqueue(
                                "creator_search_insights_videos",
                                {"keyword": keyword, "offset": 0, "count": 3},
                            )
                elif probe.capability in {"ads_search", "top_ads_spotlight"}:
                    ids = extract_ad_ids(response)
                    if ids:
                        ad_id = ids[0]
                        enqueue("ads_detail", {"ads_id": ad_id})
                        enqueue(
                            "ad_percentile",
                            {
                                "material_id": ad_id,
                                "metric": "ctr_percentile",
                                "period_type": 180,
                            },
                        )
                        enqueue(
                            "ad_keyframe_analysis",
                            {"material_id": ad_id, "metric": "retain_ctr"},
                        )
                        enqueue(
                            "ad_interactive_analysis",
                            {
                                "material_id": ad_id,
                                "metric_type": "remain",
                                "period_type": 180,
                            },
                        )
                elif probe.capability == "top_contents_list":
                    ids = extract_top_content_ids(response)
                    if ids:
                        payload = {
                            "item_id": ids[0],
                            "country_code": probe.payload.get("country_code", "US"),
                        }
                        for key in ("period_end_timestamp", "period_dimension"):
                            if key in probe.payload:
                                payload[key] = probe.payload[key]
                        enqueue("top_contents_item_detail", payload)
            except Exception as exc:
                failed += 1
                results.append(
                    {
                        "capability": probe.capability,
                        "method": entry["method"],
                        "request_location": location,
                        "path": entry["path"],
                        "status": "error",
                        "error_class": "transport",
                        "error_type": type(exc).__name__,
                    }
                )

        base_report.update(
            {
                "status": "COMPLETED" if failed == 0 else "COMPLETED_WITH_ERRORS",
                "calls_attempted": attempted,
                "calls_succeeded": succeeded,
                "calls_failed": failed,
                "results": results,
            }
        )
        (output_dir / "live-validation.json").write_text(
            json.dumps(base_report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return base_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded TikHub live contract validation")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--platform", choices=("tiktok", "douyin"), default="tiktok")
    parser.add_argument("--reference-aweme-id")
    parser.add_argument("--market", default="US")
    parser.add_argument("--max-calls", type=int)
    parser.add_argument("--max-budget-usd", type=float)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--base-url", default=core.DEFAULT_BASE_URL)
    parser.add_argument(
        "--config", default=str(Path(__file__).resolve().parent.parent / "config.json")
    )
    parser.add_argument("--out", default="live-validation-run")
    args = parser.parse_args()

    if args.platform == "douyin":
        if not args.reference_aweme_id:
            print("Douyin live validation 需要 --reference-aweme-id。")
            return 2
        probes = build_douyin_probes(
            topic=args.topic,
            reference_aweme_id=args.reference_aweme_id,
        )
        max_calls = 6 if args.max_calls is None else max(0, min(6, args.max_calls))
    else:
        probes = build_default_probes(topic=args.topic, market=args.market)
        max_calls = 15 if args.max_calls is None else args.max_calls

    unit_price = 0.001
    plan = {
        "execution_status": "PLAN_ONLY" if not args.execute else "READY",
        "platform": args.platform,
        "topic": args.topic,
        "market": args.market if args.platform == "tiktok" else None,
        "reference_aweme_id": args.reference_aweme_id if args.platform == "douyin" else None,
        "initial_capabilities": [probe.capability for probe in probes],
        "call_ceiling": max_calls,
        "estimated_max_cost_usd": round(max_calls * unit_price, 6),
        "pricing_basis": "provider_default",
    }
    if not args.execute:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0
    if not args.yes:
        print("真实 live validation 需要显式 --yes。")
        return 2
    if args.max_budget_usd is None:
        print("真实 live validation 需要 --max-budget-usd。")
        return 2
    api_key, source = core.resolve_api_key(config_path=args.config)
    if not api_key:
        print("未找到 TikHub API Key；请使用 TIKHUB_API_KEY、config.json 或系统 Keychain。")
        return 2
    result = LiveValidationRunner().run(
        probes,
        platform=args.platform,
        api_key=api_key,
        base_url=args.base_url,
        output_dir=Path(args.out),
        max_calls=max_calls,
        max_budget_usd=args.max_budget_usd,
        unit_price_usd=unit_price,
    )
    public = dict(result)
    public["api_key_source"] = source
    print(json.dumps(public, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"COMPLETED", "COMPLETED_WITH_ERRORS"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
