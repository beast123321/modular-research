# Research Workbench v1.3.0 Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconcile the existing Research Workbench implementation with released v1.2.0, make frontend CI truthful, continue the existing frontend RED/GREEN cycle, and prepare PR #6 for a future v1.3.0 release without mutating `main`.

**Architecture:** Preserve the existing Workbench history and read-only FastAPI/React architecture. Merge v1.2.0 into the feature branch with an explicit CI conflict resolution, then make the React tests first-class CI gates and continue implementation from the already-committed RED tests.

**Tech Stack:** Python >=3.10, FastAPI, Uvicorn, sqlite3, Pydantic, React 19, TypeScript, Vite 6, Vitest 3, Testing Library, GitHub Actions Node 22.

**Spec:** `docs/superpowers/specs/2026-08-27-research-workbench-v1.3.0-reconciliation-design.md`

## Global Constraints

- Released base is `main@c4889927da20bc39af3143bf97436ae450e6e17b` with `VERSION=1.2.0`.
- Workbench target release is `1.3.0`.
- Keep repository `VERSION=1.2.0` until the explicit final v1.3.0 release task.
- Preserve all v1.2.0 TikTok Provider Verification tests and Registry evidence.
- No TikHub/Provider calls from CI or Workbench runtime.
- No evidence/config/database mutation from Web.
- Host remains fixed to `127.0.0.1`.
- SQLite remains read-only with `mode=ro` and `PRAGMA query_only=ON`.
- Raw evidence must be recursively redacted at the HTTP boundary.
- No arbitrary browser-selected filesystem paths.
- No force-push/rebase of PR #6 history.
- No merge of PR #6 to `main` without a separate explicit authorization.

---

### Task 1: Reconcile PR #6 with released v1.2.0

**Files:**
- Merge: `main` into `feat/research-workbench-v1.2.0`
- Resolve: `.github/workflows/ci.yml`
- Create: `docs/superpowers/specs/2026-08-27-research-workbench-v1.3.0-reconciliation-design.md`
- Create: `docs/superpowers/plans/2026-08-27-research-workbench-v1.3.0-reconciliation.md`
- Update: PR #6 metadata

**Interfaces:**
- Produces a feature branch with `behind_by=0` against `main`.
- Produces a CI Python matrix containing both v1.2.0 Provider release tests and Workbench backend/HTTP tests.

- [x] **Step 1: Build a two-parent merge commit without rewriting Workbench history**

First parent is current feature HEAD; second parent is `c4889927da20bc39af3143bf97436ae450e6e17b`.

- [x] **Step 2: Resolve CI test inventory**

The Python matrix must include, before historical suites:

```text
scripts/test_phase13_tiktok_release.py
scripts/test_phase12_tiktok_provider_verification.py
scripts/test_phase12_provider_integrity.py
scripts/test_phase12_workbench.py
scripts/test_phase12_http.py
scripts/test_phase11_provider_verification.py
```

Compile both trees:

```bash
python -m compileall -q scripts web
```

- [x] **Step 3: Verify branch relationship**

Expected compare result:

```text
status=ahead
behind_by=0
merge_base=main@c4889927da20bc39af3143bf97436ae450e6e17b
```

- [ ] **Step 4: Update PR #6 title/body to v1.3.0 authority**

PR title:

```text
feat: Research Workbench v1.3.0
```

Body must identify the v1.3.0 reconciliation spec/plan as authoritative and the v1.2.0 docs as historical provenance.

- [ ] **Step 5: Confirm Python reconciliation CI is green**

All Python 3.10/3.12/3.13 jobs must pass before calling backend integration green.

---

### Task 2: Make frontend tests a deterministic CI gate

**Files:**
- Modify: `web/frontend/package.json`
- Create: `web/frontend/package-lock.json`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Produces script `test:ci -> vitest run`.
- Produces a `frontend-tests` GitHub Actions job using Node 22.

- [x] **Step 1: Add non-watch frontend test command**

```json
"test:ci": "vitest run"
```

- [ ] **Step 2: Generate and commit package lock**

Use the branch-scoped `frontend-bootstrap-lock` workflow to execute:

```bash
npm install --package-lock-only --ignore-scripts
```

Commit only `web/frontend/package-lock.json` from that workflow.

- [ ] **Step 3: Add frontend CI job**

```yaml
  frontend-tests:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: web/frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: web/frontend/package-lock.json
      - name: Install frontend dependencies
        run: npm ci
      - name: Run frontend tests
        run: npm run test:ci
      - name: Build frontend
        run: npm run build
```

- [ ] **Step 4: Verify the expected RED**

Expected: frontend job FAILS because the committed tests import production modules under `web/frontend/src/` that do not exist yet. This is the required TDD RED evidence, not a regression to hide.

