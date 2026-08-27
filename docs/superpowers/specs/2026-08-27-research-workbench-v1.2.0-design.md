# Research Workbench v1.2.0 Design

## Status

Target release: `1.2.0`

Base: `main@33251404731d3f34a2a7ebc5ffa27efa3adda101` (`VERSION=1.1.3`)

Feature branch: `feat/research-workbench-v1.2.0`

This design adds a bundled local Web Workbench to `modular-research` without changing the existing Provider budget gates, research semantics, or evidence boundaries.

## 1. Product goal

`modular-research` must be usable as a complete reusable research Skill, not only as a CLI plus JSON/SQLite artifacts.

A user should be able to ask an Agent a natural-language research question, let the existing Research Engine create a run, and then inspect the complete run in a local browser without manually opening JSON files or querying SQLite.

The Workbench must make these layers separately visible and traceable:

```text
User Request
→ ResearchRequest
→ Profile Resolution
→ Stage Plan
→ Provider Calls
→ Raw Evidence
→ Normalized Evidence
→ Deterministic Metrics / Ranking / VOC
→ Findings / Observations
→ Media / Creative Understanding
→ Patterns
→ Insights
→ Hypotheses
→ Briefs
→ Final Synthesis / Report
```

The Web UI is an observability and research-review surface. It is not a second Research Engine.

## 2. Release scope

### 2.1 Included in v1.2.0

- Bundled FastAPI backend.
- Bundled React + TypeScript frontend.
- Local run discovery and run history.
- Run overview and stage-flow visualization.
- Video, creator, comment/VOC, raw evidence, media, findings, pattern, insight, hypothesis, brief, report, plan, cost, and execution views.
- Evidence lineage from derived objects back to raw evidence where the current database contains the necessary references.
- Read-only access to `run.sqlite`, JSON reports, raw files, and local media/keyframes.
- Compatibility with existing v1.1.x runs that do not contain Web-specific metadata.
- A local launcher: `python scripts/research_web.py`.
- Static frontend assets bundled with the Skill so Node.js is not required at runtime.
- Responsive desktop-first UI with usable mobile layout.
- Offline CI fixtures; no TikHub calls in tests.

### 2.2 Explicitly excluded from v1.2.0

- Starting a paid ResearchRun from the Web UI.
- Editing or deleting research data from the Web UI.
- Editing `config.json`, API keys, or Provider configuration from the Web UI.
- Remote/public hosting.
- Authentication or multi-user accounts.
- WebSocket infrastructure.
- Background job queues.
- New Provider endpoints.
- New research Profiles.
- Automatic media re-download or Provider retries from the Web UI.
- Changing Evidence/Observation/Insight/Hypothesis semantics.

These exclusions keep v1.2.0 a bounded productization of already-existing research data rather than a new orchestration platform.

## 3. Security boundary

The Workbench is local-only.

Default bind:

```text
127.0.0.1:8765
```

The v1.2.0 launcher must reject a non-loopback bind address. Remote hosting requires a future authenticated design.

The Web backend must never expose:

- `config.json`;
- environment variables;
- `TIKHUB_API_KEY`;
- arbitrary files outside the configured runs root;
- arbitrary local filesystem paths requested by a browser client.

Raw evidence responses must be passed through the existing recursive redaction utility at the HTTP response boundary even when the stored payload was already redacted.

Local media/keyframe serving must use IDs resolved through the run repository, then verify that the resolved path is inside the selected run directory before opening the file. Browser-supplied filesystem paths are never accepted.

SQLite is opened read-only using URI mode and `PRAGMA query_only=ON`.

## 4. Runtime and packaging

### 4.1 Runtime stack

Backend:

- Python `>=3.10`.
- FastAPI.
- Uvicorn.
- Existing `sqlite3` and project modules.

Frontend source:

- React.
- TypeScript.
- Vite.
- React Router.
- TanStack Query.

No Node.js process is required to use the installed Skill. `web/frontend/dist/` is bundled in the repository/release and served by FastAPI.

### 4.2 Launcher

Canonical command:

```bash
python scripts/research_web.py
```

Supported options:

