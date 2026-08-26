# Douyin Video Intelligence V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a full `douyin-video-intelligence-v1` path that can start from natural-language research intent plus an optional Douyin reference video and expand into evidence-backed discovery, creator context, VOC, video understanding, patterns, hypotheses, and briefs.

**Architecture:** Preserve the existing platform-neutral Evidence/Analysis/Creative/Synthesis layers. Add Douyin-specific reference resolution, endpoint contracts, request construction, planner routing, dynamic fan-out, and normalization. Keep `douyin-topic-radar-v1` and all TikTok behavior backward compatible.

**Tech Stack:** Python >=3.10, stdlib JSON/dataclasses/urllib parsing, SQLite evidence store, TikHub HTTP provider, GitHub Actions unittest matrix.

**Spec:** `docs/superpowers/specs/2026-08-26-douyin-video-intelligence-v1-design.md`

## Global Constraints

- Do not add Douyin Ads Intelligence in V1; `ads_analysis` and `retention_analysis` must not route to the new profile.
- Reference video URLs are seeds/evidence, never instructions to copy content verbatim.
- Resolve direct Douyin IDs locally at zero API cost when possible; use provider share-link fallback only when unresolved.
- Prefer current Douyin App V3 endpoints over legacy Web endpoints.
- `fetch_video_comments` must keep `count=20` because provider docs warn against changing it.
- `fetch_user_post_videos` must use `count<=20`; default first page `max_cursor=0`.
- `fetch_video_statistics` is explicit metrics enrichment; batch no more than 2 IDs per provider call.
- No live endpoint may be marked verified without a successful provider call.
- Existing TikTok and `douyin-topic-radar-v1` tests must remain green.
- No paid API calls in CI.

---

### Task 1: Canonical reference input and local Douyin reference resolver

**Files:**
- Create: `scripts/reference_resolver.py`
- Modify: `scripts/research_request.py`
- Modify: `references/schemas/research-request.schema.json`
- Test: `scripts/test_phase9.py`

**Interfaces:**
- Produces `ResearchRequest.reference_content: list[dict[str, str | None]]`.
- Produces `resolve_reference_content(item: dict) -> dict` with `resolution_status`, `content_id`, `provider_fallback_required`.
- Local extraction recognizes `/video/<id>`, `modal_id=<id>`, `aweme_id=<id>`, and raw numeric `content_id`.

- [ ] Write failing tests for schema/model round-trip and local extraction of reference ID `7667541271225140069` from a Douyin Jingxuan URL.
- [ ] Run `PYTHONPATH=scripts python -m unittest scripts/test_phase9.py` and verify RED because `reference_content` / resolver are absent.
- [ ] Implement canonical field and resolver with no network I/O.
- [ ] Re-run Phase 9 tests and verify Task 1 tests GREEN.

### Task 2: Profile routing and current TikHub Douyin endpoint registry

**Files:**
- Create: `references/profiles/douyin-video-intelligence-v1.json`
- Modify: `scripts/profile_resolver.py`
- Modify: `references/endpoints.json`
- Test: `scripts/test_phase9.py`

**Interfaces:**
- New profile supports `trend_discovery`, `content_opportunities`, `low_follower_breakouts`, `creative_patterns`, `hooks`, `selling_angles`, `formats`, `creator_analysis`, `voc`, `purchase_objections`, `competitor_analysis`, `product_validation`.
- New profile excludes `ads_analysis` and `retention_analysis`.
- Endpoint contracts:
  - `video_search`: POST `/api/v1/douyin/search/fetch_video_search_v1`, JSON body.
  - `video_detail`: GET `/api/v1/douyin/app/v3/fetch_one_video_v3`, query `aweme_id`.
  - `video_detail_by_share_url`: GET `/api/v1/douyin/app/v3/fetch_one_video_by_share_url`, query `share_url`.
  - `video_comments`: GET `/api/v1/douyin/app/v3/fetch_video_comments`, query `aweme_id,cursor,count`.
  - `creator_posts`: GET `/api/v1/douyin/app/v3/fetch_user_post_videos`, query `sec_user_id,max_cursor,count,sort_type,channel`.
  - `user_profile`: GET `/api/v1/douyin/app/v3/handler_user_profile`, query `sec_user_id`.
  - `video_statistics`: GET `/api/v1/douyin/app/v3/fetch_video_statistics`, query `aweme_ids` with max 2 IDs/call.

