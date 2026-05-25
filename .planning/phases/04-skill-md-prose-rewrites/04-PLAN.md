---
phase: 04-skill-md-prose-rewrites
type: prose-only
status: ready
---

# Phase 4 Plan: SKILL.md Prose Rewrites

## Goal

Create the three development SKILL files in Matt-style, each short enough to read
fully and precise enough to steer the tool-use loop.

Covers: `SKILL-01` / `SKILL-02` / `SKILL-03` / `SKILL-04` in
`.planning/REQUIREMENTS.md`.

This plan uses the distilled workspace sources in their current locations. Do
not recreate `workspace/meta/`; use `workspace/docs/meta/`.

## Source Inputs

- `04-CONTEXT.md`
- `workspace/docs/meta/memory.md`
- `workspace/docs/meta/rubrics.md`
- `workspace/docs/methodology.md`
- `.planning/intel/decisions.md`
- `.planning/REQUIREMENTS.md`
- `seers_harness/tools/skill_tools.py`
- `seers_harness/domain/models.py`

## Outputs

| File | Requirement | Must preserve |
|---|---|---|
| `workspace/workflow-skills/current/discover-personalization-factors/SKILL.md` | `SKILL-01`, `SKILL-04` | transferable disposition; junior-analyst test; references advisory |
| `workspace/workflow-skills/current/generate-copy-candidates/SKILL.md` | `SKILL-02`, `SKILL-04` | U2U/U2I retrieval framing; user-history token ban; anchor literal principle |
| `workspace/workflow-skills/current/personalized-copy-rubric-judge/SKILL.md` | `SKILL-03`, `SKILL-04` | seven binary axes; critique before verdict; floor axes by name; demographic/surveillance handling |

Each file uses this front matter shape:

```yaml
---
name: <skill-directory-name>
description: <one-sentence use trigger>
---
```

## Reflection Rule

The `Reflection` section exists in every SKILL, but it must not duplicate fixed
reflection questions. Handler constants own those questions.

- Factor discovery: say when to call `reflect_on_coverage` and that the returned
  questions must be answered in writing before `submit_factors_final`.
- Copy generation: say when to call `reflect_on_diversity` and that the returned
  questions must be answered in writing before `submit_copies_final`.
- Rubric judging: use `Reflection` for critique-before-verdict discipline around
  `judge_candidate` and `submit_judgments_final`; do not invent a `reflect_*`
  tool or fixed question list.

Do not mention `tool_loop_summary`, `turns_used`, provider traces, or other loop
diagnostics in SKILL prose. Those are evidence/debug surfaces, not transferable
skill methodology.

## Steps

1. Create `workspace/workflow-skills/current/` directories for the three skills.
2. Read every Source Input above, using `docs/meta/` paths for memory/rubrics.
3. Draft each SKILL using the 8-section template and uniform front matter.
4. Apply the Reflection Rule and keep `reflect_*` questions out of prose.
5. Audit every prose sentence: deleting it must lose a transferable pattern.
6. Run the lint gates below and the full workspace pytest gate.
7. Write `04-SUMMARY.md` with requirement coverage, final line counts, lint
   results, pytest result, reflection handling, and what changed versus stayed
   fixed.
8. Update `.planning/STATE.md` to mark Phase 4 complete and Phase 5 next.

## Lint Gates

Run for each SKILL file:

```bash
F=workspace/workflow-skills/current/<skill>/SKILL.md
test -f "$F"
test "$(wc -l < "$F")" -le 60
test "$(head -1 "$F")" = "---"
test "$(sed -n '2p' "$F" | cut -d: -f1)" = "name"
test "$(sed -n '3p' "$F" | cut -d: -f1)" = "description"
test "$(sed -n '4p' "$F")" = "---"
! rg -n '艾灸|维C|B族|黄金搭档|连衣裙|范思哲|安热沙|维生素|钙片|鱼油|温灸器|泡脚' "$F"
! rg -n '^## Output|^## Self-check|JSON only|sk-' "$F"
! rg -n 'strength|confidence|uncertainty|probability|score' "$F"
! rg -n '≥|10-16|10–16|0-5|0–5|floor=4|593|mean=|std=' "$F"
! rg -n 'tool_loop_summary|turns_used|provider trace|provider_trace' "$F"
```

Also verify tool framing:

```bash
rg -n 'record_factor|submit_factors_final|record_candidate|submit_copies_final|judge_candidate|submit_judgments_final|reflect_on_coverage|reflect_on_diversity' workspace/workflow-skills/current
```

Run the full regression gate from `workspace/`:

```bash
uv run --python 3.12 --extra dev python -m pytest -q
# expect the current full workspace suite to pass; latest observed baseline: 122 passed
```

## Handoff To Phase 5

Phase 5 decides how to promote or reconcile runtime skill locations. It must not
assume runtime already matches Phase 4 output. It should compare
`harness-runtime/workflow-skills/` against `workspace/workflow-skills/` and then
choose a reviewed runtime update path.

## Skills/Methods

Use `writing-skills` / `writing-a-skill` discipline for Matt-style prose,
`docs/methodology.md` for keep/drop rules, `docs/meta/rubrics.md` for evidence,
and verification-before-completion style evidence before marking done.
