# Reference v2 Schema Design

**Phase:** 06 — Evolution Chain + Production Hardening
**Plan:** 06-01 (current-schema evolution contracts)
**Status:** Design only. Not emitted in Phase 6.

## Purpose

This document describes how a hypothetical "reference v2" schema could
represent the durable evidence the workspace evolution surface produces:
delta proposals, trial trajectories, evidence references, and portfolio
rows. It exists so future phases can promote durable evidence into a
shared reference format without re-inventing field names or losing the
language already locked into the workspace contracts.

It is a target sketch, not an implementation handle. Phase 6 only writes
delta records using the in-process Pydantic models defined in
``seers_harness/evolution/delta_portfolio.py`` and the artifact returned by
``submit_delta_distillation_final``. No emitter, migration helper, or
live writer is added in this phase.

## Vocabulary Alignment

The v2 sketch must reuse the workspace evolution language already locked
in plan 06-01 contracts:

- delta, proposal, change, trial, trajectory, portfolio, belief update.

It must not reintroduce retired runtime selection-flow vocabulary
(``compare-champion-bundles`` / ``select-seed-probes`` / ``candidate
bundle``) or any LLM self-rated metric field name.

## Sketch

The v2 reference is a flat record set keyed by stable ids. Four record
shapes cover the durable surface:

### v2_delta

A serialized form of ``DeltaPortfolioRow``. Adds a stable
``record_version`` for forward compatibility but does not introduce new
domain fields.

```jsonc
// shape only, NOT emitted in Phase 6
{
  "record_version": "v2",
  "delta_id": "...",
  "target_skill": "...",
  "change_type": "modify_skill | add_skill",
  "observation": "...",
  "proposed_change": "...",
  "evidence_refs": [{"path": "...", "value": null}],
  "applicable_surface": ["..."],
  "failure_types": ["..."],
  "belief_alpha": 1.0,
  "belief_beta": 1.0,
  "sample_count": 0,
  "success_count": 0,
  "failure_count": 0,
  "token_cost_delta_sum": 0,
  "status": "experimental | held | rejected | ready_for_review"
}
```

### v2_trajectory

A compact trajectory header per request. Pairs a request id with the
node artifact paths and the trial delta id, if any was applied.

```jsonc
// shape only, NOT emitted in Phase 6
{
  "record_version": "v2",
  "request_id": "...",
  "scenario_id": "...",
  "node_artifact_paths": {"discover-personalization-factors": "..."},
  "tool_call_count": 0,
  "token_usage": {"prompt": 0, "completion": 0, "total": 0},
  "trial_delta_id": null,
  "failure_category": null
}
```

### v2_evidence_ref

A neutral pointer into a trajectory record. Reuses the in-process
``EvidenceRef`` shape so v2 storage does not lose anything the workspace
already records.

```jsonc
// shape only, NOT emitted in Phase 6
{"path": "request_42.factor_3.text", "value": null}
```

### v2_portfolio_row

The portfolio row uses the same fields as ``v2_delta`` plus an external
provenance block (when the row is materialized). Phase 6 keeps the
in-process ``DeltaPortfolioRow`` as the single source of truth.

```jsonc
// shape only, NOT emitted in Phase 6
{
  "record_version": "v2",
  "delta_id": "...",
  "trial_history": [{"request_id": "...", "outcome": "...", "delta": 0}]
  // ... all DeltaPortfolioRow fields ...
}
```

## Field Naming Audit

The v2 sketch uses the same field names as the in-process Pydantic
contracts in ``seers_harness/evolution/delta_portfolio.py``. Renaming
fields between in-process and reference v2 would create silent drift.

The audit deliberately excludes the five LLM-self-rated metric names
locked by ADR-01-PRINCIPLE-10. Posterior counters
(``belief_alpha`` / ``belief_beta`` / ``sample_count`` /
``success_count`` / ``failure_count`` / ``token_cost_delta_sum``) are
computed from trial outcomes by portfolio code in a later plan.

## Privacy Boundary

Every v2 record stores only neutral evidence references. Private
trajectory text (``user_state``, ``private_reasoning``,
``raw_interest_fragment_private``, ``diagnostic_evidence_refs``,
``blocked_evidence_refs``, ``is_clk_c``) never enters durable
records. The handler privacy scan in
``seers_harness/tools/evolution_tools.py`` is the enforcement point;
the v2 sketch only inherits this contract.

## Not emitted in Phase 6

This document is design-only. Phase 6 explicitly forbids:

- writing a ``v2`` emitter function or class,
- writing any migration, conversion, or batch-export helper,
- promoting in-process records to a v2 file on disk,
- introducing a live ``v2_*`` writer surface,
- coupling the workspace harness to a specific reference storage path.

The Phase 6 deliverable ends with the in-process Pydantic contracts and
the tool-use distill skill. Reference v2 implementation is deferred to a
later phase that explicitly opens an emitter slot in PROJECT-level
boundaries.
