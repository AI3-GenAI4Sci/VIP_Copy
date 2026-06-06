"""Budget-aware evolution scheduling for production waves."""

from __future__ import annotations

import json
import math
import random as _random_module
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from seers_harness.evolution.delta_portfolio import DeltaPortfolioRow
from seers_harness.evolution.live_promotion import (
    PromotionResult,
    promote_ready_deltas,
)
from seers_harness.evolution.portfolio_journal import (
    fold_portfolio_entries,
    read_journal_entries,
)
from seers_harness.evolution.status_machine import apply_status_transitions
from seers_harness.evolution.traffic_exploration import (
    ExplorationAssignment,
    assign_exploration_slots,
)


def safe_request_dirname(request_id: str) -> str:
    """Make a request or pipeline id safe for use as a directory name."""
    if not isinstance(request_id, str) or not request_id:
        return "req"
    cleaned = request_id.replace("/", "_").replace("\\", "_").replace(":", "_")
    cleaned = cleaned.lstrip(".")
    if not cleaned or cleaned in {".", ".."}:
        return "req"
    return cleaned


@dataclass(frozen=True)
class EvolutionBudgetPolicy:
    """Derive evolution thresholds and trial slots from budget constraints."""

    trial_budget_fraction: float = 0.02
    max_trial_slots: int | None = None
    min_distill_eligible_trajectories: int = 5
    target_distill_calls_per_batch: int = 5
    distill_threshold_override: int | None = None

    def distill_threshold(
        self,
        *,
        eligible_trajectories: int,
        pipeline_count: int = 1,
    ) -> int:
        if self.distill_threshold_override is not None:
            return max(1, int(self.distill_threshold_override))
        allowed_calls = max(1, int(self.target_distill_calls_per_batch))
        effective_pipelines = max(1, int(pipeline_count))
        per_pipeline_budget = max(1, math.ceil(allowed_calls / effective_pipelines))
        derived = math.ceil(max(0, int(eligible_trajectories)) / per_pipeline_budget)
        return max(1, int(self.min_distill_eligible_trajectories), derived)

    def trial_slots(
        self,
        *,
        concurrency: int,
        active_delta_count: int,
        pressure: float = 1.0,
    ) -> int:
        if active_delta_count <= 0 or concurrency <= 0:
            return 0
        fraction = min(1.0, max(0.0, float(self.trial_budget_fraction)))
        scaled = max(0.0, float(pressure)) * fraction * int(concurrency)
        slots = int(math.floor(scaled))
        if scaled > 0.0 and slots == 0:
            slots = 1
        slots = min(slots, int(concurrency))
        if self.max_trial_slots is not None:
            slots = min(slots, max(0, int(self.max_trial_slots)))
        return slots


@dataclass(frozen=True)
class DistillTrajectoryCandidate:
    """One successful reject/hold trajectory eligible for distillation."""

    pipeline_id: str
    request_id: str
    request_dir: Path
    decision_bucket: str
    priority: int


@dataclass(frozen=True)
class DistillBundlePlan:
    """One distillation call planned for a pipeline."""

    pipeline_id: str
    request_dirs: tuple[Path, ...]
    evidence_dir: Path
    reject_count: int = 0
    hold_count: int = 0


@dataclass(frozen=True)
class DistillDeferral:
    """Why a pipeline did not receive a distillation call this wave."""

    pipeline_id: str
    trajectories: int
    threshold: int
    reject_count: int = 0
    hold_count: int = 0
    reason: str = ""


@dataclass(frozen=True)
class DistillPlanningResult:
    plans: tuple[DistillBundlePlan, ...] = ()
    deferrals: tuple[DistillDeferral, ...] = ()


@dataclass(frozen=True)
class ExplorationPlanningResult:
    """Budgeted trial assignments for one concurrency wave."""

    assignments: tuple[ExplorationAssignment, ...]
    trial_slots: int
    active_delta_count: int


