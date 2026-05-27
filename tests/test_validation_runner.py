from __future__ import annotations

import json
import os

import pytest

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


class _FakeRuntime:
    def __init__(self, *, provider, output_dir):
        self.output_dir = output_dir

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
