# Operating Rubrics

These rubrics are the compact standards for judging future workspace changes.
They distill the old iteration chain and current GSD decisions.

## Release-Safe Copy Rubric

A copy candidate is admissible only when all are true:

- It contains no literal user-history token from behavior, search, brand, or
  category traces.
- It is portable to a retrieved user who shares the disposition but not the same
  event history.
- It is anchored in visible product/list context, not private generator
  diagnostics.
- It avoids discount, price, medical, surveillance, demographic, and unsupported
  factual claims unless the current schema and visible input explicitly support
  them.
- It is concise enough for the recommendation surface and passes deterministic
  structural gates.
- It contributes a distinct visible move to the request/list group. A fluent
  paraphrase of another candidate is not a new candidate.

## Factor Rubric

A factor is good when it expresses a transferable disposition:

- It explains why a type of user could care, not merely which historical token was
  observed.
- It bridges user context to product/list context without copying private history
  into public release text.
- It survives U2U / U2I retrieval: another user with similar intent can receive
  the resulting copy without seeing someone else's trace.
- It is specific enough to guide copy generation, but not so specific that it
  becomes a hidden feature translation.
- It carries enough concrete hook evidence for the copy node to write from
  public factor/product signals without reopening raw user state.
- Across a list, factors should not collapse onto one safe signal when multiple
  independent user-product relations are visible.

## Admission And Export Rubric

An offline asset row is admissible only when all are true:

- A candidate has a stable `candidate_index` in the request/list group.
- If a rubric artifact exists, the candidate has a matching judgment.
- The matching judgment is `admit`; `hold` is not export evidence.
- Reports separate hard-check survivors, rubric admits, holds, rejects, and
  exported rows.
- Quality claims use request-level coverage, not exported-row count alone.

## Tool-Use Rubric

A tool-use implementation is acceptable when all are true:

- The provider exposes one tool path; JSON output is a `submit_*_final` tool call,
  not a second provider mode.
- Tool handlers are pure functions over arguments and state.
- Tool responses do not contain quality verdicts, accumulated hidden judgment, or
  domain lexicons that should live in SKILL/rubric reasoning.
- Invalid tool calls feed actionable tool messages back into the same reasoning
  loop.
- The DAG runner validates final artifacts with typed models after the loop.

## Data Intake Rubric

Request preprocessing is acceptable when all are true:

- It processes one `request_id` / list group at a time.
- It keeps only the five target category buckets, with explicit aliases rather
  than broad substring matching.
- Alias fixes are centralized and tested with both positive aliases and negative
  neighbors.
- It preserves original user and product signals in grouped fields:
  `user_state.profile`, `user_state.behavior`, `user_state.context`,
  `attributes`, `observed`, and `source_ids`.
- It computes reusable derived features once per product and exposes them at
  top level as `derived_features_by_product`.
- It dedupes same-product variants by stable ids first and canonicalized names
  second, without replacing the original product name.
- It does not upload raw large/private CSV data to Git.

## Engineering Rubric

Good changes in this workspace are:

- Scoped to `workspace/` first; `harness-runtime/` changes happen only for reviewed
  release promotion.
- Small enough to attribute: one mechanism or contract change at a time unless
  the GSD plan explicitly binds them.
- Tested at the right layer: unit tests for handlers/models, loop tests for
  mechanics, integration tests for DAG flow, real-provider runs for provider
  behavior.
- Free of compatibility shims for retired paths.
- Documented in `.planning/STATE.md` and phase summaries when they change durable
  behavior.

## Evidence Rubric

Do not call a change release-ready unless evidence includes:

- Passing targeted and full workspace tests.
- A current GSD phase summary or validation note.
- Representative real-data or real-provider evidence when provider behavior or
  product quality is affected.
- A true five-category request/list_group sample before claiming factor, copy,
  or rubric product quality across the supported scope.
- An explicit note of what changed and what stayed fixed, so attribution remains
  possible.