@dataclass
class ExplorationPlanner:
    """Plan budgeted delta trial slots for a production wave."""

    policy: EvolutionBudgetPolicy = field(default_factory=EvolutionBudgetPolicy)
    rng: _random_module.Random | None = None

    def plan_wave(
        self,
        *,
        request_ids: Sequence[str],
        portfolio: list[DeltaPortfolioRow],
        applicable_surface: list[str],
        target_skills: Sequence[str] | None,
        pressure: float = 1.0,
    ) -> ExplorationPlanningResult:
        active_count = active_delta_count(
            portfolio,
            applicable_surface=applicable_surface,
            target_skills=target_skills,
        )
        slots = self.policy.trial_slots(
            concurrency=len(request_ids),
            active_delta_count=active_count,
            pressure=pressure,
        )
        assignments = assign_exploration_slots(
            request_ids=request_ids,
            portfolio=portfolio,
            applicable_surface=applicable_surface,
            target_skills=target_skills,
            exploration_rate=1.0,
            trial_slots=slots,
            rng=self.rng,
        )
        return ExplorationPlanningResult(
            assignments=tuple(assignments),
            trial_slots=slots,
            active_delta_count=active_count,
        )


@dataclass(frozen=True)
class PortfolioStepResult:
    """Portfolio state after folding journal entries, status, and promotion."""

    portfolio: list[DeltaPortfolioRow]
    entries_seen: int
    promotion: PromotionResult | None = None


@dataclass
class PortfolioCoordinator:
    """Coordinate durable delta posterior, lifecycle, and live promotion."""

    journal_path: Path
    live_skill_root: Path
    promotion_min_ready: int
    timestamp_factory: Callable[[], str]

    def entry_count(self) -> int:
        if not self.journal_path.exists():
            return 0
        return len(read_journal_entries(self.journal_path))

    def fold_new_entries(
        self,
        *,
        portfolio: list[DeltaPortfolioRow],
        entries_seen: int,
    ) -> PortfolioStepResult:
        if not self.journal_path.exists():
            return PortfolioStepResult(
                portfolio=portfolio,
                entries_seen=entries_seen,
            )
        entries = read_journal_entries(self.journal_path)
        folded = fold_portfolio_entries(entries[entries_seen:], portfolio)
        return PortfolioStepResult(
            portfolio=folded,
            entries_seen=len(entries),
        )

    def apply_status(
        self,
        portfolio: list[DeltaPortfolioRow],
    ) -> list[DeltaPortfolioRow]:
        return apply_status_transitions(portfolio)

    def promote_if_ready(
        self,
        *,
        portfolio: list[DeltaPortfolioRow],
        batch_id: str,
    ) -> PortfolioStepResult:
        promotion = promote_ready_deltas(
            live_skill_root=self.live_skill_root,
            archive_root=self.live_skill_root / "archive",
            portfolio=portfolio,
            min_ready_count=self.promotion_min_ready,
            run_id=batch_id,
            timestamp=self.timestamp_factory(),
        )
        return PortfolioStepResult(
            portfolio=promotion.portfolio,
            entries_seen=0,
            promotion=promotion,
        )


@dataclass
class EvidencePool:
    """Read per-request evidence and surface reject/hold trajectory candidates."""

    batch_dir: Path

    def candidates_from_wave_records(
        self,
        wave_records: Sequence[dict[str, Any]],
    ) -> list[DistillTrajectoryCandidate]:
        candidates: list[DistillTrajectoryCandidate] = []
        for record in wave_records:
            if record.get("exception") is not None or record.get("skipped"):
                continue
            if record.get("trial_selected_delta_id") and record.get("trial_patch_applied") is False:
                continue
            request_id = str(record.get("request_id") or record.get("node_id") or "")
            if not request_id:
                continue
            output_id = str(record.get("node_id") or request_id)
            request_dir = self.batch_dir / safe_request_dirname(output_id)
            decision_bucket = self._decision_bucket_from_dir(request_dir)
            if decision_bucket not in {"reject", "hold"}:
                continue
            candidates.append(
                DistillTrajectoryCandidate(
                    pipeline_id=pipeline_id_for_record(record),
                    request_id=request_id,
                    request_dir=request_dir,
                    decision_bucket=decision_bucket,
                    priority=distill_decision_priority(decision_bucket),
                )
            )
        return candidates

    def _decision_bucket_from_dir(self, request_dir: Path) -> str:
        try:
            artifact = _read_json(
                request_dir / "evidence" / "personalized_copy_rubric" / "artifact.json"
            )
        except Exception:
            return "unknown"
        if not isinstance(artifact, dict):
            return "unknown"
        return rubric_decision_bucket(artifact)


