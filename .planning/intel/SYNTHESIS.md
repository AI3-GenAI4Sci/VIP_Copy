# Intel Synthesis

This is the compact map of the ingested design intelligence. It exists so agents
can locate the right authority without rereading long historical documents.

## Authority Order

1. `decisions.md`: locked ADRs and precedence.
2. `requirements.md`: source requirement extraction.
3. `constraints.md`: API/protocol/NFR details.
4. `context.md`: navigation and reasoning context.
5. `INGEST-CONFLICTS.md`: conflict audit.

## Source Set

| Type | Source | Role |
|---|---|---|
| ADR | `docs/methodology.md` | durable principles and keep/drop/defer mapping |
| SPEC | `docs/design.md` | implementation detail and provider facts |
| PRD | `.planning/ROADMAP.md` | implementation order and scope |
| DOC | `docs/history.md` | old iteration trail |

## Current Synthesis

- No blocker conflicts remain.
- Phase 1-3 implementation has landed and is represented by tests plus phase
  summaries.
- The next live work is Phase 4 SKILL prose.
- Historical candidate mechanics are provenance only; compact operating truth is
  now in `docs/memory.md` and `docs/rubrics.md`.

## Conflict Result

`INGEST-CONFLICTS.md` reports no blockers and no competing variants. The only
meaningful precedence rule is simple: locked ADRs beat design prose; current
GSD state beats historical documentation.
