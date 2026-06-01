---
name: discover-personalization-factors
description: Mine distinct, explainable user-product personalization factors as insight cards for downstream slogan copy.
---

# Discover Personalization Factors

## Purpose

Build the factor half of the personalized-copy generation surface. A factor is
an insight card: it explains a real tension between visible user signals and a
target product, then says what kind of message the user may respond to or reject.
It is not a label, demographic summary, rewritten feature, or pre-written card
line.

This skill may still run as a separate node for compatibility. Treat it as phase
1 of the merged `personalized-copy-generation` session: mine factors first, then
let copy generation write from them without losing the shared request context.

## Inputs

- `scenario.user_state` - profile, behavior, and context signals.
- `scenario.target_products[*]` - product attributes, observed labels, and ids.
- `scenario.derived_features_by_product` - reusable user-product relations.
- Standards reference: `workspace/docs/rubrics.md` and
  `workspace/docs/methodology.md`.

## Workflow

For each target product:

1. **Cluster raw signals into candidate patterns.** Read user, product, and
   derived signals together. A pattern should describe what is visible before
   making a personalization claim.

2. **Find the tension inside the pattern.** Look for the decision pressure:
   established belief without the right product form, interest without category
   confidence, family or role context with an adult-care gap, low-risk trial in a
   non-core category, or preference/aversion inferred from what was clicked and
   ignored. These are prompts for attention, not a fixed taxonomy.

3. **Write one insight card per distinct tension.** Separate the observed
   `signal_pattern`, inferred `claim`, causal `mechanism`, likely
   `manifestation`, product-specific `product_fit`, concise `evidence`, and
   `covers_product_ids`. If the runtime still uses older fields, map the same
   meaning into `user_side_signal`, `transferable_disposition`, `bridge`,
   `evidence_refs`, and `direction` without reviving old habits.

4. **Check factor separation for the product.** If two factors predict the same
   user response or would lead to the same slogan, merge them or rewrite one
   around a different tension.

5. **Maintain the artifact.** Use the available artifact tool for the current
   runtime (`maintain_factor_artifact` when present; otherwise the existing
   record/submit tools). Tool calls preserve state; they do not judge factor
   quality.

Use `reflect_on_factor_coverage` or the current coverage mirror when uncertainty
remains. Answer its reflection in the next reasoning turn before changing the
artifact.

## Key Rules

- A factor is the relation behind a signal, not the signal renamed.
- Role, identity, life stage, tier, family relation, or activity level is scene
  input, not the factor conclusion.
- `claim` says the personalization judgment; `mechanism` says why it follows;
  `manifestation` says what messages may work or fail, without writing slogans.
- `product_fit` must make the product necessary to the factor.
- Evidence is concise and human-auditable. Do not dump path/value mechanics into
  prose when a short evidence phrase will do.
- Verify transferability: another user with the same signal pattern but
  different exact tokens should still fit the factor.

## Anti-Patterns

- **Signal renamed as insight** -> ask what the signal changes about the user's
  decision.
- **Role as conclusion** -> translate the role into a pressure, gap, or care
  scene.
- **Product-free psychology** -> add why this product can satisfy or activate
  the factor.
- **Duplicate factors** -> compare claim and manifestation, not wording.
- **Copy hidden inside factor** -> leave slogan language for the copy phase.
- **Private trace as public hook** -> lift exact history into a portable pattern.

## Language

Chinese inputs should produce Chinese factor prose. Preserve ids exactly.
Evidence can keep source terms when they are the clearest audit trail, but the
factor claim should be written as transferable reasoning.

## Outputs

`FactorDiscoveryArtifact` per the active domain model. The preferred factor card
shape is `factor_id`, `covers_product_ids`, `signal_pattern`, `claim`,
`mechanism`, `manifestation`, `product_fit`, and `evidence`; compatibility
runtimes may store the same insight through the older factor fields.

## Composition

Upstream request context feeds this phase. Downstream copy generation treats the
factor artifact as the creative brief, while raw product features remain
available only to recover detail, prevent misreadings, and sharpen the visible
line.