```text
--port <int>           default 8765
--runs-root <path>     explicit runs root
--no-open              do not open the default browser
```

Host is fixed to `127.0.0.1` in v1.2.0.

Runs-root resolution when `--runs-root` is omitted:

1. `<skill-root>/social-research/runs` when present;
2. `<skill-root>/runs` when present;
3. `<skill-root>/social-research/runs` as the empty default location.

This preserves compatibility with the current real run path while also supporting the path documented by earlier releases.

## 5. Backend architecture

Create a focused `web/backend/` package.

```text
web/backend/
├── app.py
├── models.py
├── run_repository.py
├── run_summary.py
├── flow_service.py
├── lineage_service.py
├── media_service.py
└── routes/
    ├── health.py
    ├── runs.py
    ├── entities.py
    ├── evidence.py
    ├── intelligence.py
    └── media.py
```

### 5.1 `RunRepository`

`RunRepository` is the only component allowed to traverse run directories or open run SQLite databases.

Responsibilities:

- discover directories matching `run_*`;
- validate a run ID before path resolution;
- load optional `plan.json` and `execution.json`;
- locate `run.sqlite`;
- detect tables before querying them;
- provide paginated/filterable read models for videos, creators, comments, evidence, media, findings, patterns, insights, hypotheses, and briefs;
- load known report artifacts;
- tolerate absent optional tables/files in older or partial runs;
- never mutate a run.

A missing optional table/file is represented as an unavailable/empty section with an explicit reason, not as an exception that makes the entire run unreadable.

### 5.2 Read model rule

The HTTP API returns UI-oriented read models rather than leaking raw SQLite rows directly. Every read model includes stable IDs and only JSON-safe values.

Nullable metrics remain `null`; the backend does not invent zeroes.

### 5.3 Existing schema coverage

The Workbench reads the current tables, including:

- `research_runs`;
- `raw_evidence`;
- `creators`;
- `videos`;
- `video_snapshots`;
- `discoveries`;
- `comments`;
- `ads`;
- `ad_timeseries`;
- `search_insights`;
- `video_metrics_derived`;
- `creator_metrics_derived`;
- `comment_labels`;
- `findings`;
- `media_assets`;
- `media_keyframes`;
- `transcript_segments`;
- `creative_analysis`;
- `creative_patterns`;
- `insights`;
- `creative_hypotheses`;
- `media_briefs`.

No new database migration is required for the Workbench itself.

## 6. Run summary and compatibility

Existing runs were created before a Web manifest existed. v1.2.0 therefore derives a `RunSummary` at read time.

`RunSummary` contains:

```text
run_id
status
started_at
completed_at
topic
platform
market
depth
profile_id
provider
video_count
creator_count
comment_count
raw_evidence_count
provider_calls_attempted
provider_calls_succeeded
provider_calls_failed
expected_cost_usd
max_cost_usd
actual_estimated_cost_usd
stage_summary
artifact_availability
```

Values are obtained in this priority order:

1. explicit execution/plan fields;
2. `research_runs` and existing tables;
3. known report artifacts;
4. `null`/`unavailable`.

The adapter must never infer a precise cost from a call count when the execution artifact does not contain a cost estimate.

## 7. Stage-flow model

The Workbench displays the stage chain from the actual run plan when available.

Canonical UI states:

```text
COMPLETED
RUNNING
SKIPPED
FAILED
PLANNED
UNAVAILABLE
```

Each stage response also includes `status_basis`:

```text
execution
artifact
inferred
unavailable
```

Precedence:

1. explicit execution-stage status;
2. explicit stage output artifact/status;
3. conservative artifact inference;
4. `UNAVAILABLE`.

The UI must visibly distinguish an inferred status from an execution-recorded status.

For the current Douyin profile the expected order is:

```text
REFERENCE_SEED
ORGANIC_DISCOVERY
CHEAP_RANKING
CREATOR_CONTEXT
VOC
VIDEO_UNDERSTANDING
PATTERN_MINING
FINDINGS
HYPOTHESES
BRIEFS
```

but the backend must not hardcode this as the only possible order; plan-defined stages win.

## 8. Evidence lineage

