"""Phase 6 plan 06-01 task 02 — evolution tool-use handlers.

Covers the rewritten ``distill-skill-deltas`` skill: three hand handlers
(``record_delta_observation``, ``record_delta_change``,
``submit_delta_distillation_final``), strict tool specs, and the privacy +
self-rated metric rejection contract.
"""

from __future__ import annotations

import pathlib

import pytest

from seers_harness.core.errors import ToolValidationError
from seers_harness.tools.evolution_tools import (
    EVOLUTION_TOOL_HANDLERS,
    EVOLUTION_TOOLS_SPEC,
    RECORD_DELTA_CHANGE_SPEC,
    RECORD_DELTA_OBSERVATION_SPEC,
    SUBMIT_DELTA_DISTILLATION_FINAL_SPEC,
    record_delta_change,
    record_delta_observation,
    submit_delta_distillation_final,
)


# --------------------------------------------------------------------------- #
# Argument fixtures                                                           #
# --------------------------------------------------------------------------- #


def _valid_observation_args() -> dict:
    return {
        "delta_id": "D-1",
        "target_skill": "current/personalized-copy-generation/SKILL.md",
        "observation": "factor 3 transcribed a behavior token verbatim",
        "evidence_refs": [
            {
                "path": "request_42.factor_3.text",
                "value": "raw token verbatim",
            }
        ],
    }


def _valid_change_args() -> dict:
    return {
        "delta_id": "D-1",
        "target_skill": "current/personalized-copy-generation/SKILL.md",
        "function_id": "f_user_factor_to_product_hook",
        "operation": "modify",
        "observation": "factor 3 transcribed a behavior token verbatim",
        "proposed_change": (
            "add a reflect question that asks whether the disposition "
            "still holds for a retrieved user without the literal token"
        ),
        "evidence_refs": [
            {"path": "request_42.factor_3.text", "value": None}
        ],
        "applicable_surface": ["personalized_copy_generation"],
        "failure_types": ["token_leak"],
    }


def _valid_final_artifact() -> dict:
    return {
        "request_id": "R-42",
        "scenario_id": "S-7",
        "deltas": [_valid_change_args()],
    }


# --------------------------------------------------------------------------- #
# Happy path                                                                  #
# --------------------------------------------------------------------------- #


def test_record_delta_observation_appends_and_returns_recorded() -> None:
    state: dict = {}
    out = record_delta_observation(_valid_observation_args(), state)
    assert out == "recorded"
    assert state["delta_observations"][0]["delta_id"] == "D-1"


def test_record_delta_change_appends_and_returns_recorded() -> None:
    state: dict = {}
    out = record_delta_change(_valid_change_args(), state)
    assert out == "recorded"
    assert state["delta_changes"][0]["operation"] == "modify"
    assert state["delta_changes"][0]["evidence_refs"]


def test_submit_delta_distillation_final_finalizes() -> None:
    state: dict = {}
    out = submit_delta_distillation_final(_valid_final_artifact(), state)
    assert out == "finalized"
    assert state["final_artifact"]["request_id"] == "R-42"
    assert len(state["final_artifact"]["deltas"]) == 1


def test_full_record_then_submit_flow() -> None:
    """Two record turns then one submit — the natural skill loop shape."""
    state: dict = {}
    record_delta_observation(_valid_observation_args(), state)
    record_delta_change(_valid_change_args(), state)
    submit_delta_distillation_final(_valid_final_artifact(), state)
    assert state["delta_observations"]
    assert state["delta_changes"]
    assert state["final_artifact"]["deltas"][0]["delta_id"] == "D-1"


# --------------------------------------------------------------------------- #
# Privacy-term rejection (T-06-02)                                            #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "private_term",
    [
        "private_reasoning",
        "user_state",
        "raw_interest_fragment_private",
        "diagnostic_evidence_refs",
        "blocked_evidence_refs",
        "is_clk_c",
    ],
)
def test_record_delta_change_rejects_private_term_in_observation(
    private_term: str,
) -> None:
    args = _valid_change_args()
    args["observation"] = (
        f"factor 3 leaked {private_term} payload from the trajectory"
    )
    state: dict = {}
    with pytest.raises(ToolValidationError) as exc_info:
        record_delta_change(args, state)
    assert exc_info.value.tool_name == "record_delta_change"
    assert private_term in exc_info.value.message
    assert "delta_changes" not in state