@dataclass
class DistillationScheduler:
    """Plan pipeline-scoped, budget-gated distillation calls."""

    policy: EvolutionBudgetPolicy = field(default_factory=EvolutionBudgetPolicy)
    pending_by_pipeline: dict[str, list[DistillTrajectoryCandidate]] = field(
        default_factory=dict
    )

    def plan_wave(
        self,
        *,
        batch_dir: Path,
        wave_records: Sequence[dict[str, Any]],
    ) -> DistillPlanningResult:
        candidates = EvidencePool(batch_dir).candidates_from_wave_records(wave_records)
        for candidate in candidates:
            self.pending_by_pipeline.setdefault(candidate.pipeline_id, []).append(
                candidate
            )

        if not candidates and not self.pending_by_pipeline:
            threshold = self.policy.distill_threshold(
                eligible_trajectories=0,
                pipeline_count=1,
            )
            return DistillPlanningResult(
                deferrals=(
                    DistillDeferral(
                        pipeline_id="all",
                        trajectories=0,
                        threshold=threshold,
                        reason="no_reject_or_hold_success_trajectory",
                    ),
                )
            )

        plans: list[DistillBundlePlan] = []
        deferrals: list[DistillDeferral] = []
        total_candidates = sum(
            len(items) for items in self.pending_by_pipeline.values()
        )
        pipeline_count = len(self.pending_by_pipeline)
        planned_pipeline_ids: list[str] = []
        for pipeline_id in sorted(self.pending_by_pipeline):
            pipeline_candidates = sorted(
                self.pending_by_pipeline[pipeline_id],
                key=lambda item: (item.priority, item.request_dir.name),
            )
            threshold = self.policy.distill_threshold(
                eligible_trajectories=total_candidates,
                pipeline_count=pipeline_count,
            )
            reject_count = sum(
                1 for item in pipeline_candidates if item.decision_bucket == "reject"
            )
            hold_count = sum(
                1 for item in pipeline_candidates if item.decision_bucket == "hold"
            )
            if len(pipeline_candidates) < threshold:
                deferrals.append(
                    DistillDeferral(
                        pipeline_id=pipeline_id,
                        trajectories=len(pipeline_candidates),
                        threshold=threshold,
                        reject_count=reject_count,
                        hold_count=hold_count,
                        reason="below_pipeline_threshold",
                    )
                )
                continue
            request_dirs = tuple(candidate.request_dir for candidate in pipeline_candidates)
            bundle_name = (
                f"{safe_request_dirname(pipeline_id)}_wave_"
                f"{safe_request_dirname(request_dirs[0].name)}_{len(request_dirs)}"
            )
            plans.append(
                DistillBundlePlan(
                    pipeline_id=pipeline_id,
                    request_dirs=request_dirs,
                    evidence_dir=batch_dir / "_evolution_distill" / bundle_name,
                    reject_count=reject_count,
                    hold_count=hold_count,
                )
            )
            planned_pipeline_ids.append(pipeline_id)
        for pipeline_id in planned_pipeline_ids:
            self.pending_by_pipeline.pop(pipeline_id, None)
        return DistillPlanningResult(
            plans=tuple(plans),
            deferrals=tuple(deferrals),
        )


def pipeline_id_for_record(record: dict[str, Any]) -> str:
    explicit = record.get("pipeline_id")
    if explicit:
        return str(explicit)
    delta_id = record.get("trial_selected_delta_id")
    if delta_id:
        return f"trial:{delta_id}"
    return "production"


