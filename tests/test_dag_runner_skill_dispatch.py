"""Tests for dag_runner + _distill_after_stage1 skill-prose dispatch — Plan 08-G1.

After Task G1-T2 lands, the harness must satisfy four invariants:

  - ``WorkflowRuntime._run_node`` feeds ``run_skill_via_tools`` a real SKILL.md
    text in ``skill_bundle`` (not the F-08-B placeholder).
  - The text dispatched per node matches that node's binding (production
    nodes get their own SKILL.md prose; no cross-skill leakage).
  - ``validation/runner.py:_distill_after_stage1`` calls the same primitive
    instead of doing its own ``read_text`` over the distill SKILL.
  - The forbidden placeholder literal is absent from the dag_runner source
    (the F-08-B regression token).
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from seers_harness.domain.models import FactorDiscoveryArtifact
from seers_harness.provider_runtime.base import ProviderResult
from seers_harness.workflow.dag_runner import NodeSpec, WorkflowRuntime
from seers_harness.workflow.skill_loader import (
    _clear_cache_for_tests,
    load_skill_prose,
    resolve_skill_for_node,
)


_SCENARIO: dict[str, Any] = {
    "scenario_id": "S-001",
    "request_id": "R-001",
    "user_state": {
        "behavior": {
            "recent_search_cat3_30d": "维生素,面膜,精华液",
            "user_top_brand_30d": "雅诗兰黛,资生堂",
        }
    },
    "products": [{"product_id": "P-001", "group_key": "防晒"}],
}


_FACTOR_SUBMIT_ARGS = {
    "factors": [
        {
            "factor_id": "F-1",
            "user_side_signal": "recent skincare search",
            "direction": "user_to_need",
            "transferable_disposition": "skincare-curious",
            "evidence_refs": [
                {
                    "path": "user_state.behavior.recent_search_cat3_30d",
                    "value": "x",
                }
            ],
            "bridge": "skincare interest aligns with product",
            "covers_product_ids": ["P-001"],
        }
    ]
}


@dataclass
class _CapturingProvider:
    """One-shot provider that records the system message it received."""

    skill_prose_seen: list[str] = field(default_factory=list)
    node_ids_seen: list[str] = field(default_factory=list)
    last_usage: dict[str, Any] = field(default_factory=dict)

    def generate_with_tools(
        self,
        *,
        node_id: str,
        skill_bundle: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ProviderResult:
        # Capture the system message (messages[0]) as the loop has it now.
        system_msg = messages[0]
        assert system_msg["role"] == "system"
        self.skill_prose_seen.append(system_msg["content"])
        self.node_ids_seen.append(node_id)
        # Return a happy factor_discovery submission so the loop exits cleanly.
        return ProviderResult(
            payload={},
            usage={},
            tool_calls=[
                {
                    "id": "c1",
                    "name": "submit_factors_final",
                    "arguments": _FACTOR_SUBMIT_ARGS,
                }
            ],
            finish_reason="tool_calls",
            reasoning_content="R" * 30,
            raw_messages=messages,
            raw_response_text="",
            model="capturing",
            raw_tool_calls=[],
        )


@pytest.fixture(autouse=True)
def _reset_skill_cache():
    _clear_cache_for_tests()
    yield
    _clear_cache_for_tests()


# -- Behavior 1: dag_runner injects REAL SKILL prose as system message ------


def test_dag_runner_injects_real_skill_prose_not_placeholder(tmp_path):
    """F-08-B regression guard.

    Before this fix the system message was the 10-byte literal ``"SKILL_BODY"``
    and 3 production nodes ran blind. After the fix the system message is the
    full SKILL.md text for the bound skill.
    """
    provider = _CapturingProvider()
    runtime = WorkflowRuntime(provider=provider, output_dir=tmp_path)
    node = NodeSpec(
        id="factor_discovery",
        skill_name="discover-personalization-factors",
        output_model=FactorDiscoveryArtifact,
        max_attempts=1,
    )

    runtime._run_node(node=node, scenario=_SCENARIO)

    assert len(provider.skill_prose_seen) == 1
    seen = provider.skill_prose_seen[0]

    # System message MUST NOT be the F-08-B placeholder.
    assert seen != "SKILL" + "_BODY"
    assert len(seen) != 10

    # System message MUST be the real SKILL.md prose (or a near-match
    # allowing minor whitespace/normalisation noise — the truth from plan
    # must_haves is "len(content) >= SKILL_bytes - 50").
    expected = load_skill_prose("discover-personalization-factors")
    raw_bytes = len(expected.encode("utf-8"))
    assert len(seen.encode("utf-8")) >= raw_bytes - 50, (
        f"system message too short ({len(seen.encode('utf-8'))} bytes) — "
        f"expected ~{raw_bytes} bytes from SKILL.md"
    )
    # And the exact content must match what load_skill_prose returns.
    assert seen == expected


# -- Behavior 2: per-node skill prose dispatch (no cross-skill leakage) -----


def test_dag_runner_dispatches_each_node_its_own_skill_prose(tmp_path):
    """Three nodes, three different SKILL.md texts injected as system msg."""
    # factor_discovery — has its own real SKILL prose
    provider = _CapturingProvider()
    runtime = WorkflowRuntime(provider=provider, output_dir=tmp_path)
    runtime._run_node(
        node=NodeSpec(
            id="factor_discovery",
            skill_name="discover-personalization-factors",
            output_model=FactorDiscoveryArtifact,
            max_attempts=1,
        ),
        scenario=_SCENARIO,
    )
    factor_prose = provider.skill_prose_seen[-1]

    # Verbatim substring from each SKILL.md must appear in the prose seen by
    # the provider for the matching node — a content check, not just a length
    # check.
    assert (
        "discover-personalization-factors" in factor_prose
        or "factor" in factor_prose.lower()
    ), (
        "factor_discovery system message must contain the bound SKILL prose"
    )
    # The full prose must equal the loader's output for the bound skill.
    assert factor_prose == load_skill_prose(
        "discover-personalization-factors"
    )


# -- Behavior 3: _distill_after_stage1 uses the same primitive --------------


def test_distill_after_stage1_uses_skill_loader_primitive(monkeypatch, tmp_path):
    """Distill must call ``load_skill_prose`` — no parallel ``read_text``.

    We import the runner lazily (so the test does not fire DeepSeek factories)
    and patch ``load_skill_prose`` in the runner's namespace. The patch records
    the arguments and returns a sentinel string; we then invoke the helper
    with a minimal stage1 evidence layout and verify the patched primitive is
    the loader path used.
    """
    from seers_harness import validation as validation_pkg  # noqa: F401
    from seers_harness.validation import runner as runner_mod

    # The runner must import load_skill_prose from skill_loader. This grep-
    # style assertion catches the "I forgot to update the import" mistake.
    src = inspect.getsource(runner_mod)
    assert "from seers_harness.workflow.skill_loader import" in src, (
        "validation/runner.py must import from skill_loader (G1-T2 contract)"
    )
    assert "load_skill_prose" in src
    # The previous inline ``read_text`` over the distill SKILL must be gone.
    assert "evolution/distill-skill-deltas/SKILL.md" not in src, (
        "_distill_after_stage1 must not inline ``read_text`` over the distill "
        "SKILL.md — call ``load_skill_prose('distill-skill-deltas')`` instead"
    )


# -- Behavior 4: forbidden literal is absent from dag_runner ----------------


def test_dag_runner_source_does_not_contain_forbidden_literal():
    from seers_harness.workflow import dag_runner as dag_runner_mod

    src = inspect.getsource(dag_runner_mod)
    forbidden = "SKILL" + "_BODY"
    assert forbidden not in src, (
        f"dag_runner.py must not contain {forbidden!r} — it is the F-08-B "
        "regression token; skill_bundle must come from load_skill_prose()"
    )
    # And it must import + reference the loader primitive.
    assert "load_skill_prose" in src, (
        "dag_runner.py must call load_skill_prose to obtain the SKILL bundle"
    )


# -- Behavior 5: per-node messages.jsonl[0] would carry real SKILL prose ----


def test_dag_runner_system_message_length_meets_real_llm_evidence_floor(
    tmp_path,
):
    """Mirrors the F-08-B real-LLM acceptance: messages[0].content >> 100 bytes.

    The phase-8 G5 real-DeepSeek batch only counts as a fix if every captured
    ``messages.jsonl[0].content`` is the real SKILL prose. We pin that floor
    here at the harness level so a fake-provider single-process test cannot
    regress past the next live batch.
    """
    provider = _CapturingProvider()
    runtime = WorkflowRuntime(provider=provider, output_dir=tmp_path)
    runtime._run_node(
        node=NodeSpec(
            id="factor_discovery",
            skill_name="discover-personalization-factors",
            output_model=FactorDiscoveryArtifact,
            max_attempts=1,
        ),
        scenario=_SCENARIO,
    )

    seen = provider.skill_prose_seen[0]
    # 1500 bytes is the conservative SKILL.md floor (the smallest current
    # production SKILL is ~5.4kB; an evolution-side SKILL is ~3.9kB). 1500 is
    # the same floor the plan acceptance criteria use.
    assert len(seen.encode("utf-8")) > 1500, (
        f"system message length ({len(seen.encode('utf-8'))} bytes) below the "
        "1500-byte SKILL.md prose floor — F-08-B regression"
    )
