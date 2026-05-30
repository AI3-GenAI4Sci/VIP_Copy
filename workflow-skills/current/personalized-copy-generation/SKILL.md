---
name: personalized-copy-generation
description: Mine personalization factors and write linked copy candidates in one shared session.
---

# Personalized Copy Generation

## Purpose

Run the default merged generation path for one request/list group. Mine factors
and write slogans in the same reasoning session so product detail, user scene,
and list context stay alive. Keep the durable artifacts separate: factors carry
the reason a user-product relation matters; copy carries the visible line linked
back to one source factor.

The split factor and copy skills are archived reference material. Do not behave
as if the generation job has two isolated prompts unless the runtime is running
an old compatibility node.

## Inputs

- `scenario.user_state` - profile, behavior, and context signals.
- `scenario.target_products[*]` - product ids, attributes, labels, and visible
  product facts.
- `scenario.derived_features_by_product` - reusable user-product relations.
- `scenario.copy_phase.user_state_summary` - bounded profile/context fields
  for copy writing.
- `scenario.copy_phase.user_state_signals` - bounded behavior/count/derived
  signals for copy writing.
- Standards reference: `workspace/docs/rubrics.md` and
  `workspace/docs/methodology.md`.

## Durable Fields

Factor fields have separate jobs:

- `factor_id` identifies the insight card.
- `covers_product_ids` names the exact product ids the factor can support.
- `signal_pattern` states the visible user/product signal cluster before the
  inference.
- `claim` states the personalization judgment.
- `mechanism` explains why the signal pattern supports the claim.
- `manifestation` names the kind of message likely to work or fail. It must not
  contain slogan copy.
- `product_fit` says why this product can satisfy, reduce, unlock, or sharpen
  the user's tension.
- `evidence` gives short human-auditable support, not path/value dumping.

Copy fields stay small:

- `candidate_id` identifies the line.
- `product_id` links to the target product.
- `source_factor_id` links to the factor that licensed the line.
- `text` is the recommendation-card slogan.

If the active runtime still exposes older names, map the same meanings into the
old schema without reviving old behavior. Older `bridge`, `direction`,
`bridge_logic`, draft, or hook fields are storage compatibility, not a thinking
model.

## Core Mechanism

This is the merged generation path. The same session may read and revise both
factor state and copy state, but the states keep different jobs. Copy state can
show what has already been attempted; it must not substitute for factor state or
license a line before a factor exists.

Every accepted line must pass through this chain:

```text
factor -> target interest or avoidance point -> scene result -> slogan language
```

The steps are different:

- **Factor**: the relation behind the signal. Example shape: a parent repeatedly
  buys child sun protection and the target product has gentle adult protection.
- **Target interest or avoidance point**: what the user may want, avoid, or
  feel unsure about. Example shape: protect myself without feeling I am
  switching into an unfamiliar beauty ritual.
- **Scene result**: what changes in a lived moment. Example shape: after a day
  outside with the child, my own face is still cared for.
- **Slogan language**: the public card line. It sells the product through that
  result, without explaining the reasoning or exposing private traces.

Do not skip from factor wording to slogan wording. A factor sentence is allowed
to be analytical; a slogan line is not.

source_factor_id is necessary but not sufficient. The visible line must still
transduce that source factor into a product-grounded scene result; a valid id
with generic category copy is a weak link.

## Phase 1: Factor Mining

Work product by product, while keeping the whole request in view.

1. **Cluster the visible signals.** Read user signals, product facts, and
   derived relations together. Write the signal pattern before making the claim.

2. **Find the tension.** Look for the pressure inside the pattern: interest
   without category confidence, established belief without the right product
   form, family-care context with a self-care gap, low-risk trial in a non-core
   category, or an avoidance implied by what the user skipped. These are search
   lenses, not fixed categories.

3. **Write one insight card per distinct tension.** Preserve plural distinct user-product tensions or
   opportunities when the request contains them. Each card must include the
   signal, the claim, the mechanism, how the claim may show up in messaging,
   and why this product specifically fits.

4. **Check separation before keeping a factor.** Two factors are not distinct
   because their words differ. They are distinct only if they predict different
   user interests or avoidance points, or would lead to different scene results.

Use `maintain_factor_artifact` to read, upsert, replace, validate, and save
factor state when available. Use the current record/submit tools only as
compatibility hands. Call `reflect_on_factor_coverage` when the major tensions,
product fit, or factor separation are uncertain; answer the reflection before
editing the artifact again.

