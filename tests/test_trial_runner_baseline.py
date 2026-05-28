from __future__ import annotations

from pathlib import Path

from seers_harness.evolution.trial_runner import (
    SkillDeltaPatch,
    run_request_baseline,
    run_request_trial,
    sha256_of_text,
)
from tests.smoke.scripted_full_chain import (
    build_full_chain_script,
    make_nodes,
    make_runtime,
)
from tests.test_trial_runner import _build_live_skill_root, _build_scenario_for_smoke


def _build_full_live_skill_root(path: Path) -> Path:
    live = _build_live_skill_root(path)
    for skill_name in (
        "generate-copy-candidates",
        "personalized-copy-rubric-judge",
    ):
        skill_dir = live / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            f"# original {skill_name} prose\n",
            encoding="utf-8",
        )
    return live


def test_run_request_baseline_no_patch_returns_outcome(tmp_path: Path) -> None:
    live = _build_full_live_skill_root(tmp_path / "live")
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
    live = _build_full_live_skill_root(tmp_path / "live")
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


def test_run_request_baseline_does_not_emit_trial_events(tmp_path: Path) -> None:
    live = _build_full_live_skill_root(tmp_path / "live")
    runtime = make_runtime(tmp_path / "artifacts", build_full_chain_script())
    events: list[dict] = []

    outcome = run_request_baseline(
        runtime=runtime,
        scenario=_build_scenario_for_smoke(),
        nodes=make_nodes()[:1],
        live_skill_root=live,
        workspace_dir=tmp_path / "baseline-workspace",
        request_id="R-baseline",
        scenario_id="S-baseline",
        events=events,
    )

    assert outcome.success is True
    assert events == []


def test_run_request_trial_sends_patched_skill_prose_to_provider(tmp_path: Path) -> None:
    live = _build_live_skill_root(tmp_path / "live")
    target = live / "discover-personalization-factors/SKILL.md"
    original = target.read_text(encoding="utf-8")
    patched = "# PATCHED trial prose\n\nunique-patched-token\n"
    provider = build_full_chain_script()
    runtime = make_runtime(tmp_path / "trial-artifacts", provider)

    outcome = run_request_trial(
        runtime=runtime,
        scenario=_build_scenario_for_smoke(),
        nodes=make_nodes()[:1],
        live_skill_root=live,
        workspace_dir=tmp_path / "trial-workspace",
        patch=SkillDeltaPatch(
            target_path="discover-personalization-factors/SKILL.md",
            original_text_sha256=sha256_of_text(original),
            replacement_text=patched,
        ),
        request_id="R-trial",
        scenario_id="S-trial",
    )

    assert outcome.success is True
    first_system_message = provider.received_messages[0][0]["content"]
    assert "unique-patched-token" in first_system_message
    assert first_system_message == patched
    assert target.read_text(encoding="utf-8") == original
