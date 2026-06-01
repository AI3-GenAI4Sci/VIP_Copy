# Personalized Copy Skills Redesign

Date: 2026-05-28

## Purpose

This design records the agreed redesign direction for the personalized copy
skills and their tools. The goal is not to rewrite prompts from scratch, but to
iterate the current skills toward a cleaner capability model:

- Mine distinct, explainable personalization factors from real user/product
  signals.
- Turn each factor into slogan-like copy that targets a specific user interest
  or avoidance point.
- Keep tools as artifact hands and reflection mirrors, not hidden judges or
  mechanical hooks.
- Produce scored rubric artifacts so evolution deltas can be compared.

## Core Principles

The redesign follows these principles:

- Schema stores durable outputs, not thinking traces.
- Tools maintain JSON artifacts and trigger useful reflection turns; they do
  not judge copy quality.
- Skills teach the agent how to think and write; deterministic hard gates are
  minimized.
- Factor and copy generation should share one session so information is not
  lost between nodes.
- Factor and copy remain separate artifacts, even when generated in one merged
  execution context.
- Every factor field must have an irreplaceable role.
- Factors for the same product must have low similarity. If two factors predict
  the same user response, merge or rewrite them.

## Merged Generation Node

Replace separate factor and copy nodes with one session-level generation node:

```text
personalized-copy-generation
```

The node runs two conceptual phases per product:

```text
For each target product:
  Phase 1: mine personalization factors
  Phase 2: write copy candidates from those factors
```

The phases are independent per product, but all products remain in the same
session. This preserves global user/list context while reducing product-to-
product interference.

The copy phase may read the full original feature payload, but it should treat
the factor artifact as the primary creative brief. Raw features are used to
recover detail, prevent misreadings, and sharpen language, not to bypass the
factor.

## Factor Artifact

`PersonalizationFactor` becomes an insight card:

```yaml
factor_id: string
covers_product_ids: list[string]
signal_pattern: string
claim: string
mechanism: string
manifestation: string
product_fit: string
evidence: list[string]
```

Field meanings:

- `signal_pattern`: the observed user/product feature cluster. It describes
  what is visible without making the psychological claim yet.
- `claim`: the personalization judgment inferred from the signal pattern.
- `mechanism`: why the signal pattern supports the claim; the decision or
  psychological mechanism.
- `manifestation`: what kinds of messages the user is likely to respond to or
  reject if the factor is true. This must not write concrete slogan lines.
- `product_fit`: why this product can satisfy or activate the factor.
- `evidence`: concise human-readable evidence bullets. These are for audit and
  review, not technical `path/value` dumps.
- `covers_product_ids`: the exact product ids this factor applies to.

Removed factor fields:

```yaml
user_side_signal
direction
transferable_disposition
evidence_refs
bridge
```

These older fields either mixed user and product evidence, encouraged prose
summaries, or did not participate in meaningful downstream decisions.

## Factor Skill Workflow

The updated factor-mining section should teach this workflow:

```text
1. Cluster raw signals into candidate signal patterns.
2. Find tensions inside each pattern.
3. Write one insight card per distinct tension.
4. Check factor separation for the current product.
5. Maintain the factor artifact.
```

Useful tension types include:

- Established belief but missing product form.
- Interest present but category knowledge missing.
- Family or role-driven purchase context with a self/adult-care gap.
- Low-risk trial window for a non-core category.
- Strong preference or aversion inferred from ignored vs clicked items.

The skill should retain the current good principles:

- A factor is the relation behind a signal, not the signal renamed.
- Role, identity, life stage, tier, or family relation is scene input, not a
  factor conclusion.
- Reach for non-obvious angles.
- Verify transferability to another user with the same signal pattern but
  different exact tokens.

## Copy Artifact

`CopyCandidate` becomes intentionally minimal:

```yaml
candidate_id: string
product_id: string
source_factor_id: string
text: string
```

Removed copy fields:

```yaml
target_product_id
group_key
bridge_logic
considered_drafts
chosen_draft_index
used_copyable_hooks
intended_effect
```

Rationale:

- `text` is the only candidate surfaced downstream.
- `source_factor_id` links the candidate to the factor insight.
- Drafts and reasoning are thinking traces, not artifact fields.
- Bridge anchors forced mechanical substring games and did not improve slogan
  quality.

## Copy Skill Workflow

The copy skill should teach this transformation:

```text
personalization factor
  -> target user interest or avoidance point
  -> scene result the user cares about
  -> slogan language
```

Important rules:

- Do not explain the factor.
- Do not repeat product names to manufacture product relevance.
- Do not copy raw user evidence into visible text.
- Do not use generic model phrases as proof, such as vague "稳", "刚好",
  "闭眼入", unless a concrete scene result carries the claim.
- Product relevance should come from transformed product effects, forms, risks,
  or outcomes.
- Good copy often states the result in the user's scene, not the product fact.

For the real sunscreen case, lines closer to the target style were:

