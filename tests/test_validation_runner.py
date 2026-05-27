from __future__ import annotations

import json
import os

import pytest
from pydantic import ValidationError

from seers_harness.evolution.delta_portfolio import DeltaPortfolioRow
from seers_harness.core.errors import ProviderAuthError
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

    record = runner._run_one_request(
        request_id="req/success",
        scenario={"request_id": "req/success"},
        nodes=[],
        provider_factory=lambda: object(),
        request_dir=tmp_path / "req",
        events=[],
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
    assert snapshot["trials"] == [{"trial_id": "req-trial", "status": "succeeded"}]
    assert portfolio[0].sample_count == 1
    assert portfolio[0].success_count == 1


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
    assert portfolio[0].sample_count == 1
    assert portfolio[0].failure_count == 1


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


def test_distill_after_stage1_invalid_artifact_raises(tmp_path):
    stage_dir = tmp_path / "stage1"
    _write_stage1_evidence(stage_dir)
    result = runner.StageResult(
        stage=1,
        passed=True,
        records=[{"request_id": "req-1"}],
        stage_dir=stage_dir,
    )

    with pytest.raises(ValidationError):
        runner._distill_after_stage1(
            stage1_result=result,
            provider_factory=lambda: _DistillProvider({"request_id": "req-1", "deltas": [{}]}),
            current_portfolio=[],
        )


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
