# Research Workbench v1.2.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a bundled, local-only Research Workbench that turns existing `modular-research` runs into a reusable, browser-visible, full-chain research product without changing Provider execution semantics or mutating research evidence.

**Architecture:** Add a read-only FastAPI backend over existing run directories/SQLite artifacts and a bundled React + TypeScript SPA served by the backend. The backend owns filesystem/SQLite access, evidence redaction, lineage, stage-state derivation, pagination, and media path safety; the frontend only consumes typed `/api` read models and never starts paid research or writes run data.

**Tech Stack:** Python >=3.10, FastAPI, Uvicorn, sqlite3, Pydantic, React, TypeScript, Vite, React Router, TanStack Query, React Markdown, Vitest, Testing Library.

**Spec:** `docs/superpowers/specs/2026-08-27-research-workbench-v1.2.0-design.md`

## Global Constraints

- Target release is `1.2.0`; keep `VERSION=1.1.3` until the final release task.
- Host is fixed to `127.0.0.1` in v1.2.0; no public/remote bind option.
- Web is read-only: no paid ResearchRun launch, no Provider calls, no evidence/config mutation, no API-key editing.
- `config.json`, environment variables, `TIKHUB_API_KEY`, and arbitrary filesystem paths must never be exposed by HTTP.
- SQLite must be opened read-only with URI `mode=ro` and `PRAGMA query_only=ON`.
- Browser-supplied local filesystem paths are never accepted.
- Raw evidence must be passed through the existing recursive redaction utility again at the HTTP boundary.
- Missing optional files/tables in v1.1.x runs render as explicit unavailable/empty sections; they must not break the whole run.
- `null` stays `null`; never invent zero values or precise costs.
- Evidence lineage only returns stored/supported edges; never fabricate missing lineage.
- Node.js is development/build-only; committed `web/frontend/dist/` must make runtime Node-free.
- CI remains offline with respect to TikHub/Provider execution and covers Python 3.10/3.12/3.13.
- No database migration is added solely for Workbench.
- The first local acceptance target is `run_20260826T140750Z`; no counts or IDs from that run may be hard-coded in product code.

---

## File Structure Locked by This Plan

```text
web/
├── __init__.py
├── backend/
│   ├── __init__.py
│   ├── app.py
│   ├── models.py
│   ├── run_repository.py
│   ├── run_summary.py
│   ├── flow_service.py
│   ├── lineage_service.py
│   ├── media_service.py
│   └── routes/
│       ├── __init__.py
│       ├── health.py
│       ├── runs.py
│       ├── entities.py
│       ├── evidence.py
│       ├── intelligence.py
│       └── media.py
└── frontend/
    ├── package.json
    ├── package-lock.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── index.html
    ├── src/
    │   ├── main.tsx
    │   ├── app/App.tsx
    │   ├── app/api.ts
    │   ├── app/types.ts
    │   ├── app/format.ts
    │   ├── components/
    │   │   ├── AppShell.tsx
    │   │   ├── DataTable.tsx
    │   │   ├── JsonViewer.tsx
    │   │   ├── MetricCard.tsx
    │   │   ├── StageFlow.tsx
    │   │   └── StateNotice.tsx
    │   ├── pages/
    │   │   ├── RunsPage.tsx
    │   │   ├── OverviewPage.tsx
    │   │   ├── FlowPage.tsx
    │   │   ├── VideosPage.tsx
    │   │   ├── VideoDetailPage.tsx
    │   │   ├── CreatorsPage.tsx
    │   │   ├── CreatorDetailPage.tsx
    │   │   ├── VocPage.tsx
    │   │   ├── EvidencePage.tsx
    │   │   ├── EvidenceDetailPage.tsx
    │   │   ├── MediaPage.tsx
    │   │   ├── IntelligencePage.tsx
    │   │   ├── ReportPage.tsx
    │   │   └── ExecutionPage.tsx
    │   └── styles.css
    ├── tests/
    │   ├── runs.test.tsx
    │   ├── flow.test.tsx
    │   └── evidence.test.tsx
    └── dist/

scripts/
├── research_web.py
├── workbench_test_fixture.py
├── workbench_acceptance.py
└── test_phase12_workbench.py
```

---

### Task 1: Establish Web Runtime Dependencies and Deterministic Test Fixture

**Files:**
- Modify: `requirements.txt`
- Create: `web/__init__.py`
- Create: `web/backend/__init__.py`
- Create: `web/backend/routes/__init__.py`
- Create: `scripts/workbench_test_fixture.py`
- Create: `scripts/test_phase12_workbench.py`

**Interfaces:**
- Produces: `build_fixture_run(root: Path, run_id: str = "run_fixture") -> Path`.
- Fixture produces `plan.json`, `execution.json`, `run.sqlite`, `raw/`, and `reports/` with representative v1.1.x data for videos, creators, comments, VOC labels, findings, media, patterns, insights, hypotheses, briefs, and raw evidence.
- Later tasks import this fixture; production modules must never import it.

- [ ] **Step 1: Write the failing dependency/fixture tests**