Evidence traceability is a first-class feature.

### 8.1 Raw evidence detail

For one raw evidence ID, the UI shows:

- ID;
- endpoint;
- method;
- source type/key;
- fetched timestamp;
- redacted request JSON;
- redacted response JSON;
- normalized entities linked by `raw_evidence_id`;
- derived objects that cite the evidence ID where current schema refs permit resolution.

### 8.2 Reverse references

`LineageService` scans the current run for `evidence_refs_json` references from:

- derived video metrics;
- creator metrics;
- comment labels;
- findings;
- media keyframes/transcripts;
- creative analysis;
- creative patterns;
- insights;
- hypotheses;
- briefs.

It produces typed edges such as:

```text
raw_evidence → video
raw_evidence → snapshot
raw_evidence → comment
raw_evidence → finding
frame/transcript → creative_analysis
creative_analysis/evidence → pattern
pattern/evidence → insight
insight/evidence → hypothesis
hypothesis → brief
```

Only edges supported by stored IDs/refs are returned. The system must not fabricate missing lineage.

## 9. HTTP API

All routes are under `/api`.

Core endpoints:

```text
GET /api/health
GET /api/runs
GET /api/runs/{run_id}
GET /api/runs/{run_id}/flow
GET /api/runs/{run_id}/execution

GET /api/runs/{run_id}/videos
GET /api/runs/{run_id}/videos/{video_id}
GET /api/runs/{run_id}/creators
GET /api/runs/{run_id}/creators/{creator_id}
GET /api/runs/{run_id}/comments
GET /api/runs/{run_id}/voc

GET /api/runs/{run_id}/evidence
GET /api/runs/{run_id}/evidence/{evidence_id}
GET /api/runs/{run_id}/lineage/{evidence_id}

GET /api/runs/{run_id}/media
GET /api/runs/{run_id}/media/{video_id}
GET /api/runs/{run_id}/media/{video_id}/keyframes/{frame_id}/content

GET /api/runs/{run_id}/findings
GET /api/runs/{run_id}/patterns
GET /api/runs/{run_id}/insights
GET /api/runs/{run_id}/hypotheses
GET /api/runs/{run_id}/briefs
GET /api/runs/{run_id}/report
```

Collection endpoints use:

```text
page
page_size
sort
order
query
```

where relevant. `page_size` is capped server-side at 200.

Entity-specific filters are explicit, for example `label`, `creator_id`, `source_type`, or `status`; arbitrary SQL/filter expressions are not accepted.

## 10. Frontend information architecture

### 10.1 Runs home

Cards/table show:

- topic;
- platform;
- depth;
- status;
- started/completed time;
- videos;
- creators;
- comments;
- provider call usage;
- estimated cost when known;
- incomplete/blocked stage indicator.

### 10.2 Run workspace

One persistent run header plus tabs/routes:

```text
Overview
Flow
Videos
Creators
VOC
Evidence
Media
Intelligence
Report
Cost & Execution
```

### 10.3 Overview

Shows business-readable summary first:

- request/topic;
- research profile and scope;
- dataset counts;
- budget/call summary;
- stage completion summary;
- findings preview;
- explicit limitations/blockers.

Technical IDs are available but visually secondary.

### 10.4 Flow

Displays the actual stage chain as a horizontal/vertical responsive stepper. Selecting a stage opens:

- status and basis;
- planned task/capability information when available;
- request/cost counts when available;
- output artifact links;
- blocker/error text.

### 10.5 Videos

Server-paginated table with:

- caption/title;
- video ID;
- creator;
- followers;
- views/likes/comments/shares/favorites;
- engagement rate;
- follower leverage;
- discovery source;
- deep-analysis/media status.

Supported sorting includes views, engagement rate, follower leverage, and captured time when those metrics exist.

Video detail shows normalized metadata, snapshots, discoveries, comments, derived metrics, evidence refs, media/creative-analysis status, and links to referenced evidence.

### 10.6 Creators

Shows creator profile data plus run-specific derived metrics and discovered videos. A creator detail page lists the videos in the run and linked evidence.

### 10.7 VOC

