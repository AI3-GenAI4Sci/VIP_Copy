"""Tool handlers for the split personalized-copy workflow.

ROLE CLASSIFICATION
# maintain_user_factors_artifact hand
# maintain_copy_artifact hand
# judge_candidate hand
# submit_judgments_final hand
# reflect_on_user_factor_coverage mirror
# reflect_on_copy_quality mirror
# bash hand
# read eye
# glob eye
# grep eye
(eye count: 3 — basic workspace projection tools)
"""

from __future__ import annotations

from typing import Any, Callable, Literal

from pydantic import BaseModel, Field, ValidationError

from seers_harness.core.errors import ToolValidationError
from seers_harness.domain.models import (
    CopyCandidate,
    PersonalizedCopyRubricJudgment,
    UserPersonalizationFactor,
)
from seers_harness.tools.artifact_state import (
    append_judgment,
    delete_candidates,
    delete_user_factors,
    finalize_copy_artifact,
    finalize_judgments_artifact,
    finalize_user_factors_artifact,
    json_response,
    read_copy_artifact,
    read_user_factors_artifact,
    upsert_candidates,
    upsert_user_factors,
    validate_copy_state,
    validate_user_factor_state,
)
from seers_harness.tools.basic_tools import BASIC_TOOL_HANDLERS, BASIC_TOOLS_SPEC
from seers_harness.tools.skill_tool_specs import (
    JUDGE_CANDIDATE_SPEC,
    MAINTAIN_COPY_ARTIFACT_SPEC,
    MAINTAIN_USER_FACTORS_ARTIFACT_SPEC,
    REFLECT_ON_COPY_QUALITY_SPEC,
    REFLECT_ON_USER_FACTOR_COVERAGE_SPEC,
    SUBMIT_JUDGMENTS_FINAL_SPEC,
    TOOLS_SPEC,
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
        return json_response(read_user_factors_artifact(state))
    if parsed.action == "validate":
        validate_user_factor_state(state)
        return "valid"
    if parsed.action == "save":
        finalize_user_factors_artifact(state)
        return "saved"

    if parsed.action == "upsert_many":
        upsert_user_factors(state, parsed.user_factors)
        return "updated"
    if parsed.action == "delete_many":
        delete_user_factors(state, parsed.user_factor_ids)
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
        return json_response(read_copy_artifact(state))
    if parsed.action == "validate":
        validate_copy_state(state)
        return "valid"
    if parsed.action == "save":
        finalize_copy_artifact(state)
        return "saved"

    if parsed.action == "upsert_many":
        upsert_candidates(state, parsed.candidates)
        return "updated"
    if parsed.action == "delete_many":
        delete_candidates(state, parsed.candidate_ids)
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
    append_judgment(state, args)
    return "recorded"


def submit_judgments_final(args: dict, state: dict) -> str:
    """Validate and finalize the rubric artifact."""
    finalize_judgments_artifact(args, state)
    return "finalized"


TOOL_HANDLERS: dict[str, Callable[[dict, dict], str]] = {
    "maintain_user_factors_artifact": maintain_user_factors_artifact,
    "maintain_copy_artifact": maintain_copy_artifact,
    "judge_candidate": judge_candidate,
    "submit_judgments_final": submit_judgments_final,
    "reflect_on_user_factor_coverage": reflect_on_user_factor_coverage,
    "reflect_on_copy_quality": reflect_on_copy_quality,
    **BASIC_TOOL_HANDLERS,
}
