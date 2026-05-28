from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from seers_harness.evolution.delta_portfolio import DeltaPortfolioRow
from seers_harness.evolution.portfolio_journal import (
    PortfolioJournalEntry,
    append_journal_entry,
    fold_portfolio_journal,
    read_journal_entries,
)


def _row(delta_id: str = "D-1") -> DeltaPortfolioRow:
    return DeltaPortfolioRow(
        delta_id=delta_id,
        target_skill="current/generate-copy-candidates/SKILL.md",
        change_type="modify_skill",
        observation="o",
        proposed_change="c",
        evidence_refs=[{"path": "p", "value": None}],
        applicable_surface=["generate-copy-candidates"],
        failure_types=[],
    )


def _entry(delta_id: str = "D-1", success: bool = True, token_cost_delta: int = 0) -> PortfolioJournalEntry:
    return PortfolioJournalEntry(
        request_id="R-1",
        delta_id=delta_id,
        success=success,
        token_cost_delta=token_cost_delta,
        behavioral_metric_lift={"m": 0.1},
        ts="2026-05-28T00:00:00Z",
    )


def test_append_journal_entry_atomic(tmp_path) -> None:
    path = tmp_path / "portfolio_journal.jsonl"

    def append_many(worker: int) -> None:
        for i in range(10):
            append_journal_entry(
                path,
                _entry(delta_id="D-1", token_cost_delta=worker * 10 + i),
            )

    with ThreadPoolExecutor(max_workers=20) as pool:
        list(pool.map(append_many, range(20)))

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 200
    assert len(read_journal_entries(path)) == 200


def test_fold_portfolio_journal_replays_in_order(tmp_path) -> None:
    path = tmp_path / "portfolio_journal.jsonl"
    for entry in (
        _entry(success=True, token_cost_delta=10),
        _entry(success=False, token_cost_delta=20),
        _entry(success=True, token_cost_delta=-3),
    ):
        append_journal_entry(path, entry)

    folded = fold_portfolio_journal(path, [_row()])

    assert folded[0].sample_count == 3
    assert folded[0].success_count == 2
    assert folded[0].failure_count == 1
    assert folded[0].token_cost_delta_sum == 27


def test_fold_portfolio_journal_missing_journal_returns_original(tmp_path) -> None:
    portfolio = [_row()]

    assert fold_portfolio_journal(tmp_path / "missing.jsonl", portfolio) == portfolio


def test_fold_portfolio_journal_unknown_delta_id_skipped(tmp_path) -> None:
    path = tmp_path / "portfolio_journal.jsonl"
    append_journal_entry(path, _entry(delta_id="D-missing", success=True))

    folded = fold_portfolio_journal(path, [_row("D-1")])

    assert folded[0].sample_count == 0


def test_journal_entry_extra_fields_forbidden() -> None:
    payload = _entry().model_dump()
    payload["extra"] = "nope"

    with pytest.raises(ValidationError):
        PortfolioJournalEntry.model_validate(payload)
