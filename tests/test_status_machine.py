from __future__ import annotations

import pytest

from seers_harness.evolution.delta_portfolio import DeltaPortfolioRow
from seers_harness.evolution.status_machine import (
    apply_status_transitions,
    wilson_lcb,
)


def _row(
    *,
    sample_count: int = 0,
    success_count: int = 0,
    failure_count: int = 0,
    token_cost_delta_sum: int = 0,
    status: str = "experimental",
) -> DeltaPortfolioRow:
    return DeltaPortfolioRow(
        delta_id="D-1",
        target_skill="current/personalized-copy-generation/SKILL.md",
        change_type="modify_skill",
        observation="o",
        proposed_change="c",
        evidence_refs=[{"path": "p", "value": None}],
        applicable_surface=["personalized-copy-generation"],
        failure_types=[],
        sample_count=sample_count,
        success_count=success_count,
        failure_count=failure_count,
        belief_alpha=1.0 + success_count,
        belief_beta=1.0 + failure_count,
        token_cost_delta_sum=token_cost_delta_sum,
        status=status,
    )


def test_wilson_lcb_zero_total() -> None:
    assert wilson_lcb(0, 0) == 0.0


def test_wilson_lcb_high_success() -> None:
    assert wilson_lcb(95, 100) == pytest.approx(0.887, abs=0.01)


def test_apply_status_transitions_promote() -> None:
    row = _row(sample_count=20, success_count=18, failure_count=2)

    out = apply_status_transitions(
        [row],
        token_cost_deltas_by_delta={"D-1": [300, 500, 700, 200, 100]},
    )

    assert out[0].status == "ready_for_review"


def test_apply_status_transitions_reject() -> None:
    row = _row(sample_count=15, success_count=2, failure_count=13)

    out = apply_status_transitions([row])

    assert out[0].status == "rejected"


def test_apply_status_transitions_holds_when_insufficient_samples() -> None:
    row = _row(sample_count=3, success_count=3, failure_count=0)

    out = apply_status_transitions([row])

    assert out[0].status == "experimental"


def test_apply_status_transitions_ignores_token_cost_for_promotion() -> None:
    row = _row(sample_count=20, success_count=18, failure_count=2)

    out = apply_status_transitions(
        [row],
        token_cost_deltas_by_delta={"D-1": [5_000, 6_000, 7_000, 8_000, 9_000]},
    )

    assert out[0].status == "ready_for_review"
