"""TOOL-10 — TOOLS_SPEC and TOOL_HANDLERS registry invariants.

The registries are the public surface that Phase 3's agent_loop will consume:
    TOOLS_SPEC[skill_name]   -> list of tool spec dicts to pass as tools=...
    TOOL_HANDLERS[tool_name] -> callable(args, state) -> str

This file pins:
    - the three skill names that must exist
    - the exact tool list per skill
    - that every spec is strict and has additionalProperties=False
    - critique-before-verdict field order in the per_axis item of
      judge_candidate / submit_judgments_final (DATA-05, ADR-03 §C2)
"""

from __future__ import annotations

import pytest

from seers_harness.tools.skill_tools import (
    JUDGE_CANDIDATE_SPEC,
    SUBMIT_JUDGMENTS_FINAL_SPEC,
    TOOL_HANDLERS,
    TOOLS_SPEC,
)


# --------------------------------------------------------------------------- #
# Registry shape                                                              #
# --------------------------------------------------------------------------- #


def test_tools_spec_has_three_skill_keys() -> None:
    assert set(TOOLS_SPEC.keys()) == {
        "discover-personalization-factors",
        "generate-copy-candidates",
        "personalized-copy-rubric-judge",
    }


def test_tools_spec_discover_factors_tools() -> None:
    names = [t["function"]["name"] for t in TOOLS_SPEC["discover-personalization-factors"]]
    assert names == ["record_factor", "reflect_on_coverage", "submit_factors_final"]


def test_tools_spec_generate_copy_tools() -> None:
    names = [t["function"]["name"] for t in TOOLS_SPEC["generate-copy-candidates"]]
    assert names == ["record_candidate", "reflect_on_diversity", "submit_copies_final"]


def test_tools_spec_rubric_judge_tools() -> None:
    names = [t["function"]["name"] for t in TOOLS_SPEC["personalized-copy-rubric-judge"]]
    assert names == ["judge_candidate", "submit_judgments_final"]


def test_tool_handlers_has_all_eight_handlers() -> None:
    assert set(TOOL_HANDLERS.keys()) == {
        "record_factor",
        "submit_factors_final",
        "record_candidate",
        "submit_copies_final",
        "judge_candidate",
        "submit_judgments_final",
        "reflect_on_coverage",
        "reflect_on_diversity",
    }
    for name, handler in TOOL_HANDLERS.items():
        assert callable(handler), f"{name} handler not callable"


def test_every_spec_in_tools_spec_is_strict_with_additional_properties_false() -> None:
    """Every tool spec emitted to DeepSeek must be strict and forbid extras."""
    for skill_name, specs in TOOLS_SPEC.items():
        for spec in specs:
            tool_name = spec["function"]["name"]
            assert spec["type"] == "function", f"{tool_name}: type not 'function'"
            assert spec["function"]["strict"] is True, f"{tool_name}: strict not True"
            params = spec["function"]["parameters"]
            assert params["additionalProperties"] is False, (
                f"{tool_name}: additionalProperties not False"
            )
            assert "required" in params, f"{tool_name}: required missing"
            # Strict mode contract: every defined property must appear in required.
            props = params.get("properties") or {}
            assert set(params["required"]) == set(props.keys()), (
                f"{tool_name}: required != properties keys"
            )


# --------------------------------------------------------------------------- #
# Critique-before-verdict order (DATA-05, ADR-03 §C2, RESEARCH §Open Q2)     #
# --------------------------------------------------------------------------- #


def _per_axis_property_keys(spec: dict) -> list[str]:
    """Pull the per_axis item properties from a spec that has either
    judge_candidate-shape or submit_judgments_final-shape parameters."""
    params = spec["function"]["parameters"]
    # judge_candidate has per_axis directly under properties.
    if "per_axis" in params["properties"]:
        per_axis_array = params["properties"]["per_axis"]
    # submit_judgments_final has judgments[] each containing per_axis.
    else:
        per_axis_array = params["properties"]["judgments"]["items"]["properties"]["per_axis"]
    return list(per_axis_array["items"]["properties"].keys())


def test_judge_candidate_spec_per_axis_critique_before_verdict_order() -> None:
    keys = _per_axis_property_keys(JUDGE_CANDIDATE_SPEC)
    # The locked order: critique fields first, verdict last.
    assert keys == [
        "axis_id",
        "verbatim_candidate_quote",
        "bridge_to_anchor",
        "templated_flag",
        "verdict",
    ]
    # And the structural invariant: verdict must come after every critique field.
    assert keys.index("verdict") > keys.index("verbatim_candidate_quote")
    assert keys.index("verdict") > keys.index("bridge_to_anchor")


def test_submit_judgments_final_spec_per_axis_critique_before_verdict_order() -> None:
    keys = _per_axis_property_keys(SUBMIT_JUDGMENTS_FINAL_SPEC)
    assert keys == [
        "axis_id",
        "verbatim_candidate_quote",
        "bridge_to_anchor",
        "templated_flag",
        "verdict",
    ]


def test_tool_handler_names_match_tools_spec_names() -> None:
    """Every name appearing in any TOOLS_SPEC list must have a handler;
    every handler must appear in at least one TOOLS_SPEC list."""
    spec_names: set[str] = set()
    for specs in TOOLS_SPEC.values():
        for s in specs:
            spec_names.add(s["function"]["name"])
    assert spec_names == set(TOOL_HANDLERS.keys())
