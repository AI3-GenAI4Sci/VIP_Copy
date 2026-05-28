---
phase: 08-evolution-wiring-and-runner-debt
plan: G5
subsystem: real-llm-validation + phase-verification
tags: [real-llm, stage3, acceptance, gaps_found, malformed_tool_args]
requires:
  - phase: 08-evolution-wiring-and-runner-debt
    plan: G4
    provides: bandit wiring and trial journal mechanisms in local working tree
provides:
  - real DeepSeek Stage 3 failure evidence for batch 20260528T032645Z
  - Phase 8 verification verdict `gaps_found`
  - blocked status for Phase 7 WR/IN closeout
affects:
  - Phase 8 acceptance
  - Phase 7 real-LLM validation closeout
tech-stack:
  added: []
  patterns:
    - "real-provider failure evidence beats unit-test green status"
    - "failed acceptance batches produce gaps_found, not passed-with-caveats"
key-files:
  created:
    - .planning/phases/08-evolution-wiring-and-runner-debt/08-VERIFICATION.md
    - .planning/phases/08-evolution-wiring-and-runner-debt/08-G5-SUMMARY.md
  modified:
    - .planning/phases/07-real-llm-validation/07-WRIN-TRIAGE.md
key-decisions:
  - "Do not run the manual copy-quality spot-check as acceptance after Stage 3 fail-fast."
  - "Do not close 07-WRIN-TRIAGE until Stage 3 passes and phase-8 commit refs exist."
  - "Treat the current G2-G4 uncommitted code state as a GSD recovery issue."
requirements-completed: []
metrics:
  batch_id: 20260528T032645Z
  request_dirs: 20
  stage3_result: failed
  acceptance_status: gaps_found
  completed: 2026-05-28T04:05:00Z
---

# Phase 08 Plan G5: Real Stage 3 Acceptance Summary

G5 ran the real DeepSeek Stage 3 acceptance batch and found blocking gaps. The batch was launched with:

```bash
.venv/bin/python -u -m seers_harness.validation.runner --env-file .env.local --stage 3
```

Log:

```text
.planning/phases/08-evolution-wiring-and-runner-debt/.run-logs/runner-20260528T032645Z.log
```

Artifact directory:

```text
tests/smoke/.runs/20260528T032645Z/stage3/
```

## Outcome

`status: gaps_found`

Request `-6833651210813617137` failed at `factor_discovery` with:

```text
ProviderResponseError: Failed to parse tool_call.arguments for node factor_discovery
```

The runner classified the row as `malformed_tool_args` in `index.json`, wrote `batch_summary.json`, and stopped the run as Stage 3 failed.

## Evidence Snapshot

- `index.json`: present, 20 rows
- `batch_summary.json`: present, `by_failure_class = {malformed_tool_args: 1, ok: 19}`
- `portfolio_journal.jsonl`: absent
- `factor_discovery` messages: 20
- `copy_generation` messages: 19
- `personalized_copy_rubric` messages: 19
- Captured first system-message content length: 58 messages, min 5452, mean 5664.3, max 6041
- `copy_generation` prompt cache miss: 19 usage files, mean 247.42 tokens, outside the signed [500, 5000] target band
- Trial evidence: 20 snapshots, 0 positive `trials[]`, 0 trial workspaces

## Deviations from Plan

**[Acceptance Gate Failure] Stage 3 failed before manual spot-check**

- Found during: G5 Task 2 / Task 3
- Issue: real DeepSeek emitted malformed JSON in `factor_discovery` tool-call arguments.
- Fix: not attempted in G5; this is a verification result, not a coding task.
- Verification: `08-VERIFICATION.md` records 8 truth gates with PASS/FAIL/NOT_EVALUATED.

**[GSD Recovery Issue] G2-G4 summaries exist without a clean commit chain**

- Found during: G5 closeout
- Issue: local code changes and `08-G2/G3/G4-SUMMARY.md` are present, but not committed as GSD task/summary commits.
- Fix: not bundled into G5. A recovery pass should either commit the exact G2-G4 work safely or supersede it with a clean execution path.

Total deviations: 2 documented, 0 auto-fixed. Impact: Phase 8 cannot close.

## Self-Check: FAILED

The self-check intentionally fails the Phase 8 acceptance gate because the real Stage 3 batch did not pass. This is the correct GSD outcome for G5.

Next: repair the Stage 3 gaps and GSD commit-chain anomaly, then rerun G5.
