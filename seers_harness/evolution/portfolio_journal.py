"""Append-only portfolio journal and single-thread fold helpers."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from seers_harness.evolution.delta_portfolio import (
    DeltaPortfolioRow,
    update_after_trial,
)


class PortfolioJournalEntry(BaseModel):
    request_id: str
    delta_id: str
    success: bool
    baseline_mean_rubric_score: float = 0.0
    trial_mean_rubric_score: float = 0.0
    score_delta: float = 0.0
    token_cost_delta: int = 0
    behavioral_metric_lift: dict[str, float] = Field(default_factory=dict)
    ts: str = ""

    model_config = {"extra": "forbid"}


def append_journal_entry(journal_path: Path | str, entry: PortfolioJournalEntry) -> None:
    path = Path(journal_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(entry.model_dump_json())
        f.write("\n")


def read_journal_entries(journal_path: Path | str) -> list[PortfolioJournalEntry]:
    path = Path(journal_path)
    if not path.exists():
        return []
    entries: list[PortfolioJournalEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(PortfolioJournalEntry.model_validate_json(line))
    return entries


def fold_portfolio_journal(
    journal_path: Path | str,
    portfolio: list[DeltaPortfolioRow],
) -> list[DeltaPortfolioRow]:
    entries = read_journal_entries(journal_path)
    return fold_portfolio_entries(entries, portfolio)


def fold_portfolio_entries(
    entries: list[PortfolioJournalEntry],
    portfolio: list[DeltaPortfolioRow],
) -> list[DeltaPortfolioRow]:
    if not entries:
        return portfolio

    folded = list(portfolio)
    index_by_delta_id = {row.delta_id: index for index, row in enumerate(folded)}
    for entry in entries:
        index = index_by_delta_id.get(entry.delta_id)
        if index is None:
            continue
        folded[index] = update_after_trial(
            folded[index],
            success=entry.success,
            token_cost_delta=entry.token_cost_delta,
        )
    return folded
