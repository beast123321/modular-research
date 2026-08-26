# Douyin Video Intelligence V1 Design

**Date:** 2026-08-26  
**Status:** Approved in chat; written specification for Phase 9 implementation  
**Branch:** `phase9/douyin-video-intelligence`

## 1. Goal

Extend `modular-research` from the existing lightweight `douyin-topic-radar-v1` into a full `douyin-video-intelligence-v1` research profile capable of starting from a natural-language goal and optional Douyin reference video, expanding outward into evidence-backed research of a content niche.

Primary user experience:

> “使用 modular-research，我想做类似这条抖音视频的账号。研究职场高情商接话 / 人情世故 / 职场生存法则，重点找低粉爆款、Hook、文案结构、评论需求和可持续选题。先给计划和成本，付费前确认。”

The user must not need to supply endpoint names, cursors, profile IDs, request payloads, or internal IDs.

## 2. Scope

### In scope

- New profile: `douyin-video-intelligence-v1`.
- Canonical `ResearchRequest.reference_content` input.
- Local extraction of Douyin content IDs from direct URLs/query parameters.
- Provider fallback for unresolved Douyin share URLs.
- Douyin video keyword discovery.
- Reference-video detail enrichment.
- Creator profile and creator-post expansion.
- Comment collection for VOC.
- Douyin normalization into the existing platform-neutral evidence model.
- Reuse of deterministic metrics/ranking/VOC/findings.
- Reuse of media acquisition, keyframes, OCR/transcript contracts, host-agent multimodal creative analysis, pattern mining, synthesis, hypotheses, and briefs.
- Budget planning and bounded dynamic fan-out.
- Backward compatibility with `douyin-topic-radar-v1` and the TikTok pipeline.

### Explicitly out of scope for V1

- Douyin advertising intelligence. `ads_analysis` and `retention_analysis` must not route to `douyin-video-intelligence-v1`.
- Default use of the paid highest-quality video URL endpoint.
- Copying a reference video's script or creative verbatim. Reference content is evidence/seed material for pattern research, not a copying instruction.
- Claiming live endpoint verification without a successful provider call.

## 3. Architecture

```text
Natural-language request + optional Douyin reference URL
        ↓
Research Intake
        ↓
ResearchRequest.reference_content
        ↓
Reference Resolver
        ├─ local ID extraction (zero API cost)
        └─ provider fallback for unresolved share URLs
        ↓
Profile Resolver
        ↓
douyin-video-intelligence-v1
        ↓
Douyin Stage Planner
        ├─ REFERENCE_SEED
        ├─ ORGANIC_DISCOVERY
        ├─ CHEAP_RANKING (local)
        ├─ CREATOR_CONTEXT
        ├─ VOC
        ├─ VIDEO_UNDERSTANDING (local/host-agent)
        ├─ PATTERN_MINING (local)
        ├─ FINDINGS (local)
        ├─ HYPOTHESES (host-agent synthesis)
        └─ BRIEFS (host-agent synthesis)
        ↓
Evidence-backed outputs
```

The analysis and creative-understanding layers remain platform-neutral. Douyin-specific logic belongs in reference resolution, provider routing, request construction, response extraction, and normalization.

## 4. Canonical Reference Input

Add to `ResearchRequest`:

```json
{
  "reference_content": [
    {
      "platform": "douyin",
      "url": "https://www.douyin.com/jingxuan/search/...?modal_id=7667541271225140069",
      "content_id": "7667541271225140069",
      "role": "style_reference"
    }
  ]
}
```

`content_id` is optional on input. The runtime fills it when it can resolve the URL.

Supported `role` values for V1:

- `style_reference`
- `competitor_reference`
- `seed_content`

Reference records are deduplicated by `(platform, content_id)` when an ID exists, otherwise by normalized URL.

## 5. Reference Resolution

Resolution order:

1. Extract locally from known direct patterns:
   - `/video/<numeric-id>`
   - `modal_id=<numeric-id>`
   - `aweme_id=<numeric-id>`
   - `iesdouyin.com/share/video/<numeric-id>`
