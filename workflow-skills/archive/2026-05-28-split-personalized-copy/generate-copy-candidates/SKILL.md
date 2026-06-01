---
name: generate-copy-candidates
description: Turn personalization factors into short, scene-result slogan lines linked to their source factors.
---

# Generate Copy Candidates

## Purpose

Write one recommendation-card line from each useful product-factor pairing. The
line should feel like slogan copy: short, concrete, and aimed at a specific user
interest or avoidance point. It should not explain the factor, expose raw user
history, or repeat the product name to manufacture relevance.

This skill may still run as a separate node for compatibility. Treat it as phase
2 of the merged `personalized-copy-generation` session: factors remain the
primary creative brief, while raw product features are available only to recover
detail and prevent misreadings.

## Inputs

- `state['factors_artifact']` - source factors joined by `source_factor_id`.
- `scenario.user_state_summary` and `scenario.user_state_signals` - bounded
  user context for checking whether factor interpretation still fits.
- `scenario.target_products[*]` - product facts that can sharpen the visible
  product result.
- `scenario.derived_features_by_product` - reusable context, not public copy.
- Standards reference: `workspace/docs/rubrics.md` (Release-Safe Copy Rubric).

## Workflow

For each product-factor pairing worth writing:

1. **Read the factor for its target.** Identify the `claim`, `mechanism`,
   `manifestation`, and `product_fit`. In older artifacts, read the same intent from
   `transferable_disposition`, `bridge`, and evidence.

2. **Name the user interest or avoidance point.** Decide what the user wants to
   gain, avoid, feel less uncertain about, or make easier. This is the hidden
   writing target, not visible explanatory text.

3. **Translate product value into a scene result.** Use product facts to express
   what changes for the user in a moment, outcome, bodily/sensory reaction,
   social setting, habit, or comparison. Good copy states the result in the
   user's scene, not the product fact alone.

4. **Write slogan language.** Keep the line compact, concrete, and natural in
   the input language. Prefer a vivid result over generic model phrases such as
   vague "steady", "just right", or "safe pick" claims without a scene.

5. **Maintain the artifact.** Use `maintain_copy_artifact` when present.
   Preferred candidate shape is `candidate_id`, `product_id`,
   `source_factor_id`, and `text`. If the runtime still requires older fields,
   fill them as compatibility metadata after the line is chosen, not as a recipe
   for the line.

Use `reflect_on_copy_quality` or the current diversity mirror when candidates
start to paraphrase one another. Answer the reflection before changing the
artifact.

## Key Rules

- Do not explain the factor.
- Do not copy raw user evidence into visible text.
- Do not name demographic, family-role, household-role, life-stage, body, or
  relationship labels in the line.
- Do not announce the recommender, personalization mechanism, or model
  reasoning.
- Do not use numbers, currency, percentages, discount markers, or price hooks as
  the visible appeal.
- Product relevance should come from transformed effects, forms, risks, or
  outcomes, not repeated names.
- Prefer fewer strong lines over same-angle paraphrases.

## Anti-Patterns

- **Factor paraphrase** -> rewrite toward the user result, not the reasoning.
- **Merchant description** -> flip the feature into what it changes for this
  user.
- **Product name as anchor** -> make the product value visible without relying
  on naming.
- **Generic comfort phrase** -> add the concrete scene or consequence that earns
  the comfort.
- **Private-history wink** -> remove the trace and keep the transferable
  interest.
- **Compatibility fields drive wording** -> write the line first, then store
  required metadata.

## Language

Chinese inputs should produce Chinese `text`. Preserve `candidate_id`,
`product_id`, and `source_factor_id` exactly; treat retired fields such as
`target_product_id` or `bridge_logic` as storage compatibility only when the
active schema still requires them.

## Outputs

`CopyGenerationArtifact` per the active domain model. The preferred copy
candidate is intentionally minimal: id, product id, source factor id, and text.
Drafts, bridge reasoning, and chosen-draft traces are thinking, not durable
artifact content.

## Composition

Upstream factor discovery supplies the creative brief. Downstream rubric judging
scores whether the line aligns to the factor, has personalized distinction,
works as slogan copy, carries product relevance, and sounds natural.
