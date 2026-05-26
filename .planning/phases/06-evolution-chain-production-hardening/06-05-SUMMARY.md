---
phase: 06-evolution-chain-production-hardening
plan: 06-05
subsystem: evolution
tags: [evolution, promotion, smoke, dry-run, public-entry]
requirements_completed: [EVO-03, PROMOTE-01, PROC-02]
dependency_graph:
  requires:
    - "seers_harness/evolution/delta_portfolio.py — load_portfolio_jsonl, DeltaPortfolioRow, write_portfolio_jsonl from 06-01/06-02"
    - "workflow-skills/current/*/SKILL.md — three live skills audited byte-for-byte"
  provides:
    - "seers_harness/evolution/promotion_smoke.py — build_promotion_smoke_report public entry (dry-run only)"
    - "tests/test_promotion_smoke.py — 12 audits proving live-skill invariance and retired-skill absence"
  affects:
    - "Phase 7 onwards — any future plan that promotes deltas into live skills must change live_skill_writes_enabled and bump the schema version, and must do so behind a review/approval/rollback gate this file is not"
tech-stack:
  added: []
  patterns:
    - "public-entry smoke as a pure function returning a self-describing JSON report"
    - "dry-run boundary as data: live_skill_writes_enabled=False / runtime_touched=False / decision='dry_run_only' as named keys, not implicit behavior"
    - "byte-level invariance tests against both a tmp mirror AND the real workspace live root (T-06-11 mitigation)"
    - "sentinel runtime-shape directory placed in tmp_path proves T-06-12 mitigation by structural assertion, not string heuristics"
    - "retired-skill-name audit reconstructed via a single _RETIRED_SKILL_NAME literal so the test self-locks"
key-files:
  created:
    - seers_harness/evolution/promotion_smoke.py
    - tests/test_promotion_smoke.py
  modified:
    - seers_harness/evolution/__init__.py
decisions:
  - "Report writes are caller-supplied output_path only — never under workflow-skills/current/, never as a winning-delta registry, never as a release artifact"
  - "Run id auto-derives as 'dryrun-<unix_seconds>' when caller does not supply, but tests pin a fixed run_id so reports are deterministic"
  - "Two-layer byte invariance: a tmp mirror is hashed before/after AND the real workflow-skills/current root is hashed before/after a smoke against a parallel mirror"
  - "Source import audit greps only ``import`` and ``from`` lines so boundary docstring text mentioning the retired path stays allowed"
  - "Did not edit .planning/STATE.md — orchestrator owns the verified-baseline advance after the wave"
metrics:
  duration: "~5 minutes"
  completed_date: "2026-05-26"
  tests_added: 12
  tests_passing: 250
  baseline_before: 238
---

# Phase 6 Plan 06-05: Promotion Public-Entry Smoke And Phase Closeout Summary

**Phase 6's promotion-public-entry boundary lands as a pure function that writes a deterministic JSON dry-run report, plus 12 audits proving the workspace live skill root is byte-identical before and after the smoke runs and that the retired ``promote-skill-patch`` skill stays out of every live workspace surface.**

## Performance

- **Duration:** ~5 minutes (first commit 13:03:55 → SUMMARY 13:08+)
- **Completed:** 2026-05-26
- **Tasks:** 4 (3 code commits + 1 closeout regression)
- **Files modified:** 3 (1 created in seers_harness/evolution, 1 created in tests, 1 modified in evolution package surface)

## Goal

Audit promotion behavior into a deterministic current-workspace dry run and
smoke public entry points against current fixtures. Prove import, build, and
dry-run artifact writing under the current schema without real promotion,
live skill writes, runtime edits, or registry mutation.

## Outputs

| Task     | Scope                                                                                                                                                                                                          | Commit    |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| 06-05-01 | `seers_harness/evolution/promotion_smoke.py` — `build_promotion_smoke_report(skills_root, portfolio_path, output_path, run_id)` public entry; re-exported from `seers_harness.evolution`. Returns dict + writes JSON. | `39df9de` |
| 06-05-02 | `tests/test_promotion_smoke.py` — 8 tests covering JSON output, dry-run decision, current skill enumeration, hash invariance on both tmp mirror AND real live root, sentinel runtime-shape tree untouched, missing-portfolio handling, source-import audit. | `e8f1f34` |
| 06-05-03 | 3 retired-skill audits (no `promote-skill-patch` folder under `workflow-skills/`, no literal in `seers_harness/evolution/*.py`, no literal in `workflow-skills/*`) plus 1 deterministic-report test. | `286a880` |
| 06-05-04 | Final regression: `pytest -q` → 250 passed / 1 skipped. `rg -n 'harness-runtime' seers_harness tests workflow-skills` returns only negative boundary comments. STATE.md NOT touched (orchestrator-owned after wave 4). | n/a (closeout) |

## Requirement Coverage

