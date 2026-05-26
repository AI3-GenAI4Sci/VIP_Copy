---
phase: 06
slug: evolution-chain-production-hardening
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-26
---

# Phase 06 - Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run --python 3.12 --extra dev python -m pytest tests/test_evolution_*.py tests/test_workflow_progress.py -q` |
| **Full suite command** | `uv run --python 3.12 --extra dev python -m pytest -q` |
| **Estimated runtime** | < 10 seconds for current fake-provider suite |

## Sampling Rate

- **After every task commit:** run the focused tests named in that task.
- **After every plan wave:** run `uv run --python 3.12 --extra dev python -m pytest -q`.
- **Before `$gsd-verify-work`:** full suite must be green.
- **Max feedback latency:** one task without an automated test is allowed only
  for docs-only rate-limit fact recording; the next task must run full suite.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 06-01 | 1 | EVO-01 | T-06-01 | old champion/probe selection skills are not copied into workspace live surface | source audit | `rg -n 'compare-champion-bundles|select-seed-probes|champion' workflow-skills seers_harness tests` | yes | pending |
| 06-01-02 | 06-01 | 1 | EVO-02 | T-06-02 | delta tools reject private refs and model self-rated metrics | unit | `uv run --python 3.12 --extra dev python -m pytest tests/test_evolution_tools.py -q` | W0 | pending |
| 06-01-03 | 06-01 | 1 | EVO-05, EVO-06 | T-06-03 | reference v2 is docs-only and field names align to current schema | unit/source | `uv run --python 3.12 --extra dev python -m pytest tests/test_evolution_schema_design.py -q` | W0 | pending |
| 06-02-01 | 06-02 | 2 | EVO-04 | T-06-04 | portfolio update is deterministic and no live skill adoption occurs | unit | `uv run --python 3.12 --extra dev python -m pytest tests/test_delta_portfolio.py -q` | W0 | pending |
| 06-02-02 | 06-02 | 2 | EVO-04 | T-06-05 | trial cleanup restores patched skill files after success and failure | integration | `uv run --python 3.12 --extra dev python -m pytest tests/test_trial_runner.py -q` | W0 | pending |
| 06-02-03 | 06-02 | 2 | EVO-04 | T-06-06 | sedimentation deduplicates and bounds durable evidence | unit | `uv run --python 3.12 --extra dev python -m pytest tests/test_trajectory_evidence.py -q` | W0 | pending |
| 06-03-01 | 06-03 | 3 | PROD-01 | T-06-07 | concurrent fake-provider requests keep paths, messages, and records isolated | smoke | `uv run --python 3.12 --extra dev python -m pytest tests/smoke/test_concurrency_smoke.py -q` | W0 | pending |
| 06-04-01 | 06-04 | 3 | TERM-01, TERM-02 | T-06-08 | progress output is minimal and disabled in no-progress/CI modes | unit | `uv run --python 3.12 --extra dev python -m pytest tests/test_workflow_progress.py -q` | W0 | pending |
| 06-04-02 | 06-04 | 3 | PROD-02 | T-06-09 | DeepSeek facts are recorded without limiter/concurrency tuning | unit/source | `uv run --python 3.12 --extra dev python -m pytest tests/test_deepseek_rate_limit_facts.py -q` | W0 | pending |
| 06-05-01 | 06-05 | 4 | EVO-03, PROMOTE-01 | T-06-10 | promotion smoke writes dry-run artifact only and leaves live skills unchanged | unit/smoke | `uv run --python 3.12 --extra dev python -m pytest tests/test_promotion_smoke.py -q` | W0 | pending |

## Wave 0 Requirements

Existing pytest infrastructure is sufficient. Each plan creates its own focused
test file before or alongside implementation. No new test framework is needed.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visible DeepSeek rate-limit headers from a live endpoint | PROD-02 | the endpoint may omit headers or local env may lack `DEEPSEEK_API_KEY` | run the optional probe only when credentials are present; record model/base URL/SDK retry/429 behavior and any visible headers in `docs/deepseek_rate_limit_facts.md` |

## Validation Sign-Off

- [x] All tasks have automated verify or an explicit docs-only exception.
- [x] Sampling continuity: no three consecutive tasks without automated verify.
- [x] Existing infrastructure covers all Phase 6 requirements.
- [x] No watch-mode flags.
- [x] Feedback latency target is under 10 seconds for local fake-provider tests.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** pending execution