2. If unresolved and URL is a Douyin share URL, use provider capability `reference_resolve_id` (`GET /api/v1/douyin/web/get_aweme_id`).
3. If ID resolution fails but share URL remains usable, optional fallback capability `reference_video_by_share_url` may fetch reference detail directly.
4. Do not spend an API call when the ID is already locally recoverable.

The provided acceptance example must resolve locally:

```text
modal_id=7667541271225140069
→ content_id=7667541271225140069
→ provider ID-resolution calls=0
```

## 6. Provider Endpoint Contracts

Current TikHub documentation basis as of 2026-08-26:

### Douyin keyword video search

- Capability: `video_search`
- Method: `POST`
- Path: `/api/v1/douyin/search/fetch_video_search_v1`
- Location: JSON body
- Initial pagination values: `cursor=0`, `search_id=""`, `backtrace=""`
- Filters: `sort_type`, `publish_time`, `filter_duration`, `content_type`
- Search response may provide `guide_search_words`; these can be used for bounded deterministic keyword enrichment.

### Douyin video detail

- Capability: `video_detail`
- Method: `GET`
- Path: `/api/v1/douyin/app/v3/fetch_one_video_v3`
- Required: `aweme_id`

### Douyin comments

- Capability: `video_comments`
- Method: `GET`
- Path: `/api/v1/douyin/app/v3/fetch_video_comments`
- Required: `aweme_id`
- Pagination: `cursor`
- Keep provider default/recommended `count=20`.

### Creator posts

- Capability: `creator_posts`
- Method: `GET`
- Path: `/api/v1/douyin/app/v3/fetch_user_post_videos`
- Required: `sec_user_id`
- `max_cursor=0` initially
- `count<=20`
- `sort_type=0` latest, `1` hottest
- `channel=normal` default; `lite` is a fallback, not a default fan-out multiplier.

### Creator profile

- Capability: `user_profile`
- Method: `GET`
- Path: `/api/v1/douyin/app/v3/handler_user_profile`
- Required: `sec_user_id`

### Share/reference resolution

- Capability: `reference_resolve_id`
- Method: `GET`
- Path: `/api/v1/douyin/web/get_aweme_id`
- Required: `url`

Optional fallback:

- Capability: `reference_video_by_share_url`
- Method: `GET`
- Path: `/api/v1/douyin/app/v3/fetch_one_video_by_share_url`
- Required: `share_url`

### Highest-quality media URL

`/api/v1/douyin/web/fetch_video_high_quality_play_url` is NOT part of default V1 planning. It may be added later as an explicit opt-in capability when high-resolution media is materially required and the user has approved its cost.

## 7. Profile Semantics

Create `references/profiles/douyin-video-intelligence-v1.json`.

Supported goals:

- `trend_discovery`
- `content_opportunities`
- `low_follower_breakouts`
- `creative_patterns`
- `hooks`
- `selling_angles`
- `formats`
- `creator_analysis`
- `voc`
- `purchase_objections`
- `competitor_analysis`
- `product_validation`

Unsupported in V1:

- `ads_analysis`
- `retention_analysis`

Profile resolution rule:

- Douyin requests containing creative/VOC/reference-driven goals should prefer `douyin-video-intelligence-v1`.
- Lightweight Douyin trend-only requests can remain on `douyin-topic-radar-v1` when it is sufficient.
- Equal-match alphabetical tie-breaking is not acceptable for these two Douyin profiles; the resolver must use explicit specificity/priority logic.

## 8. Douyin Stage Planning

The existing TikTok planner must be generalized without changing TikTok plan semantics.

### REFERENCE_SEED

When `reference_content` contains Douyin entries:

- Resolve content ID locally first.
- Plan `video_detail` for each resolved reference ID, bounded by a profile/depth limit.
- Unresolved share URLs may plan `reference_resolve_id` before `video_detail`.
- Reference creators extracted from detail become eligible for creator context.

### ORGANIC_DISCOVERY

For each bounded keyword:

- Comprehensive search: `sort_type=0`.
- Most-liked search: `sort_type=1` when depth/preset allows.
- Latest search: `sort_type=2` for trend/content-opportunity goals when depth allows.
- Map time range to Douyin `publish_time` conservatively: 1 day, 7 days, 180 days, or unlimited when the requested range cannot be represented exactly.
- Do not falsely describe a 90-day request as a native 90-day filter; record the approximation in plan assumptions.

