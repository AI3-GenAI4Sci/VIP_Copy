# Phase 08 Deferred Items

## 2026-05-27 - Full-suite stale timeout fact test

- **Found during:** 08-03 final full-suite verification
- **Command:** `.venv/bin/python -m pytest -q`
- **Failure:** `tests/test_deepseek_rate_limit_facts.py::test_default_timeout_seconds_is_sixty`
- **Observed:** test expects `default_timeout_seconds == 60`, while the current provider fact reports `180`.
- **Scope decision:** Out of scope for 08-03. This appears tied to completed 08-01 timeout default work, not the failure-class analytics changes.
