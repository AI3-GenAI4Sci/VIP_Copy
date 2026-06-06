"""Rubric-derived reward provenance for trial outcomes."""

from __future__ import annotations

from dataclasses import dataclass, field

from seers_harness.domain.models import PersonalizedCopyRubricArtifact


@dataclass(frozen=True)
class BaselineReference:
    """Expected formal-version performance for one trial request."""

    mean_rubric_score: float
    mean_token_cost: float = 0.0
    sample_count: int = 0
    strategy: str = "same_wave"
    cohort_key: str = ""


@dataclass(frozen=True)
class TrialUplift:
    baseline_mean_rubric_score: float
    trial_mean_rubric_score: float
    score_delta: float
    token_cost_delta: int = 0
    behavioral_metric_lift: dict[str, float] = field(default_factory=dict)
    is_positive: bool = False
    baseline_reference_strategy: str = "exact_request"
    baseline_reference_sample_count: int = 1
    baseline_reference_cohort_key: str = ""


def mean_total_score(artifact: PersonalizedCopyRubricArtifact) -> float:
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
    baseline_reference = BaselineReference(
        mean_rubric_score=mean_total_score(baseline),
        sample_count=1,
        strategy="exact_request",
    )
    return compute_uplift_against_reference(
        trial,
        baseline_reference,
        token_cost_delta=token_cost_delta,
        behavioral_metric_lift=behavioral_metric_lift,
    )


def compute_uplift_against_reference(
    trial: PersonalizedCopyRubricArtifact,
    baseline_reference: BaselineReference,
    *,
    token_cost_delta: int = 0,
    behavioral_metric_lift: dict[str, float] | None = None,
) -> TrialUplift:
    trial_mean_rubric_score = mean_total_score(trial)
    score_delta = trial_mean_rubric_score - baseline_reference.mean_rubric_score
    return TrialUplift(
        baseline_mean_rubric_score=baseline_reference.mean_rubric_score,
        trial_mean_rubric_score=trial_mean_rubric_score,
        score_delta=score_delta,
        token_cost_delta=int(token_cost_delta),
        behavioral_metric_lift=dict(behavioral_metric_lift or {}),
        is_positive=trial_mean_rubric_score > baseline_reference.mean_rubric_score,
        baseline_reference_strategy=baseline_reference.strategy,
        baseline_reference_sample_count=max(0, int(baseline_reference.sample_count)),
        baseline_reference_cohort_key=baseline_reference.cohort_key,
    )
