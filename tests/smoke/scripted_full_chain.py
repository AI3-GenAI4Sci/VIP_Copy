"""Scripted full-chain driver for the split personalized-copy DAG."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from seers_harness.domain.models import (
    CopyGenerationArtifact,
    PersonalizedCopyRubricArtifact,
    UserPersonalizationArtifact,
)
from seers_harness.workflow.dag_runner import NodeSpec, WorkflowRuntime

from tests.fakes.scripted_provider import ScriptedProvider, ScriptedTurn


_USER_FACTOR_ID = "UF-SMOKE-1"
_CANDIDATE_ID = "C-SMOKE-1"
_TARGET_PRODUCT_ID = "P-SMOKE"
_CANDIDATE_TEXT = "熬夜脸也能轻松修护"


_USER_FACTOR_ARGS: dict[str, Any] = {
    "action": "upsert_many",
    "user_factors": [
        {
            "user_factor_id": _USER_FACTOR_ID,
            "signal_basis": "深夜活跃且近期浏览维生素",
            "need_or_pain": "希望低门槛改善熬夜状态",
            "scene_trigger": "23 点睡前刷购",
            "buying_heuristic": "看重高口碑和低门槛",
            "expression_hooks": ["熬夜脸", "低门槛"],
            "evidence_refs": [{"path": "user_state_signals.behavior_top_lists.prefer_cat3_topK", "value": None}],
        }
    ],
    "user_factor_ids": [],
}


_USER_FACTOR_SAVE_ARGS: dict[str, Any] = {
    "action": "save",
    "user_factors": [],
    "user_factor_ids": [],
}


_CANDIDATE_ARGS: dict[str, Any] = {
    "action": "upsert_many",
    "candidates": [
        {
            "candidate_id": _CANDIDATE_ID,
            "product_id": _TARGET_PRODUCT_ID,
            "source_user_factor_id": _USER_FACTOR_ID,
            "text": _CANDIDATE_TEXT,
            "commercial_angle": "熬夜痛点前置",
            "product_binding": "商品承接熬夜后日常调理诉求",
            "fact_binding": "商品标题和属性支持维 B/修护表达",
        }
    ],
    "candidate_ids": [],
    "product_id": "",
}


_CANDIDATE_SAVE_ARGS: dict[str, Any] = {
    "action": "save",
    "candidates": [],
    "candidate_ids": [],
    "product_id": "",
}


_JUDGMENT_DICT: dict[str, Any] = {
    "candidate_id": _CANDIDATE_ID,
    "candidate_index": 0,
    "product_id": _TARGET_PRODUCT_ID,
    "copy_text": _CANDIDATE_TEXT,
    "user_factor_id": _USER_FACTOR_ID,
    "axis_scores": [
        {"axis_id": "user_factor_grounding", "score": 5, "diagnostic": "grounded"},
        {"axis_id": "product_binding", "score": 4, "diagnostic": "bound"},
        {"axis_id": "personalized_conversion", "score": 4, "diagnostic": "specific"},
        {"axis_id": "commercial_sharpness", "score": 4, "diagnostic": "sharp"},
        {"axis_id": "expression_boundary", "score": 4, "diagnostic": "safe"},
    ],
    "total_score": 21,
    "main_strength": "",
    "main_weakness": "",
    "failure_tags": [],
    "decision": "admit",
}


_JUDGE_RECORD_ARGS: dict[str, Any] = dict(_JUDGMENT_DICT)
_JUDGE_SUBMIT_ARGS: dict[str, Any] = {"judgments": [dict(_JUDGMENT_DICT)]}


def _turn(name_args_pairs: list[tuple[str, dict[str, Any]]]) -> ScriptedTurn:
    return ScriptedTurn(
        tool_calls=[
            {"id": f"c-{i}", "name": name, "arguments": args}
            for i, (name, args) in enumerate(name_args_pairs)
        ],
        raw_tool_calls=[],
        finish_reason="tool_calls",
        reasoning_content="R" * 30,
    )


def build_full_chain_script() -> ScriptedProvider:
    script = [
        _turn([("maintain_user_factors_artifact", _USER_FACTOR_ARGS)]),
        _turn([("maintain_user_factors_artifact", _USER_FACTOR_SAVE_ARGS)]),
        _turn([("maintain_copy_artifact", _CANDIDATE_ARGS)]),
        _turn([("maintain_copy_artifact", _CANDIDATE_SAVE_ARGS)]),
        _turn([("judge_candidate", _JUDGE_RECORD_ARGS)]),
        _turn([("submit_judgments_final", _JUDGE_SUBMIT_ARGS)]),
    ]
    return ScriptedProvider(script=script)


def make_nodes() -> list[NodeSpec]:
    return [
        NodeSpec(
            id="personalized_user_mining",
            skill_name="personalized-user-mining",
            output_model=UserPersonalizationArtifact,
            max_attempts=2,
        ),
        NodeSpec(
            id="personalized_copy_generation",
            skill_name="personalized-copy-generation",
            output_model=CopyGenerationArtifact,
            max_attempts=2,
        ),
        NodeSpec(
            id="personalized_copy_rubric",
            skill_name="personalized-copy-rubric-judge",
            output_model=PersonalizedCopyRubricArtifact,
            max_attempts=1,
        ),
    ]


def make_runtime(output_dir: Path, provider: ScriptedProvider) -> WorkflowRuntime:
    return WorkflowRuntime(provider=provider, output_dir=output_dir)
