# Context

## Fresh-Agent Read Order

1. `workspace/README.md`
2. `.planning/PROJECT.md`
3. `.planning/STATE.md`
4. `docs/memory.md`
5. `docs/rubrics.md`
6. `.planning/ROADMAP.md`
7. Current phase plan under `.planning/phases/`

## Reasoning Habits To Preserve

- Read cases, not just metrics.
- Check whether methodology was migrated or accidentally lost.
- Trace production wiring before saying a capability is implemented.
- Restate architecture-level intent before acting.
- Fix root causes, not local symptoms.
- Learn principles from references, not surface form.
- Choose the right shape before minimizing the change.
- Ask what a tool does for the agent: hand, eye, or mirror.
- Verify the foundation before building on it.
- Do not turn conversation artifacts into product examples.

## Persistent Constraints

- DeepSeek key stays in `.env.local`.
- SKILL.md remains plain markdown.
- No self-rated LLM metric fields.
- No numeric thresholds in SKILL prose.
- No hook/SDK primitive changes.
- No retired polling or compatibility-shim paths.
