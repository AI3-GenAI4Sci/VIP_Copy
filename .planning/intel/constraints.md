# Intel Constraints

Compact technical constraints distilled from the design. Code and tests are the
source of truth for exact signatures.

## Provider

- Use `generate_with_tools`; do not restore `generate_json`.
- Use DeepSeek `/beta`, `tool_choice="auto"`, thinking enabled, and
  `reasoning_effort="max"`.
- Do not set `temperature` in thinking/tool mode.
- Classify auth, transient, and rate-limit failures before retry/propagation.

## Tool Loop

- Initial messages are system SKILL bundle plus serialized user payload.
- Dispatch tool calls in emitted order.
- Append each handler result as a tool message.
- Validation errors return actionable `ERROR: ...` tool content and let the model
  retry.
- Stop only when a `submit_*_final` handler sets `state["final_artifact"]`.
- Enforce bounded tool-call and transient retry budgets.

## Handlers

- Handlers mutate only local loop state and return short strings.
- Reflect tools return fixed question text from Python constants.
- Candidate handler enforces structural checks: selected draft, numeric shape,
  visible length contract, literal anchors, and dynamic user-history token
  rejection.
- Handlers must not contain static domain lexicons or quality judgment.

## SKILL Prose

- Each current SKILL file is ≤60 visible markdown lines.
- SKILL prose frames work as tool calls ending in `submit_*_final`.
- No JSON-only output sections, self-check blocks, internal examples, numeric
  thresholds, or domain enumerations.

## Testing

- Scripted provider tests mechanics.
- Real DeepSeek validation is required before product/provider quality claims.
