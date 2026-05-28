---
name: generate-copy-candidates
description: Turn each factor's persuasion angle into one short Chinese card line — slogan-cadence, perspective-flipped, anchored on a single concrete element, free of numerics and system self-reference.
---

# Generate Copy Candidates

## Purpose

For one request and one list group, write one card line per (product, factor) pair. The line sits next to image, title, price, and fact microcopy. The user is, by default, not yet interested; the line moves them toward interest by landing the upstream persuasion angle as a small, specific, well-cadenced piece of card copy. A line that could sit under any user's card has wasted the slot.

## Inputs

- `state['factors_artifact']` — upstream factors with `transferable_disposition`, `bridge`, `evidence_refs`, `direction`.
- `scenario.target_products[*]` — attributes and observed labels.
- `scenario.derived_features_by_product` — bucket labels per product.
- Standards reference: `workspace/docs/rubrics.md` (Release-Safe Copy Rubric).

## Workflow

For each (product, factor) pair, pass through five silent steps:

1. **Read the factor for its angle.** Identify the psychological door, the product entry point, and the persuasion angle. The card line works *that* angle; the factor's wording is reasoning, not vocabulary.

2. **Flip the perspective.** Restate the entry point as a user-facing consequence — what the affordance does for this user inside their life, decision, day, or feeling. A line still phrased in the merchant's voice has not flipped.

3. **Choose an anchor type.** Land the angle on exactly one of: a specific moment, a sensory or bodily reaction, a third-party reaction, a contrast, a habit or trait, an observable consequence, or a physical detail of the product itself. Anchor types are diversity dimensions across the candidate set, not a checklist for one line.

4. **Write to slogan cadence.** A short two-beat line cut by a comma; concrete nouns instead of abstract category words; conversational register, like a friend leaning in with one piece of advice. Negation often sharpens specificity — naming the precise anxiety the product removes.

5. **Match the user layer.** The factor encodes who this user is. A youthful self-expression register on a private-rare-moment angle has missed the user; a time-tested re-recognition register on a category-entry angle has done the same.

After drafting all candidates:

6. **Call `reflect_on_diversity`.** Its core questions are whether candidates spread across distinct psychological doors and across distinct anchor types, and whether any two candidates would still work after swapping their products. Same-anchor or same-door clusters are the failure to catch here. Answer in writing the next turn, then submit.

7. **Submit through `submit_copies_final`.**

## Key rules

- Hook anchors may be drawn from `factor.evidence_refs[].value`, `user_state_summary`, `user_state_signals`, `target_products`, and `derived_features_by_product[product_id]`; behavior-list identifiers explain disposition, but never become visible copy tokens.
- One anchor per line; one door per candidate.
- Numbers, currency, percentages, discount markers, and price-implication wording never appear in the visible text — these expose retrieval boundaries and degrade the slot to a banner.
- Demographic, family role, household role, life-stage, tier, body, or relationship identity is never named as a label inside the visible text.
- The line never announces the recommendation system or its reasoning.
- When the chosen door yields no hookable fragment, switch the door (mentally regenerate the factor) or return fewer candidates. Skipped pairs are cleaner than generic lines.

## Anti-patterns

- **Universal merchant line** (workflow step 2 fails — perspective not flipped) → return to step 1 and rebuild on the entry point as a user-facing consequence.
- **Factor-noun echo** (workflow step 3 fails — no anchor, just paraphrased relation) → name the moment, reaction, or consequence, not the relation.
- **System self-reference** (workflow step 4 fails — register exposes the recommender) → personalization is felt by hitting the situation, never by declaring it.
- **Identity label on the card** (workflow step 5 fails — role surfaced as text) → translate the role into the moment that role creates.
- **Numeric or price-implication hook** (key rule violated) → switch to the qualitative side of the same evidence (category, brand, derived bucket, observed label) or skip the pair.
- **Emotion-only filler** (workflow step 3 fails — no anchor) → emotion is the register; an anchor still has to appear in the content.
- **Same anchor across the set** (reflection step 6 fails) → rewrite the redundant lines onto different anchor types.

## Language

Chinese inputs → `text` is Chinese; `bridge_logic.product_anchor`, `bridge_logic.relation_anchor`, `intended_effect`, `risk` are Chinese. `source_factor_id` and `target_product_id` are passthrough identifiers.

## Outputs

`CopyGenerationArtifact` per the domain model. The artifact is the only handoff to the rubric judge; the judge will be reading for whether the angle landed and whether one anchor can be pointed at — write so both are visible.

## Composition

Upstream `discover-personalization-factors`; downstream `personalized-copy-rubric-judge`. The judge re-reads each candidate against the seven binary axes; structurally weak candidates that pass schema will fail the judge's floor axes and be rejected.
