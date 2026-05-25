# Durable Memory

Use this as the compact operating memory for new agents. It is ordered from
product truth to process truth, then by historical precedence.

## Product Truth

- Final delivery is an offline recommendation-copy asset table served through
  U2U / U2I retrieval. Copy must read honestly for a retrieved user who may not
  share the authoring user's literal history tokens.
- The smallest semantic unit is `(request_id, list_group)`: one user context plus
  one exposure list. `(request_id, product_id)` is internal task structure, not a
  production or evaluation unit.
- Each workflow node is a fresh provider session. State crosses nodes only as
  typed artifacts.
- The current development mechanism is true tool use: the model emits
  `tool_call`s in its own reasoning loop, tool results return as tool messages,
  and the model ends by calling a `submit_*_final` tool.
- Tools are hand / eye / mirror, not brain. They record, reveal bounded state, or
  prompt reflection; they do not judge quality or replace the rubric.

## Standards That Survived The Old Iterations

- Skills are language-built function approximations. Every sentence in a
  `SKILL.md` should teach a transferable pattern, not patch one remembered case.
- No internal-meme examples, static domain enumerations, or numeric thresholds in
  SKILL prose. Use placeholder concepts in prose; keep hard numbers and
  structural checks in schema or handler code.
- Do not use LLM self-rated metric fields such as `strength`, `confidence`,
  `uncertainty`, `probability`, or `score`.
- Optimize by attribution. Do not claim a skill wording improvement if schema,
  context policy, DAG shape, gates, provider settings, or evaluation protocol
  changed at the same time.
- Prefer real LLM calls and real data for validation. Simulation can test
  mechanics, not product lift.
- Pure-text roleplay and async click-rate simulation are retired. They distort
  visual attention and should not be revived as release evidence.
- Clean deletes beat compatibility residue. Do not reintroduce C14/C15/C16 slots
  or old polling paths unless a current `.planning/` decision explicitly reopens
  them.

## Time Order And Conflict Resolution

- C1-C5 established early evidence lessons: reference labels can be noisy,
  length constraints matter, offline portability matters, and latent hooks leak
  through bridge-style payloads.
- C6-C8 established the release-safe public/private split, request/list_group
  batch semantics, and factor-as-transferable-disposition framing.
- C9-C13 moved toward provider and workflow consolidation, request-level rubric
  admission, and promotion readiness.
- C14-C16 exposed the cost of partial rewrites: schema residue, enumerated skill
  patches, external polling, and over-broad rubric scales.
- The current workspace build supersedes those conflicts with one provider path,
  true tool-use loop, binary rubric judgment, schema-clean artifacts, and GSD
  phase execution.

When a historical artifact conflicts with current `.planning/` or this memory,
prefer current `.planning/` first, then this memory, then
`docs/history.md` as provenance.
