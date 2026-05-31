from __future__ import annotations

from seers_harness.domain.models import (
    PersonalizedCopyRubricArtifact,
    PersonalizedCopyRubricJudgment,
    RubricAxisScore,
)
from seers_harness.evolution.uplift import compute_uplift


def _axis(axis_id: str, score: int) -> RubricAxisScore:
    return RubricAxisScore(axis_id=axis_id, score=score, diagnostic=f"{axis_id} ok")


def _artifact(*totals: int) -> PersonalizedCopyRubricArtifact:
    judgments = []
    for index, total in enumerate(totals):
        remaining = total
        scores = []
        for _ in range(5):
            score = min(5, remaining)
            scores.append(score)
            remaining -= score
        axis_scores = [
            _axis("user_factor_grounding", scores[0]),
            _axis("product_binding", scores[1]),
            _axis("personalized_conversion", scores[2]),
            _axis("commercial_sharpness", scores[3]),
            _axis("expression_boundary", scores[4]),
        ]
        judgments.append(
            PersonalizedCopyRubricJudgment(
                candidate_id=f"c{index}",
                candidate_index=index,
                product_id=f"p{index}",
                copy_text="copy",
                user_factor_id=f"uf{index}",
                axis_scores=axis_scores,
                total_score=total,
                decision="hold",
                main_strength="s",
                main_weakness="w",
                failure_tags=[],
            )
        )
    return PersonalizedCopyRubricArtifact(judgments=judgments)


def test_uplift_positive_only_when_trial_mean_score_is_strictly_greater() -> None:
    uplift = compute_uplift(
        _artifact(18, 20),
        _artifact(22, 22),
        token_cost_delta=9999,
        behavioral_metric_lift={"coverage": -1.0},
    )

    assert uplift.baseline_mean_rubric_score == 19.0
    assert uplift.trial_mean_rubric_score == 22.0
    assert uplift.score_delta == 3.0
    assert uplift.token_cost_delta == 9999
    assert uplift.behavioral_metric_lift == {"coverage": -1.0}
    assert uplift.is_positive is True


def test_uplift_equal_mean_is_failure_even_with_record_only_improvements() -> None:
    uplift = compute_uplift(
        _artifact(20, 20),
        _artifact(19, 21),
        token_cost_delta=-500,
        behavioral_metric_lift={"coverage": 1.0},
    )

    assert uplift.baseline_mean_rubric_score == 20.0
    assert uplift.trial_mean_rubric_score == 20.0
    assert uplift.score_delta == 0.0
    assert uplift.is_positive is False


def test_uplift_lower_mean_is_failure_even_if_tokens_and_behavior_improve() -> None:
    uplift = compute_uplift(
        _artifact(24, 24),
        _artifact(20, 22),
        token_cost_delta=-800,
        behavioral_metric_lift={"diversity": 0.5},
    )

    assert uplift.baseline_mean_rubric_score == 24.0
    assert uplift.trial_mean_rubric_score == 21.0
    assert uplift.score_delta == -3.0
    assert uplift.is_positive is False


def test_uplift_empty_judgments_are_zero_mean() -> None:
    uplift = compute_uplift(
        PersonalizedCopyRubricArtifact(judgments=[]),
        PersonalizedCopyRubricArtifact(judgments=[]),
    )

    assert uplift.baseline_mean_rubric_score == 0.0
    assert uplift.trial_mean_rubric_score == 0.0
    assert uplift.score_delta == 0.0
    assert uplift.behavioral_metric_lift == {}
    assert uplift.is_positive is False
