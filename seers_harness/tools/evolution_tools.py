"""Evolution tool-use handlers — distill-skill-deltas (Phase 6 plan 06-01).

Three handlers implement the rewritten ``distill-skill-deltas`` skill as
true tool-use. Like ``skill_tools.py``, every handler signature is
``def fn(args: dict, state: dict) -> str``; handlers return literal strings
and raise ``ToolValidationError`` on any structural failure.

Roles (ADR-01-PRINCIPLE-01):
    record_delta_observation        hand
    record_delta_change             hand
    submit_delta_distillation_final hand

The handlers are deliberately small. They validate structure, scrub for
private trace text, and write to ``state``. They do not score, judge, or
overwrite live skill files. Live skill writing is out of scope for Phase 6.

Privacy scan (T-06-02):
The handler rejects any payload whose observation, proposed change, or
evidence refs contain known private-trace key names. Old runtime
trajectories carried these keys; the workspace evolution surface must not
echo them back into durable delta records.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError

from seers_harness.core.errors import ToolValidationError
from seers_harness.evolution.delta_portfolio import (
    ACTIVE_PORTFOLIO_TARGETS,
    DeltaDistillationArtifact,
    DeltaProposal,
)
from seers_harness.tools.basic_tools import BASIC_TOOL_HANDLERS, BASIC_TOOLS_SPEC


# --------------------------------------------------------------------------- #
# Privacy scan and self-rated metric ban                                      #
# --------------------------------------------------------------------------- #


_PRIVATE_TERMS: tuple[str, ...] = (
    "private_reasoning",
    "user_state",
    "raw_interest_fragment_private",
    "diagnostic_evidence_refs",
    "blocked_evidence_refs",
    "is_clk_c",
)

# Per Principle 10. The five literal names below must never appear as
# tool-arg keys; the spelling is the point of the ban.
_FORBIDDEN_SELF_RATED_KEYS: tuple[str, ...] = (
    "confidence",
    "score",
    "probability",
    "uncertainty",
    "strength",
)
_TARGET_SKILL_DESCRIPTION = (
    "Path to a mutable production skill file. Evolution may only target "
    "personalized-user-mining or personalized-copy-generation."
)
_TARGET_SKILL_ENUM = sorted(ACTIVE_PORTFOLIO_TARGETS)
_TARGET_SKILL_PROPERTY: dict[str, str] = {
    "type": "string",
    "description": _TARGET_SKILL_DESCRIPTION,
    "enum": _TARGET_SKILL_ENUM,
}


def _walk_strings(value: Any):
    """Yield every nested string from a dict/list/scalar tree."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            if isinstance(k, str):
                yield k
            yield from _walk_strings(v)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)


def _privacy_scan(payload: Any, tool_name: str) -> None:
    for s in _walk_strings(payload):
        for term in _PRIVATE_TERMS:
            if term in s:
                raise ToolValidationError(
                    message=(
                        f"private trace term {term!r} present in args; "
                        "evidence must be neutral evidence_refs, not raw private payload"
                    ),
                    tool_name=tool_name,
                    arg_path="args",
                )


def _reject_self_rated_keys(args: dict, tool_name: str) -> None:
    bad = sorted(set(args.keys()) & set(_FORBIDDEN_SELF_RATED_KEYS))
    if bad:
        raise ToolValidationError(
            message=(
                f"args contain forbidden self-rated metric keys {bad}; "
                "posterior belief is computed from trial outcomes, not model self-report"
            ),
            tool_name=tool_name,
            arg_path="args",
        )


def _validate_target_skill(target_skill: str, tool_name: str, arg_path: str = "target_skill") -> None:
    if target_skill not in ACTIVE_PORTFOLIO_TARGETS:
        raise ToolValidationError(
            message=(
                f"target_skill {target_skill!r} must be one of "
                f"{_TARGET_SKILL_ENUM}"
            ),
            tool_name=tool_name,
            arg_path=arg_path,
        )


# --------------------------------------------------------------------------- #
# record_delta_observation (hand)                                             #
# --------------------------------------------------------------------------- #


class _RecordDeltaObservationArgs(BaseModel):
    delta_id: str
    target_skill: str
    observation: str
    evidence_refs: list[dict] = Field(default_factory=list)
    model_config = {"extra": "forbid"}


