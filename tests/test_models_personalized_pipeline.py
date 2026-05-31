"""Schema invariants for user mining, copy generation, and rubric artifacts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from seers_harness.domain.models import (
    CopyCandidate,
    RubricAxisScore,
    UserPersonalizationFactor,
)


def test_user_personalization_factor_fields_are_user_side_only() -> None:
    assert list(UserPersonalizationFactor.model_fields) == [
        "user_factor_id",
        "signal_basis",
        "need_or_pain",
        "scene_trigger",
        "buying_heuristic",
        "expression_hooks",
        "evidence_refs",
    ]
    forbidden = {"product_fit", "covers_product_ids", "claim", "mechanism"}
    assert not (set(UserPersonalizationFactor.model_fields) & forbidden)


def test_copy_candidate_binds_user_factor_and_product_fact() -> None:
    assert list(CopyCandidate.model_fields) == [
        "candidate_id",
        "product_id",
        "source_user_factor_id",
        "text",
        "commercial_angle",
        "product_binding",
        "fact_binding",
    ]


def test_rubric_axis_contract_uses_split_pipeline_axes() -> None:
    axis = RubricAxisScore(
        axis_id="user_factor_grounding",
        score=5,
        diagnostic="用户因子由行为信号支撑",
    )
    assert axis.axis_id == "user_factor_grounding"
    with pytest.raises(ValidationError):
        RubricAxisScore(axis_id="factor_alignment", score=5, diagnostic="old")
