from __future__ import annotations

from seers_harness.evolution.trial_runner import TrialOutcome
from seers_harness.evolution.uplift import compute_uplift


def _outcome(*, success: bool, tokens: int) -> TrialOutcome:
    return TrialOutcome(request_id="R-1", success=success, token_cost_observed=tokens)


def test_uplift_strict_positive() -> None:
    uplift = compute_uplift(
        _outcome(success=False, tokens=1_200),
        _outcome(success=True, tokens=1_000),
        behavioral_metrics_baseline={"anchor_diversity": 0.2},
        behavioral_metrics_trial={"anchor_diversity": 0.3},
    )

    assert uplift.success_lift == 1
    assert uplift.token_cost_delta == -200
    assert uplift.behavioral_metric_lift == {"anchor_diversity": 0.1}
    assert uplift.is_positive is True


def test_uplift_token_blow_up_blocks() -> None:
    uplift = compute_uplift(
        _outcome(success=False, tokens=1_000),
        _outcome(success=True, tokens=3_000),
        budget_tolerance=1_000,
        behavioral_metrics_baseline={"m": 0.0},
        behavioral_metrics_trial={"m": 1.0},
    )

    assert uplift.token_cost_delta == 2_000
    assert uplift.is_positive is False


def test_uplift_no_behavioral_lift_blocks() -> None:
    uplift = compute_uplift(
        _outcome(success=True, tokens=1_000),
        _outcome(success=True, tokens=1_000),
        behavioral_metrics_baseline={"m1": 0.2, "m2": 0.5},
        behavioral_metrics_trial={"m1": 0.15, "m2": 0.5},
    )

    assert uplift.success_lift == 0
    assert uplift.behavioral_metric_lift == {"m1": -0.05, "m2": 0.0}
    assert uplift.is_positive is False


def test_uplift_regression_blocks() -> None:
    uplift = compute_uplift(
        _outcome(success=True, tokens=1_000),
        _outcome(success=False, tokens=900),
        behavioral_metrics_baseline={"m": 0.1},
        behavioral_metrics_trial={"m": 0.2},
    )

    assert uplift.success_lift == -1
    assert uplift.is_positive is False


def test_uplift_empty_metrics_falls_back_to_strict_lift() -> None:
    neutral = compute_uplift(
        _outcome(success=True, tokens=1_000),
        _outcome(success=True, tokens=900),
    )
    positive = compute_uplift(
        _outcome(success=False, tokens=1_000),
        _outcome(success=True, tokens=900),
    )

    assert neutral.is_positive is False
    assert positive.is_positive is True
