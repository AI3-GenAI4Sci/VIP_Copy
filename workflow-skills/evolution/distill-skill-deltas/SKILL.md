---
name: distill-skill-deltas
description: Distill one full request trajectory into a small set of evidence-backed delta proposals that target one named skill; the handler validates structure, evidence, and privacy before the artifact handoff.
---

# Distill Skill Deltas

## What this skill does

Read one full request trajectory — payload, recorded factors and copy
candidates, rubric judgments, tool-call sequence, and token cost — and
propose a small set of deltas that a later trial run could apply. Each
delta names a target skill, observes a concrete pattern in the
trajectory — a recurring failure type, a missed angle, or a working
move worth reusing — and proposes one reusable change. The artifact is
data; the trial loop later decides whether to apply a delta, and the
portfolio later computes belief from real trial outcomes.

## Glossary

- delta: one proposed change to a skill, recorded as a portfolio row;
  ``modify_skill`` adjusts an existing skill at trial time and
  ``add_skill`` proposes an experimental new skill.
- observation: a trajectory-grounded pattern that motivates the delta;
  must cite at least one evidence ref into the trajectory record.
- proposed change: the smallest reusable adjustment that, if trialed,
  would address the observation across requests sharing the surface.
- trial: a later request run that temporarily applies one delta in an
  isolated workspace, records the outcome, and restores the main path.
- trajectory: the full input/output/tool-call/token record of one
  request; the only source of evidence for a delta.
- portfolio: the durable store of delta rows; trial outcomes update
  belief and counts, never the model.
- belief update: the portfolio code recomputes posterior counters from
  trial outcomes; the skill never emits a belief number.

## How to think

Read the trajectory as evidence. A delta names what the target skill
should do differently when the next request shares the same surface or
failure type. The change must be reusable: a delta that only fixes one
phrase in one candidate is a patch, not a skill change.

Keep changes small. Several small, well-targeted deltas beat one broad
prompt rewrite. A delta that says "rewrite the skill" is rejected on
review even when the trajectory looks bad — the trial loop cannot
isolate what changed.

Cite evidence by path into the trajectory record, not by quoting raw
user state. Evidence refs are neutral pointers; private trace text and
raw payload fragments never appear in delta records.

Belief is computed downstream. The skill never asserts how confident or
strong the delta is; the portfolio updates posterior counters from
actual trial outcomes and counts.

## Anti-patterns

Do not propose a delta without an evidence ref. Do not echo private
trace keys (``user_state``, ``private_reasoning``, ``is_clk_c``, and the
like) into observation or proposed-change text. Do not emit a delta
that overwrites a live skill directly — Phase 6 stores deltas as data
and never writes to ``workflow-skills/current/``. Do not return JSON
on the side; the only handoff is the tool call.

## Reflection

This SKILL has no ``reflect_*`` tool by design. Use the trajectory and
the per-delta critique as the reflection surface: before each
``record_delta_change``, ask whether the change is reusable beyond this
one request, whether the cited evidence ref actually supports it, and
whether the change is small enough that a single trial run could
isolate its effect.

## Finishing

Call ``record_delta_observation`` once per observation worth recording,
``record_delta_change`` once per proposed change, then submit through
``submit_delta_distillation_final``. The submit handler validates the
``DeltaDistillationArtifact``, enforces evidence and privacy gates, and
hands the artifact off to the portfolio writer; live skill files are
not touched.
