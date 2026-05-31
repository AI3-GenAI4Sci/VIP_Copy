"""Schema invariants for scored personalized-copy rubric judgments."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from seers_harness.domain.models import PersonalizedCopyRubricJudgment, RubricAxisScore


def _axis(axis_id: str, score: int) -> RubricAxisScore:
    return RubricAxisScore(axis_id=axis_id, score=score, diagnostic=f"{axis_id} ok")


def test_rubric_axis_score_declares_scored_fields_in_order() -> None:
    assert list(RubricAxisScore.model_fields) == ["axis_id", "score", "diagnostic"]


def test_axis_score_rejects_values_outside_zero_to_five() -> None:
    with pytest.raises(ValidationError):
        RubricAxisScore(axis_id="user_factor_grounding", score=6, diagnostic="too high")


def test_rubric_judgment_has_five_axis_score_contract() -> None:
    judgment = PersonalizedCopyRubricJudgment(
        candidate_id="c0",
        candidate_index=0,
        product_id="p1",
        copy_text="熬夜脸也能轻松修护",
        user_factor_id="uf1",
        axis_scores=[
            _axis("user_factor_grounding", 5),
            _axis("product_binding", 4),
            _axis("personalized_conversion", 5),
            _axis("commercial_sharpness", 4),
            _axis("expression_boundary", 5),
        ],
        total_score=23,
        decision="admit",
        main_strength="痛点和商品承接清楚",
        main_weakness="可再增强活动感",
        failure_tags=[],
    )
    assert judgment.total_score == 23
    assert {axis.axis_id for axis in judgment.axis_scores} == {
        "user_factor_grounding",
        "product_binding",
        "personalized_conversion",
        "commercial_sharpness",
        "expression_boundary",
    }


def test_old_rubric_axis_rejected() -> None:
    with pytest.raises(ValidationError):
        RubricAxisScore(axis_id="factor_alignment", score=5, diagnostic="old")