```python
class Phase12FixtureTests(unittest.TestCase):
    def test_requirements_include_web_runtime(self):
        text = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
        for dep in ["fastapi", "uvicorn", "httpx"]:
            self.assertIn(dep, text)

    def test_fixture_builds_complete_read_only_run_shape(self):
        from workbench_test_fixture import build_fixture_run
        with tempfile.TemporaryDirectory() as td:
            run_dir = build_fixture_run(Path(td))
            self.assertTrue((run_dir / "plan.json").exists())
            self.assertTrue((run_dir / "execution.json").exists())
            self.assertTrue((run_dir / "run.sqlite").exists())
            self.assertTrue((run_dir / "raw").is_dir())
            self.assertTrue((run_dir / "reports" / "findings.json").exists())
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```bash
PYTHONPATH=scripts python -m unittest scripts/test_phase12_workbench.py -v
```

Expected: FAIL because Web dependencies and `workbench_test_fixture` do not exist.

- [ ] **Step 3: Add runtime dependencies and fixture builder**

Append exact runtime dependencies:

```text
fastapi>=0.115,<1
uvicorn>=0.30,<1
httpx>=0.27,<1
```

Implement fixture creation by executing the existing migrations into a temporary SQLite DB, then insert a small deterministic dataset. The builder signature is fixed:

```python
def build_fixture_run(root: Path, run_id: str = "run_fixture") -> Path:
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    # apply migrations/001..004, insert one creator/video/comment/raw evidence,
    # write plan.json/execution.json/reports artifacts
    return run_dir
```

The fixture raw response must intentionally contain a fake `Authorization`/`api_key` field so later HTTP-redaction tests prove defense-in-depth.

- [ ] **Step 4: Run the focused test and confirm GREEN**

Run:

```bash
PYTHONPATH=scripts python -m unittest scripts/test_phase12_workbench.py -v
```

Expected: PASS for dependency and fixture tests.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt web scripts/workbench_test_fixture.py scripts/test_phase12_workbench.py
git commit -m "test(workbench): add phase 12 fixture foundation"
```

---

### Task 2: Build Read-Only `RunRepository` and `RunSummary`

**Files:**
- Create: `web/backend/models.py`
- Create: `web/backend/run_repository.py`
- Create: `web/backend/run_summary.py`
- Modify: `scripts/test_phase12_workbench.py`

**Interfaces:**
- Produces: `RunRepository(runs_root: Path)`.
- Produces: `RunRepository.discover_runs() -> list[str]`.
- Produces: `RunRepository.run_dir(run_id: str) -> Path` with strict run-ID/path validation.
- Produces: `RunRepository.open_db(run_id: str) -> sqlite3.Connection` read-only/query-only.
- Produces: `RunRepository.table_exists(conn, table: str) -> bool`.
- Produces: `build_run_summary(repo: RunRepository, run_id: str) -> RunSummary`.
- Produces Pydantic models: `RunSummary`, `Page`, `ArtifactAvailability`.

- [ ] **Step 1: Add RED tests for discovery, traversal rejection, read-only SQLite, and summary derivation**

```python
class Phase12RunRepositoryTests(unittest.TestCase):
    def test_repository_discovers_only_run_directories_and_rejects_traversal(self):
        from web.backend.run_repository import RunRepository
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            build_fixture_run(root, "run_fixture")
            (root / "notes").mkdir()
            repo = RunRepository(root)
            self.assertEqual(repo.discover_runs(), ["run_fixture"])
            with self.assertRaises(ValueError):
                repo.run_dir("../escape")

    def test_sqlite_connection_is_query_only(self):
        from web.backend.run_repository import RunRepository
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); build_fixture_run(root)
            repo = RunRepository(root)
            conn = repo.open_db("run_fixture")
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute("CREATE TABLE forbidden(x INTEGER)")
            conn.close()

    def test_summary_uses_artifacts_and_never_invents_cost(self):
        from web.backend.run_repository import RunRepository
        from web.backend.run_summary import build_run_summary
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); build_fixture_run(root)
            summary = build_run_summary(RunRepository(root), "run_fixture")
            self.assertEqual(summary.topic, "fixture topic")
            self.assertEqual(summary.video_count, 1)
            self.assertEqual(summary.provider_calls_attempted, 2)
            self.assertIsNone(summary.actual_estimated_cost_usd)
```

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
PYTHONPATH=scripts:. python -m unittest scripts/test_phase12_workbench.py -v
```

Expected: import failures for `web.backend.run_repository` / `run_summary`.

- [ ] **Step 3: Implement repository and summary models**

Use strict run IDs and containment checks:

```python
RUN_ID_RE = re.compile(r"^run_[A-Za-z0-9._-]+$")

class RunRepository:
    def __init__(self, runs_root: Path):
        self.runs_root = runs_root.resolve()

    def run_dir(self, run_id: str) -> Path:
        if not RUN_ID_RE.fullmatch(run_id):
            raise ValueError("invalid run id")
        candidate = (self.runs_root / run_id).resolve()
        if candidate.parent != self.runs_root or not candidate.is_dir():
            raise FileNotFoundError(run_id)
        return candidate

    def open_db(self, run_id: str) -> sqlite3.Connection:
        db = self.run_dir(run_id) / "run.sqlite"
        conn = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        return conn