def record_delta_observation(args: dict, state: dict) -> str:
    """Hand. Append one delta observation seed to state['delta_observations']."""
    _reject_self_rated_keys(args, "record_delta_observation")
    _privacy_scan(args, "record_delta_observation")
    try:
        parsed = _RecordDeltaObservationArgs.model_validate(args)
    except ValidationError as exc:
        raise ToolValidationError(
            message=f"record_delta_observation args invalid: {exc.errors()[:3]}",
            tool_name="record_delta_observation",
        ) from exc
    _validate_target_skill(parsed.target_skill, "record_delta_observation")
    if not parsed.target_skill.strip():
        raise ToolValidationError(
            message="record_delta_observation requires non-empty target_skill",
            tool_name="record_delta_observation",
            arg_path="target_skill",
        )
    if not parsed.observation.strip():
        raise ToolValidationError(
            message="record_delta_observation requires non-empty observation",
            tool_name="record_delta_observation",
            arg_path="observation",
        )
    if not parsed.evidence_refs:
        raise ToolValidationError(
            message="record_delta_observation requires at least one evidence_refs entry",
            tool_name="record_delta_observation",
            arg_path="evidence_refs",
        )
    state.setdefault("delta_observations", []).append(parsed.model_dump())
    return "recorded"


# --------------------------------------------------------------------------- #
# record_delta_change (hand)                                                  #
# --------------------------------------------------------------------------- #


class _RecordDeltaChangeArgs(BaseModel):
    delta_id: str
    target_skill: str
    function_id: str
    operation: str
    observation: str
    proposed_change: str
    evidence_refs: list[dict] = Field(default_factory=list)
    applicable_surface: list[str] = Field(default_factory=list)
    failure_types: list[str] = Field(default_factory=list)
    model_config = {"extra": "forbid"}


def record_delta_change(args: dict, state: dict) -> str:
    """Hand. Append one validated delta proposal to state['delta_changes']."""
    _reject_self_rated_keys(args, "record_delta_change")
    _privacy_scan(args, "record_delta_change")
    try:
        parsed = _RecordDeltaChangeArgs.model_validate(args)
    except ValidationError as exc:
        raise ToolValidationError(
            message=f"record_delta_change args invalid: {exc.errors()[:3]}",
            tool_name="record_delta_change",
        ) from exc
    _validate_target_skill(parsed.target_skill, "record_delta_change")
    if parsed.operation not in ("add", "modify", "delete"):
        raise ToolValidationError(
            message=(
                f"operation {parsed.operation!r} must be 'add', 'modify', or 'delete'"
            ),
            tool_name="record_delta_change",
            arg_path="operation",
        )
    # Validate via the canonical DeltaProposal contract — it enforces
    # extra=forbid on the EvidenceRef shape and non-empty evidence_refs.
    try:
        proposal = DeltaProposal.model_validate(parsed.model_dump())
    except ValidationError as exc:
        raise ToolValidationError(
            message=f"DeltaProposal schema invalid: {exc.errors()[:3]}",
            tool_name="record_delta_change",
        ) from exc
    state.setdefault("delta_changes", []).append(proposal.model_dump())
    return "recorded"


# --------------------------------------------------------------------------- #
# submit_delta_distillation_final (hand)                                      #
# --------------------------------------------------------------------------- #


def submit_delta_distillation_final(args: dict, state: dict) -> str:
    """Hand. Validate the DeltaDistillationArtifact and hand it off.

    Sets ``state['final_artifact']`` on success — the standard final-tool
    convention used by every other ``submit_*_final`` handler in the harness.
    """
    _reject_self_rated_keys(args, "submit_delta_distillation_final")
    _privacy_scan(args, "submit_delta_distillation_final")
    try:
        artifact = DeltaDistillationArtifact.model_validate(args)
    except ValidationError as exc:
        raise ToolValidationError(
            message=f"DeltaDistillationArtifact schema invalid: {exc.errors()[:3]}",
            tool_name="submit_delta_distillation_final",
        ) from exc
    for index, delta in enumerate(artifact.deltas):
        _validate_target_skill(
            delta.target_skill,
            "submit_delta_distillation_final",
            arg_path=f"deltas.{index}.target_skill",
        )
    state["final_artifact"] = artifact.model_dump()
    return "finalized"


# --------------------------------------------------------------------------- #
# Tool specs (DeepSeek /beta strict mode)                                     #
# --------------------------------------------------------------------------- #


