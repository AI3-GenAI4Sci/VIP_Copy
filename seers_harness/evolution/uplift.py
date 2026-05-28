"""Paired-control uplift evaluator for trial outcomes."""

from __future__ import annotations

from dataclasses import dataclass, field

from seers_harness.evolution.trial_runner import TrialOutcome


@dataclass(frozen=True)
class TrialUplift:
    success_lift: int
    token_cost_delta: int
    behavioral_metric_lift: dict[str, float] = field(default_factory=dict)
    is_positive: bool = False


def compute_uplift(
    baseline: TrialOutcome,
    trial: TrialOutcome,
    *,
    budget_tolerance: int = 1_000,
    behavioral_metrics_baseline: dict[str, float] | None = None,
    behavioral_metrics_trial: dict[str, float] | None = None,
) -> TrialUplift:
    success_lift = int(bool(trial.success)) - int(bool(baseline.success))
    token_cost_delta = int(trial.token_cost_observed) - int(
        baseline.token_cost_observed
    )
    baseline_metrics = behavioral_metrics_baseline or {}
    trial_metrics = behavioral_metrics_trial or {}
    metric_names = sorted(set(baseline_metrics) | set(trial_metrics))
    metric_lift = {
        name: round(float(trial_metrics.get(name, 0.0)) - float(baseline_metrics.get(name, 0.0)), 10)
        for name in metric_names
    }
    has_behavioral_lift = any(value > 0 for value in metric_lift.values())
    if metric_lift:
        is_positive = (
            success_lift >= 0
            and token_cost_delta <= budget_tolerance
            and has_behavioral_lift
        )
    else:
        is_positive = success_lift > 0 and token_cost_delta <= budget_tolerance
    return TrialUplift(
        success_lift=success_lift,
        token_cost_delta=token_cost_delta,
        behavioral_metric_lift=metric_lift,
        is_positive=is_positive,
    )