```

`build_run_summary` uses the spec priority order: execution/plan → `research_runs`/tables → reports → `null`/unavailable. Do not calculate cost from call count.

- [ ] **Step 4: Run Phase 12 tests and full legacy foundation regression**

```bash
PYTHONPATH=scripts:. python -m unittest scripts/test_phase12_workbench.py -v
PYTHONPATH=scripts python -m unittest scripts/test_phase11_provider_verification.py scripts/test_phase10_live_validation.py scripts/test_phase9.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/backend/models.py web/backend/run_repository.py web/backend/run_summary.py scripts/test_phase12_workbench.py
git commit -m "feat(workbench): add read-only run repository"
```

---

### Task 3: Implement Stage Flow and Plan-vs-Actual Execution Read Models

**Files:**
- Create: `web/backend/flow_service.py`
- Modify: `web/backend/models.py`
- Modify: `scripts/test_phase12_workbench.py`

**Interfaces:**
- Consumes: `RunRepository` from Task 2.
- Produces: `build_stage_flow(repo, run_id) -> list[StageState]`.
- Produces: `build_execution_summary(repo, run_id) -> ExecutionSummary`.
- `StageState.status` is one of `COMPLETED|RUNNING|SKIPPED|FAILED|PLANNED|UNAVAILABLE`.
- `StageState.status_basis` is one of `execution|artifact|inferred|unavailable`.

- [ ] **Step 1: Add RED tests for recorded, skipped, prepared, and unavailable states**

```python
def test_stage_flow_preserves_execution_basis_and_maps_local_states(self):
    flow = build_stage_flow(repo, "run_fixture")
    by_name = {row.name: row for row in flow}
    self.assertEqual(by_name["REFERENCE_SEED"].status, "COMPLETED")
    self.assertEqual(by_name["REFERENCE_SEED"].status_basis, "execution")
    self.assertEqual(by_name["VIDEO_UNDERSTANDING"].status, "PLANNED")

def test_execution_summary_separates_plan_and_actual(self):
    result = build_execution_summary(repo, "run_fixture")
    self.assertEqual(result.expected_requests, 2)
    self.assertEqual(result.calls_attempted, 2)
    self.assertIsNone(result.actual_estimated_cost_usd)
```

- [ ] **Step 2: Run and confirm RED**

```bash
PYTHONPATH=scripts:. python -m unittest scripts/test_phase12_workbench.py -v
```

Expected: missing `flow_service` / models.

- [ ] **Step 3: Implement conservative status mapping**

Map current executor statuses exactly:

```python
EXECUTION_STATUS_MAP = {
    "completed": "COMPLETED",
    "completed_local": "COMPLETED",
    "prepared_local": "PLANNED",
    "awaiting_host_agent": "PLANNED",
    "skipped_no_inputs": "SKIPPED",
    "skipped_insufficient_evidence": "SKIPPED",
    "partial_failed": "FAILED",
    "local_pending": "PLANNED",
}
```

Use actual `plan.json` stage order when present. Only infer from artifacts when execution-stage data is missing, and mark those rows `status_basis="inferred"`.

- [ ] **Step 4: Run tests**

```bash
PYTHONPATH=scripts:. python -m unittest scripts/test_phase12_workbench.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/backend/flow_service.py web/backend/models.py scripts/test_phase12_workbench.py
git commit -m "feat(workbench): expose stage flow and execution summaries"
```

---

### Task 4: Add Video, Creator, Comment and VOC Query Services + Routes

**Files:**
- Create: `web/backend/routes/entities.py`
- Create: `web/backend/routes/runs.py`
- Modify: `web/backend/run_repository.py`
- Modify: `web/backend/models.py`
- Modify: `scripts/test_phase12_workbench.py`

**Interfaces:**
- Produces repository methods: `list_videos`, `get_video`, `list_creators`, `get_creator`, `list_comments`, `get_voc`.
- Collection methods accept explicit `page`, `page_size<=200`, `sort`, `order`, `query`, plus documented entity filters only.
- Produces route factory `router(repo: RunRepository) -> APIRouter` for testable dependency injection.

- [ ] **Step 1: Add RED tests for pagination, sorting whitelist, null metrics, and VOC denominator**

```python
def test_videos_are_paginated_and_reject_unknown_sort(self):
    page = repo.list_videos("run_fixture", page=1, page_size=20, sort="views", order="desc")
    self.assertEqual(page.total, 1)
    self.assertEqual(page.items[0]["video_id"], "video-1")
    with self.assertRaises(ValueError):
        repo.list_videos("run_fixture", page=1, page_size=20, sort="DROP TABLE videos", order="desc")

def test_voc_uses_real_comment_denominator(self):
    voc = repo.get_voc("run_fixture")
    self.assertEqual(voc["denominator"], 1)
    self.assertEqual(voc["labels"][0]["count"], 1)
```

- [ ] **Step 2: Run and confirm RED**

```bash
PYTHONPATH=scripts:. python -m unittest scripts/test_phase12_workbench.py -v
```

Expected: missing repository methods/routes.

- [ ] **Step 3: Implement whitelist-driven SQL and entity read models**

Use explicit sort mappings, never user-provided SQL identifiers:

```python
VIDEO_SORTS = {
    "views": "s.views",
    "engagement_rate": "m.engagement_rate",
    "follower_leverage": "m.follower_leverage",
    "captured_at": "s.captured_at",
}
column = VIDEO_SORTS.get(sort or "views")
if column is None:
    raise ValueError("unsupported video sort")
