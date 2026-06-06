"""Batch-level production traffic exploration assignment."""

from __future__ import annotations

import random as _random_module
from dataclasses import dataclass
from typing import Sequence

from seers_harness.evolution.delta_portfolio import (
    DeltaPortfolioRow,
    ExplorationDecision,
    NoTrialReason,
    select_trial_delta,
)


@dataclass(frozen=True)
class ExplorationAssignment:
    """One formal or delta-trial assignment for a production batch."""

    request_id: str
    original_request_id: str
    delta_id: str | None = None
    decision: ExplorationDecision | None = None
    execution_id: str | None = None

    @property
    def is_trial(self) -> bool:
        return self.delta_id is not None

    @property
    def run_id(self) -> str:
        """Unique id for output directories and dashboards."""
        return self.execution_id or self.request_id


def assign_exploration_slots(
    *,
    request_ids: Sequence[str],
    portfolio: list[DeltaPortfolioRow],
    applicable_surface: list[str],
    target_skills: Sequence[str] | None,
    exploration_rate: float,
    trial_slots: int = 1,
    rng: _random_module.Random | None = None,
) -> list[ExplorationAssignment]:
    """Route a bounded subset of this production wave through delta skills."""
    if rng is None:
        rng = _random_module.Random()
    normal = [
        ExplorationAssignment(request_id=rid, original_request_id=rid)
        for rid in request_ids
    ]
    if not normal:
        return []
    slot_budget = max(0, int(trial_slots))
    if slot_budget <= 0:
        return normal

    decision = select_trial_delta(
        portfolio,
        applicable_surface=applicable_surface,
        target_skills=target_skills,
        rng=rng,
    )
    if not decision.should_trial or decision.selected_delta_id is None:
        first = normal[0]
        normal[0] = ExplorationAssignment(
            request_id=first.request_id,
            original_request_id=first.original_request_id,
            decision=decision,
        )
        return normal

    blocked_reason: NoTrialReason | None = None
    baseline_slots = max(0, len(normal) - 1)
    if baseline_slots <= 0:
        blocked_reason = "no_baseline_reference"
    elif exploration_rate <= 0.0 or rng.random() > min(1.0, exploration_rate):
        blocked_reason = "exploration_rate_skip"
    if blocked_reason is not None:
        first = normal[0]
        normal[0] = ExplorationAssignment(
            request_id=first.request_id,
            original_request_id=first.original_request_id,
            decision=_blocked_decision(decision, blocked_reason),
        )
        return normal

    slot_budget = min(slot_budget, baseline_slots)
    selected_offsets = sorted(rng.sample(range(len(normal)), slot_budget))
    assignments = list(normal)
    for slot_offset, assignment_index in enumerate(selected_offsets):
        if slot_offset == 0:
            slot_decision = decision
        else:
            decision = select_trial_delta(
                portfolio,
                applicable_surface=applicable_surface,
                target_skills=target_skills,
                rng=rng,
            )
            if not decision.should_trial or decision.selected_delta_id is None:
                break
            slot_decision = decision
        base_assignment = normal[assignment_index]
        assignments[assignment_index] = ExplorationAssignment(
            request_id=base_assignment.request_id,
            original_request_id=base_assignment.original_request_id,
            delta_id=slot_decision.selected_delta_id,
            decision=slot_decision,
            execution_id=(
                f"trial:{slot_decision.selected_delta_id}:"
                f"{base_assignment.request_id}:online"
            ),
        )
    return assignments


def _blocked_decision(
    decision: ExplorationDecision,
    reason: NoTrialReason,
) -> ExplorationDecision:
    """Convert an algorithmic trial intent into an actual no-trial record."""
    return ExplorationDecision(
        should_trial=False,
        selected_delta_id=None,
        eligible_delta_count=decision.eligible_delta_count,
        trigger_reason=None,
        no_trial_reason=reason,
        posterior_samples=decision.posterior_samples,
    )
