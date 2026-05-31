"""Tool handlers for the split personalized-copy workflow.

ROLE CLASSIFICATION
# maintain_user_factors_artifact hand
# maintain_copy_artifact hand
# judge_candidate hand
# submit_judgments_final hand
# reflect_on_user_factor_coverage mirror
# reflect_on_copy_quality mirror
(eye count: 0)
"""

from __future__ import annotations

import json
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field, ValidationError

from seers_harness.core.errors import ToolValidationError
from seers_harness.domain.models import (
    CopyCandidate,
    CopyGenerationArtifact,
    PersonalizedCopyRubricArtifact,
    PersonalizedCopyRubricJudgment,
    UserPersonalizationArtifact,
    UserPersonalizationFactor,
)


ArtifactAction = Literal[
    "read",
    "upsert_many",
    "delete_many",
    "validate",
    "save",
]


_REFLECT_USER_FACTOR_COVERAGE = """\
请在本轮先回答这些问题，再决定是否更新 user factor artifact：

1. 用户因子是否覆盖了主要显性需求、潜在诉求、场景痛点和决策顾虑？
2. 是否有因子只是画像标签或行为字段改名，而没有形成可复用购买动机？
3. 是否有多个因子会导向同一个表达 hook，需要合并？
"""


_REFLECT_COPY_QUALITY = """\
请在本轮先回答这些问题，再决定是否更新 copy artifact：

1. 每条文案是否绑定了一个明确的 user factor 和商品承接点？
2. 文案是否通过痛点、场景、体验结果或价值感表达商品，而不是重复商品名？
3. 是否存在动态数字、私有轨迹或商品事实承接不足的表达？
"""


class _MaintainUserFactorsArtifactArgs(BaseModel):
    action: ArtifactAction
    user_factors: list[UserPersonalizationFactor] = Field(default_factory=list)
    user_factor_ids: list[str] = Field(default_factory=list)
    model_config = {"extra": "forbid"}


class _MaintainCopyArtifactArgs(BaseModel):
    action: ArtifactAction
    candidates: list[CopyCandidate] = Field(default_factory=list)
    candidate_ids: list[str] = Field(default_factory=list)
    product_id: str = ""
    model_config = {"extra": "forbid"}


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _dump_user_factors(
    user_factors: list[UserPersonalizationFactor],
) -> list[dict[str, Any]]:
    return [factor.model_dump() for factor in user_factors]


def _dump_candidates(candidates: list[CopyCandidate]) -> list[dict[str, Any]]:
    return [candidate.model_dump() for candidate in candidates]


def _validate_user_factor_state(state: dict) -> list[dict[str, Any]]:
    try:
        artifact = UserPersonalizationArtifact.model_validate(
            {"user_factors": state.get("user_factors", [])}
        )
    except ValidationError as exc:
        raise ToolValidationError(
            message=f"user factor artifact state invalid: {exc.errors()[:3]}",
            tool_name="maintain_user_factors_artifact",
        ) from exc
    return artifact.model_dump()["user_factors"]


def _validate_copy_state(state: dict) -> list[dict[str, Any]]:
    try:
        artifact = CopyGenerationArtifact.model_validate(
            {"candidates": state.get("candidates", [])}
        )
    except ValidationError as exc:
        raise ToolValidationError(
            message=f"copy artifact state invalid: {exc.errors()[:3]}",
            tool_name="maintain_copy_artifact",
        ) from exc
    return artifact.model_dump()["candidates"]


def maintain_user_factors_artifact(args: dict, state: dict) -> str:
    """Maintain user-side personalization factor artifact state."""
    try:
        parsed = _MaintainUserFactorsArtifactArgs.model_validate(args)
    except ValidationError as exc:
        raise ToolValidationError(
            message=f"maintain_user_factors_artifact args invalid: {exc.errors()[:3]}",
            tool_name="maintain_user_factors_artifact",
        ) from exc

    if parsed.action == "read":
        return _json({"user_factors": _validate_user_factor_state(state)})
    if parsed.action == "validate":
        _validate_user_factor_state(state)
        return "valid"
    if parsed.action == "save":
        user_factors = _validate_user_factor_state(state)
        state["final_artifact"] = {"user_factors": user_factors}
        return "saved"

    user_factors = _validate_user_factor_state(state)
    if parsed.action == "upsert_many":
        by_id = {factor["user_factor_id"]: factor for factor in user_factors}
        for factor in _dump_user_factors(parsed.user_factors):
            by_id[factor["user_factor_id"]] = factor
        state["user_factors"] = list(by_id.values())
        return "updated"
    if parsed.action == "delete_many":
        remove = set(parsed.user_factor_ids)
        state["user_factors"] = [
            f for f in user_factors if f["user_factor_id"] not in remove
        ]
        return "updated"
    raise AssertionError(f"unhandled action: {parsed.action}")