---

### Task 3: Implement the Runs page RED test

**Files:**
- Read: `web/frontend/tests/runs.test.tsx`
- Create: `web/frontend/src/main.tsx`
- Create: `web/frontend/src/app/App.tsx`
- Create: `web/frontend/src/app/api.ts`
- Create: `web/frontend/src/app/types.ts`
- Create: `web/frontend/src/pages/RunsPage.tsx`

**Interfaces:**
- `RunsPage` fetches `/api/runs` through the shared API client.
- It renders run ID/topic/platform/status values supplied by the backend read model.
- Navigation uses the route expected by the committed test.

- [ ] **Step 1: Re-run only Runs test and confirm RED cause**

```bash
cd web/frontend
npm run test:ci -- tests/runs.test.tsx
```

Expected: module/import failure for missing production source, or the exact missing UI behavior asserted by the test.

- [ ] **Step 2: Implement only the minimum app/query/router surface required by the test**

Do not add unrelated pages.

- [ ] **Step 3: Re-run Runs test**

Expected: PASS.

- [ ] **Step 4: Re-run all frontend tests**

Expected: Runs PASS; StageFlow may remain RED until Task 4.

---

### Task 4: Implement the StageFlow RED test

**Files:**
- Read: `web/frontend/tests/flow.test.tsx`
- Create: `web/frontend/src/components/StageFlow.tsx`
- Create: `web/frontend/src/pages/FlowPage.tsx`
- Modify: `web/frontend/src/app/App.tsx`
- Modify: `web/frontend/src/app/types.ts`

**Interfaces:**
- `StageFlow` consumes backend stage-state read models without inventing completion.
- States must distinguish completed, failed, prepared/pending and unavailable as required by the existing test.

- [ ] **Step 1: Run flow test and confirm RED**

```bash
cd web/frontend
npm run test:ci -- tests/flow.test.tsx
```

- [ ] **Step 2: Implement the minimum StageFlow and route**

No additional stage semantics beyond stored/derived backend state.

- [ ] **Step 3: Run full frontend test suite**

```bash
npm run test:ci
```

Expected: current committed frontend tests PASS.

- [ ] **Step 4: Run frontend build**

```bash
npm run build
```

Expected: PASS.

---

### Task 5: Expand Workbench views using test-first slices

**Files:**
- Create/modify under `web/frontend/src/`
- Add tests under `web/frontend/tests/`
- Reuse existing backend routes under `web/backend/routes/`

**Interfaces:**
- Evidence views consume `/api/runs/{run_id}/evidence` and supported lineage endpoints.
- Entity views consume videos/creators read models.
- Media/intelligence/report/execution views remain read-only.

For each slice in this order:

```text
Evidence + lineage
Videos + video detail
Creators + creator detail
VOC
Media
Intelligence
Report
Execution
```

repeat exactly:

- [ ] write one behavior test;
- [ ] run it and confirm RED for the intended missing behavior;
- [ ] implement the minimum UI/API typing;
- [ ] run focused test to GREEN;
- [ ] run full frontend suite;
- [ ] commit the slice.

Do not batch untested pages into a large implementation commit.

---

### Task 6: Node-free bundle and real-run acceptance

**Files:**
- Create/commit: `web/frontend/dist/`
- Modify backend static serving only if required by tests
- Create: `scripts/workbench_acceptance.py` if still absent
- Add acceptance tests before production changes

**Interfaces:**
- Runtime command remains Python-based through `scripts/research_web.py`.
- Browser receives bundled SPA without Node running.

- [ ] **Step 1: Add failing static-serving/runtime acceptance tests**
- [ ] **Step 2: Build and commit frontend dist**
- [ ] **Step 3: Verify Python runtime serves SPA and `/api` from `127.0.0.1`**
- [ ] **Step 4: Run acceptance against `run_20260826T140750Z`**
- [ ] **Step 5: Confirm no IDs/counts from that run are hard-coded**

---

### Task 7: v1.3.0 release gate

**Files:**
- Modify only after all implementation/acceptance gates are green: `VERSION`, release docs, frontend package version if release policy requires it

- [ ] **Step 1: Run complete Python matrix-equivalent tests locally/CI**
- [ ] **Step 2: Run complete frontend test/build gate**
- [ ] **Step 3: Run public release/security audit**
- [ ] **Step 4: Run real-run acceptance**
- [ ] **Step 5: Change `VERSION` from 1.2.0 to 1.3.0**
- [ ] **Step 6: Run all gates again on the exact release HEAD**
- [ ] **Step 7: Request whole-branch review**

PR #6 must remain Draft until these gates are satisfied. Do not merge automatically.
