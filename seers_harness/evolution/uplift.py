"""Rubric-derived reward provenance for trial outcomes."""

from __future__ import annotations

from dataclasses import dataclass, field

from seers_harness.domain.models import PersonalizedCopyRubricArtifact


@dataclass(frozen=True)
class TrialUplift:
    baseline_mean_rubric_score: float
    trial_mean_rubric_score: float
    score_delta: float
    token_cost_delta: int = 0
    behavioral_metric_lift: dict[str, float] = field(default_factory=dict)
    is_positive: bool = False


def _mean_total_score(artifact: PersonalizedCopyRubricArtifact) -> float:
    if not artifact.judgments:
        return 0.0
    total = sum(judgment.total_score for judgment in artifact.judgments)
    return total / len(artifact.judgments)


def compute_uplift(
    baseline: PersonalizedCopyRubricArtifact,
    trial: PersonalizedCopyRubricArtifact,
    *,
    token_cost_delta: int = 0,
    behavioral_metric_lift: dict[str, float] | None = None,
) -> TrialUplift:
    baseline_mean_rubric_score = _mean_total_score(baseline)
    trial_mean_rubric_score = _mean_total_score(trial)
    score_delta = trial_mean_rubric_score - baseline_mean_rubric_score
    metric_lift = dict(behavioral_metric_lift or {})
    return TrialUplift(
        baseline_mean_rubric_score=baseline_mean_rubric_score,
        trial_mean_rubric_score=trial_mean_rubric_score,
        score_delta=score_delta,
        token_cost_delta=int(token_cost_delta),
        behavioral_metric_lift=metric_lift,
        is_positive=trial_mean_rubric_score > baseline_mean_rubric_score,
    )