def maintain_copy_artifact(args: dict, state: dict) -> str:
    """Maintain copy candidate artifact state."""
    try:
        parsed = _MaintainCopyArtifactArgs.model_validate(args)
    except ValidationError as exc:
        raise ToolValidationError(
            message=f"maintain_copy_artifact args invalid: {exc.errors()[:3]}",
            tool_name="maintain_copy_artifact",
        ) from exc

    if parsed.action == "read":
        return _json({"candidates": _validate_copy_state(state)})
    if parsed.action == "validate":
        _validate_copy_state(state)
        return "valid"
    if parsed.action == "save":
        candidates = _validate_copy_state(state)
        dumped = {"candidates": candidates}
        state["final_artifact"] = dumped
        state["copies_artifact"] = dumped
        return "saved"

    candidates = _validate_copy_state(state)
    if parsed.action == "upsert_many":
        by_id = {candidate["candidate_id"]: candidate for candidate in candidates}
        for candidate in _dump_candidates(parsed.candidates):
            by_id[candidate["candidate_id"]] = candidate
        state["candidates"] = list(by_id.values())
        return "updated"
    if parsed.action == "delete_many":
        remove = set(parsed.candidate_ids)
        state["candidates"] = [
            c for c in candidates if c["candidate_id"] not in remove
        ]
        return "updated"
    raise AssertionError(f"unhandled action: {parsed.action}")


def reflect_on_user_factor_coverage(args: dict, state: dict) -> str:
    """Return user-factor coverage reflection questions."""
    return _REFLECT_USER_FACTOR_COVERAGE


def reflect_on_copy_quality(args: dict, state: dict) -> str:
    """Return copy quality reflection questions."""
    return _REFLECT_COPY_QUALITY


def judge_candidate(args: dict, state: dict) -> str:
    """Validate and append one scored rubric judgment."""
    try:
        judgment = PersonalizedCopyRubricJudgment.model_validate(args)
    except ValidationError as exc:
        first_error = exc.errors()[0] if exc.errors() else {}
        arg_path = "total_score" if first_error.get("type") == "value_error" else ""
        raise ToolValidationError(
            message=f"judgment schema invalid: {exc.errors()[:3]}",
            tool_name="judge_candidate",
            arg_path=arg_path,
        ) from exc
    candidates = (state.get("copies_artifact") or {}).get("candidates") or []
    text_by_id = {c.get("candidate_id"): c.get("text", "") for c in candidates}
    cand_text = text_by_id.get(judgment.candidate_id, "")
    if judgment.candidate_id not in text_by_id:
        raise ToolValidationError(
            message=f"candidate_id {judgment.candidate_id!r} not present in state['copies_artifact']['candidates']",
            tool_name="judge_candidate",
            arg_path="candidate_id",
        )
    if judgment.copy_text and judgment.copy_text != cand_text:
        raise ToolValidationError(
            message="copy_text must exactly match the candidate text for candidate_id",
            tool_name="judge_candidate",
            arg_path="copy_text",
        )
    state.setdefault("judgments", []).append(judgment.model_dump())
    return "recorded"


def submit_judgments_final(args: dict, state: dict) -> str:
    """Validate and finalize the rubric artifact."""
    try:
        artifact = PersonalizedCopyRubricArtifact.model_validate(args)
    except ValidationError as exc:
        raise ToolValidationError(
            message=f"PersonalizedCopyRubricArtifact schema invalid: {exc.errors()[:3]}",
            tool_name="submit_judgments_final",
        ) from exc
    state["final_artifact"] = artifact.model_dump()
    return "finalized"


_ARTIFACT_ACTION_SCHEMA: dict[str, Any] = {
    "type": "string",
    "enum": [
        "read",
        "upsert_many",
        "delete_many",
        "validate",
        "save",
    ],
}

_EVIDENCE_REF_ITEM: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["path", "value"],
    "properties": {
        "path": {"type": "string"},
        "value": {"type": ["string", "number", "boolean", "null"]},
    },
}

_USER_FACTOR_ITEM_REQUIRED = [
    "user_factor_id",
    "signal_basis",
    "need_or_pain",
    "scene_trigger",
    "buying_heuristic",
    "expression_hooks",
    "evidence_refs",
]
_USER_FACTOR_ITEM_PROPERTIES: dict[str, Any] = {
    "user_factor_id": {"type": "string"},
    "signal_basis": {"type": "string"},
    "need_or_pain": {"type": "string"},
    "scene_trigger": {"type": "string"},
    "buying_heuristic": {"type": "string"},
    "expression_hooks": {"type": "array", "items": {"type": "string"}},
    "evidence_refs": {"type": "array", "items": dict(_EVIDENCE_REF_ITEM)},
}

_CANDIDATE_ITEM_REQUIRED = [
    "candidate_id",
    "product_id",
    "source_user_factor_id",
    "text",
    "commercial_angle",
    "product_binding",
    "fact_binding",
]
_CANDIDATE_ITEM_PROPERTIES: dict[str, Any] = {
    "candidate_id": {"type": "string"},
    "product_id": {"type": "string"},
    "source_user_factor_id": {"type": "string"},
    "text": {"type": "string"},
    "commercial_angle": {"type": "string"},
    "product_binding": {"type": "string"},
    "fact_binding": {"type": "string"},
}


