---
phase: 09
slug: acceptance-metrics-evolution-algorithm-closure
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-29
---

# Phase 09 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 in `.venv` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_delta_portfolio.py tests/test_validation_runner.py tests/test_uplift.py -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q` |
| **Estimated runtime** | Quick: under 60s target; full suite: project baseline runtime |

## Sampling Rate

- **After every task commit:** Run the targeted pytest command for touched modules.
- **After every plan wave:** Run `.venv/bin/python -m pytest -q`.
- **Before `$gsd-verify-work`:** Full suite must be green, then real DeepSeek validation evidence must be gathered.
- **Max feedback latency:** Keep automated feedback under one task boundary; real-run feedback is a phase gate, not a per-task loop.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 09-01 | 09-01 | 1 | D9-EVO-01..06, D9-GATE-03 | T-09-01 | Selection and runner snapshot evidence contain no token/concurrency pressure, static probability, random skip, or hardcoded forcing. | unit + integration | `.venv/bin/python -m pytest tests/test_delta_portfolio.py tests/test_validation_runner.py -k "snapshot or exploration or delta_portfolio" -q && .venv/bin/python -m pytest -q` | yes, needs edits | pending |
| 09-02 | 09-02 | 2 | D9-EVO-07..10, D9-GATE-04 | T-09-02 | Posterior reward success and runner journal rows are derived only from baseline-vs-trial mean rubric scores. | unit + integration | `.venv/bin/python -m pytest tests/test_uplift.py tests/test_portfolio_journal.py tests/test_status_machine.py tests/test_validation_runner.py -q && .venv/bin/python -m pytest -q` | yes, needs edits | pending |
| 09-03 | 09-03 | 3 | D9-MET-02, D9-MET-07, D9-GATE-02 | T-09-03 | A journal row folds into alpha/beta/sample_count before `batch_summary.json` reports M5, and Stage 3 supports 30 requests at concurrency 5. | unit + integration | `.venv/bin/python -m pytest tests/test_validation_runner.py tests/test_08_07_behavioral_metrics.py tests/test_batch_summary_writer.py -q && .venv/bin/python -m pytest -q` | yes, needs edits | pending |
| 09-04 | 09-04 | 4 | D9-MET-03..06, D9-GATE-01..05 | T-09-04 | Acceptance gates classify factor count, cache miss, and token use as records only while preserving real-evidence requirements. | integration + artifact review | `.venv/bin/python -m pytest tests/test_phase09_acceptance_gates.py tests/test_delta_portfolio.py tests/test_uplift.py tests/test_portfolio_journal.py tests/test_validation_runner.py tests/test_08_07_behavioral_metrics.py tests/test_batch_summary_writer.py -q && .venv/bin/python -m pytest -q` | yes, needs edits | pending |
| 09-05 | 09-05 | 5 | D9-MERGE-01..09, D9-GATE-05 | T-09-05 | Bounded 5-8 request case reading records factor/copy linkage, staged tool use, and concrete failure modes. | manual evidence + contract test | `.venv/bin/python -m pytest tests/test_phase09_skill_contract.py tests/test_phase09_acceptance_gates.py -q` | no, create in plan | pending |

## Wave 0 Requirements

- [ ] Update selection tests to fail on `token_budget_pressure`, `production_pressure`, `trial_prob`, static probability skip, random skip, and hardcoded trial forcing.
- [ ] Update reward tests to construct rubric artifacts and prove success is `trial_mean_rubric_score > baseline_mean_rubric_score`.
- [ ] Update summary-order tests to prove folded journal posterior reaches `batch_summary.json`.
- [ ] Add anti-cheat source or artifact checks for forbidden no-trial reasons.
- [ ] Add a Phase 09 case-reading artifact template/checklist for the 5-8 real request quality read.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real DeepSeek 30-request concurrency-5 validation | D9-MET-07, D9-GATE-01 | FakeProvider and pytest cannot prove provider behavior or product-quality claims. | Run `.venv/bin/python -u -m seers_harness.validation.runner --env-file .env.local --stage 3 --num-requests 30 --concurrency 5`, then record run id, `index.json`, `batch_summary.json`, `portfolio_journal.jsonl`, and sampled request paths. |
| Bounded merged-node quality reading | D9-MERGE-02..05, D9-GATE-05 | The verdict depends on reading scenario, generation artifact, tool calls, and rubric artifact for real requests. | Read 5-8 sampled requests, including pressure cases, and record whether factors are distinct/product-grounded, copy links to `source_factor_id`, and reflection/repair occurred when warranted. |

## Threat Model

| Threat Ref | Risk | Mitigation |
|------------|------|------------|
| T-09-01 | Phase acceptance is laundered through renamed token/concurrency pressure or probability gates. | Delete those fields from selection inputs and snapshot evidence; add tests/grep checks for forbidden fields and reasons. |
| T-09-02 | Posterior rewards are spoofed through token, behavioral, run-success, or self-rated proxies. | Compute reward only from typed rubric artifact mean scores for baseline and trial outputs. |
| T-09-03 | M5 reports zero because summary reads pre-fold state. | Fold `portfolio_journal.jsonl` into portfolio before summary, or pass folded state explicitly into summary writer. |
| T-09-04 | Real credentials or provider details leak into logs/evidence. | Keep env-file handling and safe exception redaction; never print resolved API keys. |
| T-09-05 | Split-node diagnostic becomes a restored production architecture. | Keep any split-node control small, local, diagnostic, and explicitly out of the production path. |

## Validation Sign-Off

- [x] All planned behaviors have automated verify or manual phase-gate evidence.
- [x] Sampling continuity: no three consecutive code tasks should lack automated verification.
- [x] Wave 0 covers known missing references from research.
- [x] No watch-mode flags.
- [x] Feedback latency is bounded for pytest; real DeepSeek validation is an explicit phase gate.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** pending
