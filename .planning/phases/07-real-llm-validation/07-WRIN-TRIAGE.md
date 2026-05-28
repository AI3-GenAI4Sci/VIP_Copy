---
phase: 07-real-llm-validation
artefact: WR/IN code-review triage
source: 07-REVIEW.md (lines 142-316)
created: 2026-05-27T02:30:00Z
last_updated: 2026-05-27T02:55:00Z
status: blocked (phase 8 Stage 3 acceptance failed; scheduled items not closed)
items_total: 14
items_fixed: 7
items_waived: 0
items_scheduled: 7
items_open: 7
---

# Phase 7: WR / IN Triage — blocked on Phase 8 acceptance

User direction received 2026-05-27 (`go` after the three-decision-point
status). Disposition path: **Option 3** — phase 7 finalises evidence-layer
+ writer-layer fixes (the 7 commits below); the remaining items are
runner-touch and ride along with the phase-8 evolution wiring.

## Disposition register

| ID | Severity | One-liner | Decision | Commit / Reference |
|----|----------|-----------|----------|--------------------|
| WR-01 | warning | Stage 3 fail-fast loses in-flight future records → disk-vs-index inconsistency | **scheduled (phase 8)** | runner-touch; depends on Stage 3 c=20 actually running and tripping fail-fast |
| WR-02 | warning | finally-block flush_evidence / write_evolution_snapshot can mask the original exception | **scheduled (phase 8)** | runner-touch; partially mitigated by IN-04 (writer side) — runner finally still needs best-effort wrap |
| WR-03 | warning | runner re-implements `_detect_delimiter` while importing the canonical one unused | **scheduled (phase 8)** | runner-touch only (pure cleanup) |
| WR-04 | warning | runner reaches into recording_provider private `_current_node_id` ContextVar to call `.reset()` | **fixed-now (helper) / scheduled (callsite)** | helper landed `aa49f06`; runner callsite migration deferred to phase 8 |
| WR-05 | warning | trial_runner blanket-catches Exception, would swallow provider auth/rate-limit when 07-06 wires trials | **scheduled (phase 8)** | trial_runner is not invoked by runner.py — bug is "loaded but no trigger" until phase 8 wires evolution |
| WR-06 | warning | trial `exception_message` written to evolution_snapshot.json — CR-03 mirror leak | **fixed-now** | `f5893e3` (emitter-side redact) + pre-existing reducer redaction in `evolution_snapshot.py:94` |
| IN-01 | info | `TrialOutcome.token_cost_observed` is dead field — never written | **scheduled (phase 8)** | wiring depends on runtime.trace usage extraction; cleaner alongside evolution wiring |
| IN-02 | info | `judge_val02` accepts `True` / `False` as valid product ids because `isinstance(True, int)` is True | **fixed-now** | `242e7a2` |
| IN-03 | info | `extract_literal_overlap` Jaccard returns ~0 for CJK because `str.split()` doesn't tokenize CJK | **fixed-now** (codepoint-Jaccard) | `9e57edf` |
| IN-04 | info | `write_evolution_snapshot` doesn't defend against `events is None` / non-list (TypeError in finally cleanup) | **fixed-now** | `8aec0e6` |
| IN-05 | info | `set_current_node_id` ContextVar write is dead — RecordingProvider always receives an explicit `node_id` kwarg | **fixed-now (docs-only)** | `2400667` — fallback is intentional D-08 extension point; documented as such |
| IN-06 | info | `batch_summary_writer` can emit empty-string entries in fail_lists / manual_review_queue when row.node_id is missing | **fixed-now** | `ff68300` (positional sentinel) |
| IN-07 | info | `manual_review_queue` cap drift: queue\[:30\] + sentinel = 31 entries, docstring says "20-30" | **fixed-now** | `715d290` (cap → 29 + sentinel = 30) |
| IN-08 | info | `_PROVIDER_BUDGET_KEY = "max_" + "retries"` is forbid-list scan evasion — inverts the audit signal | **scheduled (phase 8)** | runner-touch; cleanest extracted into `deepseek_provider_from_env` alongside evolution wiring |

## Net

- **fixed-now**: 7 commits (WR-04 helper, WR-06, IN-02, IN-03, IN-04, IN-05 docs, IN-06, IN-07)
- **scheduled (phase 8)**: 7 (WR-01, WR-02, WR-03, WR-04 callsite, WR-05, IN-01, IN-08)
- **waived**: 0

The 7 phase-8 items share a single root cause: they all touch
`seers_harness/validation/runner.py`, and the user's Option 3 directive
keeps the long-running real-LLM batch on commit `aa49f06`. Phase 8 can
land the runner changes in a single sweep alongside the runner ↔
evolution wiring (the phase-8 charter).

## Status

- 2026-05-27T02:30:00Z — drafted, awaiting user direction.
- 2026-05-27T02:55:00Z — closed. 7 atomic commits landed; remaining 7
  scheduled to phase 8. `pytest -q` 253/253 throughout. No runner.py
  changes (preserves the in-flight batch on PID 98270).
- 2026-05-28T04:05:00Z — reopened/blocked for closeout accuracy.
  Phase 8 G5 real DeepSeek Stage 3 batch `20260528T032645Z` failed with
  `malformed_tool_args` before acceptance. The seven scheduled runner-touch
  items must not be marked closed until a clean Phase 8 commit chain exists
  and a new Stage 3 acceptance run passes. Evidence:
  `.planning/phases/08-evolution-wiring-and-runner-debt/08-VERIFICATION.md`.