```

Join latest run-specific snapshots/derived metrics without replacing missing values with zero. Creator/video detail must include their evidence refs where stored.

- [ ] **Step 4: Run focused and migration regression tests**

```bash
PYTHONPATH=scripts:. python -m unittest scripts/test_phase12_workbench.py scripts/test_phase3.py scripts/test_phase4.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/backend/routes/entities.py web/backend/routes/runs.py web/backend/run_repository.py web/backend/models.py scripts/test_phase12_workbench.py
git commit -m "feat(workbench): add entity and VOC read APIs"
```

---

### Task 5: Build Evidence Explorer and Evidence Lineage

**Files:**
- Create: `web/backend/lineage_service.py`
- Create: `web/backend/routes/evidence.py`
- Modify: `web/backend/run_repository.py`
- Modify: `scripts/test_phase12_workbench.py`

**Interfaces:**
- Produces: `get_evidence(repo, run_id, evidence_id) -> dict` with HTTP-boundary redaction.
- Produces: `build_lineage(repo, run_id, evidence_id) -> LineageGraph`.
- Produces typed edges with `source_type/source_id/target_type/target_id/relation`.

- [ ] **Step 1: Add RED tests proving redaction and no fabricated lineage**

```python
def test_evidence_detail_redacts_stored_secret_fields_again(self):
    detail = get_evidence(repo, "run_fixture", "run_fixture:raw:0001")
    serialized = json.dumps(detail)
    self.assertNotIn("Bearer fixture-secret", serialized)
    self.assertNotIn("fixture-api-key", serialized)

def test_lineage_contains_only_stored_references(self):
    graph = build_lineage(repo, "run_fixture", "run_fixture:raw:0001")
    relations = {(e.source_type, e.target_type, e.relation) for e in graph.edges}
    self.assertIn(("raw_evidence", "video", "normalized_as"), relations)
    self.assertFalse(any(e.target_id == "invented" for e in graph.edges))
```

- [ ] **Step 2: Run and confirm RED**

```bash
PYTHONPATH=scripts:. python -m unittest scripts/test_phase12_workbench.py -v
```

Expected: missing evidence/lineage modules.

- [ ] **Step 3: Implement defensive redaction and reverse-ref scanning**

Use the existing utility:

```python
from api_research_core import redact_payload

safe_request = redact_payload(json.loads(row["request_json"]))
safe_response = redact_payload(json.loads(row["response_json"]))
```

Scan only known `raw_evidence_id` columns and known `evidence_refs_json` columns from migrations 001-004. Ignore malformed refs instead of guessing. Evidence list filtering is limited to `endpoint`, `source_type`, `source_key`, `id`, and free-text query over safe metadata.

- [ ] **Step 4: Run Phase 12 and release-audit tests**

```bash
PYTHONPATH=scripts:. python -m unittest scripts/test_phase12_workbench.py scripts/test_phase8.py -v
```

Expected: PASS; no fixture secret appears in test output/artifacts.

- [ ] **Step 5: Commit**

```bash
git add web/backend/lineage_service.py web/backend/routes/evidence.py web/backend/run_repository.py scripts/test_phase12_workbench.py
git commit -m "feat(workbench): add evidence explorer and lineage"
```

---

### Task 6: Add Media, Intelligence and Report Read Services

**Files:**
- Create: `web/backend/media_service.py`
- Create: `web/backend/routes/media.py`
- Create: `web/backend/routes/intelligence.py`
- Modify: `web/backend/run_repository.py`
- Modify: `scripts/test_phase12_workbench.py`

**Interfaces:**
- Produces: `resolve_keyframe_path(repo, run_id, video_id, frame_id) -> Path` with containment validation.
- Produces read methods for media asset/keyframes/transcripts/creative analysis.
- Produces read methods for findings/patterns/insights/hypotheses/briefs.
- Produces `get_report(run_id)` using final-report artifact priority from the spec.

- [ ] **Step 1: Add RED tests for media containment, unavailable media, intelligence refs, and report fallback**

```python
def test_keyframe_resolver_rejects_path_outside_run(self):
    with self.assertRaises(ValueError):
        resolve_keyframe_path(repo, "run_fixture", "video-1", "frame-outside")

def test_report_does_not_fabricate_missing_final_report(self):
    report = repo.get_report("run_fixture")
    self.assertFalse(report["persisted_final_report"])
    self.assertIn("Final report not persisted", report["notice"])

def test_intelligence_preserves_evidence_refs(self):
    findings = repo.list_findings("run_fixture")
    self.assertEqual(findings[0]["evidence_refs"], ["run_fixture:raw:0001"])
```

- [ ] **Step 2: Run and confirm RED**

```bash
PYTHONPATH=scripts:. python -m unittest scripts/test_phase12_workbench.py -v
```

Expected: missing media/intelligence functions.

- [ ] **Step 3: Implement media and intelligence services**

Resolve media by DB IDs only:

```python
path = Path(row["local_path"]).resolve()
run_root = repo.run_dir(run_id).resolve()
if not path.is_relative_to(run_root):
    raise ValueError("media path escapes run directory")
