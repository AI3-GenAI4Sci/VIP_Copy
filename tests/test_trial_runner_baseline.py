from __future__ import annotations

from pathlib import Path

from seers_harness.evolution.trial_runner import run_request_baseline
from tests.smoke.scripted_full_chain import (
    build_full_chain_script,
    make_nodes,
    make_runtime,
)
from tests.test_trial_runner import _build_live_skill_root, _build_scenario_for_smoke


def test_run_request_baseline_no_patch_returns_outcome(tmp_path: Path) -> None:
    live = _build_live_skill_root(tmp_path / "live")
    runtime = make_runtime(tmp_path / "artifacts", build_full_chain_script())

    outcome = run_request_baseline(
        runtime=runtime,
        scenario=_build_scenario_for_smoke(),
        nodes=make_nodes(),
        live_skill_root=live,
        workspace_dir=tmp_path / "baseline-workspace",
        request_id="R-baseline",
        scenario_id="S-baseline",
    )

    assert outcome.success is True
    assert outcome.trial_delta_id is None
    assert set(outcome.artifact_paths) == {
        "factor_discovery",
        "copy_generation",
        "personalized_copy_rubric",
    }
    assert outcome.tool_call_count == 6


def test_run_request_baseline_does_not_modify_live_skill_root(tmp_path: Path) -> None:
    live = _build_live_skill_root(tmp_path / "live")
    target = live / "discover-personalization-factors/SKILL.md"
    before = target.read_text(encoding="utf-8")
    runtime = make_runtime(tmp_path / "artifacts", build_full_chain_script())

    run_request_baseline(
        runtime=runtime,
        scenario=_build_scenario_for_smoke(),
        nodes=make_nodes(),
        live_skill_root=live,
        workspace_dir=tmp_path / "baseline-workspace",
        request_id="R-baseline",
        scenario_id="S-baseline",
    )

    assert target.read_text(encoding="utf-8") == before
