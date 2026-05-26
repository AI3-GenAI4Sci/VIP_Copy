# Phase 6: Evolution Chain + Production Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution
> agents. Decisions are captured in CONTEXT.md — this log preserves the
> alternatives considered.

**Date:** 2026-05-26
**Phase:** 6-Evolution Chain + Production Hardening
**Areas discussed:** Evolution skill fate and delta system, Scenario cadence
and trajectory evidence, Production hardening surface, Runtime reconciliation

---

## Evolution Skill Fate And Delta System

| Option | Description | Selected |
|--------|-------------|----------|
| Strict delete | Delete old compare/select skills and rewrite the rest from scratch. | |
| Read-only research input | Keep old evolution skills only as sources of meta-intent. | yes |
| Partial migration | Move some old flows into workspace after converting them. | |
| Other | Define a different evolution boundary. | yes |

**User's choice:** Keep old skills as read-only research input. Fully rewrite
`distill-skill-deltas` as tool-use, avoid internal rewrite labels and old
terminology, and build an incremental evolution system rather than direct live
overwrites.

**Notes:** User wants a genetic-algorithm-like skill evolution system: deltas
can modify or add skills, trial runs temporarily apply them, full trajectories
are evaluated, and belief/confidence increases only through repeated useful
evidence. The system should improve task completion and reduce token cost.

---

## Scenario Cadence And Trajectory Evidence

| Option | Description | Selected |
|--------|-------------|----------|
| Trajectory-triggered | Every completed trajectory may trigger analysis. | |
| Batch-triggered | Analyze only at batch boundaries. | |
| Mixed trigger | Buffer trajectories and trigger evolution work at controlled points. | yes |
| Other | Define a different cadence. | yes |

**User's choice:** Normal production runs continue. When evolution analysis
needs to generate and settle deltas, pause the main production line to avoid
compute pressure explosion. Random delta trials happen inside the main request
flow: apply one delta in isolation, run the full chain, evaluate, update belief,
then continue to the next request.

**Notes:** Every trajectory can enter a short-term buffer, but durable evidence
must be filtered. Combine pattern detection, information gain, deduplication,
and diversity quotas. Do not create a privileged online path for structural
failures; those should be solved during development.

---

## Production Hardening Surface

| Option | Description | Selected |
|--------|-------------|----------|
| Harness concurrency safety only | Use fake latency to prove no state/path/message cross-contamination. | yes |
| Add limiter/circuit breaker | Also build provider pressure controls. | |
| DeepSeek production concurrency | Design real DeepSeek concurrency in this phase. | |
| Other | Define a different hardening scope. | |

**User's choice:** Verify harness concurrency safety only, with realistic
latency fake provider. Keep progress minimal. Record DeepSeek rate-limit facts
only. Smoke promotion public entry points only.

**Notes:** User emphasized not overdesigning and avoiding module explosion.
Progress should be a small terminal display with `--no-progress` / CI-safe
plain output.

---

## Runtime Reconciliation

| Option | Description | Selected |
|--------|-------------|----------|
| Read-only reference plus minimal migration | Read runtime for intent and migrate only tiny helpers. | |
| Modify runtime for schema reconciliation | Edit `harness-runtime/` to align it. | |
| Do not touch runtime | Keep all work in workspace/current-schema line. | yes |
| Other | Define a different runtime boundary. | |

**User's choice:** Do not touch `harness-runtime/`.

**Notes:** `harness-runtime/` remains a release line. Phase 6 public-entry smoke
should be implemented in the workspace line rather than repairing old runtime
modules.

---

## Agent Discretion

- Choose exact names for the delta portfolio, trial scheduler, selector,
  temporary workspace, trajectory evaluator, and belief update mechanisms.
- Choose a lightweight posterior-update formula.
- Choose the smallest progress implementation after checking current
  dependency/API reality.

## Deferred Ideas

- Durable automatic live-skill adoption after enough evidence, behind later
  review/approval/rollback gates.
- Full real-chain debugging of the evolution trial loop.
- Real DeepSeek concurrency tuning after rate-limit fact recording.
