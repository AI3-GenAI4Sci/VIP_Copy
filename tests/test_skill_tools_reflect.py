"""TOOL-07 / TOOL-08 — reflect_on_coverage / reflect_on_diversity invariants.

Both reflect tools are pure mirrors: they ignore args/state and return a fixed
3-question prompt. The diversity prompt is contractually required to mention
the 22-year-old age-swap canary (master_plan §2.5).
"""

from __future__ import annotations

from seers_harness.tools.skill_tools import (
    reflect_on_coverage,
    reflect_on_diversity,
)


def test_reflect_on_coverage_returns_fixed_three_question_prompt() -> None:
    out = reflect_on_coverage({}, {})
    assert isinstance(out, str)
    # Three numbered questions are the contract.
    assert "1." in out
    assert "2." in out
    assert "3." in out
    assert "submit_factors_final" in out


def test_reflect_on_coverage_is_idempotent_and_state_pure() -> None:
    state: dict = {"factors": [{"factor_id": "F-1"}]}
    out1 = reflect_on_coverage({"any": "args"}, state)
    out2 = reflect_on_coverage({}, {})
    assert out1 == out2
    assert state == {"factors": [{"factor_id": "F-1"}]}  # state untouched


def test_reflect_on_diversity_includes_22_year_old_canary() -> None:
    """The 22-year-old age-swap canary must appear literally in the prompt
    (master_plan §2.5; absence of this string would silently disable the
    diversity sanity check)."""
    out = reflect_on_diversity({}, {})
    assert "22-year-old" in out
    assert "35-year-old" in out
    assert "55-year-old" in out


def test_reflect_on_diversity_is_idempotent_and_state_pure() -> None:
    state: dict = {"candidates": [{"candidate_id": "C-1"}]}
    out1 = reflect_on_diversity({"any": "args"}, state)
    out2 = reflect_on_diversity({}, {})
    assert out1 == out2
    assert "submit_copies_final" in out1
    assert state == {"candidates": [{"candidate_id": "C-1"}]}
