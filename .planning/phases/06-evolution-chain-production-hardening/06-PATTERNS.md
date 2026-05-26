# Phase 6 Pattern Map

**Phase:** 06 - evolution-chain-production-hardening
**Status:** Pattern mapping complete

## Existing Patterns To Reuse

| New responsibility | Closest existing analog | Pattern to preserve |
|---|---|---|
| Strict tool-use delta handlers | `seers_harness/tools/skill_tools.py` | Pydantic args models, strict specs, universal handler signature, handler returns literal strings, final artifact in `state["final_artifact"]` |
| Evolution artifact schemas | `seers_harness/domain/models.py` | small Pydantic models with `extra="forbid"` and no model self-rated fields |
| Full request trajectory | `seers_harness/workflow/dag_runner.py` | `run_request` runs nodes in order and returns artifact paths keyed by node id |
| Fake-provider full-chain run | `tests/smoke/scripted_full_chain.py` | scripted tool calls, fresh provider per request, canonical smoke content |
| Provider usage/facts | `seers_harness/provider_runtime/openai_compatible.py` and `seers_harness/core/errors.py` | single provider path, defaults from env, `ProviderRateLimitError` classification |
| Progress output | `tests/smoke/test_e2e_smoke.py` | plain stdout progress line per request, no logging/rich/tqdm |
| Runtime boundary | `.planning/PROJECT.md` and `.planning/phases/06-*/06-CONTEXT.md` | edit only workspace code and docs, do not touch `harness-runtime/` |

## File Placement Guidance

### `seers_harness/evolution/delta_portfolio.py`

Use this for typed delta records, portfolio JSONL persistence, posterior update,
adaptive selection, and bounded evidence sedimentation. Keep it data/function
oriented. Do not add a manager class unless execution shows repeated state
threading that functions cannot handle clearly.

Read first:

- `seers_harness/domain/models.py`
- `.planning/intel/decisions.md` ADR-01-PRINCIPLE-10
- `.planning/phases/06-evolution-chain-production-hardening/06-CONTEXT.md`

### `seers_harness/tools/evolution_tools.py`

Use this for `distill-skill-deltas` handlers and specs if adding them to
`skill_tools.py` would make the existing file too broad. Re-export specs and
handlers from `seers_harness/tools/__init__.py` or import them explicitly from
the new module in tests. If execution chooses to register the new skill in the
existing `TOOLS_SPEC`, keep the role classification updated.

Read first:

- `seers_harness/tools/skill_tools.py`
- `tests/test_skill_tools_registry.py`
- `tests/test_skill_tools_roles.py`

### `workflow-skills/evolution/distill-skill-deltas/SKILL.md`

Use the Phase 4 eight-section skill style but keep it short. It should explain
how to propose observations and changes through tool calls. It should not emit
JSON-only instructions, internal examples, old rewrite labels, `candidate`
vocabulary, or self-rated metrics.

Read first:

- `workflow-skills/current/discover-personalization-factors/SKILL.md`
- `workflow-skills/current/generate-copy-candidates/SKILL.md`
- `workflow-skills/current/personalized-copy-rubric-judge/SKILL.md`
- `.planning/phases/04-skill-md-prose-rewrites/04-SUMMARY.md`

### `seers_harness/evolution/trial_runner.py`

Use this for request-boundary trial mechanics: select one delta, apply it to an
isolated temporary skill surface, run a full request, record trajectory, update
portfolio, and restore. It should call existing `WorkflowRuntime.run_request`
instead of duplicating node orchestration.

Read first:

- `seers_harness/workflow/dag_runner.py`
- `tests/smoke/scripted_full_chain.py`
- `tests/fakes/scripted_provider.py`

### `seers_harness/workflow/progress.py`

Use this for minimal progress rendering. Keep output as plain strings written to
a supplied stream. Do not add a dependency unless execution verifies one already
exists.

Read first:

- `pyproject.toml`
- `tests/smoke/test_e2e_smoke.py`

### `seers_harness/evolution/promotion_smoke.py`

Use this for public-entry smoke only. It should import cleanly, read current
workspace skill paths and portfolio artifacts, write a dry-run report to a temp
or caller-provided output path, and report that live skill writes are disabled.

Read first:

- `workflow-skills/current/*/SKILL.md`
- `seers_harness/domain/models.py`
- `.planning/phases/06-evolution-chain-production-hardening/06-CONTEXT.md`

## Anti-Patterns To Avoid

- No edits under `../harness-runtime/`.
- No old `champion`, `candidate bundle`, or probe-selection live workflow in
  workspace code.
- No `generate_json`, `response_format`, polling path, hard-check gate, or
  compatibility schema slot.
- No model-emitted `confidence`, `score`, `probability`, `uncertainty`, or
  `strength` in tool args or Pydantic schemas.
- No terminal UX dependency churn unless current dependencies already support it.
- No live skill overwrite in Phase 6.

## Pattern Mapping Complete