def test_record_delta_change_rejects_private_term_in_evidence_refs() -> None:
    args = _valid_change_args()
    args["evidence_refs"] = [
        {
            "path": "request_42.factor_3.is_clk_c",
            "value": "leak",
        }
    ]
    state: dict = {}
    with pytest.raises(ToolValidationError):
        record_delta_change(args, state)
    assert "delta_changes" not in state


def test_submit_final_rejects_private_term_in_proposed_change() -> None:
    artifact = _valid_final_artifact()
    artifact["deltas"][0]["proposed_change"] = (
        "expose user_state.behavior verbatim in the prompt"
    )
    state: dict = {}
    with pytest.raises(ToolValidationError):
        submit_delta_distillation_final(artifact, state)
    assert "final_artifact" not in state


# --------------------------------------------------------------------------- #
# Self-rated metric rejection (Principle 10, T-06-03)                         #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "metric_key",
    ["confidence", "score", "probability", "uncertainty", "strength"],
)
def test_record_delta_change_rejects_self_rated_metric_arg(metric_key: str) -> None:
    args = _valid_change_args()
    args[metric_key] = 0.9
    state: dict = {}
    with pytest.raises(ToolValidationError) as exc_info:
        record_delta_change(args, state)
    assert metric_key in exc_info.value.message
    assert "delta_changes" not in state


@pytest.mark.parametrize(
    "metric_key",
    ["confidence", "score", "probability", "uncertainty", "strength"],
)
def test_record_delta_observation_rejects_self_rated_metric_arg(
    metric_key: str,
) -> None:
    args = _valid_observation_args()
    args[metric_key] = 0.5
    state: dict = {}
    with pytest.raises(ToolValidationError) as exc_info:
        record_delta_observation(args, state)
    assert metric_key in exc_info.value.message


# --------------------------------------------------------------------------- #
# Structural rejections                                                       #
# --------------------------------------------------------------------------- #


def test_record_delta_change_rejects_unknown_operation() -> None:
    args = _valid_change_args()
    args["operation"] = "rewrite_everything"
    state: dict = {}
    with pytest.raises(ToolValidationError) as exc_info:
        record_delta_change(args, state)
    assert exc_info.value.arg_path == "operation"


def test_record_delta_change_rejects_empty_evidence_refs() -> None:
    args = _valid_change_args()
    args["evidence_refs"] = []
    state: dict = {}
    with pytest.raises(ToolValidationError):
        record_delta_change(args, state)
    assert "delta_changes" not in state


def test_record_delta_observation_rejects_empty_observation() -> None:
    args = _valid_observation_args()
    args["observation"] = "   "
    state: dict = {}
    with pytest.raises(ToolValidationError):
        record_delta_observation(args, state)


def test_record_delta_observation_rejects_empty_evidence_refs() -> None:
    args = _valid_observation_args()
    args["evidence_refs"] = []
    state: dict = {}
    with pytest.raises(ToolValidationError):
        record_delta_observation(args, state)


def test_submit_final_rejects_unknown_top_level_field() -> None:
    artifact = _valid_final_artifact()
    artifact["bonus_field"] = "extra"  # extra=forbid
    state: dict = {}
    with pytest.raises(ToolValidationError):
        submit_delta_distillation_final(artifact, state)


def test_target_skill_must_match_pattern() -> None:
    args = _valid_change_args()
    args["target_skill"] = "personalized-copy-generation"
    state: dict = {}

    with pytest.raises(ToolValidationError) as exc_info:
        record_delta_change(args, state)

    assert exc_info.value.arg_path == "target_skill"
    assert "target_skill" in exc_info.value.message
    assert "pattern" in exc_info.value.message
    assert "delta_changes" not in state


def test_target_skill_pattern_accepts_canonical() -> None:
    state: dict = {}

    out = record_delta_change(_valid_change_args(), state)

    assert out == "recorded"
    assert state["delta_changes"][0]["target_skill"] == (
        "current/personalized-copy-generation/SKILL.md"
    )


def test_record_delta_observation_target_skill_pattern() -> None:
    state: dict = {}
    assert record_delta_observation(_valid_observation_args(), state) == "recorded"

    args = _valid_observation_args()
    args["target_skill"] = "evolution/distill-skill-deltas/SKILL.md"
    with pytest.raises(ToolValidationError) as exc_info:
        record_delta_observation(args, {})
    assert exc_info.value.arg_path == "target_skill"
    assert "pattern" in exc_info.value.message


