from __future__ import annotations

import os

import pytest

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
