# Project: SEERS Harness Workspace

## What This Is

`workspace/` is the single development line for SEERS Harness v3. The active
rewrite turns SKILL execution into a true tool-use loop: the model emits
`tool_call`s, pure-function handlers return tool messages, and each node ends by
calling a `submit_*_final` tool. `harness-runtime/` remains the publishable
runtime.

## Core Value

Tools are the agent's hand / eye / mirror, not its brain. SKILL prose teaches
transferable thinking patterns; Pydantic schemas and tool handlers enforce the
artifact contract.

## Current State

- Completed: Phase 1 Schema + Tools, Phase 2 Single Provider Path, Phase 3 Tool
  Loop + DAG Integration.
- Current focus: Phase 4 SKILL.md prose rewrites.
- Verification baseline: 122 workspace tests pass.

See `.planning/STATE.md` for live progress and `.planning/ROADMAP.md` for phase
scope.

## Non-Negotiable Decisions

Authoritative decisions live in `.planning/intel/decisions.md`. The compact set
new agents should keep in working memory is:

| Area | Decision |
|---|---|
| Tool role | Tool handlers are hand / eye / mirror only; no quality judgment in tools. |
| Provider | One provider path: `generate_with_tools`; final JSON is a tool call. |
| Public surface | Copy contains no literal user-history tokens; final assets serve U2U/U2I retrieval. |
| Skill prose | No internal examples, domain enumerations, numeric thresholds, or patch lists. |
| Schema | No LLM self-rated fields: `strength`, `confidence`, `uncertainty`, `probability`, `score`. |
| Validation | Real provider/data evidence is required for provider or product-quality claims. |
| Cleanup | Clean deletes beat compatibility shims for retired paths. |
| Process | Each GSD phase plan must name the skills/methods it relies on. |

## Operating References

- `docs/meta/memory.md`: durable cross-iteration memory.
- `docs/meta/rubrics.md`: standards for judging future changes.
- `.planning/REQUIREMENTS.md`: requirement IDs and phase traceability.
- `.planning/intel/decisions.md`: full ADR text and precedence.
- `docs/design.md`: implementation detail when needed.
- `docs/history.md`: historical provenance only.
- `docs/methodology.md`: SKILL and agent-method distillation.

## Boundaries

- Edit development code in `workspace/seers_harness/` and tests in
  `workspace/tests/`.
- Keep new PRDs/issues in `workspace/.scratch/<feature-slug>/`.
- Do not modify `harness-runtime/` for routine development.
- Do not recreate candidate lanes, old polling paths, or legacy compatibility
  slots unless current `.planning/` decisions explicitly reopen them.
