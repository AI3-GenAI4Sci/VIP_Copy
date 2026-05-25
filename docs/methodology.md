# Methodology

This file is the compact source for Phase 4 SKILL rewrites and future SKILL
work. It keeps method, not old wording.

## Core Principles

- Tools are hand / eye / mirror, not brain.
- SKILL prose is a language-built function approximation: every sentence must
  preserve a transferable pattern.
- Do not write internal examples, patch lists, static domain enumerations, or
  numeric thresholds in SKILL prose.
- Real provider/data evidence beats in-context simulation for product claims.
- Clean deletes beat compatibility residue.
- Restate architecture-level intent before acting.

## Phase 4 Keep Map

| Skill | Keep | Drop |
|---|---|---|
| discover-personalization-factors | transferable disposition; junior-analyst test; references advisory | 5-class anchor list; STOP-GATE prose; user narration |
| generate-copy-candidates | user-history token ban; literal anchors; drafts as thinking trace | draft quotas; emotion/price/state static lists; explanation-phrase bans |
| personalized-copy-rubric-judge | seven binary axes; critique before verdict; floor axes by name; demographic/surveillance handling; binary-not-scale rationale | JSON output blocks; self-check blocks; old D4 axis; numeric score framing |

## Candidate-Derived Method Rules

- Discover relations, not renamed columns. A factor should leave a public hook
  the copy node can use without seeing raw user state.
- Transform factor to bridge to visible line; do not translate the factor noun
  into merchant copy.
- Prefer fewer strong candidates over same-angle paraphrases.
- Judge admission with candidate linkage and critique-before-verdict; do not let
  export mechanics become the evaluator.

## Writing Rules

- Use the 8-section SKILL shape: front matter, title, what, glossary, how to
  think, anti-patterns, reflection, finishing.
- Use placeholder tokens such as `<cat3>` and `<brand>` only when examples are
  necessary.
- Do not duplicate fixed reflection questions in SKILL prose; handlers own them.
- Name tool sequences explicitly: `record_*`, optional `reflect_*`,
  `submit_*_final`.
- Before finishing, audit every body sentence by asking: deleting this sentence
  loses which reusable pattern?

## Agent Self-Prompts

- Did I read cases, not just metrics?
- Did I migrate methodology or accidentally erase it?
- Is the capability wired into the production path?
- Am I fixing a root cause or adding a patch?
- What does this tool do for the agent: hand, eye, or mirror?
- Does the foundation actually support the next layer?
