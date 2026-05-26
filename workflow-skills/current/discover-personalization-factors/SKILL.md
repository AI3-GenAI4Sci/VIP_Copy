---
name: discover-personalization-factors
description: Discover transferable user-product factors a downstream copy node can speak from without reopening raw user state.
---

# Discover Personalization Factors

## What this skill does

Mine sparse user-product relations for one request and one list group, and
record each as a transferable disposition that survives U2U/U2I retrieval.
A factor names a relation and surfaces a public hook for the copy node; it
never narrates the user and never pre-writes the card line.

## Glossary

- transferable disposition: the latent reason a *type* of user could care
  about this product, distilled so a retrieved user with the same disposition
  but different history tokens still fits the factor.
- public hook: a concrete fragment from `derived_features_by_product` or
  product attributes the copy node can quote without seeing raw user state.
- references advisory: catalog labels are evidence for relation hypothesis,
  not verdicts; treat them as inputs, not as the factor.

## How to think

Read user, product, and derived signals together. Behavior is usually closer
to shopping intent than declared profile fields. A derived bucket is a seed,
not the factor itself; the factor is the relation behind the bucket.

Apply the junior-analyst test before recording. If a beginner could produce
the line by reading one field and renaming the column, it is a column
rename, not a factor. Re-record it as the disposition the column reveals.

Pick one direction per factor — `user_to_need`, `item_to_need`, or `cross`
— as a hook-origin label, not a quota. Prefer fewer strong factors over
many thin paraphrases; record only relations distinct in evidence.

## Anti-patterns

Do not transcribe a single user-side field and call it a factor. Do not
hard-stitch a literal token from this user's behavior when a retrieved user
without that token cannot carry the relation. Do not pre-pick the card
angle, name a demographic or family role as a conclusion, or invent product
facts the schema does not show.

## Reflection

Use `record_factor` once per relation; call `reflect_on_coverage` whenever
you are uncertain whether transferable angles are exhausted, before
`submit_factors_final`. The tool returns its own questions; answer each in
writing in the next turn, then submit. Reflection is a mirror, not a
verdict — it surfaces blind spots, it does not approve the list.

## Finishing

Submit through `submit_factors_final` once every recorded factor passes the
relation-not-translation, public-hook, and disposition-portability checks;
the artifact is the only handoff to the copy node.
