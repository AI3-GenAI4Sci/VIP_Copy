"""Evolution tool-use handlers — distill-skill-deltas (Phase 6 plan 06-01).

One handler implements the rewritten ``distill-skill-deltas`` skill as
true tool-use. Like ``skill_tools.py``, every handler signature is
``def fn(args: dict, state: dict) -> str``; handlers return literal strings
and raise ``ToolValidationError`` on any structural failure.

Roles (ADR-01-PRINCIPLE-01):
    record_delta_change             hand
    finalize_delta_distillation_state deterministic harness finalizer

The handlers are deliberately small. They validate structure, scrub for
private trace text, and write to ``state``. They do not score, judge, or
overwrite live skill files. Live skill writing is out of scope for Phase 6.

Privacy scan (T-06-02):
The handler rejects any payload whose observation, change summary, JSON edits,
or evidence refs contain known private-trace key names. Old runtime
trajectories carried these keys; the workspace evolution surface must not
echo them back into durable delta records.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError

from seers_harness.core.errors import ToolValidationError
from seers_harness.evolution.delta_portfolio import (
    ACTIVE_PORTFOLIO_TARGETS,
    DeltaDistillationArtifact,
    DeltaProposal,
)
from seers_harness.workflow.structured_skill import uses_numeric_section_index


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


def _reject_unstable_section_paths(args: dict, tool_name: str) -> None:
    edits = ((args.get("patch") or {}).get("edits") or []) if isinstance(args, dict) else []
    for index, edit in enumerate(edits):
        if not isinstance(edit, dict):
            continue
        path = str(edit.get("path") or "")
        if uses_numeric_section_index(path):
            raise ToolValidationError(
                message=(
                    "patch.edits must address skill sections by heading, not by "
                    "array index. Use paths like "
                    "/sections/by_heading/方法/body so hand-edited skills and "
                    "concurrent runs do not shift the target section."
                ),
                tool_name=tool_name,
                arg_path=f"patch.edits.{index}.path",
            )


# --------------------------------------------------------------------------- #
# record_delta_change (hand)                                                  #
# --------------------------------------------------------------------------- #


class _RecordDeltaChangeArgs(BaseModel):
    delta_id: str
    target_skill: str
    function_id: str
    operation: str
    observation: str
    change_summary: str
    patch: dict
    evidence_refs: list[dict] = Field(default_factory=list)
    applicable_surface: list[str] = Field(default_factory=list)
    failure_types: list[str] = Field(default_factory=list)
    model_config = {"extra": "forbid"}


def record_delta_change(args: dict, state: dict) -> str:
    """Hand. Append one validated delta proposal to state['delta_changes']."""
    _reject_self_rated_keys(args, "record_delta_change")
    _privacy_scan(args, "record_delta_change")
    _reject_unstable_section_paths(args, "record_delta_change")
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


def canonical_delta_id(delta_change: dict[str, Any]) -> str:
    """Return a stable harness-owned id for one proposed delta.

    Model-emitted ids are local labels inside a single distillation call. The
    durable portfolio id is content-addressed so identical deltas share one
    posterior, while unrelated deltas both named ``D_001`` do not collide.
    """
    signature = {
        "target_skill": delta_change.get("target_skill"),
        "function_id": delta_change.get("function_id"),
        "operation": delta_change.get("operation"),
        "patch": delta_change.get("patch"),
    }
    encoded = json.dumps(signature, ensure_ascii=False, sort_keys=True)
    return "D_" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]


def _canonicalize_delta_changes(changes: list[Any]) -> list[Any]:
    out: list[Any] = []
    for change in changes:
        if not isinstance(change, dict):
            out.append(change)
            continue
        normalized = dict(change)
        normalized["delta_id"] = canonical_delta_id(normalized)
        out.append(normalized)
    return out


# --------------------------------------------------------------------------- #
# deterministic finalization                                                  #
# --------------------------------------------------------------------------- #


def finalize_delta_distillation_state(state: dict[str, Any]) -> dict[str, Any]:
    """Build the final DeltaDistillationArtifact from recorded changes.

    The model never submits the final artifact directly. It records zero or
    more ``record_delta_change`` calls, then stops tool calling; the harness
    deterministically attaches request metadata and validates the final shape.
    """
    payload = state.get("payload") if isinstance(state.get("payload"), dict) else {}
    request_id = str(payload.get("request_id") or payload.get("scenario_id") or "")
    scenario_id = str(payload.get("scenario_id") or payload.get("request_id") or "")
    candidate = {
        "request_id": request_id,
        "scenario_id": scenario_id,
        "deltas": _canonicalize_delta_changes(list(state.get("delta_changes") or [])),
    }
    try:
        artifact = DeltaDistillationArtifact.model_validate(candidate)
    except ValidationError as exc:
        raise ToolValidationError(
            message=f"DeltaDistillationArtifact schema invalid: {exc.errors()[:3]}",
            tool_name="finalize_delta_distillation_state",
        ) from exc
    for index, delta in enumerate(artifact.deltas):
        _validate_target_skill(
            delta.target_skill,
            "finalize_delta_distillation_state",
            arg_path=f"deltas.{index}.target_skill",
        )
    final = artifact.model_dump()
    state["final_artifact"] = final
    return final


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


_JSON_EDIT_VALUE_SCHEMA: dict = {
    "anyOf": [
        {"type": "string"},
        {"type": "number"},
        {"type": "boolean"},
        {"type": "null"},
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["level", "heading", "body"],
            "properties": {
                "level": {"type": "integer"},
                "heading": {"type": "string"},
                "body": {"type": "string"},
            },
        },
    ]
}


_JSON_EDIT_OBJECT: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["op", "path", "value"],
    "properties": {
        "op": {"type": "string", "enum": ["add", "replace", "remove"]},
        "path": {
            "type": "string",
            "description": (
                "JSON Pointer. Existing sections must be addressed by heading, "
                "for example /sections/by_heading/方法/body. Appending a new "
                "section may use /sections/-. Numeric section indexes are not "
                "accepted for model-proposed deltas."
            ),
        },
        "value": dict(_JSON_EDIT_VALUE_SCHEMA),
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
                "observation", "change_summary", "patch", "evidence_refs",
                "applicable_surface", "failure_types",
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
                "change_summary": {"type": "string"},
                "patch": {
                    "type": "object",
                    "description": (
                        "Structured JSON edits against SKILL.json. Address "
                        "existing sections by heading, for example "
                        "/sections/by_heading/方法/body. Do not use numeric "
                        "section indexes such as /sections/4/body."
                    ),
                    "additionalProperties": False,
                    "required": ["edits"],
                    "properties": {
                        "edits": {
                            "type": "array",
                            "items": dict(_JSON_EDIT_OBJECT),
                        },
                    },
                },
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


# --------------------------------------------------------------------------- #
# Registry                                                                    #
# --------------------------------------------------------------------------- #


EVOLUTION_TOOLS_SPEC: dict[str, list[dict]] = {
    "distill-skill-deltas": [
        RECORD_DELTA_CHANGE_SPEC,
    ],
}


EVOLUTION_TOOL_HANDLERS: dict[str, Callable[[dict, dict], str]] = {
    "record_delta_change": record_delta_change,
}


__all__ = [
    "EVOLUTION_TOOLS_SPEC",
    "EVOLUTION_TOOL_HANDLERS",
    "RECORD_DELTA_CHANGE_SPEC",
    "canonical_delta_id",
    "finalize_delta_distillation_state",
    "record_delta_change",
]
