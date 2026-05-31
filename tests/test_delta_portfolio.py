"""Phase 6 plan 06-02 task 01 — delta portfolio persistence, posterior update,
and trial selection.

Tests are deterministic. ``select_trial_delta`` accepts an injected
``rng`` so Thompson sampling over eligible experimental rows is reproducible.
``update_after_trial`` is pure: it returns a
new ``DeltaPortfolioRow`` rather than mutating in place, so tests assert
the prior shape stays intact.
"""

from __future__ import annotations

import json
import inspect
from pathlib import Path

import pytest

from seers_harness.evolution.delta_portfolio import (
    DeltaPortfolioRow,
    belief_mean,
    load_portfolio_jsonl,
    select_trial_delta,
    update_after_trial,
    write_portfolio_jsonl,
)


class _DeterministicBetaRng:
    def __init__(self, samples: dict[tuple[float, float], float]):
        self.samples = samples
        self.calls: list[tuple[float, float]] = []

    def betavariate(self, alpha: float, beta: float) -> float:
        key = (alpha, beta)
        self.calls.append(key)
        return self.samples[key]


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _make_row(
    *,
    delta_id: str = "D-1",
    target_skill: str = "personalized-copy-generation",
    applicable_surface: list[str] | None = None,
    sample_count: int = 0,
    success_count: int = 0,
    failure_count: int = 0,
    belief_alpha: float = 1.0,
    belief_beta: float = 1.0,
    token_cost_delta_sum: int = 0,
    status: str = "experimental",
) -> DeltaPortfolioRow:
    return DeltaPortfolioRow(
        delta_id=delta_id,
        target_skill=target_skill,
        function_id="f_user_factor_to_product_hook",
        operation="modify",
        observation="o",
        proposed_change="c",
        evidence_refs=[{"path": "request_42.factor_3.text", "value": None}],
        applicable_surface=applicable_surface or ["personalized_copy_generation"],
        failure_types=[],
        belief_alpha=belief_alpha,
        belief_beta=belief_beta,
        sample_count=sample_count,
        success_count=success_count,
        failure_count=failure_count,
        token_cost_delta_sum=token_cost_delta_sum,
        status=status,
    )


# --------------------------------------------------------------------------- #
# JSONL persistence                                                           #
# --------------------------------------------------------------------------- #


def test_write_and_load_portfolio_jsonl_roundtrip(tmp_path: Path) -> None:
    rows = [_make_row(delta_id="D-1"), _make_row(delta_id="D-2", sample_count=3)]
    path = tmp_path / "portfolio.jsonl"
    write_portfolio_jsonl(path, rows)

    loaded = load_portfolio_jsonl(path)
    assert [r.delta_id for r in loaded] == ["D-1", "D-2"]
    assert loaded[1].sample_count == 3


def test_load_portfolio_jsonl_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_portfolio_jsonl(tmp_path / "nope.jsonl") == []


def test_load_portfolio_jsonl_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "portfolio.jsonl"
    row = _make_row(delta_id="D-7")
    path.write_text("\n" + row.model_dump_json() + "\n\n", encoding="utf-8")

    loaded = load_portfolio_jsonl(path)
    assert len(loaded) == 1
    assert loaded[0].delta_id == "D-7"