def test_submit_final_rejects_noncanonical_target_skill() -> None:
    artifact = _valid_final_artifact()
    artifact["deltas"][0]["target_skill"] = "current/Bad_Skill/SKILL.md"

    with pytest.raises(ToolValidationError) as exc_info:
        submit_delta_distillation_final(artifact, {})

    assert exc_info.value.arg_path == "deltas.0.target_skill"
    assert "pattern" in exc_info.value.message


def test_skill_prose_has_dual_track_sections_and_no_user_example_phrases() -> None:
    skill_path = (
        pathlib.Path(__file__).resolve().parent.parent
        / "workflow-skills/evolution/distill-skill-deltas/SKILL.md"
    )
    text = skill_path.read_text(encoding="utf-8")

    assert text.count("## 核心定义") == 1
    assert text.count("## 成功路径与失败路径") == 1
    assert text.count("## target_skill 格式") == 1
    for required in (
        "Skill = {f_signal, f_factor, f_copy, f_judge, f_tool, f_finish, ...}",
        "`add`",
        "`modify`",
        "`delete`",
        "成功路径",
        "失败路径",
        "current/personalized-copy-generation/SKILL.md",
        "record_delta_observation",
        "record_delta_change",
        "submit_delta_distillation_final",
    ):
        assert required in text
    forbidden = ["低价大牌", "周三早9点", "代理父亲", "信息饕餮", "多娃妈妈"]
    assert not [term for term in forbidden if term in text]


# --------------------------------------------------------------------------- #
# Spec / registry shape                                                       #
# --------------------------------------------------------------------------- #


def test_evolution_tools_spec_has_distill_skill_key() -> None:
    assert "distill-skill-deltas" in EVOLUTION_TOOLS_SPEC


def test_evolution_tools_spec_distill_tools_in_order() -> None:
    names = [
        t["function"]["name"]
        for t in EVOLUTION_TOOLS_SPEC["distill-skill-deltas"]
    ]
    assert names == [
        "record_delta_observation",
        "record_delta_change",
        "submit_delta_distillation_final",
    ]


def test_every_evolution_spec_is_strict() -> None:
    for spec in EVOLUTION_TOOLS_SPEC["distill-skill-deltas"]:
        assert spec["type"] == "function"
        assert spec["function"]["strict"] is True
        params = spec["function"]["parameters"]
        assert params["additionalProperties"] is False
        props = params.get("properties") or {}
        assert set(params["required"]) == set(props.keys())


def test_evolution_handlers_match_spec_names() -> None:
    spec_names = {
        spec["function"]["name"]
        for spec in EVOLUTION_TOOLS_SPEC["distill-skill-deltas"]
    }
    assert spec_names == set(EVOLUTION_TOOL_HANDLERS.keys())


def test_target_skill_specs_share_canonical_pattern() -> None:
    expected_pattern = r"^current/[a-z0-9][a-z0-9-]*/SKILL\.md$"
    expected_description_fragment = "current/<skill-slug>/SKILL.md"
    props = RECORD_DELTA_CHANGE_SPEC["function"]["parameters"]["properties"]
    obs_props = RECORD_DELTA_OBSERVATION_SPEC["function"]["parameters"]["properties"]
    submit_inner = (
        SUBMIT_DELTA_DISTILLATION_FINAL_SPEC["function"]["parameters"]
        ["properties"]["deltas"]["items"]["properties"]
    )

    for target_skill_prop in (
        props["target_skill"],
        obs_props["target_skill"],
        submit_inner["target_skill"],
    ):
        assert target_skill_prop["pattern"] == expected_pattern
        assert expected_description_fragment in target_skill_prop["description"]


def test_record_delta_change_spec_does_not_expose_self_rated_keys() -> None:
    """Defensive: the spec's properties never include the banned key names.

    A future edit that adds e.g. ``confidence`` to the spec would let the
    model emit it before the handler can scrub. Lock it at the spec layer too.
    """
    forbidden = {"confidence", "score", "probability", "uncertainty", "strength"}
    props = RECORD_DELTA_CHANGE_SPEC["function"]["parameters"]["properties"]
    assert not (set(props.keys()) & forbidden)
    obs_props = RECORD_DELTA_OBSERVATION_SPEC["function"]["parameters"]["properties"]
    assert not (set(obs_props.keys()) & forbidden)
    submit_inner = (
        SUBMIT_DELTA_DISTILLATION_FINAL_SPEC["function"]["parameters"]
        ["properties"]["deltas"]["items"]["properties"]
    )
    assert not (set(submit_inner.keys()) & forbidden)