- [ ] Write failing endpoint/profile routing tests.
- [ ] Verify RED.
- [ ] Add profile and documented endpoint metadata with `status=documented` (not live-verified).
- [ ] Make resolver prefer `douyin-video-intelligence-v1` when creative/VOC/reference-style goals require it while preserving Topic Radar for lightweight trend-only cases.
- [ ] Verify Task 2 tests GREEN.

### Task 3: Douyin stage planner

**Files:**
- Modify: `scripts/stage_planner.py`
- Test: `scripts/test_phase9.py`

**Interfaces:**
- `build_stage_plan()` dispatches by `request.platform` instead of rejecting non-TikTok requests.
- Douyin stages: `REFERENCE_SEED`, `ORGANIC_DISCOVERY`, `CHEAP_RANKING`, `CREATOR_CONTEXT`, `VOC`, `VIDEO_UNDERSTANDING`, `PATTERN_MINING`, `FINDINGS`, `HYPOTHESES`, `BRIEFS` as required by goals.
- Search first-page payload uses `cursor=0`, `search_id=''`, `backtrace=''`, `content_type='1'`, and provider-supported sort/time filters.
- Reference direct IDs schedule `video_detail` without provider URL resolution; unresolved short/share URLs schedule `video_detail_by_share_url`.
- Metrics enrichment schedules `video_statistics` in `per_video_batch2` mode.

- [ ] Write failing planner tests for reference seed, organic search payload, VOC, creator context, video understanding, and exclusion of ads stages.
- [ ] Verify RED.
- [ ] Add platform-aware `_make_task(..., platform=...)`, Douyin time mapping, and `_build_douyin_stage_plan()` while leaving TikTok planner behavior unchanged.
- [ ] Verify planner tests GREEN and legacy TikTok planner tests remain GREEN.

### Task 4: Executor fan-out and Douyin normalization

**Files:**
- Create: `scripts/normalizers/douyin.py`
- Modify: `scripts/research_executor_v2.py`
- Test: `scripts/test_phase9.py`

**Interfaces:**
- Executor selects normalizer by `plan.request.platform`.
- Dynamic modes support `per_video_batch2` for `aweme_ids`, `per_creator` with Douyin `sec_user_id`, reference share URL fallback, and existing TikTok modes unchanged.
- Douyin normalizer emits the existing evidence bundle keys: `videos`, `video_snapshots`, `creators`, `comments`, `ads`, `ad_timeseries`, `search_insights`, `discoveries`.
- `video_statistics` writes snapshots with views/likes/shares/download-derived stable fields where supported; no semantic insight is created.

- [ ] Write failing fixture tests for Douyin video/search/comment/statistics normalization and batch-2 dynamic params.
- [ ] Verify RED.
- [ ] Implement Douyin normalizer and platform-aware executor routing.
- [ ] Verify Task 4 tests GREEN.

### Task 5: Agent/CLI usability for reference videos

**Files:**
- Modify: `scripts/run_research.py`
- Modify: `README.md`
- Modify: `SKILL.md`
- Test: `scripts/test_phase9.py`

**Interfaces:**
- CLI adds repeatable `--reference-url` for convenience; canonical `--request` remains preferred for machine use.
- Agent-facing docs show natural-language usage and require plan/cost before paid execution.
- Example uses the user's approved Douyin content-niche research pattern without hardcoding the Skill core to that niche.

- [ ] Write failing CLI/request-construction test for `--reference-url` semantics.
- [ ] Verify RED.
- [ ] Implement minimal CLI plumbing and docs.
- [ ] Verify Task 5 tests GREEN.

### Task 6: Full regression, public branch CI, and PR

**Files:**
- Modify: `.github/workflows/ci.yml`
- Test: `scripts/test_phase9.py` plus all existing suites.

**Interfaces:**
- GitHub Actions runs Phase 9 before existing Phase 8→Foundation suites on Python 3.10/3.12/3.13.
- CI remains offline and never supplies a TikHub key.

- [ ] Add Phase 9 to CI and first run it against pre-implementation code to capture RED evidence.
- [ ] After implementation run all Phase 9 tests plus existing V2/Foundation and Legacy suites.
- [ ] Run compileall, release audit, and core environment checks in CI.
- [ ] Open PR from `phase9/douyin-video-intelligence` to `main` only after branch CI is GREEN.
- [ ] Do not merge automatically; report PR/head/CI for user acceptance.
