# History

This file preserves candidate provenance. Daily operating truth lives in
`docs/memory.md`, `docs/rubrics.md`, and `.planning/`; this file explains where
those rules came from.

## Lineage

| Iteration | What mattered |
|---|---|
| C0 | Runtime baseline snapshot. |
| C1-C5 | Evidence discipline: references can be noisy, visible copy has a tight surface, offline U2U/U2I portability matters, public/private payload split is mandatory, and latent hooks can still leak. |
| C6-C8 | Product contract: release-safe schema projection, `(request_id, list_group)` as semantic unit, and factors as transferable dispositions. |
| C9-C13 | System contract: one provider/workflow direction, request-level artifact boundaries, rubric admission above item scoring, attribution-safe promotion, and repeatable validation. |
| C14-C16 | Cleanup lesson: partial rewrites create schema residue, compatibility slots, enumerated skill patches, overbroad scales, and external polling. Delete them cleanly. |
| C17 | True tool-use loop: model emits tool calls; tools are hand/eye/mirror; final JSON is a submit tool call. |
| Current | Single `workspace/` development line with request-level CSV intake, five-category scope, preserved original signals, top-level derived features, and GSD phase execution. |

## C13 Failure Distillation

| Failure | Current distilled rule |
|---|---|
| Valid business alias missed target scope. | Category scope must be explicit, centralized, and tested with positive aliases such as `防晒` plus negative neighbors such as `防晒衣`. |
| Generation category display fell back to parent category. | Provider-visible payloads must carry the normalized target cat3/list group, not a broad parent label. |
| Factor discovery stopped after one safe angle. | Factors must preserve signal bandwidth when multiple independent relations exist. |
| Copy variants became same-angle paraphrases. | Candidate diversity is judged by visible move, not surface fluency. |
| Rubric rows missed `candidate_index`; holds exported as if admitted. | Export requires stable candidate linkage and matched `admit`; hold is human-review state, not release evidence. |
| The 20-request C13 batch covered too few target products for quality claims. | Mechanics samples can prove wiring; product-quality claims need a true five-category request/list_group sample. |

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
- Raw data preprocessing that hides derived features in metadata only.
- Broad substring category matching that admits neighbor categories such as
  vitamin drinks or perfume tools.
- Export reports that treat row count as admission evidence.
- Candidate pools whose visible lines are interchangeable.

## Conflict Rule

If old material conflicts with current work, prefer:

1. `.planning/intel/decisions.md`
2. `docs/memory.md` and `docs/rubrics.md`
3. current code/tests
4. this history file
