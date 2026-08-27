# Research Workbench v1.3.0 Reconciliation Design

## Status

Approved architectural reconciliation for Draft PR #6 after `modular-research` v1.2.0 TikTok Provider Verification shipped to `main`.

This document is authoritative for versioning, integration and remaining Workbench execution. The earlier files:

- `docs/superpowers/specs/2026-08-27-research-workbench-v1.2.0-design.md`
- `docs/superpowers/plans/2026-08-27-research-workbench-v1.2.0.md`

remain historical design/implementation provenance. Their product architecture is retained unless this document explicitly overrides it.

## Baseline

- Released base: `main@c4889927da20bc39af3143bf97436ae450e6e17b`.
- Released version: `VERSION=1.2.0`.
- v1.2.0 owns TikTok Provider Verification and its Phase 12/13 regression contracts.
- Workbench target release is now **v1.3.0**.
- The existing branch name `feat/research-workbench-v1.2.0` is retained to preserve commit/PR provenance; branch naming is not release authority.
- Draft PR #6 remains the integration surface.

## Product scope retained

Research Workbench remains a bundled, local-only, read-only Web product over existing research runs:

- FastAPI backend over run directories and SQLite artifacts;
- React + TypeScript SPA;
- run history and stage flow;
- videos, creators, VOC, evidence, media, intelligence, report and execution views;
- evidence lineage back to stored Provider evidence;
- no paid ResearchRun launch from Web;
- no Provider calls from Web;
- no evidence/config mutation;
- bind fixed to `127.0.0.1`;
- runtime must not require Node after the built frontend is committed;
- no license change.

## Versioning override

The old v1.2.0 Workbench plan said to keep `VERSION=1.1.3` until release. That statement is superseded.

For v1.3.0 development:

- keep repository `VERSION=1.2.0` throughout implementation and acceptance;
- do not mutate the released v1.2.0 Provider Verification metadata;
- only the final v1.3.0 release task may set `VERSION=1.3.0`;
- frontend package metadata may remain `1.2.0` during development and is synchronized during final release packaging.

## Reconciliation strategy

Use a normal two-parent merge commit, never rebase or force-push the 42+ commit Workbench history.

The merge result must:

1. contain the full v1.2.0 `main` tree;
2. overlay Workbench files from PR #6;
3. explicitly resolve `.github/workflows/ci.yml` so both release regression suites and Workbench Python tests run;
4. leave `main` unchanged;
5. leave TikHub/Provider execution disabled in CI.

After reconciliation, `git compare main...feature` must report `behind_by=0`.

## CI truth model

A green Python matrix is not sufficient evidence for Workbench completion.

Required CI gates are:

### Python offline matrix

Python 3.10 / 3.12 / 3.13 must run:

- Phase 13 TikTok v1.2.0 release assertions;
- Phase 12 TikTok Provider Verification tests;
- Phase 12 Provider integrity tests;
- Phase 12 Workbench backend tests;
- Phase 12 Workbench HTTP tests;
- all prior provider/planner/foundation regressions;
- legacy suite;
- compileall for `scripts` and `web`;
- public release audit;
- core environment check.

### Frontend gate

Node 22 must run from `web/frontend`:

1. deterministic dependency install from committed `package-lock.json` using `npm ci`;
2. `npm run test:ci` (`vitest run`);
3. `npm run build`.

Frontend tests are allowed and expected to be RED before production source is added. The branch must not be described as fully green until this gate passes.

## TDD continuation point

At reconciliation time the branch already contains RED tests for:

- Runs page rendering and run navigation;
- StageFlow state rendering.

There is no committed `web/frontend/src/` implementation yet. Continue from those tests rather than rewriting them after implementation.

Implementation order:

1. RunsPage + minimal app/query/router shell;
2. StageFlow + FlowPage;
3. evidence browsing + lineage;
4. videos/creators/VOC/media/intelligence/report/execution views;
5. build artifact and Node-free runtime serving;
6. real-run acceptance using `run_20260826T140750Z` without hard-coded IDs/counts;
7. v1.3.0 release closeout.

## Security invariants

- Never expose `TIKHUB_API_KEY`, environment variables, configuration secrets or arbitrary local paths over HTTP.
- Browser input must never select arbitrary filesystem paths.
- SQLite remains read-only (`mode=ro`, `PRAGMA query_only=ON`).
- Raw evidence is recursively redacted again at the HTTP boundary.
- Media routes must remain constrained to the selected run directory.
- `null` is preserved as `null`; missing data is not fabricated as zero.
- Missing optional v1.1.x/v1.2.0 artifacts render as unavailable/empty sections instead of failing the run.

## Acceptance boundary

PR #6 becomes merge-ready only when all of the following are true:

- branch is based on current v1.2.0 main (`behind_by=0`);
- PR metadata names v1.3.0 and points to this reconciliation design/plan;
- Python 3.10/3.12/3.13 matrix is green;
- frontend Vitest/build gate is green;
- no Provider call occurs during CI or Workbench runtime;
- built frontend is served locally without Node runtime dependency;
- real-run acceptance passes on `run_20260826T140750Z`;
- whole-branch security/release review has no blocking finding;
- `VERSION` remains 1.2.0 until the explicit final v1.3.0 release commit.

No merge to `main` is authorized by this design.