```text
带娃晒一天，回家脸也不狼狈
不懂护肤也会选，晒完不红脸
```

The lesson is not to hard-code these forms. The lesson is that the product
benefit is translated into the target user's scene result.

## Generation Tools

Use tools, not hooks, for generation artifacts.

Tools are available to the agent and should be called when useful. The skill
should not force a rigid tool call after every thought.

### Factor Tools

```text
maintain_factor_artifact
reflect_on_factor_coverage
```

`maintain_factor_artifact` is a JSON artifact hand. It should support:

```text
read
upsert_many
delete_many
replace_for_product
validate
save
```

It maintains factors with the new factor schema. It should not score quality.

`reflect_on_factor_coverage` is a mirror. It should force a new reasoning turn
that asks, for the current product:

```text
1. Are the recorded factors covering the major visible tensions?
2. Are any factors too similar in claim or manifestation?
3. Is any factor shallow, merely renamed from a signal, or missing product fit?
```

### Copy Tools

```text
maintain_copy_artifact
reflect_on_copy_quality
```

`maintain_copy_artifact` is a JSON artifact hand. It should support:

```text
read
upsert_many
delete_many
replace_for_product
validate
save
```

It maintains candidates with the minimal copy schema. It should not enforce
style, numeric, self-reference, or privacy rules. Those remain skill/rubric
concerns.

`reflect_on_copy_quality` is a mirror. It should force a new reasoning turn that
asks, for the current product:

```text
1. Do the candidates aim at distinct factors rather than paraphrasing one idea?
2. Does each candidate sound like a slogan, not an explanation?
3. Does each line target a user interest or avoidance point from its factor?
4. Does product relevance come from transformed benefit, not repeated naming?
```

## Submit Tools

Remove submit tools from the generation path:

```text
submit_factors_final
submit_copies_final
```

The maintain tools own artifact state. A separate submit action duplicates the
same responsibility and turns the flow into a mechanical protocol.

## Rubric Judge

The judge remains independent from generation. It should produce scored outputs
for evolution, not only `admit/hold/reject`.

The initial rubric uses five 0-5 axes:

```yaml
factor_alignment: 0-5
personalized_distinction: 0-5
slogan_quality: 0-5
product_relevance: 0-5
naturalness: 0-5
total_score: 0-25
decision: admit | hold | reject
diagnostics:
  main_strength: string
  main_weakness: string
  failure_tags: list[string]
```

### factor_alignment

Whether the line targets the source factor's `claim`, `mechanism`, and
`manifestation`.

```text
0: unrelated to the factor.
1: only touches a surface word.
2: matches the broad topic but loses the key tension.
3: basically maps to the factor claim.
4: clearly captures the claim and mechanism.
5: precisely translates the deep mechanism without explaining it.
```

### personalized_distinction

Whether the line reveals a specific target interest or avoidance point.

```text
0: applicable to any user.
1: extremely weak user shadow.
2: user scenario exists but is generic or hard-copied.
3: clear interest entry is visible.
4: scene and interest naturally fuse with good distinction.
5: sharply targets a user tension without exposing private history.
```

### slogan_quality

Whether the line reads like slogan copy rather than explanation or platform
guidance.

```text
0: not copy; reads like analysis or instructions.
1: understandable but no advertising language feel.
2: has rhythm, but explanatory or model-ish.
3: usable recommendation-card slogan.
4: clear scene result, natural rhythm, memorable.
5: short, vivid, sharp, and like strong ecommerce copy.
```

### product_relevance

Whether product value is naturally present.

```text
0: product is invisible.
1: only deictic reference such as "this bottle".
2: repeats product or brand name without translating value.
3: product category or basic function is clear.
4: product benefit is translated into a concrete result.
5: unique product value is naturally embedded in the user's scene.
```

### naturalness

Whether the line sounds human, credible, and non-mechanical.

```text
0: unnatural, misleading, offensive, or clearly wrong.
1: stiff and obviously generated from a profile.
2: readable but templated, vague, or model-like.
3: naturally acceptable.
4: credible and fluent with real ecommerce tone.
5: very natural, human, and free of visible reasoning traces.
```

Derived decision:

```text
admit:
  total_score >= 21 and no axis <= 2

hold:
  total_score 15-20, or total >= 21 with any axis <= 2

reject:
  total_score < 15, or any critical axis is 0
```

Critical axes:

```text
factor_alignment
slogan_quality
product_relevance
```

This rubric is an initial version. It should be evaluated against real evolution
runs for score spread and failure coverage.

## Open Validation Questions

- Does the 0-5 rubric create enough score spread, or do candidates cluster too
  tightly?
- Are the five axes sufficient to capture common failures after the redesign?
- Does per-product two-phase generation reduce cross-product factor leakage?
- Do maintain tools reduce token waste compared with append + submit tools?
- Does copy improve when it can access raw features in the same session while
  still using factor artifacts as the creative brief?
