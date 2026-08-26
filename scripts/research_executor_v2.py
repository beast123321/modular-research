"""Executable StageResearchPlan chain for Modular Research V2.

The executor performs provider calls in stage order, fans out identifiers found
upstream, persists normalized evidence, and then runs local deterministic / media /
synthesis preparation stages. Provider-specific semantics stay in the planner and
normalizers; the execution engine remains shared.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable

import api_research_core as core
from analysis.runner import run_deterministic_intelligence
from creative.runner import run_video_understanding
from evidence_store import EvidenceStore
from normalizers.douyin import normalize_capability as normalize_douyin_capability
from normalizers.tiktok import normalize_capability as normalize_tiktok_capability
from profile_loader import load_profiles
from stage_planner import PlanTask, StageResearchPlan
from synthesis.runner import prepare_synthesis


def _walk(value: Any):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def extract_video_ids(payload: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for node in _walk(payload):
        if not isinstance(node, dict):
            continue
        for key in ("aweme_id", "item_id"):
            raw = node.get(key)
            if raw not in (None, ""):
                value = str(raw)
                if value not in seen:
                    seen.add(value)
                    out.append(value)
    return out


def extract_search_insights(payload: Any) -> list[dict[str, str | None]]:
    out: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for node in _walk(payload):
        if not isinstance(node, dict):
            continue
        raw_id = node.get("query_id", node.get("query_id_str"))
        if raw_id in (None, ""):
            continue
        query_id = str(raw_id)
        if query_id in seen:
            continue
        keyword = None
        for key in ("query", "keyword", "search_word", "query_name"):
            if node.get(key) not in (None, ""):
                keyword = str(node[key])
                break
        seen.add(query_id)
        out.append({"query_id": query_id, "keyword": keyword})
    return out


def extract_top_content_ids(payload: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for node in _walk(payload):
        if not isinstance(node, dict):
            continue
        items = node.get("items")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            raw = item.get("item_id")
            if raw in (None, ""):
                continue
            value = str(raw)
            if value not in seen:
                seen.add(value)
                out.append(value)
    return out


def extract_creator_ids(payload: Any) -> list[dict[str, str | None]]:
    out: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for node in _walk(payload):
        if not isinstance(node, dict):
            continue
        author = node.get("author")
        candidates = [author] if isinstance(author, dict) else []
        if "sec_user_id" in node or "sec_uid" in node or "unique_id" in node:
            candidates.append(node)
        for candidate in candidates:
            sec = candidate.get("sec_user_id", candidate.get("sec_uid"))
            unique = candidate.get("unique_id")
            if sec in (None, "") and unique in (None, ""):
                continue
            sec_s = str(sec) if sec not in (None, "") else None
            unique_s = str(unique) if unique not in (None, "") else None
            dedupe_key = f"sec:{sec_s}" if sec_s else f"unique:{unique_s}"
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            out.append({"sec_user_id": sec_s, "unique_id": unique_s})
    return out


def extract_ad_ids(payload: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for node in _walk(payload):
        if not isinstance(node, dict):
            continue
        materials = node.get("materials")
        if not isinstance(materials, list):
            continue
        for material in materials:
            if not isinstance(material, dict):
                continue
            raw = material.get("material_id", material.get("id"))
            if raw not in (None, ""):
                value = str(raw)
                if value not in seen:
                    seen.add(value)
                    out.append(value)
    return out


def _extract_comment_cursor(payload: Any) -> tuple[Any | None, bool]:
    if not isinstance(payload, dict):
        return None, False
    data = payload.get("data")
    return (data.get("cursor"), bool(data.get("has_more"))) if isinstance(data, dict) else (None, False)


def _extend_unique(target: list[Any], values: list[Any], key_fn: Callable[[Any], str]) -> None:
    seen = {key_fn(item) for item in target}
    for item in values:
        key = key_fn(item)
        if key not in seen:
            seen.add(key)
            target.append(item)


def _normalizer_for(platform: str):
    return normalize_douyin_capability if platform == "douyin" else normalize_tiktok_capability


@dataclass
class ExecutionResult:
    status: str
    run_id: str
    calls_attempted: int
    calls_succeeded: int
    calls_failed: int
    stages: list[dict[str, Any]]
    output_dir: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ResearchExecutorV2:
    def __init__(self, transport: Callable[..., Any] | None = None):
        self.transport = transport or core.request_json

    @staticmethod
    def _dynamic_params(task: PlanTask, item: Any, variant: dict[str, Any]) -> dict[str, Any]:
        params = dict(variant)
        if task.mode == "per_video":
            params["item_id" if task.capability == "video_metrics" else "aweme_id"] = str(item)
        elif task.mode == "per_video_batch2":
            params["aweme_ids"] = ",".join(str(value) for value in item)
        elif task.mode == "per_creator":
            if item.get("sec_user_id"):
                params["sec_user_id"] = item["sec_user_id"]
            elif item.get("unique_id"):
                params["unique_id"] = item["unique_id"]
        elif task.mode == "per_ad":
            params["ads_id" if task.capability == "ads_detail" else "material_id"] = str(item)
        elif task.mode == "per_search_insight":
            if task.capability == "creator_search_insights_videos":
                if item.get("keyword"):
                    params["keyword"] = item["keyword"]
            else:
                params["query_id_str"] = item["query_id"]
        elif task.mode == "per_top_content":
            params["item_id"] = str(item)
        return params

    @staticmethod
    def _dynamic_items(
        task: PlanTask,
        video_ids: list[str],
        creators: list[dict[str, str | None]],
        ad_ids: list[str],
        search_insights: list[dict[str, str | None]],
        top_content_ids: list[str],
    ) -> list[Any]:
        if task.mode == "per_video":
            return list(video_ids[: task.max_items])
        if task.mode == "per_video_batch2":
            selected = list(video_ids[: task.max_items])
            return [selected[index:index + 2] for index in range(0, len(selected), 2)]
        if task.mode == "per_creator":
            selected = creators
            if task.capability in {"creator_posts_v3", "user_profile_v3"}:
                selected = [creator for creator in creators if creator.get("sec_user_id")]
            return list(selected[: task.max_items])
        if task.mode == "per_ad":
            return list(ad_ids[: task.max_items])
        if task.mode == "per_search_insight":
            return list(search_insights[: task.max_items])
        if task.mode == "per_top_content":
            return list(top_content_ids[: task.max_items])
        return []

    def _perform_call(self, *, task: PlanTask, payload: dict[str, Any], api_key: str, base_url: str) -> Any:
        kwargs = {
            "base_url": base_url,
            "api_key": api_key,
            "method": task.method,
            "path": task.endpoint,
            "params": None,
            "body": None,
        }
        kwargs["body" if task.request_location == "json" else "params"] = payload
        return self.transport(**kwargs)

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def execute(
        self,
        plan: StageResearchPlan,
        *,
        api_key: str,
        base_url: str,
        output_root: Path,
        run_id: str | None = None,
        download_media: bool = False,
        media_limit: int | None = None,
    ) -> ExecutionResult:
        run_id = run_id or "run_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = Path(output_root) / "runs" / run_id
        raw_dir = run_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(run_dir / "plan.json", plan.to_dict())
        video_ids: list[str] = []
        creators: list[dict[str, str | None]] = []
        ad_ids: list[str] = []
        search_insights: list[dict[str, str | None]] = []
        top_content_ids: list[str] = []
        normalizer = _normalizer_for(plan.request.platform)
        store = EvidenceStore(run_dir / "run.sqlite")
        store.record_run(run_id, plan.request.to_dict(), plan.profile_id, plan.provider)
        attempted = succeeded = failed = 0
        stage_results: list[dict[str, Any]] = []
        raw_counter = 0

        def absorb(response: Any, capability: str) -> None:
            _extend_unique(video_ids, extract_video_ids(response), str)
            _extend_unique(
                creators,
                extract_creator_ids(response),
                lambda item: f"sec:{item.get('sec_user_id')}" if item.get("sec_user_id") else f"unique:{item.get('unique_id')}",
            )
            _extend_unique(ad_ids, extract_ad_ids(response), str)
            if capability == "creator_search_insights":
                _extend_unique(search_insights, extract_search_insights(response), lambda item: str(item.get("query_id")))
            if capability == "top_contents_list":
                _extend_unique(top_content_ids, extract_top_content_ids(response), str)

        def call_and_store(stage_name: str, task: PlanTask, call_payload: dict[str, Any]):
            nonlocal attempted, succeeded, failed, raw_counter
            attempted += 1
            raw_counter += 1
            try:
                response = self._perform_call(task=task, payload=call_payload, api_key=api_key, base_url=base_url)
                succeeded += 1
                absorb(response, task.capability)
                raw_evidence_id = f"{run_id}:raw:{raw_counter:04d}"
                envelope = {
                    "raw_evidence_id": raw_evidence_id,
                    "stage": stage_name,
                    "capability": task.capability,
                    "request": call_payload,
                    "response": response,
                }
                safe = core.redact_payload(envelope)
                self._write_json(raw_dir / f"{raw_counter:04d}_{stage_name.lower()}_{task.capability}.json", safe)
                safe_response = safe.get("response") if isinstance(safe, dict) else core.redact_payload(response)
                source_key = next(
                    (
                        str(call_payload[key])
                        for key in (
                            "keyword", "query_id_str", "aweme_id", "aweme_ids", "item_id",
                            "material_id", "ads_id", "sec_user_id", "share_url",
                        )
                        if call_payload.get(key) not in (None, "")
                    ),
                    None,
                )
                store.record_raw_evidence(
                    evidence_id=raw_evidence_id,
                    run_id=run_id,
                    endpoint=task.endpoint,
                    method=task.method,
                    request_payload=core.redact_payload(call_payload),
                    response_payload=safe_response,
                    source_type=task.capability,
                    source_key=source_key,
                )
                store.persist_bundle(
                    normalizer(
                        task.capability,
                        safe_response,
                        raw_evidence_id=raw_evidence_id,
                        request_payload=call_payload,
                    ),
                    run_id=run_id,
                )
                return True, response
            except Exception as exc:
                failed += 1
                self._write_json(
                    raw_dir / f"{raw_counter:04d}_{stage_name.lower()}_{task.capability}_error.json",
                    core.redact_payload({"stage": stage_name, "capability": task.capability, "request": call_payload, "error": str(exc)}),
                )
                return False, None

        for stage in plan.stages:
            if stage.local_only:
                stage_results.append({"stage": stage.name, "status": "local_pending", "calls_attempted": 0, "calls_succeeded": 0, "calls_failed": 0})
                continue
            before_attempted, before_succeeded, before_failed = attempted, succeeded, failed
            any_inputs = False
            task_failures = False
            for task in stage.tasks:
                if task.mode == "static":
                    if task.static_calls:
                        any_inputs = True
                    for payload in task.static_calls:
                        ok, _ = call_and_store(stage.name, task, dict(payload))
                        if not ok:
                            task_failures = True
                            break
                    continue

                items = self._dynamic_items(task, video_ids, creators, ad_ids, search_insights, top_content_ids)
                if items:
                    any_inputs = True
                for item in items:
                    stop_item = False
                    for variant in task.variants:
                        payload = self._dynamic_params(task, item, variant)
                        ok, response = call_and_store(stage.name, task, payload)
                        if not ok:
                            task_failures = True
                            stop_item = True
                            break
                        if task.capability in {"video_comments", "video_comments_v3"} and task.pages_per_item > 1:
                            cursor, has_more = _extract_comment_cursor(response)
                            page = 1
                            while has_more and cursor not in (None, "") and page < task.pages_per_item:
                                next_payload = dict(payload)
                                next_payload["cursor"] = cursor
                                ok, response = call_and_store(stage.name, task, next_payload)
                                if not ok:
                                    task_failures = True
                                    stop_item = True
                                    break
                                cursor, has_more = _extract_comment_cursor(response)
                                page += 1
                        if stop_item:
                            break
                    if task_failures:
                        break

            stage_attempted = attempted - before_attempted
            stage_succeeded = succeeded - before_succeeded
            stage_failed = failed - before_failed
            status = (
                "skipped_no_inputs" if not any_inputs and stage_attempted == 0
                else "partial_failed" if stage_failed
                else "completed"
            )
            stage_results.append({
                "stage": stage.name,
                "status": status,
                "calls_attempted": stage_attempted,
                "calls_succeeded": stage_succeeded,
                "calls_failed": stage_failed,
            })

        store.conn.commit()
        store.close()
        local_failed = False
        try:
            run_deterministic_intelligence(run_dir / "run.sqlite", run_dir / "reports", run_id)
            for row in stage_results:
                if row["stage"] in {"CHEAP_RANKING", "FINDINGS"}:
                    row["status"] = "completed_local"
        except Exception:
            local_failed = True

        if any(row["stage"] == "VIDEO_UNDERSTANDING" for row in stage_results) and not local_failed:
            try:
                profiles = load_profiles()
                profile = profiles.get(plan.profile_id) or {}
                preset = (profile.get("depth_presets") or {}).get(plan.request.depth) or {}
                resolved_limit = int(media_limit or preset.get("deep_analysis_limit") or 20)
                phase5 = run_video_understanding(
                    run_dir / "run.sqlite",
                    run_dir,
                    run_id,
                    limit=resolved_limit,
                    download=download_media,
                    video_filters=plan.request.video_filters,
                )
                for row in stage_results:
                    if row["stage"] == "VIDEO_UNDERSTANDING":
                        row["status"] = (
                            "partial_failed" if phase5.get("media_failed")
                            else "completed_local" if phase5.get("semantic_analysis_count", 0) >= phase5.get("shortlist_count", 0) > 0
                            else "prepared_local"
                        )
                        row["summary"] = phase5
            except Exception:
                local_failed = True

        if any(row["stage"] == "PATTERN_MINING" for row in stage_results) and not local_failed:
            try:
                phase6 = prepare_synthesis(run_dir / "run.sqlite", run_dir, run_id)
                pattern_count = int(phase6.get("pattern_count") or 0)
                for row in stage_results:
                    if row["stage"] == "PATTERN_MINING":
                        row["status"] = "completed_local" if pattern_count > 0 else "skipped_insufficient_evidence"
                        row["summary"] = phase6
                    elif row["stage"] in {"HYPOTHESES", "BRIEFS"}:
                        row["status"] = "awaiting_host_agent" if pattern_count > 0 else "skipped_insufficient_evidence"
            except Exception:
                local_failed = True

        status = "completed" if failed == 0 and not local_failed else "partial_failed"
        finishing_store = EvidenceStore(run_dir / "run.sqlite")
        finishing_store.finish_run(run_id, status)
        finishing_store.close()
        result = ExecutionResult(
            status=status,
            run_id=run_id,
            calls_attempted=attempted,
            calls_succeeded=succeeded,
            calls_failed=failed,
            stages=stage_results,
            output_dir=str(run_dir),
        )
        self._write_json(run_dir / "execution.json", core.redact_payload(result.to_dict()))
        return result
