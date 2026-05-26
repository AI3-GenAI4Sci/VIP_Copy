---
name: generate-copy-candidates
description: Write one short Chinese card line per (product, factor) that survives U2U/U2I retrieval and never leaks a user-history token.
---

# Generate Copy Candidates

## What this skill does

Write one short Chinese line under a product card, one per (product,
factor) pair from upstream. Each line is an offline asset routed through
U2U/U2I retrieval; it must read honestly for a retrieved user who shares
the disposition but not the authoring user's literal history tokens.

## Glossary

- factor: upstream user-product relation; carries the public hook.
- bridge: how the factor becomes a visible moment, decision, or scene.
- product anchor: a literal product-side fragment — category, brand, or
  feature name — that must appear in the visible text.
- relation anchor: a literal fragment of the bridge moment that also must
  appear in the visible text, tying the line to the factor.

## How to think

Transform the factor into a bridge, then into a line short enough to sit
under the title beside fact microcopy. Turn the relation into a moment,
decision, or scene; do not restate the factor noun or echo product-page
merit.

Hook words come only from factor evidence and this product's
`derived_features_by_product` label. The handler enforces that both
anchors are literal substrings of the text and that structural number,
length, and user-history-token rules hold; do not paraphrase its rules.

Emotion can carry register, not payload. Keep one structural fingerprint
in every line: a category fragment, brand, use-scene, role/relation word,
or decision verb the line cannot drop without becoming generic.

## Anti-patterns

Do not write a generic merchant line, label the user with a demographic or
family identity, announce the system's reasoning, or invent a fact the
schema does not show. Do not put a user-history token from this user's
behavior into the visible text — a retrieved user without that token will
read it as someone else's trace. When the only honest hook is missing,
return fewer candidates rather than weak ones.

## Reflection

Use `record_candidate` once per pair; call `reflect_on_diversity` when the
set risks same-angle paraphrase, head collision, or over-fit to one age
register, before `submit_copies_final`. Answer its questions in writing in
the next turn, then submit. Reflection is a mirror, not a verdict.

## Finishing

Submit through `submit_copies_final` once every candidate passes hook
trace, bridge transformation, and retrieval portability; the artifact is
the only handoff to the rubric judge.
