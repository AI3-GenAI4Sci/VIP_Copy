# SEERS Harness Context

This file names the durable domain concepts used by architecture reviews and
code organization. Current `.planning/` decisions remain authoritative when
they are more specific.

## Domain Terms

- **request/list_group**: the smallest semantic unit. One user context plus one
  exposure list is processed, judged, and exported together.
- **scenario**: the workflow-ready request payload produced from raw CSV intake.
  It contains `user_state`, `products`, `target_products`, and
  `derived_features_by_product`.
- **tool-use loop**: the model emits tool calls, pure handlers return tool
  messages, and the node ends by calling a `submit_*_final` tool.
- **artifact**: the typed Pydantic output of one workflow node.
- **evidence**: the captured provider messages, tool calls, artifacts, usage,
  batch index, and evolution snapshot used to audit a run.
- **delta portfolio**: durable evolution state for SKILL changes that may be
  trialed against live request/list_group traffic.
- **trial**: an isolated run of a proposed SKILL delta against a request, paired
  with a baseline outcome and folded into the portfolio journal.
- **offline asset**: admitted recommendation-copy rows served later through
  U2U/U2I retrieval. Copy must not expose literal user-history tokens.

## Architecture Shape

- `workflow` owns the node/DAG tool-use mechanics.
- `tools` owns hand/eye/mirror tool handlers and their artifact state.
- `intake` owns raw CSV to scenario projection.
- `validation` owns real-run orchestration, evidence, dashboards, and offline
  asset export.
- `evolution` owns delta proposals, portfolio selection, trial execution, and
  portfolio journals.
