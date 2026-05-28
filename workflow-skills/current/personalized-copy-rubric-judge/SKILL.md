---
name: personalized-copy-rubric-judge
description: Judge each copy candidate against seven binary axes with critique-before-verdict, in the candidate's input language, and decide admit/hold/reject by the floor rule. Reads in list-group context; never aggregates the binaries into a score.
---

# Personalized Copy Rubric Judge

## Purpose

For one request and one list group, judge every candidate in `state['copies_artifact']` on a fixed set of seven binary axes, then decide `admit`, `hold`, or `reject` per candidate. Verify whether the line lands the persuasion angle on a specific anchor without breaking safety and welcome rules. Admit-everything leaks generic and unwelcome lines into the offline buffer; reject-everything starves the buffer. The floor rule keeps both failures off.

## Inputs

- `state['copies_artifact']` — candidates with `text`, `source_factor_id`, `target_product_id`, `bridge_logic`.
- `state['factors_artifact']` — upstream factors, joined by `source_factor_id`.
- Standards reference: `workspace/docs/rubrics.md` (Release-Safe Copy Rubric, Admission And Export Rubric).

## The seven axes

Each axis carries `axis_id`, a `verbatim_candidate_quote` that is a literal substring of `text` (or empty for a structural absence), a one-sentence `bridge_to_anchor` critique in the candidate's input language, and a `verdict` of `pass` or `fail`. The axes are not aggregated.

Floor axes (any failure → `reject`):

- `factor_fit` — the line carries the upstream factor's persuasion angle through the same psychological door the factor named.
- `persuasion_specificity` — at least one anchor (specific moment, sensory or bodily reaction, third-party reaction, contrast, habit or trait, observable consequence, physical detail) is present and quotable from the visible text.
- `user_perspective` — the line is written from the user's vantage; product-facing description without a user-facing consequence fails.
- `welcome_address` — no demographic, family role, household role, life-stage, tier, body, or relationship identity is presented as a label inside the visible text.
- `no_system_introspection` — the line does not announce the recommender, the personalization mechanism, or the model's reasoning.
- `no_price_or_number_hook` — no number, currency, percentage, discount marker, or price-implication wording carries the line.

Non-floor axis (failure → `hold`, only if all floor axes pass):

- `retrieval_portability` — another user sharing the same scene and door, but not this exact history, would still receive the line honestly.

## Workflow

For each candidate:

1. **Reconstruct the user.** Read the joined factor's scene and door, then read the candidate as a user in that scene would. Skip this step and the verdict becomes a copy review, not a personalization judgment.

2. **For each axis, write the critique first.** One sentence in the candidate's input language. Quote the literal fragment that does or fails to do the axis's work into `verbatim_candidate_quote` (a non-quote axis may leave it empty; the critique still names what is missing). Only after the critique is on the page, write the verdict.

3. **Apply the floor rule.** Any floor axis at `fail` → `decision = reject` and the failed `axis_id`s populate `floor_violations`. All seven `pass` → `admit`. Floor axes all `pass` and only `retrieval_portability` `fail` → `hold`.

4. **Write `primary_strength`, `primary_risk`, and `rationale`** in the candidate's input language. The rationale names the dominant axis driving the decision, not a hedge.

5. **Record through `judge_candidate`.**

After all candidates:

6. **Submit through `submit_judgments_final`.**

## Key rules

- The seven axes above are the contract; do not add, drop, or reorder them.
- Critique precedes verdict on every axis, every candidate.
- Floor failure → `reject`; never `admit` to preserve a near-miss line.
- `verbatim_candidate_quote` is a literal substring of `text` or empty; paraphrase is forbidden.
- Binaries do not aggregate into a score, weight, or average.
- `bridge_to_anchor`, `primary_strength`, `primary_risk`, `rationale` are written in the candidate's input language.

## Anti-patterns

- **Admit despite floor failure** (workflow step 3 violated) → respect the floor rule; populate `floor_violations` and reject.
- **Reject for non-floor failure alone** (workflow step 3 violated) → `hold` is the correct decision when only `retrieval_portability` fails.
- **Verdict before critique** (workflow step 2 reversed) → if the critique is being written to fit a chosen verdict, restart the axis.
- **Paraphrase in `verbatim_candidate_quote`** (key rule violated) → copy the literal substring, or leave empty for structural absence.
- **English critique on Chinese input** (language rule violated) → judge in the candidate's input language so the quote and the reasoning live in the same script.
- **Aggregating axes into a number** (key rule violated) → seven binary calls, one floor rule, one decision.
- **Inventing axes outside the seven** (key rule violated) → route the observation to the existing axis it most fits, or note it in `notes` for case review.

## Reflection

This skill has no `reflect_*` tool by design. The per-axis critique is the reflection surface. Before each verdict, ask whether the quote is in the text, whether a similar-scene user would receive the line honestly, and whether a floor axis is failing under the critique just written. If a floor axis is failing, the decision is already `reject`.

## Outputs

`PersonalizedCopyRubricArtifact` per the domain model. Each judgment carries the seven axes in critique-before-verdict order, accurate `floor_violations`, a decision consistent with the floor rule, and a rationale in the input language.

## Composition

Upstream `discover-personalization-factors` and `generate-copy-candidates`. Downstream consumers (admission/export, offline buffer, case-reading) rely on this artifact's `decision` field; the floor rule is what keeps the buffer trustworthy across batches.
