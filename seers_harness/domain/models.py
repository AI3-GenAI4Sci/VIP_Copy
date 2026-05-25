"""C17 domain schema — pydantic v2 contracts for factors, candidates, rubric judgments.

Every BaseModel sets ``model_config = {"extra": "ignore"}`` so legacy c14/c15
JSON on disk decodes silently. Field declaration order is load-bearing for
critique-before-verdict tools (RESEARCH Open Q2 RESOLVED — pydantic
``model_json_schema()`` preserves declaration order in ``properties`` dict;
DeepSeek tool spec emits arguments in that order).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class EvidenceRef(BaseModel):
    path: str
    value: str | int | float | bool | None = None
    model_config = {"extra": "ignore"}


FactorDirection = Literal["user_to_need", "item_to_need", "cross"]


class PersonalizationFactor(BaseModel):
    factor_id: str | None = None
    user_side_signal: str | None = None
    direction: FactorDirection | None = None
    transferable_disposition: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    bridge: str | None = None
    covers_product_ids: list[str] = Field(default_factory=list)

    model_config = {"extra": "ignore"}

    @field_validator("evidence_refs", mode="before")
    @classmethod
    def _coerce_evidence_refs(cls, value):
        if isinstance(value, list):
            out: list[object] = []
            for item in value:
                if isinstance(item, str):
                    out.append({"path": item, "value": None})
                else:
                    out.append(item)
            return out
        return value


class BridgeLogic(BaseModel):
    product_anchor: str = ""
    relation_anchor: str = ""
    model_config = {"extra": "ignore"}


class CopyCandidate(BaseModel):
    candidate_id: str | None = None
    product_id: str | None = None
    target_product_id: str | None = None
    group_key: str = ""
    text: str
    source_factor_id: str = ""
    bridge_logic: BridgeLogic | None = None
    considered_drafts: list[str] = Field(default_factory=list)
    chosen_draft_index: int | None = None
    used_copyable_hooks: list[str] = Field(default_factory=list)
    intended_effect: str = ""

    model_config = {"extra": "ignore"}

    @model_validator(mode="after")
    def _hydrate(self):
        if not self.product_id and self.target_product_id:
            object.__setattr__(self, "product_id", self.target_product_id)
        if not self.product_id:
            raise ValueError("CopyCandidate requires product_id or target_product_id")
        if not self.source_factor_id:
            raise ValueError("CopyCandidate requires source_factor_id")
        return self


class PerAxisVerdict(BaseModel):
    axis_id: str
    verbatim_candidate_quote: str = ""
    bridge_to_anchor: str = ""
    templated_flag: Literal[
        "ok", "empty", "anchor_echo", "source_path_missing", "quote_too_short"
    ] = "ok"
    verdict: Literal["pass", "fail"] = "pass"
    model_config = {"extra": "ignore"}


RubricDecision = Literal["admit", "hold", "reject"]


class PersonalizedCopyRubricJudgment(BaseModel):
    candidate_id: str
    candidate_index: int | None = None
    product_id: str = ""
    copy_text: str = ""
    factor_id: str = ""
    per_axis: list[PerAxisVerdict] = Field(default_factory=list)
    floor_violations: list[str] = Field(default_factory=list)
    primary_strength: str = ""
    primary_risk: str = ""
    rationale: str = ""
    decision: RubricDecision = "hold"
    model_config = {"extra": "ignore"}


class FactorDiscoveryArtifact(BaseModel):
    factors: list[PersonalizationFactor] = Field(default_factory=list)
    model_config = {"extra": "ignore"}


class CopyGenerationArtifact(BaseModel):
    candidates: list[CopyCandidate] = Field(default_factory=list)
    model_config = {"extra": "ignore"}


class PersonalizedCopyRubricArtifact(BaseModel):
    judgments: list[PersonalizedCopyRubricJudgment] = Field(default_factory=list)
    model_config = {"extra": "ignore"}
