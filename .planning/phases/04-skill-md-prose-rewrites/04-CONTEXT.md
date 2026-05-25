# Phase 4 Context: SKILL.md Prose Rewrites

## Scope

Phase 4 creates three development SKILL files under `workspace/workflow-skills/`.
It does not edit runtime skills, schemas, handlers, providers, or DAG code.

Outputs:

- `workspace/workflow-skills/current/discover-personalization-factors/SKILL.md`
- `workspace/workflow-skills/current/generate-copy-candidates/SKILL.md`
- `workspace/workflow-skills/current/personalized-copy-rubric-judge/SKILL.md`

## Authority

- `docs/memory.md` and `docs/rubrics.md` for compact durable
  standards. Do not recreate `workspace/meta/` or `docs/meta/`; the durable
  memory was distilled into flat `docs/`.
- `.planning/intel/decisions.md` for locked ADRs.
- `docs/methodology.md` for keep/drop/defer methodology and Phase 4 writing
  rules.
- `seers_harness/tools/skill_tools.py` and `seers_harness/domain/models.py` for
  tool names and artifact shape.

## Required Shape

Each SKILL is at most 60 visible markdown lines and uses:

1. front matter
2. title
3. `What this skill does`
4. `Glossary`
5. `How to think`
6. `Anti-patterns`
7. `Reflection`
8. `Finishing`

The `Reflection` section describes when to use the available reflection surface,
not the fixed questions themselves. `reflect_on_coverage` and
`reflect_on_diversity` questions live in Python handler constants; SKILL prose
only points to the tool and says to answer its returned questions in writing
before final submit. The judge SKILL has no `reflect_*` tool; its reflection is
critique-before-verdict reasoning before `submit_judgments_final`.

## Keep

- Factor discovery keeps transferable disposition, junior-analyst test, and
  references-as-advisory.
- Copy generation keeps the user-history-token ban as a transferable retrieval
  principle.
- Rubric judging keeps critique-before-verdict, floor axes by name, demographic
  / surveillance handling, and the binary-not-scale rationale.

## Drop

- JSON-output framing and self-check blocks.
- Internal examples from old conversations.
- Numeric thresholds in prose.
- Static domain enumerations and patch lists.
- LLM self-rated metric words.
- Tool-loop diagnostics such as `tool_loop_summary`, `turns_used`, or provider
  trace heuristics.

## Scope Fence

Phase 4 must not touch `harness-runtime/`, call real providers, introduce new
tool handlers, rewrite evolution skills, or change current Python code.