_EVIDENCE_REF_OBJECT: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["path", "value"],
    "properties": {
        "path": {"type": "string"},
        "value": {"type": ["string", "number", "boolean", "null"]},
    },
}


RECORD_DELTA_OBSERVATION_SPEC: dict = {
    "type": "function",
    "function": {
        "name": "record_delta_observation",
        "description": (
            "Record one trajectory observation that motivates a possible delta. "
            "Cite at least one evidence ref. Do not include private trace text "
            "or self-rated metric fields."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "delta_id", "target_skill", "observation", "evidence_refs",
            ],
            "properties": {
                "delta_id": {"type": "string"},
                "target_skill": dict(_TARGET_SKILL_PROPERTY),
                "observation": {"type": "string"},
                "evidence_refs": {
                    "type": "array",
                    "items": dict(_EVIDENCE_REF_OBJECT),
                },
            },
        },
    },
}


RECORD_DELTA_CHANGE_SPEC: dict = {
    "type": "function",
    "function": {
        "name": "record_delta_change",
        "description": (
            "Record one proposed change derived from observations. Keep changes "
            "small and reusable. operation is 'add', 'modify', or 'delete' "
            "for a named skill function. "
            "Cite at least one evidence ref. Do not include self-rated metric "
            "fields — posterior belief is computed from trial outcomes."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "delta_id", "target_skill", "function_id", "operation",
                "observation", "proposed_change",
                "evidence_refs", "applicable_surface", "failure_types",
            ],
            "properties": {
                "delta_id": {"type": "string"},
                "target_skill": dict(_TARGET_SKILL_PROPERTY),
                "function_id": {"type": "string"},
                "operation": {
                    "type": "string",
                    "enum": ["add", "modify", "delete"],
                },
                "observation": {"type": "string"},
                "proposed_change": {"type": "string"},
                "evidence_refs": {
                    "type": "array",
                    "items": dict(_EVIDENCE_REF_OBJECT),
                },
                "applicable_surface": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "failure_types": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        },
    },
}


SUBMIT_DELTA_DISTILLATION_FINAL_SPEC: dict = {
    "type": "function",
    "function": {
        "name": "submit_delta_distillation_final",
        "description": (
            "Submit the final DeltaDistillationArtifact. Run terminates after "
            "this call. Each delta must already pass record_delta_change."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["request_id", "scenario_id", "deltas"],
            "properties": {
                "request_id": {"type": "string"},
                "scenario_id": {"type": "string"},
                "deltas": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "delta_id", "target_skill", "function_id", "operation",
                            "observation", "proposed_change",
                            "evidence_refs", "applicable_surface", "failure_types",
                        ],
                        "properties": {
                            "delta_id": {"type": "string"},
                            "target_skill": dict(_TARGET_SKILL_PROPERTY),
                            "function_id": {"type": "string"},
                            "operation": {
                                "type": "string",
                                "enum": ["add", "modify", "delete"],
                            },
                            "observation": {"type": "string"},
                            "proposed_change": {"type": "string"},
                            "evidence_refs": {
                                "type": "array",
                                "items": dict(_EVIDENCE_REF_OBJECT),
                            },
                            "applicable_surface": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "failure_types": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
    },
}


# --------------------------------------------------------------------------- #
# Registry                                                                    #
# --------------------------------------------------------------------------- #


EVOLUTION_TOOLS_SPEC: dict[str, list[dict]] = {
    "distill-skill-deltas": [
        RECORD_DELTA_OBSERVATION_SPEC,
        RECORD_DELTA_CHANGE_SPEC,
        SUBMIT_DELTA_DISTILLATION_FINAL_SPEC,
        *BASIC_TOOLS_SPEC,
    ],
}


EVOLUTION_TOOL_HANDLERS: dict[str, Callable[[dict, dict], str]] = {
    "record_delta_observation": record_delta_observation,
    "record_delta_change": record_delta_change,
    "submit_delta_distillation_final": submit_delta_distillation_final,
    **BASIC_TOOL_HANDLERS,
}


__all__ = [
    "EVOLUTION_TOOLS_SPEC",
    "EVOLUTION_TOOL_HANDLERS",
    "RECORD_DELTA_OBSERVATION_SPEC",
    "RECORD_DELTA_CHANGE_SPEC",
    "SUBMIT_DELTA_DISTILLATION_FINAL_SPEC",
    "record_delta_observation",
    "record_delta_change",
    "submit_delta_distillation_final",
]
