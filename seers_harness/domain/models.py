"""Domain schema — pydantic v2 contracts for factors, candidates, rubric judgments.

Field declaration order is load-bearing for critique-before-verdict tools
(RESEARCH Open Q2 RESOLVED — pydantic ``model_json_schema()`` preserves
declaration order in ``properties`` dict; DeepSeek tool spec emits arguments
in that order).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class EvidenceRef(BaseModel):
    path: str
    value: str | int | float | bool | None = None
    model_config = {"extra": "forbid"}


class UserPersonalizationFactor(BaseModel):
    user_factor_id: str
    signal_basis: str
    need_or_pain: str
    scene_trigger: str = ""
    buying_heuristic: str = ""
    expression_hooks: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    model_config = {"extra": "forbid"}


class CopyCandidate(BaseModel):
    candidate_id: str
    product_id: str
    source_user_factor_id: str
    text: str
    commercial_angle: str = ""
    product_binding: str = ""
    fact_binding: str = ""
    model_config = {"extra": "forbid"}


RubricAxisId = Literal[
    "user_factor_grounding",
    "product_binding",
    "personalized_conversion",
    "commercial_sharpness",
    "expression_boundary",
]


class RubricAxisScore(BaseModel):
    axis_id: RubricAxisId
    score: int = Field(ge=0, le=5)
    diagnostic: str
    model_config = {"extra": "forbid"}


RubricDecision = Literal["admit", "hold", "reject"]


class PersonalizedCopyRubricJudgment(BaseModel):
    candidate_id: str
    candidate_index: int | None = None
    product_id: str = ""
    copy_text: str = ""
    user_factor_id: str = ""
    axis_scores: list[RubricAxisScore] = Field(default_factory=list)
    total_score: int = Field(default=0, ge=0, le=25)
    main_strength: str = ""
    main_weakness: str = ""
    failure_tags: list[str] = Field(default_factory=list)
    decision: RubricDecision = "hold"
    model_config = {"extra": "forbid"}

    @field_validator("axis_scores")
    @classmethod
    def _require_distinct_axis_ids(
        cls,
        value: list[RubricAxisScore],
    ) -> list[RubricAxisScore]:
        axis_ids = [axis.axis_id for axis in value]
        if len(axis_ids) != len(set(axis_ids)):
            raise ValueError("axis_scores axis_id values must be distinct")
        return value

    @model_validator(mode="after")
    def _check_total_score(self):
        expected = sum(axis.score for axis in self.axis_scores)
        if self.total_score != expected:
            raise ValueError(
                f"total_score must equal sum(axis_scores.score): {expected}"
            )
        return self


class UserPersonalizationArtifact(BaseModel):
    user_factors: list[UserPersonalizationFactor] = Field(default_factory=list)
    model_config = {"extra": "forbid"}


class CopyGenerationArtifact(BaseModel):
    candidates: list[CopyCandidate] = Field(default_factory=list)
    model_config = {"extra": "forbid"}


class PersonalizedCopyGenerationArtifact(BaseModel):
    candidates: list[CopyCandidate] = Field(default_factory=list)
    model_config = {"extra": "forbid"}


class PersonalizedCopyRubricArtifact(BaseModel):
    judgments: list[PersonalizedCopyRubricJudgment] = Field(default_factory=list)
    model_config = {"extra": "forbid"}