MAINTAIN_USER_FACTORS_ARTIFACT_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "maintain_user_factors_artifact",
        "description": "Maintain user personalization factor artifact state.",
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["action", "user_factors", "user_factor_ids"],
            "properties": {
                "action": dict(_ARTIFACT_ACTION_SCHEMA),
                "user_factors": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": list(_USER_FACTOR_ITEM_REQUIRED),
                        "properties": dict(_USER_FACTOR_ITEM_PROPERTIES),
                    },
                },
                "user_factor_ids": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}


REFLECT_ON_USER_FACTOR_COVERAGE_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "reflect_on_user_factor_coverage",
        "description": "Return user-factor coverage reflection questions.",
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": [],
            "properties": {},
        },
    },
}


MAINTAIN_COPY_ARTIFACT_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "maintain_copy_artifact",
        "description": "Maintain copy candidate artifact state.",
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["action", "candidates", "candidate_ids", "product_id"],
            "properties": {
                "action": dict(_ARTIFACT_ACTION_SCHEMA),
                "candidates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": list(_CANDIDATE_ITEM_REQUIRED),
                        "properties": dict(_CANDIDATE_ITEM_PROPERTIES),
                    },
                },
                "candidate_ids": {"type": "array", "items": {"type": "string"}},
                "product_id": {"type": "string"},
            },
        },
    },
}


REFLECT_ON_COPY_QUALITY_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "reflect_on_copy_quality",
        "description": "Return copy quality reflection questions.",
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": [],
            "properties": {},
        },
    },
}


_AXIS_SCORE_REQUIRED = [
    "axis_id",
    "score",
    "diagnostic",
]
_AXIS_SCORE_PROPERTIES: dict[str, Any] = {
    "axis_id": {
        "type": "string",
        "enum": [
            "user_factor_grounding",
            "product_binding",
            "personalized_conversion",
            "commercial_sharpness",
            "expression_boundary",
        ],
    },
    "score": {"type": "integer", "minimum": 0, "maximum": 5},
    "diagnostic": {"type": "string"},
}

_JUDGMENT_REQUIRED = [
    "candidate_id",
    "candidate_index",
    "product_id",
    "copy_text",
    "user_factor_id",
    "axis_scores",
    "total_score",
    "main_strength",
    "main_weakness",
    "failure_tags",
    "decision",
]
_JUDGMENT_PROPERTIES: dict[str, Any] = {
    "candidate_id": {"type": "string"},
    "candidate_index": {"type": "integer"},
    "product_id": {"type": "string"},
    "copy_text": {"type": "string"},
    "user_factor_id": {"type": "string"},
    "axis_scores": {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": list(_AXIS_SCORE_REQUIRED),
            "properties": dict(_AXIS_SCORE_PROPERTIES),
        },
    },
    "total_score": {"type": "integer", "minimum": 0, "maximum": 25},
    "main_strength": {"type": "string"},
    "main_weakness": {"type": "string"},
    "failure_tags": {"type": "array", "items": {"type": "string"}},
    "decision": {"type": "string", "enum": ["admit", "hold", "reject"]},
}


JUDGE_CANDIDATE_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "judge_candidate",
        "description": "Append one rubric judgment for one candidate.",
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": list(_JUDGMENT_REQUIRED),
            "properties": dict(_JUDGMENT_PROPERTIES),
        },
    },
}


SUBMIT_JUDGMENTS_FINAL_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "submit_judgments_final",
        "description": "Submit the final PersonalizedCopyRubricArtifact.",
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["judgments"],
            "properties": {
                "judgments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": list(_JUDGMENT_REQUIRED),
                        "properties": dict(_JUDGMENT_PROPERTIES),
                    },
                },
            },
        },
    },
}


TOOLS_SPEC: dict[str, list[dict[str, Any]]] = {
    "personalized-user-mining": [
        MAINTAIN_USER_FACTORS_ARTIFACT_SPEC,
        REFLECT_ON_USER_FACTOR_COVERAGE_SPEC,
    ],
    "personalized-copy-generation": [
        MAINTAIN_COPY_ARTIFACT_SPEC,
        REFLECT_ON_COPY_QUALITY_SPEC,
    ],
    "personalized-copy-rubric-judge": [
        JUDGE_CANDIDATE_SPEC,
        SUBMIT_JUDGMENTS_FINAL_SPEC,
    ],
}


TOOL_HANDLERS: dict[str, Callable[[dict, dict], str]] = {
    "maintain_user_factors_artifact": maintain_user_factors_artifact,
    "maintain_copy_artifact": maintain_copy_artifact,
    "judge_candidate": judge_candidate,
    "submit_judgments_final": submit_judgments_final,
    "reflect_on_user_factor_coverage": reflect_on_user_factor_coverage,
    "reflect_on_copy_quality": reflect_on_copy_quality,
}
