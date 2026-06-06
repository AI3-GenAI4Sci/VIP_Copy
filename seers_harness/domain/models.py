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
    # Historical artifacts may contain evidence_refs, but production user
    # mining no longer emits them because downstream copy generation does not
    # consume audit evidence as a business signal.
    evidence_refs: list[EvidenceRef] = Field(default_factory=list, exclude=True)
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
    "motivation_fit",
    "product_value",
    "conversion_pull",
    "copycraft",
    "distinctiveness",
    "scene_texture",
    "benefit_clarity",
]

RUBRIC_AXIS_IDS: tuple[str, ...] = (
    "motivation_fit",
    "product_value",
    "conversion_pull",
    "copycraft",
    "distinctiveness",
    "scene_texture",
    "benefit_clarity",
)


class RubricAxisScore(BaseModel):
    axis_id: RubricAxisId
    score: int = Field(ge=0, le=5)
    diagnostic: str
    model_config = {"extra": "forbid"}


ObjectiveCheckId = Literal[
    "no_private_trace",
    "no_specific_numeric_claim",
    "no_product_name_echo",
    "product_value_visible",
    "publishable_copy",
]

OBJECTIVE_CHECK_IDS: tuple[str, ...] = (
    "no_private_trace",
    "no_specific_numeric_claim",
    "no_product_name_echo",
    "product_value_visible",
    "publishable_copy",
)


class ObjectiveCheck(BaseModel):
    check_id: ObjectiveCheckId
    passed: bool
    model_config = {"extra": "forbid"}


RubricDecision = Literal["admit", "hold", "reject"]


class PersonalizedCopyRubricJudgment(BaseModel):
    candidate_id: str
    candidate_index: int | None = None
    product_id: str = ""
    copy_text: str = ""
    user_factor_id: str = ""
    objective_checks: list[ObjectiveCheck] = Field(default_factory=list)
    axis_scores: list[RubricAxisScore] = Field(default_factory=list)
    total_score: int = Field(default=0, ge=0, le=35)
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
        if axis_ids and set(axis_ids) != set(RUBRIC_AXIS_IDS):
            raise ValueError("axis_scores must contain all rubric axis ids")
        return value

    @field_validator("objective_checks")
    @classmethod
    def _require_distinct_check_ids(
        cls,
        value: list[ObjectiveCheck],
    ) -> list[ObjectiveCheck]:
        check_ids = [check.check_id for check in value]
        if len(check_ids) != len(set(check_ids)):
            raise ValueError("objective_checks check_id values must be distinct")
        if set(check_ids) != set(OBJECTIVE_CHECK_IDS):
            raise ValueError("objective_checks must contain all objective check ids")
        return value

    @model_validator(mode="after")
    def _check_total_score(self):
        if any(not check.passed for check in self.objective_checks):
            if self.total_score != 0:
                raise ValueError(
                    "total_score must be 0 when any objective check fails"
                )
            if self.axis_scores:
                raise ValueError(
                    "axis_scores must be empty when any objective check fails"
                )
            self.decision = "reject"
            return self
        if not self.axis_scores:
            raise ValueError(
                "axis_scores must contain all rubric axis ids when objective checks pass"
            )
        expected = sum(axis.score for axis in self.axis_scores)
        if self.total_score != expected:
            raise ValueError(
                f"total_score must equal sum(axis_scores.score): {expected}"
            )
        expected_decision = self._expected_decision()
        if self.decision != expected_decision:
            self.decision = expected_decision
        return self

    def _expected_decision(self) -> RubricDecision:
        scores = [axis.score for axis in self.axis_scores]
        if self.total_score < 21 or any(score == 0 for score in scores):
            return "reject"
        if self.total_score >= 29 and not any(score <= 2 for score in scores):
            return "admit"
        return "hold"


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
