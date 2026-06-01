"""Artifact state transitions behind personalized-copy tool handlers."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from seers_harness.core.errors import ToolValidationError
from seers_harness.domain.models import (
    CopyCandidate,
    CopyGenerationArtifact,
    PersonalizedCopyRubricArtifact,
    PersonalizedCopyRubricJudgment,
    UserPersonalizationArtifact,
    UserPersonalizationFactor,
)


def json_response(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def read_user_factors_artifact(state: dict) -> dict[str, Any]:
    return {"user_factors": validate_user_factor_state(state)}


def upsert_user_factors(
    state: dict,
    user_factors: list[UserPersonalizationFactor | dict[str, Any]],
) -> None:
    current = validate_user_factor_state(state)
    by_id = {factor["user_factor_id"]: factor for factor in current}
    for factor in _dump_user_factors(user_factors):
        by_id[factor["user_factor_id"]] = factor
    state["user_factors"] = list(by_id.values())


def delete_user_factors(state: dict, user_factor_ids: list[str]) -> None:
    remove = set(user_factor_ids)
    state["user_factors"] = [
        factor
        for factor in validate_user_factor_state(state)
        if factor["user_factor_id"] not in remove
    ]


def finalize_user_factors_artifact(state: dict) -> dict[str, Any]:
    artifact = read_user_factors_artifact(state)
    state["final_artifact"] = artifact
    return artifact


def read_copy_artifact(state: dict) -> dict[str, Any]:
    return {"candidates": validate_copy_state(state)}


def upsert_candidates(
    state: dict,
    candidates: list[CopyCandidate | dict[str, Any]],
) -> None:
    current = validate_copy_state(state)
    by_id = {candidate["candidate_id"]: candidate for candidate in current}
    for candidate in _dump_candidates(candidates):
        by_id[candidate["candidate_id"]] = candidate
    state["candidates"] = list(by_id.values())


def delete_candidates(state: dict, candidate_ids: list[str]) -> None:
    remove = set(candidate_ids)
    state["candidates"] = [
        candidate
        for candidate in validate_copy_state(state)
        if candidate["candidate_id"] not in remove
    ]


def finalize_copy_artifact(state: dict) -> dict[str, Any]:
    artifact = read_copy_artifact(state)
    state["final_artifact"] = artifact
    state["copies_artifact"] = artifact
    return artifact


def append_judgment(
    state: dict,
    judgment: PersonalizedCopyRubricJudgment | dict[str, Any],
) -> None:
    parsed = _validate_judgment(judgment)
    candidates = (state.get("copies_artifact") or {}).get("candidates") or []
    text_by_id = {candidate.get("candidate_id"): candidate.get("text", "") for candidate in candidates}
    cand_text = text_by_id.get(parsed.candidate_id, "")
    if parsed.candidate_id not in text_by_id:
        raise ToolValidationError(
            message=f"candidate_id {parsed.candidate_id!r} not present in state['copies_artifact']['candidates']",
            tool_name="judge_candidate",
            arg_path="candidate_id",
        )
    if parsed.copy_text and parsed.copy_text != cand_text:
        raise ToolValidationError(
            message="copy_text must exactly match the candidate text for candidate_id",
            tool_name="judge_candidate",
            arg_path="copy_text",
        )
    state.setdefault("judgments", []).append(parsed.model_dump())


def finalize_judgments_artifact(args: dict[str, Any], state: dict) -> dict[str, Any]:
    try:
        artifact = PersonalizedCopyRubricArtifact.model_validate(args)
    except ValidationError as exc:
        raise ToolValidationError(
            message=f"PersonalizedCopyRubricArtifact schema invalid: {exc.errors()[:3]}",
            tool_name="submit_judgments_final",
        ) from exc
    dumped = artifact.model_dump()
    state["final_artifact"] = dumped
    return dumped


def validate_user_factor_state(state: dict) -> list[dict[str, Any]]:
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


def validate_copy_state(state: dict) -> list[dict[str, Any]]:
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


def _dump_user_factors(
    user_factors: list[UserPersonalizationFactor | dict[str, Any]],
) -> list[dict[str, Any]]:
    dumped: list[dict[str, Any]] = []
    for factor in user_factors:
        if isinstance(factor, UserPersonalizationFactor):
            dumped.append(factor.model_dump())
        else:
            dumped.append(UserPersonalizationFactor.model_validate(factor).model_dump())
    return dumped


def _dump_candidates(
    candidates: list[CopyCandidate | dict[str, Any]],
) -> list[dict[str, Any]]:
    dumped: list[dict[str, Any]] = []
    for candidate in candidates:
        if isinstance(candidate, CopyCandidate):
            dumped.append(candidate.model_dump())
        else:
            dumped.append(CopyCandidate.model_validate(candidate).model_dump())
    return dumped


def _validate_judgment(
    judgment: PersonalizedCopyRubricJudgment | dict[str, Any],
) -> PersonalizedCopyRubricJudgment:
    if isinstance(judgment, PersonalizedCopyRubricJudgment):
        return judgment
    try:
        return PersonalizedCopyRubricJudgment.model_validate(judgment)
    except ValidationError as exc:
        first_error = exc.errors()[0] if exc.errors() else {}
        arg_path = "total_score" if first_error.get("type") == "value_error" else ""
        raise ToolValidationError(
            message=f"judgment schema invalid: {exc.errors()[:3]}",
            tool_name="judge_candidate",
            arg_path=arg_path,
        ) from exc
