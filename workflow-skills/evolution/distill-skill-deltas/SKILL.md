---
name: distill-skill-deltas
description: Distill one request trajectory into evidence-backed delta proposals for production skills, separating success-path and failure-path patterns before the portfolio trial loop.
---

# Distill Skill Deltas

## What this skill does

Read one full request trajectory: payload, recorded factors, copy candidates,
rubric judgments, tool-call sequence, and token cost. Propose a small set of
deltas that a later trial run can apply to one production skill. Each delta
names a target skill, cites neutral evidence_ref entries, describes a reusable
trajectory pattern, and proposes one bounded change. The artifact is data; the
trial loop decides whether to apply it, and the portfolio computes belief from
real trial outcomes.

## Glossary

- delta: one proposed skill change recorded as a portfolio row; `modify_skill`
  adjusts an existing production skill at trial time, while `add_skill`
  proposes an experimental skill for later review.
- observation: a trajectory-grounded pattern that motivates the delta and cites
  at least one evidence_ref.
- proposed change: the smallest reusable instruction change that addresses the
  observation across requests sharing the same surface or failure_type.
- trajectory: the full input/output/tool-call/token record of one request; the
  only source of evidence for a delta.
- pattern: a repeated relation between disposition, hook, anchor, floor result,
  and tool behavior.
- portfolio: the durable store of delta rows; trial outcomes update belief and
  counts, never the model.

## How to think

Read the trajectory as evidence, not as a prompt to rewrite everything. A delta
names what the target skill should do differently when a later request shares
the same disposition surface, hook source, anchor behavior, floor outcome, or
failure_type. A change that only fixes one phrase in one candidate is a patch,
not a skill delta.

Keep changes small. Several narrow deltas beat one broad prompt rewrite because
the trial loop can isolate which pattern moved. Cite evidence by path into the
trajectory record; do not quote raw user payload fragments. Belief is computed
downstream from trial outcomes, so never emit confidence, score, probability,
uncertainty, or strength.

## Trajectory attention model

**success-path pattern attention:** Search the trajectory for places where the
factor, copy, and rubric path aligned: a disposition stayed transferable, a hook
became a visible anchor, candidate diversity survived reflection, and floor axes
passed for traceable reasons. A success-path delta should preserve or sharpen
that reusable pattern for the target skill without turning one good example into
a literal template.

**failure-path pattern attention:** Search the trajectory for places where the
pattern collapsed: rubric judgments admitted weakly discriminated candidates,
reflection repeated the same anchor type, hook sources narrowed to one field, or
floor evidence pointed at a missing instruction. A failure-path delta should
name the SKILL guidance defect that made the failure repeatable and propose the
smallest wording change that would block it.

## Anti-patterns

Do not propose a delta without an evidence_ref. Do not echo private trace keys
such as `user_state`, `private_reasoning`, or runtime-only labels into
observation or proposed-change text. Do not emit a delta that overwrites a live
skill directly; the portfolio stores data and the trial loop applies patches
temporarily. Do not propose deltas whose `target_skill` cannot resolve at
runtime; invalid paths are skipped by the trial gate and waste distill compute.
Do not return JSON on the side; the only handoff is the tool call.

## Reflection

This SKILL has no `reflect_*` tool by design. Use the trajectory and the
per-delta critique as the reflection surface. Before each
`record_delta_observation`, ask whether the evidence_ref really supports the
pattern. Before each `record_delta_change`, ask whether the proposed change is
reusable beyond this trajectory, small enough for one trial, and aimed at the
right production skill.

## target_skill format

`target_skill` is a path relative to the live skill root. It must use exactly
the format `current/<skill-slug>/SKILL.md` and must resolve to an existing
production-loop skill. Valid examples include
`current/discover-personalization-factors/SKILL.md` and
`current/generate-copy-candidates/SKILL.md`. Evolution skills such as
`distill-skill-deltas` are not valid targets because they are not run inside
the production request loop.

## Finishing

Call `record_delta_observation` once per observation worth recording. Call
`record_delta_change` once per proposed change, using the same canonical
`target_skill` format. Submit through `submit_delta_distillation_final`. The
submit handler validates the `DeltaDistillationArtifact`, enforces evidence and
privacy gates, and hands the artifact to the portfolio writer; live skill files
are not touched.