```

`get_report` priority is exactly:

```python
for name in ["final_report.md", "research_report.md", "report.md"]:
    ...
```

When none exists, return structured artifact availability plus the explicit notice from the spec; do not generate a synthetic final report.

- [ ] **Step 4: Run tests**

```bash
PYTHONPATH=scripts:. python -m unittest scripts/test_phase12_workbench.py scripts/test_phase5.py scripts/test_phase6.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/backend/media_service.py web/backend/routes/media.py web/backend/routes/intelligence.py web/backend/run_repository.py scripts/test_phase12_workbench.py
git commit -m "feat(workbench): expose media and intelligence artifacts"
```

---

### Task 7: Assemble FastAPI App, Health API, Static SPA Delivery, and Local Launcher

**Files:**
- Create: `web/backend/routes/health.py`
- Create: `web/backend/app.py`
- Create: `scripts/research_web.py`
- Modify: `scripts/test_phase12_workbench.py`

**Interfaces:**
- Produces: `create_app(runs_root: Path, frontend_dist: Path | None = None) -> FastAPI`.
- Produces CLI `python scripts/research_web.py [--port N] [--runs-root PATH] [--no-open]`.
- Host is not a CLI option and is always `127.0.0.1`.

- [ ] **Step 1: Add RED HTTP/security tests with FastAPI TestClient**

```python
def test_health_and_runs_api_are_local_read_models(self):
    app = create_app(root, frontend_dist=None)
    client = TestClient(app)
    self.assertEqual(client.get("/api/health").status_code, 200)
    payload = client.get("/api/runs").json()
    self.assertEqual(payload[0]["run_id"], "run_fixture")

def test_browser_cannot_request_arbitrary_filesystem_path(self):
    paths = [route.path for route in create_app(root, frontend_dist=None).routes]
    self.assertFalse(any("{path" in p for p in paths if p.startswith("/api")))

def test_launcher_has_no_host_option(self):
    text = (ROOT / "scripts" / "research_web.py").read_text(encoding="utf-8")
    self.assertNotIn('add_argument("--host"', text)
    self.assertIn('host="127.0.0.1"', text)