### CHEAP_RANKING

Local-only deterministic ranking reusing Phase 4. No composite viral score.

### CREATOR_CONTEXT

For bounded shortlisted creators:

- `user_profile`
- `creator_posts` hottest and/or latest based on depth.

### VOC

For bounded shortlisted/reference videos:

- `video_comments` with bounded pages.
- Comment replies are not default V1 fan-out.

### VIDEO_UNDERSTANDING

Reuse existing media/creative pipeline. Prefer playable URLs already present in normalized video evidence. Media download remains opt-in according to existing safety/budget rules.

## 9. Normalization

Add a Douyin normalizer that emits the existing bundle contract where applicable:

```text
videos
video_snapshots
creators
comments
discoveries
```

No Douyin Ads objects in V1.

Normalized IDs are strings. Every normalized record carries `raw_evidence_id`. Provider-specific source fields may be retained under structured metadata, but deterministic analysis must consume canonical fields.

The normalizer must handle at least:

- video search rows
- V3 single-video detail
- creator posts
- creator profile
- comments
- guide search words / discovery keywords

## 10. Executor Dynamic Fan-out

Extend the V2 executor with Douyin-aware extractors while preserving TikTok behavior.

Required dynamic identifiers:

- `aweme_id`
- `sec_user_id`
- search pagination fields where used
- reference `content_id`

Dynamic tasks must never exceed the planner's `max_requests` / item ceilings. Missing upstream IDs reduce actual calls rather than causing fabricated calls.

## 11. Evidence and Analysis Boundary

Unchanged project-wide rules:

- Provider response / deterministic metric = Evidence.
- Deterministic description = Observation.
- Semantic interpretation = Insight.
- Testable proposition = Hypothesis.
- Model output is never persisted as source Evidence.
- Pattern lift is association, not causality.
- No composite viral score.
- Insufficient evidence means no fabricated pattern.

## 12. Acceptance Case

Canonical Phase 9 acceptance seed:

- Platform: Douyin
- Topic: `职场高情商接话 / 人情世故 / 职场生存法则`
- Reference content ID: `7667541271225140069`
- Reference role: `style_reference`
- Goals: `low_follower_breakouts`, `hooks`, `creative_patterns`, `formats`, `selling_angles`, `voc`, `content_opportunities`

Expected agent-level behavior:

1. Natural-language request is converted to `ResearchRequest` with reference content.
2. `modal_id` is resolved locally, costing zero provider calls.
3. Resolver selects `douyin-video-intelligence-v1`.
4. Plan includes reference detail + organic discovery + ranking + creator context + VOC + video understanding + pattern/synthesis stages.
5. Plan exposes request/cost ceilings before paid execution.
6. No Ads stages appear.
7. Actual execution is still gated by explicit confirmation and hard budget limit.

## 13. Backward Compatibility

- Existing TikTok request/plan/execution snapshots must remain unchanged except for intentional schema addition of optional `reference_content=[]`.
- Existing `douyin-topic-radar-v1` remains available.
- Legacy CLI remains supported.
- Existing migrations/evidence tables are reused unless a concrete normalization requirement proves a schema gap.

## 14. Testing

Phase 9 must add offline tests covering:

- direct `/video/<id>` resolution
- `modal_id` resolution
- `aweme_id` query resolution
- unresolved short-link fallback planning
- `ResearchRequest.reference_content` validation/dedupe
- profile specificity routing
- Douyin endpoint registry metadata
- Douyin time-filter approximation
- reference seed planning
- keyword discovery planning
- no Ads stage for Douyin V1
- creator/VOC dynamic fan-out
- Douyin normalizer fixtures
- media/creative pipeline compatibility
- budget ceiling behavior
- acceptance-case plan
- full regression of Phase 1–8 + Legacy

GitHub CI must pass on Python 3.10, 3.12, and 3.13 before merge.

## 15. Release Boundary

Phase 9 implementation ships through a PR from `phase9/douyin-video-intelligence` to `main`. Do not merge until the full CI matrix is green. Live TikHub validation is a separate evidence gate; documented endpoints can be marked `documented`, but only successful real calls can mark them live-validated.
