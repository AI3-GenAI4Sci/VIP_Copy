"""Strict final-submit tool specifications for the production workflow."""

from __future__ import annotations

from typing import Any


_USER_FACTOR_ITEM_REQUIRED = [
    "user_factor_id",
    "signal_basis",
    "need_or_pain",
    "scene_trigger",
    "buying_heuristic",
    "expression_hooks",
]
_USER_FACTOR_ITEM_PROPERTIES: dict[str, Any] = {
    "user_factor_id": {"type": "string"},
    "signal_basis": {"type": "string"},
    "need_or_pain": {"type": "string"},
    "scene_trigger": {"type": "string"},
    "buying_heuristic": {"type": "string"},
    "expression_hooks": {"type": "array", "items": {"type": "string"}},
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


SUBMIT_USER_FACTORS_FINAL_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "submit_user_factors_final",
        "description": (
            "Submit the final UserPersonalizationArtifact. This is the only "
            "tool available to personalized-user-mining; the harness performs "
            "schema validation and finalization deterministically."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["user_factors"],
            "properties": {
                "user_factors": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": list(_USER_FACTOR_ITEM_REQUIRED),
                        "properties": dict(_USER_FACTOR_ITEM_PROPERTIES),
                    },
                },
            },
        },
    },
}


SUBMIT_COPY_CANDIDATES_FINAL_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "submit_copy_candidates_final",
        "description": (
            "Submit the final CopyGenerationArtifact. This is the only tool "
            "available to personalized-copy-generation; the harness performs "
            "schema validation and finalization deterministically."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["candidates"],
            "properties": {
                "candidates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": list(_CANDIDATE_ITEM_REQUIRED),
                        "properties": dict(_CANDIDATE_ITEM_PROPERTIES),
                    },
                },
            },
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
            "motivation_fit",
            "product_value",
            "conversion_pull",
            "copycraft",
            "distinctiveness",
            "scene_texture",
            "benefit_clarity",
        ],
    },
    "score": {"type": "integer", "minimum": 0, "maximum": 5},
    "diagnostic": {"type": "string"},
}

_OBJECTIVE_CHECK_REQUIRED = [
    "check_id",
    "passed",
]
_OBJECTIVE_CHECK_PROPERTIES: dict[str, Any] = {
    "check_id": {
        "type": "string",
        "enum": [
            "no_private_trace",
            "no_specific_numeric_claim",
            "no_product_name_echo",
            "product_value_visible",
            "publishable_copy",
        ],
    },
    "passed": {"type": "boolean"},
}

_JUDGMENT_REQUIRED = [
    "candidate_id",
    "candidate_index",
    "product_id",
    "copy_text",
    "user_factor_id",
    "objective_checks",
    "axis_scores",
    "total_score",
    "main_strength",
    "main_weakness",
    "failure_tags",
]
_JUDGMENT_PROPERTIES: dict[str, Any] = {
    "candidate_id": {"type": "string"},
    "candidate_index": {"type": "integer"},
    "product_id": {"type": "string"},
    "copy_text": {"type": "string"},
    "user_factor_id": {"type": "string"},
    "objective_checks": {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": list(_OBJECTIVE_CHECK_REQUIRED),
            "properties": dict(_OBJECTIVE_CHECK_PROPERTIES),
        },
    },
    "axis_scores": {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": list(_AXIS_SCORE_REQUIRED),
            "properties": dict(_AXIS_SCORE_PROPERTIES),
        },
    },
    "total_score": {"type": "integer", "minimum": 0, "maximum": 35},
    "main_strength": {"type": "string"},
    "main_weakness": {"type": "string"},
    "failure_tags": {"type": "array", "items": {"type": "string"}},
}


SUBMIT_JUDGMENTS_FINAL_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "submit_judgments_final",
        "description": (
            "Submit the final PersonalizedCopyRubricArtifact. This is the "
            "only tool available to personalized-copy-rubric-judge."
        ),
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
    "personalized-user-mining": [SUBMIT_USER_FACTORS_FINAL_SPEC],
    "personalized-copy-generation": [SUBMIT_COPY_CANDIDATES_FINAL_SPEC],
    "personalized-copy-rubric-judge": [SUBMIT_JUDGMENTS_FINAL_SPEC],
}
