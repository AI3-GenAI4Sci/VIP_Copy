---
name: discover-personalization-factors
description: Build deep, scene-grounded user-product reasoning so the downstream copy node has a distinct persuasion angle per factor. A factor here is a paragraph of reasoning, not a label.
---

# Discover Personalization Factors

## Purpose

A user shown a recommended product is, by default, not yet interested. The copy node's job is to move them toward interest. This skill builds the upstream reasoning that gives the copy node something to push off from — one *psychological door* per factor, named through a transferable disposition and a concrete public hook the next node can quote.

## Inputs

- `scenario.user_state` — profile, behavior, context.
- `scenario.target_products[*]` — attributes, observed labels.
- `scenario.derived_features_by_product` — precomputed user-product relations (price gap, brand-level fit, cold-start combo, recent-search distance, activity tier).
- Standards reference: `workspace/docs/rubrics.md` (Factor Rubric) and `workspace/docs/methodology.md` (Candidate-Derived Method Rules).

## Workflow

1. **Build the scene picture.** Read profile + behavior + context + derived features as one short narrative — who this user is right now, what life-stage and shopping mood the signals imply. Stop at "buyer of category X" and every subsequent step degrades.

2. **Enumerate psychological doors.** For this user × this product, list silently the plausible routes by which they could become interested: self-reward in a private moment, peer validation against purchase uncertainty, time-tested re-recognition, anxiety-resolution, identity-shift, category-extension, exploration-of-new-affordance, and so on. Doors arise from the scene; never from a fixed taxonomy. If only one door surfaces, the scene picture is too thin — revisit step 1.

3. **Select doors for this request.** Choose distinct doors — one per factor — so the candidate set downstream is structurally diverse. Crowding multiple factors through the same door produces same-angle copy.

4. **For each chosen door, write the factor through five silent layers.**
   - Raw evidence — the literal user-side, product-side, or derived fragment.
   - Scene inference — what state of life or mood the evidence reveals.
   - Door selection — which door this factor is approached through.
   - Product entry point — the concrete affordance behind that door (attribute, derived bucket, observed label).
   - Persuasion angle — one sentence on why a user in this scene, approached through this door with this entry point, could move from indifference to interest.

5. **Compose the factor record.** Carry the reasoning compactly into `transferable_disposition`, name the door's logic in `bridge`, and put a quotable concrete fragment into every `evidence_refs[].value`. Do not write the card line; leave room for the copy node.

6. **Reach for the non-obvious angle.** Before recording, ask whether the chosen angle is the surface one any other recommendation today would pick. If yes, search for the angle a thoughtful product manager would notice — a tension the data implies but does not state.

7. **Verify transferability.** Another user with the same scene and door, but different exact history tokens, must still fit the factor. If the factor depends on one private trace, lift it to the disposition behind the trace.

8. **Call `reflect_on_coverage`** when uncertainty remains about door diversity. Its question is whether the recorded factors enter through different doors, not whether more factors could be invented. Answer in writing the next turn, then submit.

9. **Submit through `submit_factors_final`.**

## Key rules

- A factor is the relation behind a signal, not the signal renamed.
- A role, identity, life stage, tier, or family relation is a *scene input*, not a factor conclusion.
- One door per factor; distinct doors across the request.
- `evidence_refs[].value` is a literal data fragment; paraphrase belongs in `transferable_disposition` and `bridge`.
- The factor body does not pre-write the card angle.

## Anti-patterns

- **Single-field translation as factor** (workflow step 4 fails) → re-enter step 1 and lift the underlying disposition.
- **Role-as-conclusion** (workflow step 4 fails) → ask what *being in that role right now* changes about how this product is heard; that change is the factor.
- **Doors crowded onto one route** (workflow step 3 fails) → re-read the scene; a real user has more than one way of being persuaded by a real product.
- **Surface-angle settling** (workflow step 6 fails) → demand the second-look angle.
- **Paraphrase in evidence value** (workflow step 5 fails) → replace with the literal fragment.
- **Card line inside the factor** (workflow step 5 fails) → leave the writing to the copy node.

## Language

Chinese inputs → Chinese in `transferable_disposition`, `bridge`, `user_side_signal`. `evidence_refs[].value` is the literal data fragment in its original form. `direction` is the schema enum.

## Outputs

`FactorDiscoveryArtifact` per the domain model. The artifact is the only handoff downstream; what the factor does not carry, the copy node cannot recover.

## Composition

`discover-personalization-factors` → `generate-copy-candidates` → `personalized-copy-rubric-judge`. The factor's psychological door is read by the copy node as its persuasion angle; the rubric judge reads the factor only via the candidate's `source_factor_id` linkage.
