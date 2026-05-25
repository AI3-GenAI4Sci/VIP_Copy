# History

This file is the distilled old-iteration trail. It is provenance, not daily
instruction. Daily operating truth lives in `docs/meta/memory.md`,
`docs/meta/rubrics.md`, and `.planning/`.

## Timeline

| Iteration | What mattered |
|---|---|
| C0 | Runtime baseline snapshot. |
| C1 | Reference labels can be noisy; audit judge/reference disagreements. |
| C2 | Visible copy length has a narrow surface contract. |
| C3 | Offline object-bridge portability matters for U2U/U2I retrieval. |
| C4 | Public/private payload split is required for release-safe assets. |
| C5 | Latent hooks reduce visible leaks but can still leak on release surface. |
| C6 | Release-safe schema projection became a core contract. |
| C7 | `(request_id, list_group)` became the production semantic unit. |
| C8 | Factors should be relational/transferable, not feature translation. |
| C9-C13 | Provider/workflow consolidation and request-level rubric admission emerged. |
| C14-C16 | Partial rewrites exposed schema residue, enumerated skill patches, overbroad rubrics, and external polling. |
| C17/current | True tool-use loop: model emits tool calls; tools are hand/eye/mirror. |

## Regression Watch

- Internal examples from old conversations in SKILL prose.
- Numeric thresholds or static enumerations in SKILL prose.
- LLM self-rated fields.
- 0-5/Likert rubric scales for single-pass judgment.
- LLM-as-champion-judge evolution skills.
- External `check_feedback` polling shape.
- C15 bridge compatibility slots.
- Deleted D4 rubric axis.
- Pure-text click/roleplay evidence as release proof.

## Conflict Rule

If old material conflicts with current work, prefer:

1. `.planning/intel/decisions.md`
2. `docs/meta/memory.md` and `docs/meta/rubrics.md`
3. current code/tests
4. this history file
