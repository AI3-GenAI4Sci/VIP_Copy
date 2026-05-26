---
phase: 04-skill-md-prose-rewrites
status: complete
---

# Phase 4 Summary: SKILL.md Prose Rewrites

## Goal

Create three Matt-style development SKILL files under
`workspace/workflow-skills/current/`, each short enough to read fully and
precise enough to steer the C17 tool-use loop.

## Outputs

| File | Lines | Requirement | Status |
|---|---:|---|---|
| `workspace/workflow-skills/current/discover-personalization-factors/SKILL.md` | 59 | SKILL-01, SKILL-04 | Complete |
| `workspace/workflow-skills/current/generate-copy-candidates/SKILL.md` | 60 | SKILL-02, SKILL-04 | Complete |
| `workspace/workflow-skills/current/personalized-copy-rubric-judge/SKILL.md` | 60 | SKILL-03, SKILL-04 | Complete |

All three files use the eight-section template (front matter, title, What
this skill does, Glossary, How to think, Anti-patterns, Reflection,
Finishing) with uniform front matter (`name`, `description`).

## Requirement Coverage

- SKILL-01 — Factor SKILL preserves transferable disposition, junior-analyst
  test, and references-as-advisory; declares the direction trichotomy as
  hook-origin label, not a quota.
- SKILL-02 — Copy SKILL preserves the user-history token ban as a U2U/U2I
  retrieval principle, names product anchor and relation anchor as required
  literal substrings, and defers structural number/length checks to the
  handler instead of paraphrasing them in prose.
- SKILL-03 — Judge SKILL preserves seven binary axes, critique-before-verdict
  ordering, the named floor axes rule, the demographic / surveillance floor
  concern, and the binary-not-Likert rationale.
- SKILL-04 — All three files avoid numeric thresholds, internal-meme examples,
  static enumerations, JSON-only framing, and tool-loop diagnostics in prose.

## Reflection Handling

Reflection sections describe **when to use** the available reflection
surface and never duplicate the fixed questions, which live in handler
constants (`_REFLECT_COVERAGE`, `_REFLECT_DIVERSITY`):

- discover-personalization-factors → `reflect_on_coverage` before
  `submit_factors_final`.
- generate-copy-candidates → `reflect_on_diversity` before
  `submit_copies_final`.
- personalized-copy-rubric-judge → no `reflect_*` tool by design; the
  per-axis critique is the reflection surface before
  `submit_judgments_final`.

No SKILL prose mentions `tool_loop_summary`, `turns_used`, or provider trace
heuristics.

## Lint Gates

For each SKILL file the following all hold:

- file exists; `wc -l ≤ 60`
- line 1 is `---`; line 2 begins `name`; line 3 begins `description`;
  line 4 is `---`
- forbidden internal-meme tokens absent
  (`艾灸 / 维C / B族 / 黄金搭档 / 连衣裙 / 范思哲 / 安热沙 / 维生素 / 钙片 / 鱼油 / 温灸器 / 泡脚`)
- forbidden structural headings absent (`## Output`, `## Self-check`,
  `JSON only`, `sk-`)
- forbidden self-rated metric tokens absent
  (`strength / confidence / uncertainty / probability / score`)
- forbidden numeric tokens absent
  (`≥`, `10-16`, `10–16`, `0-5`, `0–5`, `floor=4`, `593`, `mean=`, `std=`)
- forbidden tool-loop diagnostics absent
  (`tool_loop_summary / turns_used / provider trace / provider_trace`)

The phase-level tool-framing check confirms each SKILL points at its
expected tool surface:

- factor SKILL → `record_factor`, `reflect_on_coverage`,
  `submit_factors_final`
- copy SKILL → `record_candidate`, `reflect_on_diversity`,
  `submit_copies_final`
- judge SKILL → `judge_candidate`, `submit_judgments_final`

## Pytest

`uv run --python 3.12 --extra dev python -m pytest -q` from `workspace/`:
**122 passed in 0.28s** — matches the Phase 3 baseline.

## What Changed vs. Stayed Fixed

Changed in this phase:

- New directory tree `workspace/workflow-skills/current/<skill>/SKILL.md`
  for the three development SKILLs (none existed under `workspace/`
  before; `harness-runtime/workflow-skills/` is untouched).
- Prose adopts the eight-section Matt-style template, uniform front
  matter, transferable-pattern audit, and reflect-as-mirror framing.

Stayed fixed:

- Tool registry, tool handlers, schemas, provider, tool loop, DAG runner,
  and tests are unchanged.
- Reflection question text remains in handler constants
  (`_REFLECT_COVERAGE`, `_REFLECT_DIVERSITY`); no copy of those questions
  in any SKILL.
- `harness-runtime/` is unchanged; Phase 5 owns the runtime promotion
  decision.

## Handoff to Phase 5

Phase 5 must decide how to promote or reconcile runtime SKILL locations
and resolve the remaining cleanup items (CLEAN-01..04). It should compare
`harness-runtime/workflow-skills/` against
`workspace/workflow-skills/current/` and choose a reviewed runtime update
path; `harness-runtime/` currently lacks the rubric-judge SKILL entirely.
