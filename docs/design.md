# Design

## Runtime Shape

`workspace/` is the development build. `harness-runtime/` is the publishable
runtime.

```text
SKILL.md prose
  -> intake.preprocess_request_from_csv(...) for raw CSV request payloads
  -> workflow.payloads.provider_payload_for_node(...)
  -> provider_runtime.generate_with_tools(...)
  -> agentic.run_skill_via_tools(...)
  -> tools.skill_tools handlers
  -> domain.models Pydantic artifacts
  -> workflow.dag_runner validation
```

## Invariants

- One provider path: `generate_with_tools`.
- Final JSON is emitted by `submit_*_final` tool calls.
- Tool handlers are hand / eye / mirror only: handlers enforce structure;
  rubrics judge quality.
- Copy contains no literal user-history tokens.
- Factors express transferable disposition, not token bridges.
- No self-rated LLM metric fields.
- No old polling/check-feedback path.
- Raw CSV intake is one request at a time and emits top-level
  `derived_features_by_product`; do not hide provider-visible features inside
  metadata-only structures.
- Generation scope is the five target third-level category buckets:
  `防晒霜/乳`, `牙膏/牙粉`, `维生素`, `香水`, `护肩`.

## Code Map

| Area | File |
|---|---|
| Tool loop | `seers_harness/agentic/tool_loop.py` |
| Provider contract | `seers_harness/provider_runtime/base.py` |
| OpenAI-compatible DeepSeek provider | `seers_harness/provider_runtime/openai_compatible.py` |
| Domain models | `seers_harness/domain/models.py` |
| Request intake | `seers_harness/intake/request_preprocessor.py` |
| Category scope | `seers_harness/intake/categories.py` |
| Feature preprocessing | `seers_harness/intake/features.py` |
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

## Provider Facts

Current DeepSeek runtime shape, from the 2026-05-25 probe and locked ADR:

- `model = "deepseek-v4-pro"`
- `base_url = "https://api.deepseek.com/beta"`
- `reasoning_effort = "max"`
- `extra_body = {"thinking": {"type": "enabled"}}`
- `tool_choice = "auto"`
- no `temperature`

Multi-turn DeepSeek tool conversations must echo prior `reasoning_content` back
in later requests. The Phase 3 tool loop accounts for this.

## Data Contract

Raw CSV preprocessing keeps enough original signal for factor discovery without
duplicating noisy source columns:

- user fields are grouped into `user_state.profile`, `user_state.behavior`, and
  `user_state.context`;
- product fields are grouped into `attributes`, `observed`, and `source_ids`;
- same-product variants are deduped by stable ids first, then canonicalized
  product name;
- derived features are computed once per product and exposed at top level for
  payload builders.
- category normalization must use explicit business aliases and tested
  exclusions. The C13 alias lesson is load-bearing: valid sunscreen aliases
  including plain `防晒` should enter `防晒霜/乳`, while neighboring categories
  such as `防晒衣` must stay out.

## Request Diagnostics

Future evaluation summaries should be request-level, not just exported-row
counts. The minimum diagnostic row is:

- request/list group id;
- target products and normalized categories;
- factor count;
- candidate count;
- rubric admit / hold / reject counts;
- exported asset count.
