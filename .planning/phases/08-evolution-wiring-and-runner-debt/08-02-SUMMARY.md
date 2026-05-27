---
phase: 08-evolution-wiring-and-runner-debt
plan: 02
subsystem: validation-runner
tags: [runner, env-file, secrets, deepseek, d8-d]

# Dependency graph
requires:
  - phase: 07-real-llm-validation
    provides: RC-03 stale shell environment failure from the 2026-05-26 real-LLM batch
provides:
  - `--env-file` CLI option for `seers_harness.validation.runner`
  - `_load_env_file(path)` helper that merges KEY=VALUE lines into `os.environ`
  - Two stderr-only env-file markers that never print secret values
affects: [08-03, 08-05, 08-12, 08-13, phase-7-real-llm-rerun]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Runner startup secrets are loaded before provider construction and logged only by count plus DEEPSEEK_API_KEY suffix."

key-files:
  created:
    - tests/test_validation_runner.py
  modified:
    - seers_harness/validation/runner.py

key-decisions:
  - "Env-file values override existing process env values so `.env.local` can defeat stale shell exports."
  - "No shell expansion, quote stripping, nested env files, or inline comment parsing are supported."
  - "The runner logs exactly two env-file marker lines and never logs any env value."

patterns-established:
  - "CLI startup helpers that can affect provider construction run immediately after argparse parsing and before `run()`."

requirements-completed: []

# Metrics
duration: 16min
completed: 2026-05-27
---

# Phase 08 Plan 08-02: Runner Env-File Summary

**The validation runner can now load a KEY=VALUE env file before provider construction, with file values taking precedence over stale shell exports and secret-safe stderr markers for auditability.**

## Performance

- **Duration:** ~16 min
- **Started:** 2026-05-27T07:05:12Z
- **Completed:** 2026-05-27T07:21:00Z
- **Tasks:** 1 / 1
- **Files modified:** 2

## Accomplishments

- Added `--env-file PATH` to `python -m seers_harness.validation.runner`.
- Added `_load_env_file(path: Path) -> int`, supporting blank lines, whole-line comments, and literal `KEY=VALUE` assignment.
- Ensured file values override existing `os.environ` values, which directly addresses the stale-shell-env failure mode.
- Added two stderr markers: loaded key count and masked `DEEPSEEK_API_KEY` suffix.
- Added five unit tests for override behavior, value non-disclosure, comments/blank lines, missing file handling, and no shell expansion.

## Task Commits

1. **Task 1 RED: env-file tests** - `9da4c46` (test)
2. **Task 1 GREEN: runner env-file support** - `1a9f9f1` (feat)

## Files Created/Modified

- `seers_harness/validation/runner.py` - Adds env-file parsing, CLI argument, and secret-safe startup markers.
- `tests/test_validation_runner.py` - Adds focused env-file coverage without constructing a real provider.

## Decisions Made

- File wins over existing env because D8-D exists specifically to bypass stale shell exports.
- Missing files raise `RuntimeError` instead of silently continuing.
- Values are never printed; only the key count and final four characters of `DEEPSEEK_API_KEY` are logged.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `tests/test_validation_runner.py` did not exist yet. The plan explicitly named that file, so it was created and added with `git add -f` because the repository ignores `tests/`.

## Verification

Commands run:

```bash
.venv/bin/python -m pytest -q tests/test_validation_runner.py -k env_file -x
# 5 passed in 0.06s

grep -c "_load_env_file" seers_harness/validation/runner.py
# 2

grep -c "args.env_file" seers_harness/validation/runner.py
# 3

grep -c -E '(loaded.*keys from|suffix=\*\*\*\*)' seers_harness/validation/runner.py
# 2

rg -n "print\(.*value|print\(.*api_key|DEEPSEEK_API_KEY=.*\{|env_file.*index|env_file.*summary" \
  seers_harness/validation/runner.py \
  seers_harness/validation/index_writer.py \
  seers_harness/validation/batch_summary_writer.py
# no matches
```

## User Setup Required

Use `--env-file .env.local` for the final Phase 8 real-LLM batch. The log should show the two env-file marker lines and must not contain the full key.

## Next Phase Readiness

Ready for `08-03`: `failure_class` rows and `by_failure_class` aggregation. The runner startup path can now source credentials from `.env.local` before any provider is built.

---
*Phase: 08-evolution-wiring-and-runner-debt*
*Completed: 2026-05-27*
