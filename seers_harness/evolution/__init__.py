"""Evolution surface — typed delta contracts, trials, and live promotion.

Public exports mirror the contracts that ``tools/evolution_tools.py``,
production traffic exploration, and live-promotion rollback code read and
write.
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
from seers_harness.evolution.live_promotion import (
    PromotionResult,
    promote_ready_deltas,
    restore_from_promotion_manifest,
)
from seers_harness.evolution.promotion_smoke import build_promotion_smoke_report
from seers_harness.evolution.scheduler import (
    DistillationScheduler,
    EvolutionBudgetPolicy,
    ExplorationPlanner,
    PortfolioCoordinator,
)

__all__ = [
    "DeltaDistillationArtifact",
    "DeltaOperation",
    "DeltaPortfolioRow",
    "DeltaProposal",
    "DeltaStatus",
    "DistillationScheduler",
    "EvolutionBudgetPolicy",
    "ExplorationPlanner",
    "PortfolioCoordinator",
    "PromotionResult",
    "TrajectoryRecord",
    "belief_mean",
    "buffer_trajectory",
    "build_promotion_smoke_report",
    "load_portfolio_jsonl",
    "promote_ready_deltas",
    "restore_from_promotion_manifest",
    "sediment_trajectories",
    "select_trial_delta",
    "trajectory_signature",
    "update_after_trial",
    "write_portfolio_jsonl",
]