Shows label counts and percentages using the actual denominator from the run. Selecting a label lists the comments assigned that label, matched terms, intensity, video, and evidence refs.

The UI labels these as sample/run statistics and never presents them as platform-wide market shares.

### 10.8 Evidence Explorer

Search/filter raw evidence by endpoint, source type, source key, and ID.

Evidence detail uses a split view:

- metadata and lineage summary;
- redacted request/response JSON viewer;
- normalized entities;
- reverse references / `used by`.

### 10.9 Media

Per shortlisted/analyzed video:

- media asset status/error;
- local asset metadata;
- keyframe gallery;
- OCR text/confidence;
- transcript segments;
- creative analysis response and confidence.

A missing media asset remains an explicit blocker. The Web UI never retries the download.

### 10.10 Intelligence

Separate sections:

```text
Findings / Observations
Patterns
Insights
Hypotheses
Briefs
```

The UI must visually preserve the semantic boundary:

```text
Evidence ≠ Observation ≠ Insight ≠ Hypothesis ≠ Brief
```

Every object shows confidence/status where stored and links to its evidence refs.

### 10.11 Report

Artifact priority:

1. `reports/final_report.md`;
2. `reports/research_report.md`;
3. `reports/report.md`;
4. structured available research artifacts rendered as an explicit evidence summary.

If no persisted final report exists, the UI says `Final report not persisted for this run`; it does not fabricate one.

Markdown is rendered with raw HTML disabled.

### 10.12 Cost & Execution

Shows Plan vs Actual separately:

```text
Expected requests
Maximum requests
Expected cost
Maximum cost
Actual attempted/succeeded/failed calls
Actual estimated cost when explicitly recorded
```

It also shows per-stage/per-capability call information if present in `execution.json`.

Provider-default cost estimates are labeled `estimate`; the UI never calls them an invoice or actual bill.

## 11. Frontend UX requirements

- Desktop-first command/workbench layout.
- Responsive at tablet/mobile widths.
- Large datasets use pagination rather than rendering all rows at once.
- Empty, unavailable, blocked, and failed states have different copy and visual treatment.
- Long JSON and evidence details are collapsed by default and expandable.
- IDs and technical metadata can be copied without dominating the primary business view.
- No critical information is communicated only by color.
- Keyboard focus and semantic button/link behavior are preserved.

## 12. Static frontend delivery

`web/frontend/` contains source plus a committed `dist/` build.

Vite build output uses stable entry names where practical so the committed bundle can be verified in CI.

FastAPI serves:

- `/api/*` from backend routes;
- static JS/CSS/assets from `dist/`;
- SPA history fallback for non-API paths.

The launcher fails with an explicit setup error if the bundled frontend build is missing rather than silently serving an incomplete page.

## 13. Error handling

### Run-level errors

- unknown run ID → HTTP 404;
- malformed run ID/path traversal attempt → HTTP 400;
- missing `run.sqlite` → run remains listed, DB-backed sections show unavailable;
- malformed JSON artifact → the affected section reports artifact parse failure; other sections remain usable;
- missing table → section unavailable, not server failure;
- locked/running SQLite → use short-lived read-only connections and return a recoverable section error if a consistent read cannot be obtained.

### Media errors

- local path outside run root → deny;
- missing file → 404;
- unregistered frame ID → 404;
- browser client cannot provide filesystem path.

### Frontend errors

Each route has loading, empty, unavailable, and error states. A failure in one tab does not blank the whole run workspace.

## 14. Testing strategy

### 14.1 Backend

Use offline tests with a synthetic temporary run fixture containing:

- `plan.json`;
- `execution.json`;
- SQLite initialized with migrations 001–004;
- representative raw evidence;
- videos/creators/comments/snapshots;
- derived metrics/comment labels/findings;
- media/keyframe/transcript/creative analysis;
- pattern/insight/hypothesis/brief rows;
- report artifacts.

Required test classes:

- run discovery and path validation;
- summary derivation;
- old/partial run compatibility;
- read-only SQLite enforcement;
- pagination/sorting/filtering;
- evidence redaction;
- lineage correctness;
- media path containment;
- report fallback behavior;
- FastAPI endpoint contracts;
- launcher loopback/runs-root behavior.

