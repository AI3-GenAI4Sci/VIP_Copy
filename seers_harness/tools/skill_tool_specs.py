"""Strict tool specifications for personalized-copy workflow tools."""

from __future__ import annotations

from typing import Any

from seers_harness.tools.basic_tools import BASIC_TOOLS_SPEC

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
        *BASIC_TOOLS_SPEC,
    ],
    "personalized-copy-generation": [
        MAINTAIN_COPY_ARTIFACT_SPEC,
        REFLECT_ON_COPY_QUALITY_SPEC,
        *BASIC_TOOLS_SPEC,
    ],
    "personalized-copy-rubric-judge": [
        JUDGE_CANDIDATE_SPEC,
        SUBMIT_JUDGMENTS_FINAL_SPEC,
        *BASIC_TOOLS_SPEC,
    ],
}