```

- [ ] **Step 2: Run and confirm RED**

```bash
PYTHONPATH=scripts:. python -m unittest scripts/test_phase12_workbench.py -v
```

Expected: missing app/launcher.

- [ ] **Step 3: Implement app factory and launcher**

Launcher root resolution must be deterministic:

```python
def resolve_runs_root(skill_root: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    social = skill_root / "social-research" / "runs"
    legacy = skill_root / "runs"
    if social.exists():
        return social
    if legacy.exists():
        return legacy
    return social
```

`create_app` mounts all `/api` routers. If `frontend_dist` exists, serve its assets and return `index.html` only for non-API SPA routes. Never let SPA fallback swallow `/api/*` 404s.

- [ ] **Step 4: Run Phase 12 tests and Python compile check**

```bash
PYTHONPATH=scripts:. python -m unittest scripts/test_phase12_workbench.py -v
python -m compileall -q scripts web/backend
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/backend/app.py web/backend/routes/health.py scripts/research_web.py scripts/test_phase12_workbench.py
git commit -m "feat(workbench): add local FastAPI launcher"
```

---

### Task 8: Scaffold React App, Typed API Client, Runs Home, Overview and Flow

**Files:**
- Create: `web/frontend/package.json`
- Create: `web/frontend/package-lock.json`
- Create: `web/frontend/tsconfig.json`
- Create: `web/frontend/vite.config.ts`
- Create: `web/frontend/index.html`
- Create: `web/frontend/src/main.tsx`
- Create: `web/frontend/src/app/App.tsx`
- Create: `web/frontend/src/app/api.ts`
- Create: `web/frontend/src/app/types.ts`
- Create: `web/frontend/src/app/format.ts`
- Create: `web/frontend/src/components/AppShell.tsx`
- Create: `web/frontend/src/components/MetricCard.tsx`
- Create: `web/frontend/src/components/StageFlow.tsx`
- Create: `web/frontend/src/components/StateNotice.tsx`
- Create: `web/frontend/src/pages/RunsPage.tsx`
- Create: `web/frontend/src/pages/OverviewPage.tsx`
- Create: `web/frontend/src/pages/FlowPage.tsx`
- Create: `web/frontend/src/styles.css`
- Create: `web/frontend/tests/runs.test.tsx`
- Create: `web/frontend/tests/flow.test.tsx`

**Interfaces:**
- Consumes `/api/runs`, `/api/runs/{run_id}`, `/api/runs/{run_id}/flow`.
- Produces route shell: `/`, `/runs/:runId/overview`, `/runs/:runId/flow`, with later task routes registered in the same nav.
- `api.ts` exports typed `apiGet<T>(path: string, params?: Record<string,string|number|undefined>): Promise<T>`.

- [ ] **Step 1: Create package manifest and RED component tests**

Required dependencies:

```json
{
  "dependencies": {
    "@tanstack/react-query": "^5.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-markdown": "^10.0.0",
    "react-router-dom": "^7.0.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.0.0",
    "@testing-library/react": "^16.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.0.0",
    "jsdom": "^26.0.0",
    "typescript": "^5.7.0",
    "vite": "^6.0.0",
    "vitest": "^3.0.0"
  }
}
```

Test behavior:

```tsx
it("renders business-readable run metrics", async () => {
  render(<RunsPage />)
  expect(await screen.findByText("fixture topic")).toBeInTheDocument()
  expect(screen.getByText("1 video")).toBeInTheDocument()
})

it("labels inferred stage status", () => {
  render(<StageFlow stages={[{name:"VOC", status:"COMPLETED", status_basis:"inferred"}]} />)
  expect(screen.getByText(/inferred/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Install and run tests to confirm RED**

```bash
cd web/frontend
npm install
npm test -- --run
```

Expected: FAIL because app/components/pages are missing.

- [ ] **Step 3: Implement shell, types, API client and first three screens**

Use `QueryClientProvider` in `main.tsx`, keep technical IDs secondary, and render state basis as visible text/icon rather than color only. `vite.config.ts` must set deterministic asset names:

```ts
build: {
  sourcemap: false,
  rollupOptions: {
    output: {
      entryFileNames: "assets/app.js",
      chunkFileNames: "assets/[name].js",
      assetFileNames: "assets/[name][extname]"
    }
  }
}
```

- [ ] **Step 4: Run unit tests and production build**

```bash
npm test -- --run
npm run build
```

Expected: PASS and `web/frontend/dist/index.html` exists.

- [ ] **Step 5: Commit**

```bash
git add web/frontend
git commit -m "feat(workbench): add runs overview and flow UI"
```

---

### Task 9: Implement Videos, Creators and VOC Web Views

**Files:**
- Create: `web/frontend/src/components/DataTable.tsx`
- Create: `web/frontend/src/pages/VideosPage.tsx`
- Create: `web/frontend/src/pages/VideoDetailPage.tsx`
- Create: `web/frontend/src/pages/CreatorsPage.tsx`
- Create: `web/frontend/src/pages/CreatorDetailPage.tsx`
- Create: `web/frontend/src/pages/VocPage.tsx`
- Modify: `web/frontend/src/app/App.tsx`
- Modify: `web/frontend/tests/runs.test.tsx`

**Interfaces:**
- Consumes Task 4 APIs and `Page<T>` types.
- `DataTable` receives columns, rows, sort state, and pagination callbacks; it never loads all rows client-side.

- [ ] **Step 1: Add RED UI tests for nulls, pagination and VOC drill-down**

```tsx
it("renders missing metrics as em dash instead of zero", () => {
  render(<DataTable columns={columns} rows={[{views: null}]} />)
  expect(screen.getByText("—")).toBeInTheDocument()
})

it("shows VOC as run sample statistics and opens matching comments", async () => {
  render(<VocPage />)
  expect(await screen.findByText(/run sample/i)).toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", {name:/真实性/}))
  expect(await screen.findByText("fixture comment")).toBeInTheDocument()
})
```

- [ ] **Step 2: Run and confirm RED**

```bash
cd web/frontend
npm test -- --run
```

Expected: FAIL because pages/DataTable do not exist.

- [ ] **Step 3: Implement server-paginated entity views**

Videos show caption, creator, followers, latest snapshot metrics, engagement/follower leverage, source, and media/deep-analysis status. Detail pages expose linked evidence IDs as clickable links to the Evidence route. VOC label percentages are computed/rendered from the API-provided denominator, never a platform-wide claim.

- [ ] **Step 4: Run tests and build**

```bash
npm test -- --run
npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src web/frontend/tests web/frontend/dist
git commit -m "feat(workbench): add entity and VOC exploration UI"
```

---

### Task 10: Implement Evidence, Media, Intelligence, Report and Cost Web Views

**Files:**
- Create: `web/frontend/src/components/JsonViewer.tsx`
- Create: `web/frontend/src/pages/EvidencePage.tsx`
- Create: `web/frontend/src/pages/EvidenceDetailPage.tsx`
- Create: `web/frontend/src/pages/MediaPage.tsx`
- Create: `web/frontend/src/pages/IntelligencePage.tsx`
- Create: `web/frontend/src/pages/ReportPage.tsx`
- Create: `web/frontend/src/pages/ExecutionPage.tsx`
- Modify: `web/frontend/src/app/App.tsx`
- Create: `web/frontend/tests/evidence.test.tsx`

**Interfaces:**
- Consumes Task 5/6/3 APIs.
- Evidence detail renders safe JSON and reverse references.
- Intelligence renders five visibly distinct sections: Findings/Observations, Patterns, Insights, Hypotheses, Briefs.
- Report uses `react-markdown`; raw HTML remains disabled.

- [ ] **Step 1: Add RED tests for evidence lineage, semantic separation and cost labeling**

```tsx
it("shows evidence used-by lineage and collapsed JSON", async () => {
  render(<EvidenceDetailPage />)
  expect(await screen.findByText(/Used by/i)).toBeInTheDocument()
  expect(screen.getByRole("button", {name:/show response json/i})).toBeInTheDocument()
})

it("keeps evidence intelligence layers visibly separate", async () => {
  render(<IntelligencePage />)
  for (const label of ["Findings", "Patterns", "Insights", "Hypotheses", "Briefs"])
    expect(await screen.findByRole("heading", {name: label})).toBeInTheDocument()
})

it("labels provider cost as estimate, not invoice", async () => {
  render(<ExecutionPage />)
  expect(await screen.findByText(/estimate/i)).toBeInTheDocument()
  expect(screen.queryByText(/invoice/i)).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Run and confirm RED**

```bash
cd web/frontend
npm test -- --run
```

Expected: FAIL because pages/components are missing.

- [ ] **Step 3: Implement remaining Workbench screens**

`JsonViewer` is collapsed by default. Media page shows asset status/error even when no downloadable asset exists. Keyframes use backend ID routes only. Report page displays the persisted-report notice when absent. Intelligence cards show confidence/status and evidence links when available.

- [ ] **Step 4: Run tests and production build**

```bash
npm test -- --run
npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src web/frontend/tests web/frontend/dist
git commit -m "feat(workbench): complete evidence and intelligence UI"
```

---

### Task 11: Add CI Web Gates and Runtime Distribution Audit

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `scripts/test_phase12_workbench.py`
- Modify: `scripts/release_check.py`
- Modify: `web/frontend/vite.config.ts`

**Interfaces:**
- CI Python matrix includes Phase 12 backend tests.
- Separate frontend job uses Node 22, `npm ci`, Vitest, TypeScript/Vite build, and verifies committed `dist/` is current.
- Release audit requires Workbench source plus built `dist/index.html` and rejects obvious secret-bearing frontend artifacts.

- [ ] **Step 1: Add RED distribution assertions**

```python
def test_ci_runs_phase12_and_frontend_without_provider_execution(self):
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    self.assertIn("test_phase12_workbench.py", text)
    self.assertIn("npm ci", text)
    self.assertIn("npm test -- --run", text)
    self.assertNotIn("live_validation.py --execute", text)
    self.assertNotIn("run_research.py --yes", text)

def test_bundled_frontend_distribution_exists(self):
    self.assertTrue((ROOT / "web" / "frontend" / "dist" / "index.html").exists())
```

- [ ] **Step 2: Run and confirm RED**

```bash
PYTHONPATH=scripts:. python -m unittest scripts/test_phase12_workbench.py -v
```

Expected: FAIL until CI/release audit are updated.

- [ ] **Step 3: Update CI and release audit**

Add frontend job:

```yaml
frontend-tests:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: "22"
        cache: npm
        cache-dependency-path: web/frontend/package-lock.json
    - run: npm ci
      working-directory: web/frontend
    - run: npm test -- --run
      working-directory: web/frontend
    - run: npm run build
      working-directory: web/frontend
    - run: git diff --exit-code -- web/frontend/dist
```

Add `scripts/test_phase12_workbench.py` to the Python loop. Extend `release_check.py` required paths with `web/frontend/dist/index.html`, `web/backend/app.py`, and `scripts/research_web.py` while retaining all existing secret checks.

- [ ] **Step 4: Run all local offline gates**

```bash
PYTHONPATH=scripts:. python -m unittest scripts/test_phase12_workbench.py -v
python scripts/test_skill.py
python -m compileall -q scripts web/backend
python scripts/release_check.py --root .
cd web/frontend && npm test -- --run && npm run build && cd ../..
```

Expected: all PASS; no Provider/TikHub calls.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml scripts/test_phase12_workbench.py scripts/release_check.py web/frontend
git commit -m "ci(workbench): gate backend frontend and bundled build"
```

---

### Task 12: Add Real-Run Acceptance Harness, Docs, Version 1.2.0 and Final Release Gate

**Files:**
- Create: `scripts/workbench_acceptance.py`
- Modify: `README.md`
- Modify: `SKILL.md`
- Modify: `docs/RELEASE.md`
- Modify: `VERSION`
- Modify: `scripts/test_phase12_workbench.py`

**Interfaces:**
- Produces CLI:

```text
python scripts/workbench_acceptance.py \
  --runs-root <path> \
  --run-id <run_id> \
  [--expect-videos N] [--expect-creators N] [--expect-comments N]
```

- Acceptance is read-only and calls `create_app(... )` with FastAPI TestClient; it does not start a Provider call or mutate a run.
- For the current local acceptance run, expected values are supplied by command-line flags, never hard-coded.

- [ ] **Step 1: Add RED acceptance/version/docs tests**

```python
def test_version_is_1_2_0_at_release(self):
    self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), "1.2.0")

def test_docs_explain_workbench_and_read_only_boundary(self):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for token in ["Research Workbench", "python scripts/research_web.py", "127.0.0.1:8765", "read-only"]:
        self.assertIn(token, readme)
```

Acceptance script exits nonzero if required APIs fail, counts differ from explicitly supplied expectations, evidence endpoint exposes a secret-like fixture value, or stage-flow endpoint is unreadable.

- [ ] **Step 2: Run and confirm RED**

```bash
PYTHONPATH=scripts:. python -m unittest scripts/test_phase12_workbench.py -v
```

Expected: FAIL on VERSION/docs/acceptance script.

- [ ] **Step 3: Implement acceptance script and release docs/version**

Core acceptance logic:

```python
app = create_app(Path(args.runs_root), frontend_dist=ROOT / "web" / "frontend" / "dist")
client = TestClient(app)
summary = client.get(f"/api/runs/{args.run_id}").json()
flow = client.get(f"/api/runs/{args.run_id}/flow").json()
assert summary["run_id"] == args.run_id
assert flow
```

Document one-command Web startup, full Workbench tabs, data provenance semantics, existing v1.1.x compatibility, and the explicit v1.2.0 rule that Web cannot launch paid Provider work.

Set:

```text
VERSION=1.2.0
```

- [ ] **Step 4: Run complete offline release suite and current real-run acceptance**

Offline suite:

```bash
PYTHONPATH=scripts:. python -m unittest \
  scripts/test_phase12_workbench.py \
  scripts/test_phase11_provider_verification.py \
  scripts/test_phase10_live_validation.py \
  scripts/test_phase9_budget.py \
  scripts/test_phase9_cli.py \
  scripts/test_phase9.py \
  scripts/test_phase8.py \
  scripts/test_phase7.py \
  scripts/test_phase6.py \
  scripts/test_phase5.py \
  scripts/test_phase4.py \
  scripts/test_phase3.py \
  scripts/test_phase2.py \
  scripts/test_foundation.py -v
python scripts/test_skill.py
python -m compileall -q scripts web/backend
python scripts/release_check.py --root .
cd web/frontend && npm ci && npm test -- --run && npm run build && cd ../..
```

Current real-run local acceptance:

```powershell
python scripts/workbench_acceptance.py `
  --runs-root social-research\runs `
  --run-id run_20260826T140750Z `
  --expect-videos 168 `
  --expect-creators 16 `
  --expect-comments 193
```

Expected report:

```text
WORKBENCH_ACCEPTANCE=PASS
RUN_ID=run_20260826T140750Z
VIDEOS=168
CREATORS=16
COMMENTS=193
FLOW_VISIBLE=YES
EVIDENCE_VISIBLE=YES
PROVIDER_CALLS_MADE=0
RUN_MUTATION=NO
```

Then launch for visual acceptance:

```powershell
python scripts/research_web.py --runs-root social-research\runs
```

Codex/worker must verify in the browser that the current run appears on Runs Home and that Overview, Flow, Videos, Creators, VOC, Evidence, Media, Intelligence, Report, and Cost & Execution routes load without console/runtime errors. This visual check does not authorize or trigger Provider calls.

- [ ] **Step 5: Commit final release changes**

```bash
git add scripts/workbench_acceptance.py README.md SKILL.md docs/RELEASE.md VERSION scripts/test_phase12_workbench.py web/frontend/dist
git commit -m "release: modular-research v1.2.0 research workbench"
```

---

## Final Verification Before PR Readiness

Run all of the following from a clean checkout of the feature branch:

```bash
python -m pip install -r requirements.txt
PYTHONPATH=scripts:. python -m unittest scripts/test_phase12_workbench.py -v
python scripts/test_skill.py
python -m compileall -q scripts web/backend
python scripts/release_check.py --root .
cd web/frontend
npm ci
npm test -- --run
npm run build
cd ../..
git diff --exit-code -- web/frontend/dist
```

Then verify CI on the exact feature HEAD for Python 3.10, 3.12, 3.13 and frontend-tests. No PR may be marked ready until all checks pass.

## Spec Coverage Self-Review Matrix

| Spec requirement | Implementation task |
|---|---|
| Local-only FastAPI + launcher | Task 7 |
| React/TypeScript bundled SPA | Tasks 8-10 |
| Runtime without Node | Tasks 8, 11 |
| Run discovery/history/summary | Task 2, Task 8 |
| Stage flow + status basis | Task 3, Task 8 |
| Videos/creators/VOC | Tasks 4, 9 |
| Evidence explorer + redaction | Tasks 5, 10 |
| Evidence lineage | Tasks 5, 10 |
| Media/keyframes/OCR/transcript | Tasks 6, 10 |
| Findings/patterns/insights/hypotheses/briefs | Tasks 6, 10 |
| Report artifact priority | Tasks 6, 10 |
| Plan vs Actual / cost labeling | Tasks 3, 10 |
| Read-only SQLite/filesystem security | Tasks 2, 6, 7 |
| Old/partial v1.1.x compatibility | Tasks 1-3, 6 |
| Pagination/max page size | Task 4, Task 9 |
| Mobile/responsive/accessible states | Tasks 8-10 |
| Offline CI / no TikHub | Task 11 |
| Existing real run acceptance | Task 12 |
| v1.2.0 docs/release/version | Task 12 |

## Execution Handoff

Recommended execution mode: **Subagent-Driven Development**. Each task above is independently reviewable and should use a fresh implementation context, TDD RED→GREEN, then spec/compliance review before the next task. If subagents are unavailable in the current product, execute the same tasks sequentially with the executing-plans workflow and preserve the same review gates.