### 14.2 Frontend

Use Vitest + React Testing Library for:

- runs page;
- run header and navigation;
- stage-flow status/basis;
- video table sorting/pagination request state;
- VOC label drill-down;
- evidence detail/lineage;
- media blocked/available states;
- intelligence semantic labels;
- report no-final-report state;
- cost estimate labeling.

### 14.3 CI

Existing Python `3.10 / 3.12 / 3.13` offline matrix remains.

Add one Node 20 frontend job that runs:

```text
npm ci
npm test -- --run
npm run build
```

CI performs no Provider/network research calls and receives no TikHub credential.

The release audit verifies that `config.json`, local run outputs, provider raw captures, and secrets are not committed.

## 15. Real-run acceptance

The first product acceptance target is the existing local run:

```text
run_20260826T140750Z
```

Expected visible facts, based on the completed research execution supplied by the user:

```text
Platform: douyin
Profile: douyin-video-intelligence-v1
Depth: standard
Videos: 168
Creators: 16
Comments: 193
Provider calls: 46 attempted / 46 succeeded / 0 failed
Estimated provider-default cost: $0.046
```

Expected stage presentation:

```text
REFERENCE_SEED        completed
ORGANIC_DISCOVERY     completed
CHEAP_RANKING         completed
CREATOR_CONTEXT       completed
VOC                   completed
VIDEO_UNDERSTANDING   blocked/skipped due insufficient media evidence
PATTERN_MINING        skipped due insufficient evidence
FINDINGS              completed
HYPOTHESES            skipped due insufficient evidence
BRIEFS                skipped due insufficient evidence
```

The Workbench must expose the stored evidence supporting these facts rather than hardcoding the numbers or statuses.

The acceptance also requires that evidence references used by findings/VOC are clickable into the Evidence Explorer and that unavailable media is visible as a blocker rather than silently omitted.

## 16. Reusability acceptance

A second synthetic or subsequent real run with a different topic must appear automatically without frontend code changes.

No page may contain topic-specific logic for `职场高情商接话`, product-specific logic, or hardcoded IDs from the acceptance run.

Profile/platform-specific labels may come from run metadata, but the Workbench remains generic across supported `douyin` and `tiktok` research data.

## 17. Versioning and compatibility

- Release target becomes `1.2.0` only after implementation and complete CI acceptance.
- Existing CLI commands remain valid.
- Existing Profiles and Provider contracts remain unchanged.
- Existing v1.1.x run directories remain readable.
- No database migration is required solely to use the Web Workbench.
- No license change; repository remains without a declared license.

## 18. Definition of done

v1.2.0 is not complete until all of the following are true:

```text
RUN_HISTORY_WEB=PASS
RESEARCH_FLOW_WEB=PASS
VIDEOS_WEB=PASS
CREATORS_WEB=PASS
VOC_WEB=PASS
EVIDENCE_EXPLORER_WEB=PASS
EVIDENCE_LINEAGE_WEB=PASS
MEDIA_WEB=PASS
FINDINGS_WEB=PASS
PATTERNS_WEB=PASS
INSIGHTS_WEB=PASS
HYPOTHESES_WEB=PASS
BRIEFS_WEB=PASS
COST_EXECUTION_WEB=PASS
FINAL_REPORT_WEB=PASS

LOCAL_ONLY_SECURITY=PASS
RAW_RESPONSE_REDACTION=PASS
MEDIA_PATH_CONTAINMENT=PASS
OLD_RUN_COMPATIBILITY=PASS
NO_PROVIDER_CALLS_FROM_WEB=PASS

CURRENT_REAL_DOUYIN_RUN_VISIBLE_IN_WEB=PASS
REUSABLE_FOR_NEXT_RESEARCH_RUN=PASS
PYTHON_3_10=PASS
PYTHON_3_12=PASS
PYTHON_3_13=PASS
FRONTEND_TESTS=PASS
FRONTEND_BUILD=PASS
PUBLIC_RELEASE_AUDIT=PASS
```

Until this gate is satisfied, `modular-research` must not be described as having a complete Research Workbench.