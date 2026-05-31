"""Evolution surface — typed delta contracts and portfolio bookkeeping.

Phase 6 keeps evolution as data, not live skill mutation. Public exports
mirror the contracts that ``tools/evolution_tools.py`` and any future
trial/sedimentation code will read and write.
"""

from seers_harness.evolution.delta_portfolio import (
    DeltaDistillationArtifact,
    DeltaOperation,
    DeltaPortfolioRow,
    DeltaProposal,
    DeltaStatus,
    TrajectoryRecord,
    belief_mean,
    buffer_trajectory,
    load_portfolio_jsonl,
    sediment_trajectories,
    select_trial_delta,
    trajectory_signature,
    update_after_trial,
    write_portfolio_jsonl,
)
from seers_harness.evolution.promotion_smoke import build_promotion_smoke_report

__all__ = [
    "DeltaDistillationArtifact",
    "DeltaOperation",
    "DeltaPortfolioRow",
    "DeltaProposal",
    "DeltaStatus",
    "TrajectoryRecord",
    "belief_mean",
    "buffer_trajectory",
    "build_promotion_smoke_report",
    "load_portfolio_jsonl",
    "sediment_trajectories",
    "select_trial_delta",
    "trajectory_signature",
    "update_after_trial",
    "write_portfolio_jsonl",
]
