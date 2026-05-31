"""Phase 6 plan 06-02 tasks 02 + 04 — trial runner isolation and integration.

Tests verify three guarantees:

1. ``apply_delta_patch_temporarily`` writes the replacement text inside
   the temp workspace and never touches the live skill root.
2. The original temp-side content is restored on normal exit and on
   exceptions raised inside the ``with`` body.
3. ``run_request_trial`` runs the default merged DAG through a
   ``ScriptedProvider`` and returns artifact paths for the merged generation
   node plus the rubric node.

The trial runner isolates the *skill text* via a temp copy of the live skill
root, and the DAG runner now reads the real patched prose through
``load_skill_prose``.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from seers_harness.evolution.delta_portfolio import (
    DeltaPortfolioRow,
    select_trial_delta,
    update_after_trial,
)
from seers_harness.evolution.trial_runner import (
    SkillDeltaPatch,
    apply_delta_patch_temporarily,
    run_request_trial,
    sha256_of_text,
)

from tests.smoke.scripted_full_chain import (
    build_full_chain_script,
    make_nodes,
    make_runtime,
)


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _build_live_skill_root(root: Path) -> Path:
    """Build a tiny live skill root for the default merged surface."""
    root.mkdir(parents=True, exist_ok=True)
    for skill_name in (
        "personalized-copy-generation",
        "personalized-copy-rubric-judge",
    ):
        skill_dir = root / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            f"# original {skill_name} prose\n", encoding="utf-8"
        )
    return root


def _build_scenario_for_smoke() -> dict:
    """A minimum-viable scenario the scripted chain accepts."""
    return {
        "request_id": "R-trial-1",
        "scenario_id": "S-trial-1",
        "list_group": "G-trial",
        "minimum_semantic_unit": "request/list_group",
        "user_state": {"behavior": {}},
        "products": [
            {
                "product_id": "P-SMOKE",
                "group_key": "smoke-group",
                "attributes": {
                    "item_cat3_name": "n",
                    "item_brand_name": "b",
                    "item_name": "i",
                },
            }
        ],
        "derived_features_by_product": {"P-SMOKE": {"cat3_alignment": "match"}},
    }


# --------------------------------------------------------------------------- #
# Patch contract — isolation + restore                                        #
# --------------------------------------------------------------------------- #


def test_apply_delta_patch_temporarily_shows_replacement_inside_context(
    tmp_path: Path,
) -> None:
    live = _build_live_skill_root(tmp_path / "live")
    workspace = tmp_path / "workspace"

    target_rel = "personalized-copy-generation/SKILL.md"
    original = (live / target_rel).read_text(encoding="utf-8")
    patch = SkillDeltaPatch(
        target_path=target_rel,
        original_text_sha256=sha256_of_text(original),
        replacement_text="# PATCHED skill prose\n",
    )

    with apply_delta_patch_temporarily(live, workspace, patch) as temp_root:
        patched_text = (temp_root / target_rel).read_text(encoding="utf-8")
        assert patched_text == "# PATCHED skill prose\n"
        # The live root must not be touched at any point.
        assert (live / target_rel).read_text(encoding="utf-8") == original


def test_apply_delta_patch_temporarily_restores_on_normal_exit(
    tmp_path: Path,
) -> None:
    live = _build_live_skill_root(tmp_path / "live")
    workspace = tmp_path / "workspace"
    target_rel = "personalized-copy-generation/SKILL.md"
    original = (live / target_rel).read_text(encoding="utf-8")
    patch = SkillDeltaPatch(
        target_path=target_rel,
        original_text_sha256=sha256_of_text(original),
        replacement_text="# PATCHED skill prose\n",
    )

    with apply_delta_patch_temporarily(live, workspace, patch) as temp_root:
        pass

    # After exit the temp file has been restored to the original text.
    assert (
        (workspace / "skills" / target_rel).read_text(encoding="utf-8")
        == original
    )
    # And the live file was never modified.
    assert (live / target_rel).read_text(encoding="utf-8") == original


def test_apply_delta_patch_temporarily_restores_after_exception(
    tmp_path: Path,
) -> None:
    live = _build_live_skill_root(tmp_path / "live")
    workspace = tmp_path / "workspace"
    target_rel = "personalized-copy-generation/SKILL.md"
    original = (live / target_rel).read_text(encoding="utf-8")
    patch = SkillDeltaPatch(
        target_path=target_rel,
        original_text_sha256=sha256_of_text(original),
        replacement_text="# PATCHED skill prose\n",
    )

    class _Boom(RuntimeError):
        pass

    with pytest.raises(_Boom):
        with apply_delta_patch_temporarily(live, workspace, patch) as temp_root:
            assert (
                (temp_root / target_rel).read_text(encoding="utf-8")
                == "# PATCHED skill prose\n"
            )
            raise _Boom("simulated trial body failure")

    # After exception the temp file is restored AND the live root is intact.
    assert (
        (workspace / "skills" / target_rel).read_text(encoding="utf-8")
        == original
    )
    assert (live / target_rel).read_text(encoding="utf-8") == original


def test_apply_delta_patch_temporarily_refuses_drifted_live_root(
    tmp_path: Path,
) -> None:
    live = _build_live_skill_root(tmp_path / "live")
    workspace = tmp_path / "workspace"
    target_rel = "personalized-copy-generation/SKILL.md"

    # Compute a hash for content that does NOT match the live file.
    bogus_hash = sha256_of_text("# something else entirely")
    patch = SkillDeltaPatch(
        target_path=target_rel,
        original_text_sha256=bogus_hash,
        replacement_text="# PATCHED skill prose\n",
    )

    with pytest.raises(ValueError, match="drift"):
        with apply_delta_patch_temporarily(live, workspace, patch):
            pytest.fail("body should not run on a drifted live root")


def test_apply_delta_patch_temporarily_missing_target_raises(
    tmp_path: Path,
) -> None:
    live = _build_live_skill_root(tmp_path / "live")
    workspace = tmp_path / "workspace"
    patch = SkillDeltaPatch(
        target_path="nonexistent-skill/SKILL.md",
        original_text_sha256=sha256_of_text(""),
        replacement_text="x",
    )

    with pytest.raises(FileNotFoundError):
        with apply_delta_patch_temporarily(live, workspace, patch):
            pytest.fail("body should not run when target is missing")


def test_apply_delta_patch_temporarily_works_without_patch(tmp_path: Path) -> None:
    """A control run (no delta) still produces a usable temp skill root."""
    live = _build_live_skill_root(tmp_path / "live")
    workspace = tmp_path / "workspace"

    with apply_delta_patch_temporarily(live, workspace, None) as temp_root:
        assert (
            (temp_root / "personalized-copy-generation/SKILL.md")
            .read_text(encoding="utf-8")
            .startswith("# original")
        )


# --------------------------------------------------------------------------- #
# run_request_trial — runs the 3-node DAG inside the temp surface             #
# --------------------------------------------------------------------------- #


def test_run_request_trial_returns_artifact_paths_for_default_merged_nodes(
    tmp_path: Path,
) -> None:
    live = _build_live_skill_root(tmp_path / "live")
    workspace = tmp_path / "workspace"
    artifacts_dir = tmp_path / "artifacts"

    provider = build_full_chain_script()
    runtime = make_runtime(artifacts_dir, provider)
    nodes = make_nodes()

    target_rel = "personalized-copy-generation/SKILL.md"
    original = (live / target_rel).read_text(encoding="utf-8")
    patch = SkillDeltaPatch(
        target_path=target_rel,
        original_text_sha256=sha256_of_text(original),
        replacement_text="# trial-patched prose\n",
    )

    outcome = run_request_trial(
        runtime=runtime,
        scenario=_build_scenario_for_smoke(),
        nodes=nodes,
        live_skill_root=live,
        workspace_dir=workspace,
        patch=patch,
        request_id="R-trial-1",
        scenario_id="S-trial-1",
    )

    assert outcome.success is True
    assert outcome.failure_category is None
    assert set(outcome.artifact_paths.keys()) == {
        "personalized_user_mining",
        "personalized_copy_generation",
        "personalized_copy_rubric",
    }
    for p in outcome.artifact_paths.values():
        assert p.exists()
        assert p.read_text(encoding="utf-8").strip()
    assert outcome.tool_call_count == 6
    # The patched delta id surfaces back on the outcome.
    assert outcome.trial_delta_id is not None
    # Live skill root is unchanged after a trial.
    assert (live / target_rel).read_text(encoding="utf-8") == original


def test_run_request_trial_without_patch_records_control_run(
    tmp_path: Path,
) -> None:
    live = _build_live_skill_root(tmp_path / "live")
    workspace = tmp_path / "workspace"
    artifacts_dir = tmp_path / "artifacts"

    provider = build_full_chain_script()
    runtime = make_runtime(artifacts_dir, provider)
    nodes = make_nodes()

    outcome = run_request_trial(
        runtime=runtime,
        scenario=_build_scenario_for_smoke(),
        nodes=nodes,
        live_skill_root=live,
        workspace_dir=workspace,
        patch=None,
        request_id="R-control-1",
    )

    assert outcome.success is True
    assert outcome.trial_delta_id is None
    assert set(outcome.artifact_paths) == {
        "personalized_user_mining",
        "personalized_copy_generation",
        "personalized_copy_rubric",
    }


# --------------------------------------------------------------------------- #
# Task 06-02-04 — portfolio selection + isolated trial + belief update        #
# --------------------------------------------------------------------------- #


def test_integration_select_trial_buffer_and_update(tmp_path: Path) -> None:
    """End-to-end: select a delta, run an isolated trial, update belief.

    Uses a deterministic ``random.Random`` so the selected delta id is
    stable. Asserts the live skill root is unchanged afterward and the
    final portfolio row carries ``sample_count == 1``.
    """
    live = _build_live_skill_root(tmp_path / "live")
    workspace = tmp_path / "workspace"
    artifacts_dir = tmp_path / "artifacts"

    target_rel = "personalized-copy-generation/SKILL.md"
    original = (live / target_rel).read_text(encoding="utf-8")

    portfolio = [
        DeltaPortfolioRow(
            delta_id="D-INT-1",
            target_skill="personalized-copy-generation",
            function_id="f_user_factor_to_product_hook",
            operation="modify",
            observation="o",
            proposed_change="c",
            evidence_refs=[{"path": "request_42.factor_3.text", "value": None}],
            applicable_surface=["personalized_copy_generation"],
            failure_types=[],
        )
    ]

    selected = select_trial_delta(
        portfolio=portfolio,
        applicable_surface=["personalized_copy_generation"],
        recent_failure_rate=0.0,
        token_budget_pressure=0.0,
        production_pressure=0.0,
        rng=random.Random(7),
    )
    assert selected == "D-INT-1"

    patch = SkillDeltaPatch(
        target_path=target_rel,
        original_text_sha256=sha256_of_text(original),
        replacement_text="# trial-patched prose\n",
    )

    provider = build_full_chain_script()
    runtime = make_runtime(artifacts_dir, provider)

    outcome = run_request_trial(
        runtime=runtime,
        scenario=_build_scenario_for_smoke(),
        nodes=make_nodes(),
        live_skill_root=live,
        workspace_dir=workspace,
        patch=patch,
        request_id="R-INT-1",
        scenario_id="S-INT-1",
    )

    updated = update_after_trial(
        portfolio[0],
        success=outcome.success,
        token_cost_delta=outcome.token_cost_observed,
    )
    assert updated.sample_count == 1
    assert updated.success_count == 1
    assert updated.failure_count == 0
    # Live skill root must remain identical to its pre-trial content.
    assert (live / target_rel).read_text(encoding="utf-8") == original
