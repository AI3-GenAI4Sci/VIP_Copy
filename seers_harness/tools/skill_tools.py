"""Production tool handlers for the personalized-copy workflow.

ROLE CLASSIFICATION
# submit_user_factors_final hand
# submit_copy_candidates_final hand
# submit_judgments_final hand
(production tool count: 3)
"""

from __future__ import annotations

from typing import Any, Callable

from pydantic import ValidationError

from seers_harness.core.errors import ToolValidationError
from seers_harness.domain.models import (
    CopyGenerationArtifact,
    PersonalizedCopyRubricArtifact,
    PersonalizedCopyRubricJudgment,
    UserPersonalizationArtifact,
)
from seers_harness.tools.skill_tool_specs import (
    SUBMIT_COPY_CANDIDATES_FINAL_SPEC,
    SUBMIT_JUDGMENTS_FINAL_SPEC,
    SUBMIT_USER_FACTORS_FINAL_SPEC,
    TOOLS_SPEC,
)


def submit_user_factors_final(args: dict, state: dict) -> str:
    """Validate and finalize the user personalization artifact."""
    try:
        artifact = UserPersonalizationArtifact.model_validate(args)
    except ValidationError as exc:
        raise ToolValidationError(
            message=f"UserPersonalizationArtifact schema invalid: {exc.errors()[:3]}",
            tool_name="submit_user_factors_final",
        ) from exc
    state["final_artifact"] = artifact.model_dump()
    return "finalized"


def submit_copy_candidates_final(args: dict, state: dict) -> str:
    """Validate and finalize the generated copy artifact."""
    try:
        artifact = CopyGenerationArtifact.model_validate(args)
    except ValidationError as exc:
        raise ToolValidationError(
            message=f"CopyGenerationArtifact schema invalid: {exc.errors()[:3]}",
            tool_name="submit_copy_candidates_final",
        ) from exc
    state["final_artifact"] = artifact.model_dump()
    return "finalized"


def submit_judgments_final(args: dict, state: dict) -> str:
    """Validate and finalize the rubric artifact."""
    _reject_model_submitted_decision(args)
    try:
        artifact = PersonalizedCopyRubricArtifact.model_validate(args)
    except ValidationError as exc:
        raise ToolValidationError(
            message=f"PersonalizedCopyRubricArtifact schema invalid: {exc.errors()[:3]}",
            tool_name="submit_judgments_final",
        ) from exc
    for judgment in artifact.judgments:
        _validate_judgment_candidate_reference(judgment, state)
    state["final_artifact"] = artifact.model_dump()
    return "finalized"


def _reject_model_submitted_decision(args: dict) -> None:
    judgments = args.get("judgments") if isinstance(args, dict) else None
    if not isinstance(judgments, list):
        return
    for index, judgment in enumerate(judgments):
        if isinstance(judgment, dict) and "decision" in judgment:
            raise ToolValidationError(
                message=(
                    "submit_judgments_final input must not include decision; "
                    "the harness derives admit/hold/reject from objective checks "
                    "and total_score"
                ),
                tool_name="submit_judgments_final",
                arg_path=f"judgments.{index}.decision",
            )


def _validate_judgment_candidate_reference(
    judgment: PersonalizedCopyRubricJudgment,
    state: dict[str, Any],
) -> None:
    payload = state.get("payload") or {}
    candidates = payload.get("candidates") if isinstance(payload, dict) else None
    if not candidates:
        return
    text_by_id = {
        candidate.get("candidate_id"): candidate.get("copy_text", "")
        for candidate in candidates
        if isinstance(candidate, dict)
    }
    candidate_text = text_by_id.get(judgment.candidate_id, "")
    if judgment.candidate_id not in text_by_id:
        raise ToolValidationError(
            message=(
                f"candidate_id {judgment.candidate_id!r} not present in "
                "payload['candidates']"
            ),
            tool_name="submit_judgments_final",
            arg_path="candidate_id",
        )
    if judgment.copy_text and judgment.copy_text != candidate_text:
        raise ToolValidationError(
            message="copy_text must exactly match the candidate text for candidate_id",
            tool_name="submit_judgments_final",
            arg_path="copy_text",
        )


TOOL_HANDLERS: dict[str, Callable[[dict, dict], str]] = {
    "submit_user_factors_final": submit_user_factors_final,
    "submit_copy_candidates_final": submit_copy_candidates_final,
    "submit_judgments_final": submit_judgments_final,
}


__all__ = [
    "SUBMIT_COPY_CANDIDATES_FINAL_SPEC",
    "SUBMIT_JUDGMENTS_FINAL_SPEC",
    "SUBMIT_USER_FACTORS_FINAL_SPEC",
    "TOOLS_SPEC",
    "TOOL_HANDLERS",
    "submit_user_factors_final",
    "submit_copy_candidates_final",
    "submit_judgments_final",
]
