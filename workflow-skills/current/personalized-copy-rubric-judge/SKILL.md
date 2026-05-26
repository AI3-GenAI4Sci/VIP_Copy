---
name: personalized-copy-rubric-judge
description: Judge each copy candidate on seven binary axes with critique before verdict; admit only what passes the named floor axes.
---

# Personalized Copy Rubric Judge

## What this skill does

Judge each copy candidate from `state['copies_artifact']` against a fixed
set of seven binary axes for one request and one list group, then decide
admit, hold, or reject per candidate. Per-axis critique always precedes
the per-axis verdict; the artifact records both, never a numeric rating.

## Glossary

- binary axis: one rubric question with two outcomes — `pass` or `fail`.
  No scale, no points, no aggregated rating; pretending precision the
  rubric does not have only obscures the failure.
- floor axes: the named axes whose failure forces a non-admit decision;
  the schema lists them and the judgment must respect them by name.
- group-level axis: one axis is judged across the candidate's request
  and list group; treat its evidence as the visible set, not the row.
- floor violation: a list on the judgment of axes whose verdict is `fail`
  among the floor axes — empty when the candidate is admissible.

## How to think

For every axis, write the critique first. The critique reads the candidate
in its list-group context, points at the literal fragment that earns or
breaks the verdict, and only then chooses `pass` or `fail`. The handler
verifies the verbatim quote is a literal substring of the candidate; write
the quote from the text, not from memory.

A candidate is admissible only when no floor axis fails. Hold is for a
non-floor failure that would resolve with rewrite; reject is for a floor
failure or a structural problem rewrite cannot reach. Demographic and
surveillance failures are floor concerns — a line that names a protected
identity or reveals private signal back to the user is unsafe.

## Anti-patterns

Do not aggregate the binary axes into a number, compromise the verdict
toward an average, or admit a candidate when a floor axis has failed. Do
not paraphrase the candidate in the verbatim field, invent quotes, or
move the verdict before the critique in the per-axis record.

## Reflection

This SKILL has no `reflect_*` tool by design. Use the per-axis critique
as the reflection surface: before each verdict, ask whether the quote is
in the text, whether a non-current user with the same factor would still
receive the line honestly, and whether a named floor axis is failing
under the current critique.

## Finishing

Record each candidate through `judge_candidate`, then submit through
`submit_judgments_final` once every candidate has a matching judgment with
critique-before-verdict order, recorded floor violations, and an
admit/hold/reject decision aligned with the floor rule.