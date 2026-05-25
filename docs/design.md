# Design

## Shape

`workspace/` is the development build. `harness-runtime/` is the publishable
runtime.

```text
SKILL.md prose
  -> provider_runtime.generate_with_tools(...)
  -> agentic.run_skill_via_tools(...)
  -> tools.skill_tools handlers
  -> domain.models Pydantic artifacts
  -> workflow.dag_runner validation
```

## Invariants

- One provider path: `generate_with_tools`.
- Final JSON is emitted by `submit_*_final` tool calls.
- Tool handlers are hand / eye / mirror only.
- Handlers enforce structure; rubrics judge quality.
- Copy contains no literal user-history tokens.
- Factors express transferable disposition, not token bridges.
- No self-rated LLM metric fields.
- No old polling/check-feedback path.

## Code Map

| Area | File |
|---|---|
| Tool loop | `seers_harness/agentic/tool_loop.py` |
| Provider contract | `seers_harness/provider_runtime/base.py` |
| DeepSeek provider | `seers_harness/provider_runtime/openai_compatible.py` |
| Domain models | `seers_harness/domain/models.py` |
| Tool specs/handlers | `seers_harness/tools/skill_tools.py` |
| DAG integration | `seers_harness/workflow/dag_runner.py` |
| Payload policy | `seers_harness/workflow/payloads.py` |
| Scripted provider tests | `tests/fakes/scripted_provider.py` |

## Verification

```bash
cd workspace
uv run --python 3.12 --extra dev python -m pytest -q
```

Current baseline: 122 passing tests.