- **EVO-03** — Phase 6 distillation of evolution behavior keeps `promote-skill-patch`
  out of every live workspace surface. Three audits enforce: no live folder
  named `promote-skill-patch` exists under `workflow-skills/`; the literal
  `promote-skill-patch` does not appear in any `seers_harness/evolution/*.py`
  file; and the literal does not appear in any `workflow-skills/*` file.
  Negative-assertion test files outside `workflow-skills/` are exempt by
  construction (this plan's tests live under `tests/`). The retired skill
  name is held in a single `_RETIRED_SKILL_NAME` test literal so the
  three audits self-lock.
- **PROMOTE-01** — Public promotion-chain entry implemented in the
  workspace/current-schema line per D-24, not by repairing
  `harness-runtime/`. `build_promotion_smoke_report` reads current
  `workflow-skills/current/` and an optional portfolio JSONL artifact,
  writes a dry-run JSON report, and explicitly sets
  `live_skill_writes_enabled=False` / `runtime_touched=False` /
  `decision="dry_run_only"`. The report is the only durable artifact.
- **PROC-02** — PLAN.md "Skills/Methods" names `tdd` and
  `verification-before-completion`. Each task in this plan applied tdd
  (tests landed alongside implementation) and verification-before-completion
  (focused gate `pytest tests/test_promotion_smoke.py -q` ran green before
  each commit; the final full suite ran green at the closeout).

## Verification Gates

All three PLAN.md verification commands pass:

| Gate | Result |
|---|---|
| `pytest tests/test_promotion_smoke.py -q` | 12 passed in 0.10s |
| `pytest -q` (full suite) | 250 passed, 1 skipped in 0.44s |
| `git status --short` confirms no `../harness-runtime/` edits | confirmed — diff scope is exactly `seers_harness/evolution/__init__.py`, `seers_harness/evolution/promotion_smoke.py`, `tests/test_promotion_smoke.py` |

Baseline before this plan: 238 passed + 1 skipped. Plan added 12 tests
(8 from task 02 + 4 from task 03). 238 + 12 = 250. ✓

The boundary grep `rg -n 'harness-runtime' seers_harness tests workflow-skills`
returns 11 hits; every hit is a negative boundary comment (explicit "Does
not", boundary docstring, sentinel directory literal, or pre-existing
historical-context line in `tests/test_evolution_schema_design.py`). No
hit is an import, an actual filesystem read, or a code reference that
would mutate the runtime.

## Promotion Smoke Public Entry Shape

```python
def build_promotion_smoke_report(
    *,
    skills_root: Path | str,
    portfolio_path: Path | str | None,
    output_path: Path | str,
    run_id: str | None = None,
) -> dict[str, Any]:
```

The report dict (also written as JSON to `output_path`) is:

```python
{
    "schema_version": "promotion-smoke.v1",
    "run_id": <caller-supplied or "dryrun-<unix_seconds>">,
    "skill_files": [
        {"path": "<rel/posix/path>", "sha256": "<hex>", "size_bytes": <int>},
        ...
    ],
    "portfolio_count": <int>,
    "live_skill_writes_enabled": False,
    "runtime_touched": False,
    "decision": "dry_run_only",
}
```

`skill_files` is sorted by relative path so consecutive runs against the
same skill mirror produce identical reports (the determinism test
asserts byte-identical reports for a fixed `run_id` + identical inputs).

## Threat Model Coverage

| Threat | Mitigation | Evidence |
|---|---|---|
| T-06-11 (promotion smoke accidentally becomes live promotion) | Smoke writes the JSON report only to a caller-supplied `output_path`; never mutates anything under `skills_root`; report explicitly sets `live_skill_writes_enabled=False` and `decision="dry_run_only"`. Hash invariance asserted on both a tmp mirror AND the real `workflow-skills/current/` tree. | `test_build_promotion_smoke_report_does_not_mutate_skill_files`, `test_build_promotion_smoke_report_does_not_mutate_real_live_skills`, `test_build_promotion_smoke_report_decision_is_dry_run_only`, `test_promotion_smoke_report_states_deterministic_dry_run_only` |
| T-06-12 (public entry smoke silently depends on old runtime schema) | Smoke imports only workspace modules — source-import audit greps `import`/`from` lines and asserts no `harness-runtime` / `harness_runtime` token appears. A sentinel runtime-shape tree placed alongside tmp_path inputs is byte-identical after the call, proving the smoke does not even read under it. | `test_promotion_smoke_source_does_not_import_harness_runtime`, `test_build_promotion_smoke_report_does_not_touch_harness_runtime_sentinel` |

## Decisions Made

- **Pure-function shape, not a manager service (D-25).** Phase 6 prefers small
  explicit functions over service objects. `build_promotion_smoke_report` is
  one function; there is no `PromotionSmokeRunner` class, no orchestrator,
  no global registry. The report is the only durable artifact.
- **Caller-owned output path.** Writing the report to a caller-supplied path
  (`tmp/promotion_dry_run.md`-shape paths in tests) keeps the smoke from
  ever owning a "live promotion record" or "release artifact" location.
  Tests pass `tmp_path / "rep.json"`-shape paths exclusively.
- **Run id auto-derives, but tests pin.** `run_id=None` derives
  `dryrun-<unix_seconds>` so two consecutive calls without a caller-supplied
  id still produce distinct reports; the determinism test passes a fixed
  `run_id="fixed-run-id"` so byte-identical reports are provable.
- **Two-layer byte invariance.** The smoke could theoretically be tested
  with only a tmp mirror, but a tmp-mirror-only test would not catch a
  bug where the smoke read live state from a relative path and wrote
  back to it. The plan's hard requirement is that
  `workflow-skills/current/` is byte-identical, so one test hashes the
  real tree before/after a smoke against a parallel mirror.
- **Sentinel runtime-shape directory.** Rather than try to assert "this
  function did not read or write under `../harness-runtime/`" via
  introspection (impossible without invasive instrumentation), the test
  places a sentinel directory in `tmp_path / "harness-runtime"` and
  hashes it before and after. Identity proves no read or write occurred.
- **Source-import audit is grep-line-prefixed.** The audit checks only
  lines that start with `import ` or `from ` after lstrip. This keeps
  the audit grep-clean while still allowing the boundary docstring
  prose to mention the retired runtime path explicitly.
- **STATE.md not touched in the worktree.** PLAN task 06-05-04 says
  "Update `.planning/STATE.md` verified baseline line only after the
  full command passes." The orchestrator brief explicitly says STATE.md
  is orchestrator-owned. The full command did pass (250 passed,
  1 skipped); the orchestrator owns the actual STATE.md edit after
  wave 4.

## Deviations from Plan

None — plan executed exactly as written, with one orchestrator-mandated
boundary respected: PLAN's `files_modified` list includes
`.planning/STATE.md` for the closeout step, but the executor brief says
STATE.md is orchestrator-owned post-wave. STATE.md is therefore left
unchanged in this worktree; the orchestrator advances the verified
baseline after wave 4 verification. No code or test changes were
deferred or skipped because of this.

## What Stayed Fixed

- `workflow-skills/current/` — untouched. Two tests prove byte-identity
  before and after the smoke (one against a tmp mirror, one against the
  real live root).
- `harness-runtime/` — untouched. D-23 boundary preserved. The sentinel
  test asserts the runtime-shape path is never read or written.
- `seers_harness/tools/skill_tools.py` — untouched.
- `seers_harness/tools/evolution_tools.py` — untouched.
- `seers_harness/evolution/delta_portfolio.py` — untouched. Promotion
  smoke imports `load_portfolio_jsonl` only.
- `seers_harness/evolution/trial_runner.py` — untouched.
- `seers_harness/workflow/dag_runner.py` — untouched. The smoke does
  not run a request through the DAG; it audits skill paths and
  portfolio rows only.
- `pyproject.toml` — untouched. No new dependency added.
- `.planning/STATE.md` — intentionally untouched (orchestrator owns).

## Handoff To Next Phase

Phase 6 is complete with all five plans (06-01..06-05) landing on
``main`` after orchestrator merge. Phase 7 owns:

- Real DeepSeek 20-scenario validation (Phase 6 made no claim about
  real-LLM quality; the recorded facts in
  `docs/deepseek_rate_limit_facts.md` are the starting baseline for
  any Phase 7 concurrency-tuning decisions).
- Live promotion gating (this plan ships `build_promotion_smoke_report`
  as the dry-run public entry; any future plan that promotes deltas
  into live skills must change `live_skill_writes_enabled`, bump the
  schema version, and ship a review/approval/rollback gate).
- Long-run progress integration at the request fan-out boundary
  (Phase 6 plan 06-04 documented the hook point in
  `docs/design.md`).

## Known Stubs

None. The smoke does not introduce placeholder UI data, mock-only
components, or unwired imports. The dry-run boundary is intentional and
load-bearing; flipping `live_skill_writes_enabled` to `True` is a
future plan's job and is structurally guarded by the schema-version
literal and the threat-mitigation tests.

## Self-Check

- created files exist:
  - `seers_harness/evolution/promotion_smoke.py` — FOUND
  - `tests/test_promotion_smoke.py` — FOUND
- modified files exist:
  - `seers_harness/evolution/__init__.py` — FOUND (re-exports `build_promotion_smoke_report`)
- commits exist on branch `worktree-agent-a0d5a80b48ecc65e7`:
  - `39df9de` — FOUND (`feat(06-05): add promotion smoke public entry build_promotion_smoke_report`)
  - `e8f1f34` — FOUND (`test(06-05): assert promotion smoke is dry-run only and skill-root invariant`)
  - `286a880` — FOUND (`test(06-05): assert promote-skill-patch is not live workspace skill`)
- focused gate: 12 passed
- full suite: 250 passed, 1 skipped (238 baseline + 12 new)

## Self-Check: PASSED