def test_write_portfolio_jsonl_creates_parent_dirs(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "c" / "portfolio.jsonl"
    write_portfolio_jsonl(nested, [_make_row()])
    assert nested.exists()
    parsed = json.loads(nested.read_text(encoding="utf-8").splitlines()[0])
    assert parsed["delta_id"] == "D-1"


# --------------------------------------------------------------------------- #
# Posterior update + computed belief                                          #
# --------------------------------------------------------------------------- #


def test_update_after_trial_success_increments_alpha_and_counts() -> None:
    row = _make_row()
    out = update_after_trial(row, success=True, token_cost_delta=12)

    assert out.belief_alpha == pytest.approx(2.0)
    assert out.belief_beta == pytest.approx(1.0)
    assert out.sample_count == 1
    assert out.success_count == 1
    assert out.failure_count == 0
    assert out.token_cost_delta_sum == 12

    # Source row is untouched (pure function).
    assert row.sample_count == 0
    assert row.success_count == 0
    assert row.belief_alpha == pytest.approx(1.0)


def test_update_after_trial_failure_increments_beta_and_counts() -> None:
    row = _make_row()
    out = update_after_trial(row, success=False, token_cost_delta=-5)

    assert out.belief_alpha == pytest.approx(1.0)
    assert out.belief_beta == pytest.approx(2.0)
    assert out.sample_count == 1
    assert out.success_count == 0
    assert out.failure_count == 1
    assert out.token_cost_delta_sum == -5


def test_update_after_trial_token_cost_accumulates() -> None:
    row = _make_row()
    row1 = update_after_trial(row, success=True, token_cost_delta=10)
    row2 = update_after_trial(row1, success=False, token_cost_delta=20)
    row3 = update_after_trial(row2, success=True, token_cost_delta=-3)

    assert row3.token_cost_delta_sum == 27
    assert row3.sample_count == 3
    assert row3.success_count == 2
    assert row3.failure_count == 1


def test_belief_mean_seed_prior_is_one_half() -> None:
    assert belief_mean(_make_row()) == pytest.approx(0.5)


def test_belief_mean_after_three_successes() -> None:
    row = _make_row()
    for _ in range(3):
        row = update_after_trial(row, success=True)
    # alpha=4, beta=1 → mean = 0.8
    assert belief_mean(row) == pytest.approx(0.8)


# --------------------------------------------------------------------------- #
# Trial selection — exploration decisions and Thompson sampling               #
# --------------------------------------------------------------------------- #


def test_select_trial_delta_records_no_eligible_delta_decision() -> None:
    decision = select_trial_delta(
        portfolio=[],
        applicable_surface=["personalized_copy_generation"],
    )
    assert decision.should_trial is False
    assert decision.selected_delta_id is None
    assert decision.eligible_delta_count == 0
    assert decision.trigger_reason is None
    assert decision.no_trial_reason == "no_eligible_delta"
    assert decision.posterior_samples == {}


def test_select_trial_delta_records_no_eligible_delta_when_surface_mismatches() -> None:
    rows = [_make_row(delta_id="D-1", applicable_surface=["other_surface"])]
    decision = select_trial_delta(
        portfolio=rows,
        applicable_surface=["personalized_copy_generation"],
    )
    assert decision.should_trial is False
    assert decision.selected_delta_id is None
    assert decision.eligible_delta_count == 0
    assert decision.no_trial_reason == "no_eligible_delta"


def test_select_trial_delta_universal_row_with_empty_surface_is_eligible() -> None:
    rows = [_make_row(delta_id="D-X", applicable_surface=[])]
    decision = select_trial_delta(
        portfolio=rows,
        applicable_surface=["personalized_copy_generation"],
    )
    assert decision.should_trial is True
    assert decision.selected_delta_id == "D-X"
    assert decision.eligible_delta_count == 1
    assert decision.trigger_reason == "insufficient_sample_count"
    assert decision.no_trial_reason is None


def test_select_trial_delta_records_evidence_sufficient_no_trial() -> None:
    rows = [
        _make_row(
            delta_id="D-evidenced",
            sample_count=12,
            success_count=10,
            failure_count=2,
            belief_alpha=11.0,
            belief_beta=3.0,
        )
    ]

    decision = select_trial_delta(
        portfolio=rows,
        applicable_surface=["personalized_copy_generation"],
    )

    assert decision.should_trial is False
    assert decision.selected_delta_id is None
    assert decision.eligible_delta_count == 1
    assert decision.no_trial_reason == "all_eligible_deltas_evidence_sufficient"
    assert decision.trigger_reason is None
    assert decision.posterior_samples == {}


def test_select_trial_delta_records_non_experimental_no_trial() -> None:
    rows = [
        _make_row(delta_id="D-rejected", status="rejected"),
        _make_row(delta_id="D-held", status="held"),
    ]
    decision = select_trial_delta(
        portfolio=rows,
        applicable_surface=["personalized_copy_generation"],
    )
    assert decision.should_trial is False
    assert decision.selected_delta_id is None
    assert decision.eligible_delta_count == 0
    assert decision.no_trial_reason == "all_eligible_deltas_non_experimental"


def test_select_trial_delta_information_value_triggers_low_sample_row() -> None:
    rows = [_make_row(delta_id="D-low-sample", sample_count=0)]
    decision = select_trial_delta(
        portfolio=rows,
        applicable_surface=["personalized_copy_generation"],
    )
    assert decision.should_trial is True
    assert decision.selected_delta_id == "D-low-sample"
    assert decision.trigger_reason == "insufficient_sample_count"


def test_select_trial_delta_information_value_triggers_near_boundary_row() -> None:
    rows = [
        _make_row(
            delta_id="D-boundary",
            sample_count=8,
            success_count=4,
            failure_count=4,
            belief_alpha=5.0,
            belief_beta=5.0,
        )
    ]
    decision = select_trial_delta(
        portfolio=rows,
        applicable_surface=["personalized_copy_generation"],
    )
    assert decision.should_trial is True
    assert decision.selected_delta_id == "D-boundary"
    assert decision.trigger_reason == "posterior_near_boundary"


def test_select_trial_delta_thompson_samples_eligible_experimental_rows() -> None:
    rows = [
        _make_row(delta_id="D-low", sample_count=0, belief_alpha=1.0, belief_beta=2.0),
        _make_row(delta_id="D-high", sample_count=0, belief_alpha=3.0, belief_beta=1.0),
        _make_row(delta_id="D-other", applicable_surface=["other_surface"]),
    ]
    rng = _DeterministicBetaRng({(1.0, 2.0): 0.2, (3.0, 1.0): 0.9})

    decision = select_trial_delta(
        portfolio=rows,
        applicable_surface=["personalized_copy_generation"],
        rng=rng,
    )

    assert decision.should_trial is True
    assert decision.selected_delta_id == "D-high"
    assert decision.eligible_delta_count == 2
    assert decision.posterior_samples == {"D-low": 0.2, "D-high": 0.9}
    assert rng.calls == [(1.0, 2.0), (3.0, 1.0)]


def test_select_trial_delta_skips_non_experimental_rows() -> None:
    rows = [
        _make_row(delta_id="D-rejected", status="rejected"),
        _make_row(delta_id="D-held", status="held"),
    ]
    decision = select_trial_delta(
        portfolio=rows,
        applicable_surface=["personalized_copy_generation"],
    )
    assert decision.should_trial is False
    assert decision.selected_delta_id is None


def test_select_trial_delta_contract_has_no_pressure_or_probability_inputs() -> None:
    signature = inspect.signature(select_trial_delta)
    forbidden = {
        "token_budget_pressure",
        "production_pressure",
        "trial_prob",
        "recent_failure_rate",
        "manual_prior",
    }
    assert forbidden.isdisjoint(signature.parameters)


def test_exploration_decision_payload_has_no_forbidden_gate_fields() -> None:
    decision = select_trial_delta(
        portfolio=[_make_row(delta_id="D-clean")],
        applicable_surface=["personalized_copy_generation"],
    )
    payload = decision.model_dump()

    assert payload["should_trial"] is True
    assert payload["selected_delta_id"] == "D-clean"
    forbidden = {
        "token_budget_pressure",
        "production_pressure",
        "trial_prob",
        "random_skip",
        "static_probability_miss",
        "manual_prior",
    }
    assert forbidden.isdisjoint(payload)