def distill_decision_priority(decision_bucket: str) -> int:
    return {"reject": 0, "hold": 1, "admit": 2}.get(decision_bucket, 3)


def rubric_decision_bucket(rubric_artifact: dict[str, Any]) -> str:
    decisions = {
        str(judgment.get("decision") or "").strip()
        for judgment in (rubric_artifact.get("judgments") or [])
        if isinstance(judgment, dict)
    }
    if "reject" in decisions:
        return "reject"
    if "hold" in decisions:
        return "hold"
    if "admit" in decisions:
        return "admit"
    return "unknown"


def build_trajectory_payload(request_dir: Path) -> dict:
    """Assemble one request trace payload handed to distill-skill-deltas."""
    node_ids = (
        "personalized_user_mining",
        "personalized_copy_generation",
        "personalized_copy_rubric",
    )
    evidence_dir = request_dir / "evidence"
    artifacts: dict[str, Any] = {}
    tool_calls_per_node: dict[str, list[dict]] = {}
    usage_per_node: dict[str, Any] = {}

    for node_id in node_ids:
        node_dir = evidence_dir / node_id
        artifacts[node_id] = _read_json(node_dir / "artifact.json")
        tool_calls_per_node[node_id] = _read_jsonl(node_dir / "tool_calls.jsonl")
        usage_per_node[node_id] = _read_json(node_dir / "usage.json")

    return {
        "request_id": request_dir.name,
        "personalized_user_mining": artifacts["personalized_user_mining"],
        "personalized_copy_generation": artifacts["personalized_copy_generation"],
        "personalized_copy_rubric": artifacts["personalized_copy_rubric"],
        "rubric_decision_bucket": rubric_decision_bucket(
            artifacts["personalized_copy_rubric"]
        ),
        "tool_calls_per_node": tool_calls_per_node,
        "usage_per_node": usage_per_node,
    }


def build_trajectory_bundle_payload(
    request_dirs: Sequence[Path],
    *,
    pipeline_id: str = "production",
    target_skill_snapshots: Sequence[dict[str, Any]] | None = None,
) -> dict:
    trajectories = [build_trajectory_payload(request_dir) for request_dir in request_dirs]
    for trajectory in trajectories:
        trajectory["pipeline_id"] = pipeline_id
    skill_snapshots = list(target_skill_snapshots or [])
    if not trajectories:
        return {
            "request_id": "wave:empty",
            "scenario_id": "wave:empty",
            "pipeline_id": pipeline_id,
            "trajectory_count": 0,
            "trajectories": [],
            "target_skill_snapshots": skill_snapshots,
        }
    request_ids = [str(trajectory["request_id"]) for trajectory in trajectories]
    bundle_id = f"{pipeline_id}:wave:{request_ids[0]}:{len(request_ids)}"
    return {
        "request_id": bundle_id,
        "scenario_id": bundle_id,
        "pipeline_id": pipeline_id,
        "trajectory_count": len(trajectories),
        "request_ids": request_ids,
        "trajectories": trajectories,
        "target_skill_snapshots": skill_snapshots,
    }


def active_delta_count(
    portfolio: Sequence[DeltaPortfolioRow],
    *,
    applicable_surface: list[str],
    target_skills: Sequence[str] | None,
) -> int:
    return len(
        [
            row
            for row in portfolio
            if row.status == "experimental"
            and _surface_matches(row, applicable_surface)
            and _target_matches(row, target_skills)
        ]
    )


def _surface_matches(row: DeltaPortfolioRow, applicable_surface: list[str]) -> bool:
    return not row.applicable_surface or any(
        surface in row.applicable_surface for surface in applicable_surface
    )


def _target_matches(
    row: DeltaPortfolioRow,
    target_skills: Sequence[str] | None,
) -> bool:
    if target_skills is None:
        return True
    return row.target_skill in set(target_skills)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows
