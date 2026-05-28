from __future__ import annotations

import json
import os
import threading

import pytest
from pydantic import ValidationError

from seers_harness.evolution.delta_portfolio import DeltaPortfolioRow
from seers_harness.core.errors import ProviderAuthError
from seers_harness.evolution.portfolio_journal import read_journal_entries
from seers_harness.validation import runner


def test_env_file_overrides_existing_env(monkeypatch, tmp_path):
    env_file = tmp_path / "runner.env"
    env_file.write_text("FOO=new\n", encoding="utf-8")
    monkeypatch.setenv("FOO", "old")

    assert runner._load_env_file(env_file) == 1
    assert os.environ["FOO"] == "new"


def test_env_file_does_not_log_values(monkeypatch, tmp_path, capsys):
    secret = "sk-secret-1234abcd"
    env_file = tmp_path / "runner.env"
    env_file.write_text(f"DEEPSEEK_API_KEY={secret}\n", encoding="utf-8")

    def fake_run(**kwargs):
        return 0

    monkeypatch.setattr(runner, "run", fake_run)

    assert runner.main(["--env-file", str(env_file), "--stage", "1"]) == 0
    captured = capsys.readouterr()

    assert secret not in captured.err
    assert "loaded 1 keys from" in captured.err
    assert "suffix=****abcd" in captured.err


def test_env_file_handles_comments_and_blank(monkeypatch, tmp_path):
    env_file = tmp_path / "runner.env"
    env_file.write_text("\n# comment\nFOO=bar\nNO_EQUALS\n", encoding="utf-8")
    monkeypatch.delenv("FOO", raising=False)

    assert runner._load_env_file(env_file) == 1
    assert os.environ["FOO"] == "bar"


def test_env_file_missing_raises(tmp_path):
    with pytest.raises(RuntimeError, match="--env-file path not found"):
        runner._load_env_file(tmp_path / "missing.env")


def test_env_file_no_shell_expansion(monkeypatch, tmp_path):
    env_file = tmp_path / "runner.env"
    env_file.write_text("BAR=$FOO\n", encoding="utf-8")
    monkeypatch.setenv("FOO", "expanded")
    monkeypatch.delenv("BAR", raising=False)

    assert runner._load_env_file(env_file) == 1
    assert os.environ["BAR"] == "$FOO"


def test_trial_rng_seed_reads_env(monkeypatch):
    monkeypatch.setenv("SEERS_TRIAL_RNG_SEED", "7")

    seeded = runner._make_trial_rng()

    assert seeded.random() == runner.random.Random(7).random()


def _valid_delta_row(
    *,
    delta_id: str = "D-test",
    target_skill: str = "current/test-skill/SKILL.md",
    change_type: str = "modify_skill",
    proposed_change: str = "replacement skill text",
) -> DeltaPortfolioRow:
    return DeltaPortfolioRow(
        delta_id=delta_id,
        target_skill=target_skill,
        change_type=change_type,
        observation="copy generation needs tighter anchoring",
        proposed_change=proposed_change,
        evidence_refs=[{"path": "factor_discovery.factors.0", "value": None}],
        applicable_surface=["copy_generation"],
        failure_types=["weak_anchor"],
    )


def _write_live_skill_root(tmp_path, *, target: str = "current/test-skill/SKILL.md"):
    live_skill_root = tmp_path / "workflow-skills"
    target_path = live_skill_root / target
    target_path.parent.mkdir(parents=True, exist_ok=True)
    original = "---\nname: test-skill\n---\n\nOriginal skill text\n"
    target_path.write_text(original, encoding="utf-8")
    return live_skill_root, target, original


def _read_snapshot(request_dir):
    return json.loads((request_dir / "evolution_snapshot.json").read_text(encoding="utf-8"))


class _FakeRuntime:
    def __init__(self, *, provider, output_dir):
        self.output_dir = output_dir
        self.trace = []

    def run_request(self, *, scenario, nodes):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        factor = self.output_dir / "factor.json"
        copy = self.output_dir / "copy.json"
        rubric = self.output_dir / "rubric.json"
        factor.write_text(
            json.dumps(
                {
                    "factors": [
                        {
                            "factor_id": "f1",
                            "user_side_signal": "compact",
                            "transferable_disposition": "prefers short copy",
                            "covers_product_ids": ["p1"],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        copy.write_text(
            json.dumps(
                {
                    "candidates": [
                        {
                            "candidate_id": "c1",
                            "product_id": "p1",
                            "text": "Short copy",
                            "source_factor_id": "f1",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        rubric.write_text(
            json.dumps(
                {
                    "judgments": [
                        {
                            "candidate_id": "c1",
                            "candidate_index": 0,
                            "product_id": "p1",
                            "copy_text": "Short copy",
                            "factor_id": "f1",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return {
            "factor_discovery": factor,
            "copy_generation": copy,
            "personalized_copy_rubric": rubric,
        }


class _TrialFailingRuntime(_FakeRuntime):
    def run_request(self, *, scenario, nodes):
        if "trial_workspace" in str(self.output_dir):
            raise AssertionError("trial branch failed")
        return super().run_request(scenario=scenario, nodes=nodes)


class _DistillProvider:
    def __init__(self, artifact):
        self.artifact = artifact

    def generate_with_tools(self, *, node_id, skill_bundle, messages, tools):
        return type(
            "ToolResult",
            (),
            {
                "raw_response_text": "",
                "raw_tool_calls": [
                    {
                        "id": "call-submit",
                        "type": "function",
                        "function": {
                            "name": "submit_delta_distillation_final",
                            "arguments": json.dumps(self.artifact),
                        },
                    }
                ],
                "reasoning_content": "",
                "tool_calls": [
                    {
                        "id": "call-submit",
                        "name": "submit_delta_distillation_final",
                        "arguments": self.artifact,
                    }
                ],
            },
        )()


def _write_stage1_evidence(stage_dir):
    request_dir = stage_dir / "req-1"
    for node_id in (
        "factor_discovery",
        "copy_generation",
        "personalized_copy_rubric",
    ):
        node_dir = request_dir / "evidence" / node_id
        node_dir.mkdir(parents=True, exist_ok=True)
        node_dir.joinpath("tool_calls.jsonl").write_text(
            json.dumps({"name": "submit_final", "arguments": {}}) + "\n",
            encoding="utf-8",
        )
        node_dir.joinpath("usage.json").write_text(
            json.dumps({"total_tokens": 11}), encoding="utf-8"
        )
    request_dir.joinpath("evidence/factor_discovery/artifact.json").write_text(
        json.dumps({"factors": []}), encoding="utf-8"
    )
    request_dir.joinpath("evidence/copy_generation/artifact.json").write_text(
        json.dumps({"candidates": []}), encoding="utf-8"
    )
    request_dir.joinpath("evidence/personalized_copy_rubric/artifact.json").write_text(
        json.dumps({"judgments": []}), encoding="utf-8"
    )
    return request_dir


def _distill_artifact(*, deltas):
    return {"request_id": "req-1", "scenario_id": "scenario-1", "deltas": deltas}


def _distill_delta(delta_id="D-distilled"):
    return {
        "delta_id": delta_id,
        "target_skill": "current/test-skill/SKILL.md",
        "change_type": "modify_skill",
        "observation": "the trajectory missed a reusable anchor",
        "proposed_change": "distilled full replacement text",
        "evidence_refs": [{"path": "factor_discovery.factors.0", "value": None}],
        "applicable_surface": ["copy_generation"],
        "failure_types": ["weak_anchor"],
    }


def test_run_one_request_success_record_has_ok_failure_class(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "WorkflowRuntime", _FakeRuntime)
    live_skill_root, _target, _original = _write_live_skill_root(tmp_path)

    record = runner._run_one_request(
        request_id="req/success",
        scenario={"request_id": "req/success"},
        nodes=[],
        provider_factory=lambda: object(),
        request_dir=tmp_path / "req",
        events=[],
        delta_portfolio=[],
        live_skill_root=live_skill_root,
    )

    assert record["failure_class"] == "ok"


def test_run_stage_fail_record_has_failure_class_from_cause_chain(monkeypatch, tmp_path):
    def raise_auth(**kwargs):
        raise RuntimeError("wrapped") from ProviderAuthError("secret-auth-message")

    monkeypatch.setattr(runner, "_run_one_request", raise_auth)
    monkeypatch.setitem(runner._STAGE_CONFIG, 1, (1, 1))

    result = runner._run_stage(
        stage=1,
        request_ids=["req-auth"],
        scenario_loader=lambda request_id: {"request_id": request_id},
        nodes=[],
        provider_factory=lambda: object(),
        out_dir=tmp_path,
        batch_id="batch-test",
        delta_portfolio=[],
        live_skill_root=tmp_path / "workflow-skills",
    )

    assert result.records[0]["failure_class"] == "auth"


def test_run_one_request_fires_trial_when_portfolio_nonempty(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "WorkflowRuntime", _FakeRuntime)
    live_skill_root, target, original = _write_live_skill_root(tmp_path)
    portfolio = [
        _valid_delta_row(
            delta_id="D-live",
            target_skill=target,
            proposed_change=original + "\nTrial refinement\n",
        )
    ]
    request_dir = tmp_path / "req"

    record = runner._run_one_request(
        request_id="req-trial",
        scenario={"request_id": "req-trial", "scenario_id": "scenario-1"},
        nodes=[],
        provider_factory=lambda: object(),
        request_dir=request_dir,
        events=[],
        delta_portfolio=portfolio,
        live_skill_root=live_skill_root,
    )

    snapshot = _read_snapshot(request_dir)
    assert record["exception"] is None
    assert snapshot["trials"] == [
        {"trial_id": "req-trial", "delta_id": "D-live", "status": "succeeded"},
    ]
    assert record["trial_selected_delta_id"] == "D-live"
    assert read_journal_entries(request_dir.parent / "portfolio_journal.jsonl")


def test_run_one_request_snapshot_records_visible_portfolio(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "WorkflowRuntime", _FakeRuntime)
    monkeypatch.setattr(runner._trial_rng, "random", lambda: 1.0)
    live_skill_root, target, original = _write_live_skill_root(tmp_path)
    portfolio = [
        _valid_delta_row(
            delta_id="D-visible",
            target_skill=target,
            proposed_change=original + "\nVisible portfolio refinement\n",
        )
    ]
    request_dir = tmp_path / "req"

    record = runner._run_one_request(
        request_id="req-visible",
        scenario={"request_id": "req-visible", "scenario_id": "scenario-1"},
        nodes=[],
        provider_factory=lambda: object(),
        request_dir=request_dir,
        events=[],
        delta_portfolio=portfolio,
        live_skill_root=live_skill_root,
    )

    snapshot = _read_snapshot(request_dir)
    assert record["exception"] is None
    assert record["trial_selected_delta_id"] is None
    assert snapshot["delta_portfolio_before"] == ["D-visible"]
    assert snapshot["delta_portfolio_after"] == ["D-visible"]
    assert snapshot["trials"] == []


def test_run_one_request_skips_trial_when_portfolio_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "WorkflowRuntime", _FakeRuntime)
    live_skill_root, _target, _original = _write_live_skill_root(tmp_path)
    request_dir = tmp_path / "req"

    record = runner._run_one_request(
        request_id="req-empty",
        scenario={"request_id": "req-empty"},
        nodes=[],
        provider_factory=lambda: object(),
        request_dir=request_dir,
        events=[],
        delta_portfolio=[],
        live_skill_root=live_skill_root,
    )

    assert record["exception"] is None
    assert _read_snapshot(request_dir)["trials"] == []


def test_run_one_request_trial_failure_does_not_abort_host(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "WorkflowRuntime", _TrialFailingRuntime)
    live_skill_root, target, original = _write_live_skill_root(tmp_path)
    portfolio = [
        _valid_delta_row(
            target_skill=target,
            proposed_change=original + "\nTrial branch\n",
        )
    ]
    request_dir = tmp_path / "req"

    record = runner._run_one_request(
        request_id="req-trial-fail",
        scenario={"request_id": "req-trial-fail"},
        nodes=[],
        provider_factory=lambda: object(),
        request_dir=request_dir,
        events=[],
        delta_portfolio=portfolio,
        live_skill_root=live_skill_root,
    )

    snapshot = _read_snapshot(request_dir)
    assert record["exception"] is None
    assert snapshot["trials"][0]["status"] == "failed"
    assert snapshot["trials"][0]["exception_class"] == "AssertionError"
    assert portfolio[0].sample_count == 0
    entries = read_journal_entries(request_dir.parent / "portfolio_journal.jsonl")
    assert len(entries) == 1
    assert entries[0].success is False


def test_run_one_request_skips_non_modify_skill_delta(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "WorkflowRuntime", _FakeRuntime)
    live_skill_root, target, _original = _write_live_skill_root(tmp_path)
    portfolio = [_valid_delta_row(target_skill=target, change_type="add_skill")]
    request_dir = tmp_path / "req"

    record = runner._run_one_request(
        request_id="req-add-skill",
        scenario={"request_id": "req-add-skill"},
        nodes=[],
        provider_factory=lambda: object(),
        request_dir=request_dir,
        events=[],
        delta_portfolio=portfolio,
        live_skill_root=live_skill_root,
    )

    assert record["exception"] is None
    assert _read_snapshot(request_dir)["trials"] == []
    assert portfolio[0].sample_count == 0


def test_patch_from_portfolio_row_warns_on_non_modify_skill(tmp_path, capsys):
    live_skill_root, target, _original = _write_live_skill_root(tmp_path)
    row = _valid_delta_row(target_skill=target, change_type="add_skill")

    patch = runner._patch_from_portfolio_row(row, live_skill_root)
    captured = capsys.readouterr()

    assert patch is None
    assert "trial_skipped" in captured.err
    assert "non_modify_skill" in captured.err
    assert "D-test" in captured.err


def test_run_one_request_skips_drifted_target_path(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "WorkflowRuntime", _FakeRuntime)
    live_skill_root, _target, _original = _write_live_skill_root(tmp_path)
    portfolio = [_valid_delta_row(target_skill="current/missing/SKILL.md")]
    request_dir = tmp_path / "req"

    record = runner._run_one_request(
        request_id="req-drifted",
        scenario={"request_id": "req-drifted"},
        nodes=[],
        provider_factory=lambda: object(),
        request_dir=request_dir,
        events=[],
        delta_portfolio=portfolio,
        live_skill_root=live_skill_root,
    )

    assert record["exception"] is None
    assert _read_snapshot(request_dir)["trials"] == []
    assert portfolio[0].sample_count == 0


def test_patch_from_portfolio_row_warns_on_unresolvable_target(tmp_path, capsys):
    live_skill_root, _target, _original = _write_live_skill_root(tmp_path)
    row = _valid_delta_row(target_skill="current/missing/SKILL.md")

    patch = runner._patch_from_portfolio_row(row, live_skill_root)
    captured = capsys.readouterr()

    assert patch is None
    assert "trial_skipped" in captured.err
    assert "target_unresolvable" in captured.err
    assert "current/missing/SKILL.md" in captured.err


def test_patch_from_portfolio_row_resolves_canonical_path(tmp_path, capsys):
    live_skill_root, target, _original = _write_live_skill_root(tmp_path)
    row = _valid_delta_row(target_skill=target)

    patch = runner._patch_from_portfolio_row(row, live_skill_root)
    captured = capsys.readouterr()

    assert patch is not None
    assert patch.target_path == target
    assert "trial_skipped" not in captured.err


def test_distill_after_stage1_with_recording_provider(tmp_path):
    stage_dir = tmp_path / "stage1"
    _write_stage1_evidence(stage_dir)
    result = runner.StageResult(
        stage=1,
        passed=True,
        records=[{"request_id": "req-1"}],
        stage_dir=stage_dir,
    )

    portfolio = runner._distill_after_stage1(
        stage1_result=result,
        provider_factory=lambda: _DistillProvider(
            _distill_artifact(deltas=[_distill_delta("D-1"), _distill_delta("D-2")])
        ),
        current_portfolio=[],
    )

    assert [row.delta_id for row in portfolio] == ["D-1", "D-2"]


def test_distill_persists_evidence_to_disk(tmp_path):
    stage_dir = tmp_path / "stage1"
    request_dir = _write_stage1_evidence(stage_dir)
    result = runner.StageResult(
        stage=1,
        passed=True,
        records=[{"request_id": "req-1"}],
        stage_dir=stage_dir,
    )

    runner._distill_after_stage1(
        stage1_result=result,
        provider_factory=lambda: _DistillProvider(
            _distill_artifact(deltas=[_distill_delta("D-1")])
        ),
        current_portfolio=[],
    )

    evidence_dir = request_dir / "distill_evidence" / "distill_after_stage1"
    assert (evidence_dir / "messages.jsonl").read_text(encoding="utf-8").strip()
    assert (evidence_dir / "tool_calls.jsonl").read_text(encoding="utf-8").strip()
    assert (evidence_dir / "artifact.json").exists()
    assert (evidence_dir / "usage.json").exists()


def test_distill_evidence_flush_failure_does_not_mask_artifact(
    monkeypatch, tmp_path, capsys
):
    stage_dir = tmp_path / "stage1"
    _write_stage1_evidence(stage_dir)
    result = runner.StageResult(
        stage=1,
        passed=True,
        records=[{"request_id": "req-1"}],
        stage_dir=stage_dir,
    )

    def raise_flush(*_args, **_kwargs):
        raise PermissionError("distill evidence denied")

    monkeypatch.setattr(runner, "flush_evidence", raise_flush)

    portfolio = runner._distill_after_stage1(
        stage1_result=result,
        provider_factory=lambda: _DistillProvider(
            _distill_artifact(deltas=[_distill_delta("D-1")])
        ),
        current_portfolio=[],
    )
    captured = capsys.readouterr()

    assert [row.delta_id for row in portfolio] == ["D-1"]
    assert "distill_evidence flush failed" in captured.err
    assert "PermissionError" in captured.err


def test_distill_after_stage1_empty_proposals_yields_empty_portfolio(tmp_path):
    stage_dir = tmp_path / "stage1"
    _write_stage1_evidence(stage_dir)
    result = runner.StageResult(
        stage=1,
        passed=True,
        records=[{"request_id": "req-1"}],
        stage_dir=stage_dir,
    )

    portfolio = runner._distill_after_stage1(
        stage1_result=result,
        provider_factory=lambda: _DistillProvider(_distill_artifact(deltas=[])),
        current_portfolio=[],
    )

    assert portfolio == []


def test_distill_after_stage1_invalid_artifact_raises(monkeypatch, tmp_path):
    from seers_harness.agentic import tool_loop

    stage_dir = tmp_path / "stage1"
    _write_stage1_evidence(stage_dir)
    result = runner.StageResult(
        stage=1,
        passed=True,
        records=[{"request_id": "req-1"}],
        stage_dir=stage_dir,
    )

    def fake_run_skill_via_tools(**kwargs):
        return type(
            "ToolLoopResult",
            (),
            {"artifact": {"request_id": "req-1", "deltas": [{}]}},
        )()

    monkeypatch.setattr(tool_loop, "run_skill_via_tools", fake_run_skill_via_tools)

    with pytest.raises(ValidationError):
        runner._distill_after_stage1(
            stage1_result=result,
            provider_factory=lambda: object(),
            current_portfolio=[],
        )


class _AlwaysTrialSignalWindow:
    def failure_rate(self):
        return 0.0

    def token_pressure(self, *, budget_per_request):
        return 0.0

    def record_baseline_outcome(self, *, success, total_tokens):
        self.last = {"success": success, "total_tokens": total_tokens}


class _SuppressTrialSignalWindow(_AlwaysTrialSignalWindow):
    def failure_rate(self):
        return 1.0


def test_select_trial_delta_gate_skips_when_signals_high(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(runner, "WorkflowRuntime", _FakeRuntime)
    monkeypatch.setattr(runner, "_signal_window", _SuppressTrialSignalWindow())
    live_skill_root, target, _original = _write_live_skill_root(tmp_path)
    portfolio = [_valid_delta_row(delta_id="D-skip", target_skill=target)]

    record = runner._run_one_request(
        request_id="req-skip",
        scenario={"request_id": "req-skip"},
        nodes=[],
        provider_factory=lambda: object(),
        request_dir=tmp_path / "req-skip",
        events=[],
        delta_portfolio=portfolio,
        live_skill_root=live_skill_root,
        journal_path=tmp_path / "portfolio_journal.jsonl",
        max_concurrent=20,
    )

    assert record["exception"] is None
    assert record["trial_selected_delta_id"] is None
    assert not (tmp_path / "portfolio_journal.jsonl").exists()
    assert "trial_skipped" not in capsys.readouterr().err
    snapshot = _read_snapshot(tmp_path / "req-skip")
    assert snapshot["trial_gate"]["selected_delta_id"] is None
    assert snapshot["trial_gate"]["eligible_delta_count"] == 1
    assert snapshot["trial_gate"]["trial_prob"] == 0.0


def test_select_trial_delta_gate_fires_paired_when_signals_low(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "WorkflowRuntime", _FakeRuntime)
    monkeypatch.setattr(runner, "_signal_window", _AlwaysTrialSignalWindow())
    live_skill_root, target, original = _write_live_skill_root(tmp_path)
    portfolio = [
        _valid_delta_row(
            delta_id="D-live",
            target_skill=target,
            proposed_change=original + "\nTrial refinement\n",
        )
    ]
    journal_path = tmp_path / "portfolio_journal.jsonl"

    record = runner._run_one_request(
        request_id="req-trial",
        scenario={"request_id": "req-trial", "scenario_id": "scenario-1"},
        nodes=[],
        provider_factory=lambda: object(),
        request_dir=tmp_path / "req-trial",
        events=[],
        delta_portfolio=portfolio,
        live_skill_root=live_skill_root,
        journal_path=journal_path,
        max_concurrent=20,
    )

    assert record["exception"] is None
    assert record["trial_selected_delta_id"] == "D-live"
    assert (tmp_path / "req-trial/trial_workspace/_baseline").exists()
    assert (tmp_path / "req-trial/trial_workspace/D-live").exists()
    entries = read_journal_entries(journal_path)
    assert len(entries) == 1
    assert entries[0].delta_id == "D-live"
    assert entries[0].behavioral_metric_lift
    assert "val01_pass" in entries[0].behavioral_metric_lift
    snapshot = _read_snapshot(tmp_path / "req-trial")
    assert snapshot["trial_gate"]["selected_delta_id"] == "D-live"
    assert snapshot["trial_gate"]["eligible_delta_count"] == 1
    assert snapshot["trial_gate"]["trial_prob"] == 1.0


def test_fold_portfolio_journal_at_stage_boundary(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "WorkflowRuntime", _FakeRuntime)
    monkeypatch.setattr(runner, "_signal_window", _AlwaysTrialSignalWindow())
    monkeypatch.setitem(runner._STAGE_CONFIG, 2, (1, 1))
    live_skill_root, target, original = _write_live_skill_root(tmp_path)
    portfolio = [
        _valid_delta_row(
            delta_id="D-stage",
            target_skill=target,
            proposed_change=original + "\nTrial refinement\n",
        )
    ]

    result = runner._run_stage(
        stage=2,
        request_ids=["req-stage"],
        scenario_loader=lambda rid: {"request_id": rid, "scenario_id": "scenario-1"},
        nodes=[],
        provider_factory=lambda: object(),
        out_dir=tmp_path,
        batch_id="batch-test",
        delta_portfolio=portfolio,
        live_skill_root=live_skill_root,
    )

    assert result.passed is True
    assert portfolio[0].sample_count == 1


def test_run_drives_distill_only_after_stage1_passes(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "_STAGE_CONFIG", {1: (1, 1)})
    distill_calls = []

    def fake_distill(**kwargs):
        distill_calls.append(kwargs["stage1_result"].stage)
        return kwargs["current_portfolio"]

    monkeypatch.setattr(runner, "_distill_after_stage1", fake_distill, raising=False)

    def failing_stage(**kwargs):
        return runner.StageResult(
            stage=kwargs["stage"],
            passed=False,
            records=[{"request_id": "req-1", "exception": "boom"}],
            stage_dir=tmp_path / "stage1",
        )

    monkeypatch.setattr(runner, "_run_stage", failing_stage)
    assert runner.run(
        stages=(1,),
        out_dir=tmp_path / "failing",
        request_ids=["req-1"],
        scenario_loader=lambda rid: {"request_id": rid},
        nodes_factory=lambda: [],
        provider_factory=lambda: object(),
    ) == 1
    assert distill_calls == []

    def passing_stage(**kwargs):
        return runner.StageResult(
            stage=kwargs["stage"],
            passed=True,
            records=[{"request_id": "req-1"}],
            stage_dir=tmp_path / "stage1",
        )

    monkeypatch.setattr(runner, "_run_stage", passing_stage)
    assert runner.run(
        stages=(1,),
        out_dir=tmp_path / "passing",
        request_ids=["req-1"],
        scenario_loader=lambda rid: {"request_id": rid},
        nodes_factory=lambda: [],
        provider_factory=lambda: object(),
    ) == 0
    assert distill_calls == [1]


def test_stage3_only_bootstraps_distilled_portfolio_from_current_trace(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(runner, "WorkflowRuntime", _FakeRuntime)
    live_skill_root, target, original = _write_live_skill_root(tmp_path)
    monkeypatch.setattr(runner, "LIVE_SKILL_ROOT", live_skill_root)
    distilled_row = _valid_delta_row(
        delta_id="D-bootstrap",
        target_skill=target,
        proposed_change=original + "\nBootstrap trial refinement\n",
    )
    distill_calls = []
    stage_portfolios = []

    def fake_distill(**kwargs):
        distill_calls.append(kwargs["stage1_result"].stage)
        return [distilled_row]

    def fake_run_stage(**kwargs):
        stage_portfolios.append(list(kwargs["delta_portfolio"]))
        return runner.StageResult(
            stage=kwargs["stage"],
            passed=True,
            records=[{"request_id": "req-stage3"}],
            stage_dir=tmp_path / "stage3",
        )

    monkeypatch.setattr(runner, "_distill_after_stage1", fake_distill, raising=False)
    monkeypatch.setattr(runner, "_run_stage", fake_run_stage)

    assert runner.run(
        stages=(3,),
        out_dir=tmp_path / "stage3-only",
        request_ids=["req-stage3"],
        scenario_loader=lambda rid: {"request_id": rid, "scenario_id": rid},
        nodes_factory=lambda: [],
        provider_factory=lambda: object(),
    ) == 0

    assert distill_calls == [1]
    assert [row.delta_id for row in stage_portfolios[0]] == ["D-bootstrap"]


def test_stage3_fail_fast_drains_inflight(monkeypatch, tmp_path):
    """D8-G-WR-01: Stage 3 fail-fast must drain in-flight futures.

    Setup: c=20 / n=20 with a scripted ``_run_one_request`` substitute
    such that ONE request (rid-04) raises ``ProviderAuthError`` as soon
    as it starts (triggering fail-fast in the as_completed loop of the
    main thread). The other 19 requests block on a ``threading.Event``.
    The main thread, after capturing the auth failure, drains the
    remaining in-flight futures: it cancels them (best-effort), then
    walks ``as_completed(remaining)`` waiting for each to finish.

    The test releases the event AFTER fail-fast is observed so the
    in-flight workers complete naturally. Cancelled (= never started)
    futures must NOT contribute records; in-flight completed futures
    DO contribute records. The drain path must populate
    ``failure_class`` per plan 08-03 and must NOT overwrite the
    original ``failure_exc`` (the auth error stays the canonical
    cause).
    """
    # Stage config narrows to a small, deterministic n.  Use n=6,
    # concurrency=6 — enough to assert the multi-future drain path
    # without slowing the test suite.  The bug surfaces identically at
    # any n>=2 (one fail-fast trigger plus >=1 drained future).
    monkeypatch.setitem(runner._STAGE_CONFIG, 3, (6, 6))

    fail_fast_observed = threading.Event()
    release_inflight = threading.Event()

    def scripted_run_one_request(*, request_id, **_kwargs):
        # rid-04 is the fail-fast trigger.  It raises immediately on
        # entry — no waiting for the release event.  This guarantees
        # the as_completed loop in the main thread sees the auth
        # exception while the other 5 futures are still blocked.
        if request_id == "rid-04":
            raise ProviderAuthError("scripted-auth-failure")
        # Other rids: block until the test releases them.  Once the
        # main thread observes fail-fast and enters the drain loop,
        # the test releases the event so each blocked future returns
        # a normal success record.  These records MUST be appended
        # by the drain branch.
        if not release_inflight.wait(timeout=10.0):
            raise RuntimeError(f"release_inflight not set in {request_id}")
        return {
            "node_id": runner._safe_request_dirname(request_id),
            "request_id": request_id,
            "artifact": None,
            "reflow_triggered": False,
            "trial_selected_delta_id": None,
            "exception": None,
            "failure_class": "ok",
        }

    monkeypatch.setattr(runner, "_run_one_request", scripted_run_one_request)

    # Spawn a watcher thread that releases in-flight futures shortly
    # after the as_completed loop starts.  The fail-fast trigger
    # (rid-04) raises as soon as it begins, so the main thread will
    # observe it within milliseconds.  We give it 200 ms then release.
    def _release_after_failfast():
        # Wait until the main thread has had a chance to observe the
        # auth exception.  ThreadPoolExecutor.submit returns futures
        # in the same order, and rid-04 raises immediately, so a
        # short sleep is sufficient.
        import time

        time.sleep(0.2)
        fail_fast_observed.set()
        release_inflight.set()

    releaser = threading.Thread(target=_release_after_failfast, daemon=True)
    releaser.start()

    request_ids = [f"rid-{i:02d}" for i in range(6)]
    result = runner._run_stage(
        stage=3,
        request_ids=request_ids,
        scenario_loader=lambda rid: {"request_id": rid},
        nodes=[],
        provider_factory=lambda: object(),
        out_dir=tmp_path,
        batch_id="batch-test",
        delta_portfolio=[],
        live_skill_root=tmp_path / "workflow-skills",
    )
    releaser.join(timeout=2.0)

    # Acceptance: every submitted future contributes one record.
    # The fail-fast trigger contributes its auth failure record,
    # and the 5 drained in-flight futures contribute their success
    # records.  Cancelled (= never started) futures contribute none
    # — but with 6 workers and 6 submitted requests every future
    # gets a worker so cancellation is a no-op here.
    assert len(result.records) == 6, (
        f"expected 6 records (1 fail-fast + 5 drained), got {len(result.records)}"
    )

    # Exactly one auth failure record exists, and it carries
    # failure_class == "auth" per plan 08-03's 7-enum router.
    auth_records = [r for r in result.records if r.get("failure_class") == "auth"]
    assert len(auth_records) == 1, "expected exactly one auth fail-fast record"
    assert auth_records[0]["request_id"] == "rid-04"
    assert auth_records[0]["exception"] is not None
    assert "scripted-auth-failure" in auth_records[0]["exception"]

    # The 5 drained in-flight futures land as success records (the
    # scripted body returned a normal dict once released).  None of
    # them overwrites the auth record's failure_class.
    success_records = [r for r in result.records if r.get("failure_class") == "ok"]
    assert len(success_records) == 5, (
        f"expected 5 drained-success records, got {len(success_records)}"
    )

    # Stage failed (failure_exc was set on auth path); records-vs-n
    # parity holds (= the WR-01 disk-vs-index fix).
    assert result.passed is False


def test_stage3_fail_fast_drains_inflight_failure_with_class(monkeypatch, tmp_path):
    """A drained in-flight future that raises non-auth must still get
    its own ``failure_class`` per plan 08-03 routing — and must NOT
    overwrite the original auth fail-fast cause on the runner level.

    This complements the success-drain test above: it proves the
    drain branch's ``except BaseException as drain_exc`` arm handles
    non-cancellation exceptions correctly and routes them through
    ``failure_class(drain_exc)`` (not through the D-19 ``classify``
    surface — drain failures never become ``trial_failure``).
    """
    from seers_harness.core.errors import ProviderTransientError

    monkeypatch.setitem(runner._STAGE_CONFIG, 3, (3, 3))

    release = threading.Event()

    def scripted(*, request_id, **_kwargs):
        if request_id == "rid-00":
            # Fail-fast trigger: auth.
            raise ProviderAuthError("primary-auth-cause")
        if not release.wait(timeout=10.0):
            raise RuntimeError(f"release not set in {request_id}")
        if request_id == "rid-01":
            # Drained-and-then-fails: transient.
            raise ProviderTransientError("secondary-transient-cause")
        return {
            "node_id": runner._safe_request_dirname(request_id),
            "request_id": request_id,
            "artifact": None,
            "reflow_triggered": False,
            "trial_selected_delta_id": None,
            "exception": None,
            "failure_class": "ok",
        }

    monkeypatch.setattr(runner, "_run_one_request", scripted)

    def _release_after():
        import time

        time.sleep(0.2)
        release.set()

    releaser = threading.Thread(target=_release_after, daemon=True)
    releaser.start()

    result = runner._run_stage(
        stage=3,
        request_ids=["rid-00", "rid-01", "rid-02"],
        scenario_loader=lambda rid: {"request_id": rid},
        nodes=[],
        provider_factory=lambda: object(),
        out_dir=tmp_path,
        batch_id="batch-test",
        delta_portfolio=[],
        live_skill_root=tmp_path / "workflow-skills",
    )
    releaser.join(timeout=2.0)

    # 3 records total: auth fail-fast, transient drained-failure,
    # one success drained.
    assert len(result.records) == 3
    classes = sorted(r.get("failure_class") for r in result.records)
    assert classes == ["auth", "ok", "transient"]

    # The transient drained-failure carries failure_class="transient"
    # per plan 08-03 router (not "trial_failure"; D-19 routes are
    # forbidden in drain).
    transient_records = [
        r for r in result.records if r.get("failure_class") == "transient"
    ]
    assert len(transient_records) == 1
    assert transient_records[0]["request_id"] == "rid-01"
    assert "secondary-transient-cause" in transient_records[0]["exception"]
    assert result.passed is False


# ---------------------------------------------------------------------------
# Plan 08-10 — D8-G-WR-02 finally best-effort wrapping (test 3 cases)
# ---------------------------------------------------------------------------


class _AuthFailingRuntime(_FakeRuntime):
    """Runtime that raises ProviderAuthError inside ``run_request``.

    Used to verify that finally-block cleanup failures do NOT mask the
    original try-block exception (Python finally anti-pattern guard).
    """

    def run_request(self, *, scenario, nodes):
        raise ProviderAuthError("primary-auth-cause-from-try-block")


def _raise_perm_error(*args, **kwargs):
    raise PermissionError("disk-full-or-permission-denied-cleanup-fault")


def test_finally_writer_failure_does_not_mask_original_flush_evidence(
    monkeypatch, tmp_path, capsys
):
    """Case A: try block raises ProviderAuthError; flush_evidence raises
    PermissionError in finally. Original ProviderAuthError must propagate;
    stderr must contain ``flush_evidence failed for {request_id}``."""
    monkeypatch.setattr(runner, "WorkflowRuntime", _AuthFailingRuntime)
    monkeypatch.setattr(runner, "flush_evidence", _raise_perm_error)
    live_skill_root, _target, _original = _write_live_skill_root(tmp_path)
    request_dir = tmp_path / "req-flush-fail"

    with pytest.raises(ProviderAuthError, match="primary-auth-cause-from-try-block"):
        runner._run_one_request(
            request_id="req-flush-fail-id",
            scenario={"request_id": "req-flush-fail-id"},
            nodes=[],
            provider_factory=lambda: object(),
            request_dir=request_dir,
            events=[],
            delta_portfolio=[],
            live_skill_root=live_skill_root,
        )

    captured = capsys.readouterr()
    assert "flush_evidence failed for req-flush-fail-id" in captured.err
    assert "PermissionError" in captured.err
    # Cleanup-exception message must be redacted via safe_exc, not raw stack.
    # No traceback frames should be printed for the cleanup failure path.
    assert 'File "' not in captured.err.split("flush_evidence failed for")[1].split("\n")[0]


def test_finally_writer_failure_does_not_mask_original_write_snapshot(
    monkeypatch, tmp_path, capsys
):
    """Case B: try block raises ProviderAuthError; write_evolution_snapshot
    raises PermissionError in finally. flush_evidence succeeds. Original
    ProviderAuthError must propagate; stderr must contain
    ``write_evolution_snapshot failed for {request_id}``."""
    monkeypatch.setattr(runner, "WorkflowRuntime", _AuthFailingRuntime)
    monkeypatch.setattr(runner, "write_evolution_snapshot", _raise_perm_error)
    live_skill_root, _target, _original = _write_live_skill_root(tmp_path)
    request_dir = tmp_path / "req-snapshot-fail"

    with pytest.raises(ProviderAuthError, match="primary-auth-cause-from-try-block"):
        runner._run_one_request(
            request_id="req-snapshot-fail-id",
            scenario={"request_id": "req-snapshot-fail-id"},
            nodes=[],
            provider_factory=lambda: object(),
            request_dir=request_dir,
            events=[],
            delta_portfolio=[],
            live_skill_root=live_skill_root,
        )

    captured = capsys.readouterr()
    assert "write_evolution_snapshot failed for req-snapshot-fail-id" in captured.err
    assert "PermissionError" in captured.err


def test_finally_writer_failure_does_not_mask_original_happy_path(
    monkeypatch, tmp_path, capsys
):
    """Case C (happy path): no cleanup failure → stderr contains NEITHER
    ``flush_evidence failed for`` NOR ``write_evolution_snapshot failed for``.
    Confirms the best-effort wrap is silent on the success path."""
    monkeypatch.setattr(runner, "WorkflowRuntime", _FakeRuntime)
    live_skill_root, _target, _original = _write_live_skill_root(tmp_path)
    request_dir = tmp_path / "req-happy"

    record = runner._run_one_request(
        request_id="req-happy-id",
        scenario={"request_id": "req-happy-id"},
        nodes=[],
        provider_factory=lambda: object(),
        request_dir=request_dir,
        events=[],
        delta_portfolio=[],
        live_skill_root=live_skill_root,
    )

    assert record["exception"] is None
    captured = capsys.readouterr()
    assert "flush_evidence failed for" not in captured.err
    assert "write_evolution_snapshot failed for" not in captured.err


def test_build_scratch_csv_resolves_detect_delimiter(tmp_path):
    """Regression: detect_delimiter must be visible at module scope so
    _build_scratch_csv (a sibling function) can call it.

    Earlier shape imported request_preprocessor inside
    _default_scenario_loader's body, which made detect_delimiter a
    function-local in the loader but invisible to _build_scratch_csv —
    the runner crashed at cold-launch with NameError before the first
    DeepSeek request was issued.
    """
    csv_path = tmp_path / "tiny.csv"
    csv_path.write_text(
        "request_id,col1\nr1,a\nr2,b\nr3,c\n",
        encoding="utf-8",
    )
    scratch_path = tmp_path / "scratch.csv"

    chosen = runner._build_scratch_csv(csv_path, scratch_path, limit=2)

    assert chosen == ["r1", "r2"]
    assert scratch_path.exists()
