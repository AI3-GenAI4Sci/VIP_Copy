from __future__ import annotations

from seers_harness.workflow.skill_loader import NODE_SKILL_BINDING, load_skill_prose, resolve_skill_for_node


def test_resolve_skill_for_node_split_pipeline_bindings():
    assert resolve_skill_for_node("personalized_user_mining") == "personalized-user-mining"
    assert resolve_skill_for_node("personalized_copy_generation") == "personalized-copy-generation"
    assert resolve_skill_for_node("personalized_copy_rubric") == "personalized-copy-rubric-judge"
    assert set(NODE_SKILL_BINDING) == {
        "personalized_user_mining",
        "personalized_copy_generation",
        "personalized_copy_rubric",
        "distill_after_stage1",
    }


def test_load_skill_prose_user_mining_skill_exists():
    prose = load_skill_prose("personalized-user-mining")
    assert "用户侧个性化挖掘" in prose
    assert "maintain_user_factors_artifact" in prose