## Phase 2: Copy Writing

Treat the factor artifact as the creative brief. Raw product facts remain
available to recover detail and avoid mistakes; they do not replace the factor.

For each useful product-factor pairing:

1. **Name the hidden writing target.** Convert the factor into one user
   interest or avoidance point: what this user wants to gain, avoid, simplify,
   trust, try, repair, or stop worrying about.

2. **Translate product value into a scene result.** Use product facts to state
   what changes for the user in a moment, outcome, sensory reaction, habit,
   social setting, or comparison. Product relevance should be visible as an
   effect, form, risk reduction, or outcome, not as repeated product naming.

3. **Write slogan language.** Keep the line compact, concrete, and natural in
   the input language. Let structure follow the message: single-beat,
   two-segment, and longer balanced lines are all valid when earned.

4. **Link the line.** Record `candidate_id`, `product_id`,
   `source_factor_id`, and `text`. The source factor must be the reason this
   line exists.

Use `maintain_copy_artifact` to read, upsert, replace, validate, and save copy
state when available. Use `reflect_on_copy_quality` when lines start to sound
like paraphrases, explanations, merchant descriptions, or generic comfort
claims. Tool calls are work surfaces: call them when state, validation, or a
fresh mirror helps; do not turn them into a mechanical call after every thought.
If copy state appears before factor state, pause and rebuild the factor brief
before saving the line; copy-before-factor behavior is a red flag.

## Separation Criteria

Factor separation:

- Different if the claim or mechanism changes the user's likely response.
- Different if the manifestation would lead to a different scene result.
- Not different if both factors would produce the same line with swapped nouns.
- Not different if one factor is only a role, tier, age, or behavior label.
- Watch for single-angle collapse: several factors or lines may look varied
  while all point to the same user interest, avoidance point, or scene result.
- Watch for duplicate factors: repeated claims with changed wording do not add
  coverage.

Copy separation:

- Different if the user interest or avoidance point changes.
- Different if the product value is transformed into a different scene result.
- Not different if lines are rhythm changes around the same promise.
- Not different if one line merely repeats the product name more often.

Prefer fewer strong factors and lines over a list of same-angle variants.

## Key Rules

- A factor is the relation behind a signal, not the signal renamed.
- Role, identity, life stage, tier, family relation, or activity level is scene
  input, not the factor conclusion or visible label.
- A role or label renamed as factor is still not a factor; translate it into
  the decision pressure, risk, permission gap, or opportunity it creates with
  this product.
- `manifestation` says what messages may work or fail; it does not draft the
  message.
- `product_fit` must make the product necessary to the factor.
- Do not copy raw user evidence into visible copy.
- Do not announce the recommender, personalization mechanism, or model
  reasoning.
- Do not use numbers, currency, percentages, discount markers, or price hooks
  as the visible appeal.
- Qualitative product facts are allowed when supported: brand, category,
  attribute, qualitative value position, social proof band, product form, or
  use result.

## Anti-Patterns

- **Signal renamed as factor** -> ask what the signal changes about the user's
  decision.
- **Product-free psychology** -> add the product fact or product result that
  activates the tension.
- **Copy hidden in the factor** -> move slogan language to the copy phase and
  keep only manifestation in the factor.
- **Factor paraphrase as copy** -> rewrite toward the user's scene result.
- **Product name as relevance** -> show what the product does, reduces, enables,
  or makes feel possible.
- **Private trace wink** -> lift the transferable pattern and remove the trace.
- **Identity label on the card** -> translate the label into the moment it
  creates.
- **Single-angle collapse** -> separate the user interests, avoidance points,
  or scene results before writing more lines.
- **Duplicate factors** -> merge or replace repeated claims instead of keeping
  wording variants.
- **Copy-before-factor** -> rebuild and validate factor state before saving copy.
- **Valid id, weak line** -> keep the `source_factor_id` and rewrite the text
  until the source factor becomes a product-grounded scene result.

## Language

Write factors and `text` in the input language. Chinese inputs should produce
Chinese factor prose and Chinese slogans. Preserve ids exactly.

## Outputs

Produce two artifacts per the active domain model:

- `FactorDiscoveryArtifact`
- `CopyGenerationArtifact`

The copy artifact must link each candidate to its source factor through
`source_factor_id`. Downstream `personalized-copy-rubric-judge` scores factor
alignment, personalized distinction, slogan quality, product relevance, and
naturalness.
