---
phase: 09-acceptance-metrics-evolution-algorithm-closure
plan: 05
run_id: 20260530T022014Z
verdict: stable-with-lightweight-repair
repair_decision: skill-wording-repair
---

# Phase 09 Merged Node Assessment

## Verdict

The merged production path remains the correct production path for
`personalized_copy_generation`.

The bounded request reading does not show an architecture-level failure. In the
sampled real run evidence, the merged node usually builds factor state before
copy state, records copy candidates with valid `source_factor_id` links, calls
reflection tools when uncertainty or separation gaps are plausible, and
produces trial evidence for every sampled request.

The quality issue is narrower: some valid factors and valid `source_factor_id`
values are later weakened into generic visible copy, product-invisible lines, or
role/label shortcuts. That maps to SKILL wording and mirror emphasis, not to a
need to restore the archived split workflow as production behavior.

## Evidence Basis

Primary artifact: `.planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-CASE-READING.md`

Real run source: `tests/smoke/.runs/20260530T022014Z/stage3/`

Eight sampled requests were read:

- Request `-2222528033296871792`: structurally linked copy, one strong
  fashion-layering transduction, and one product-invisible shoulder-protection
  line.
- Request `-2223161019833131686`: two independent factors; one candidate admits
  while the brand-trust/price-friction factor becomes generic selection copy.
- Request `-6833651210813617137`: distinct factors collapse into generic mom or
  sitting copy; all four candidates hold despite reflection and a copy repair
  tool call.
- Request `-6833651252302891142`: three separable factors; candidates preserve
  ids but sometimes compress the factor into generic sensitive-skin or SPF
  language.
- Request `-6833674815337504199`: healthy staged workflow and one admitted
  final-step fragrance line; the self-reward line under-transfers the
  low-burden/no-guilt nuance.
- Request `-6833675077757301063`: one factor reads too much like a household
  purchaser role label, leaving deeper gift-risk or scent-safety tensions
  underexplored.
- Request `-6833721464958057635`: strong factor separation and multiple admits;
  held lines still reveal product-invisibility and slogan-flatness.
- Request `-6833721702418762089`: valid links and staged state; held lines show
  weak factor alignment and a season-label shortcut.

## Stability Assessment

Stable enough to keep merged production path:

- Structural linkage held: sampled copy candidates point to existing
  `source_factor_id` values.
- Tool staging held: first copy upserts followed factor upserts in the sampled
  requests even when an early copy-artifact read occurred.
- Reflection was reachable and used across the sample.
- Strong samples show the merged node can maintain factor/copy separation in
  one reasoning session, especially requests `-6833721464958057635`,
  `-6833721702418762089`, and `-6833674815337504199`.

Not stable enough to leave the SKILL untouched:

- Request `-6833651210813617137` shows single-angle collapse after distinct
  factors were available.
- Request `-6833675077757301063` shows role/label-as-factor pressure.
- Requests `-2223161019833131686`, `-6833651252302891142`, and
  `-6833721702418762089` show semantic weak linkage even with valid
  `source_factor_id` fields.
- Product invisibility repeats across several requests, which means the copy
  phase needs stronger wording that the product must remain necessary to the
  factor-to-scene transduction.

## Diagnostic-Only Control

No split-node diagnostic-only control was run for Plan 09-05.

Reason: the failure pattern is clear enough without a control. The sample does
not show the merged architecture losing tool state or invalidating factor/copy
ids. It shows recurring wording-level shortcuts after state is available. A
split reference comparison would be diagnostic-only if future evidence showed
state-ordering or architecture ambiguity, but this plan should not change the
production DAG or reintroduce the archived split path as normal operation.

## Repair Decision

repair decision: apply a lightweight SKILL wording repair.

Repair decision: apply a lightweight SKILL wording repair.

Scope:

- Clarify the plural distinct user-product tension contract without adding any
  hard factor-count threshold.
- Make multi-record tool-state awareness explicit: read current factor and copy
  state before repair, but do not let copy state substitute for factor state.
- Add red flags for single-angle collapse, duplicate factors, copy-before-factor
  behavior, and role/label-as-factor shortcuts.
- Strengthen semantic linkage: `source_factor_id` is necessary but insufficient;
  the visible line must transduce that factor into a product-grounded scene
  result.

Non-goals:

- No hard numeric factor thresholds.
- No JSON skeletons, internal examples, or ellipsis templates.
- No enumeration/taxonomy prompting.
- No new tool implementation or DAG wiring change.
- No production rollback to archived split-node behavior.

The repair is evidence-driven by request `-6833651210813617137` for
single-angle collapse, request `-6833675077757301063` for role/label pressure,
and requests `-2223161019833131686`, `-6833651252302891142`, and
`-6833721702418762089` for semantic weak linkage despite valid ids.

## Repair Applied

Applied in Plan 09-05 Task 3 as lightweight SKILL wording only:

- Added merged-path state wording so factor state and copy state remain
  separate work surfaces inside the shared session.
- Added the plural distinct user-product tensions contract without any numeric
  factor threshold.
- Added red flags for single-angle collapse, duplicate factors,
  copy-before-factor behavior, role/label-as-factor shortcuts, and valid-id
  weak-line failures.
- Strengthened the `source_factor_id` contract so ids must be backed by
  product-grounded scene-result transduction.

No tool implementation, DAG wiring, or production split-node behavior changed.
