"""Evolution delta contracts and portfolio rows (Phase 6 plan 06-01).

These are pure-data Pydantic models. They never mutate live skill files,
never accept LLM self-rated metric fields (the five names banned by
Principle 10 — see ``intel/decisions.md`` ADR-01-PRINCIPLE-10), and never
carry old runtime selection-flow vocabulary.

A ``DeltaProposal`` is what the model emits, via the rewritten
``distill-skill-deltas`` tool-use skill. The model proposes an observation
and a small reusable change; handler code validates structure, evidence
references, and privacy scans before the proposal becomes a portfolio row.

A ``DeltaPortfolioRow`` is durable state. It accumulates trial outcomes
(``sample_count``, ``success_count``, ``failure_count``) and bandit-style
posterior counters (``belief_alpha``/``belief_beta``). The portfolio code
(later plans) updates these from real trial outcomes — not from any LLM
self-report.

A ``DeltaDistillationArtifact`` is the final tool-call payload of the
rewritten distill skill: a list of validated proposals plus minimal request
metadata. It is the only handoff to the portfolio writer.
"""

from __future__ import annotations

import json
import math
import random as _random_module
from pathlib import Path
from typing import Iterable, Literal

from pydantic import BaseModel, Field, field_validator

from seers_harness.domain.models import EvidenceRef


ChangeType = Literal["modify_skill", "add_skill"]
"""Phase 6 only allows two change shapes; both are reversible.

``modify_skill`` adjusts an existing live skill at trial time without
overwriting the live file. ``add_skill`` proposes a new experimental skill
that lives only in the trial workspace until later review.
"""

DeltaStatus = Literal["experimental", "held", "rejected", "ready_for_review"]
"""Lifecycle states. ``experimental`` is the default seed.

A delta moves to ``held`` after enough trials show no signal, ``rejected``
after evidence shows it harms quality or token cost, and
``ready_for_review`` only as a future gate marker. Phase 6 never writes
durably to ``workflow-skills/current/`` — ``ready_for_review`` is bookkeeping.
"""

NoTrialReason = Literal[
    "no_eligible_delta",
    "all_eligible_deltas_evidence_sufficient",
    "all_eligible_deltas_non_experimental",
    "target_unresolvable",
    "provider_auth_schema_blocker",
]
TriggerReason = Literal[
    "insufficient_sample_count",
    "posterior_near_boundary",
    "insufficient_lower_bound_confidence",
]

MIN_INFORMATION_SAMPLES = 5
EVIDENCE_SUFFICIENT_SAMPLES = 10
DECISION_BOUNDARY_MEAN = 0.5
NEAR_BOUNDARY_MARGIN = 0.15
LOWER_BOUND_CONFIDENCE_MIN = 0.55


class ExplorationDecision(BaseModel):
    """Durable per-request trial decision evidence.

    The selector always returns this object so no-trial paths are explicit
    structural/evidence decisions instead of hidden probability skips.
    """

    should_trial: bool
    selected_delta_id: str | None
    eligible_delta_count: int
    trigger_reason: TriggerReason | None
    no_trial_reason: NoTrialReason | None
    posterior_samples: dict[str, float] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.selected_delta_id == other
        return super().__eq__(other)


class DeltaProposal(BaseModel):
    """One model-proposed delta after handler validation.

    Emitted via ``record_delta_change`` followed by ``submit_delta_distillation_final``.
    The handler enforces non-empty ``evidence_refs`` and rejects any payload
    carrying private trace text or self-rated metric fields.
    """

    delta_id: str
    target_skill: str
    change_type: ChangeType
    observation: str
    proposed_change: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    applicable_surface: list[str] = Field(default_factory=list)
    failure_types: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    @field_validator("evidence_refs")
    @classmethod
    def _require_evidence(cls, value: list[EvidenceRef]) -> list[EvidenceRef]:
        if not value:
            raise ValueError(
                "DeltaProposal requires at least one evidence_refs entry"
            )
        return value


class DeltaPortfolioRow(BaseModel):
    """Durable portfolio bookkeeping for one delta.

    Trial outcomes update ``sample_count`` / ``success_count`` /
    ``failure_count`` and the bandit posterior counters
    (``belief_alpha`` / ``belief_beta``). All counters are non-negative
    integers or floats; nothing here is LLM-emitted.

    ``token_cost_delta_sum`` accumulates measured token-cost deltas (in
    tokens), positive means the delta costs more tokens than baseline.
    """

    delta_id: str
    target_skill: str
    change_type: ChangeType
    observation: str
    proposed_change: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    applicable_surface: list[str] = Field(default_factory=list)
    failure_types: list[str] = Field(default_factory=list)
    belief_alpha: float = 1.0
    belief_beta: float = 1.0
    sample_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    token_cost_delta_sum: int = 0
    status: DeltaStatus = "experimental"

    model_config = {"extra": "forbid"}

    @field_validator("evidence_refs")
    @classmethod
    def _require_evidence(cls, value: list[EvidenceRef]) -> list[EvidenceRef]:
        if not value:
            raise ValueError(
                "DeltaPortfolioRow requires at least one evidence_refs entry"
            )
        return value


class DeltaDistillationArtifact(BaseModel):
    """Final tool-call payload of the rewritten distill-skill-deltas skill.

    A bounded list of validated proposals. Submit also records the request
    id and scenario id when the caller supplies them so portfolio writers
    can attribute trial outcomes back to the trajectory that produced the
    proposal.
    """

    request_id: str = ""
    scenario_id: str = ""
    deltas: list[DeltaProposal] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


# --------------------------------------------------------------------------- #
# Portfolio JSONL persistence (Phase 6 plan 06-02 task 01)                    #
# --------------------------------------------------------------------------- #


def load_portfolio_jsonl(path: Path | str) -> list[DeltaPortfolioRow]:
    """Read a JSONL portfolio file, returning a list of validated rows.

    Empty lines are skipped. A missing path returns an empty list rather
    than raising — a fresh portfolio is the natural starting state. Each
    line is validated against ``DeltaPortfolioRow`` so any drift surfaces
    at load time, not at trial time.
    """
    p = Path(path)
    if not p.exists():
        return []
    rows: list[DeltaPortfolioRow] = []
    text = p.read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line.strip():
            continue
        rows.append(DeltaPortfolioRow.model_validate_json(line))
    return rows


def write_portfolio_jsonl(
    path: Path | str, rows: Iterable[DeltaPortfolioRow]
) -> None:
    """Write rows as JSONL to ``path``. Parent directories are created."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(row.model_dump_json())
            f.write("\n")


# --------------------------------------------------------------------------- #
# Posterior update (Phase 6 plan 06-02 task 01) — D-26                        #
# --------------------------------------------------------------------------- #


def belief_mean(row: DeltaPortfolioRow) -> float:
    """Beta posterior mean ``alpha / (alpha + beta)``.

    Phase 6 keeps belief computed, never model-emitted (Principle 10). With
    the seed prior of (1.0, 1.0), an unsampled delta returns 0.5.
    """
    denom = row.belief_alpha + row.belief_beta
    if denom <= 0:
        return 0.5
    return row.belief_alpha / denom


def update_after_trial(
    row: DeltaPortfolioRow,
    *,
    success: bool,
    token_cost_delta: int = 0,
) -> DeltaPortfolioRow:
    """Return a new row with one trial outcome folded in.

    Increments ``sample_count`` and either ``success_count`` /
    ``belief_alpha`` or ``failure_count`` / ``belief_beta`` from an
    explicit observed outcome. Token-cost deltas accumulate.

    The function is pure: it returns a new ``DeltaPortfolioRow`` and does
    not mutate the input. Tests rely on this property to assert prior vs.
    posterior shape independently.
    """
    new_alpha = row.belief_alpha + (1.0 if success else 0.0)
    new_beta = row.belief_beta + (0.0 if success else 1.0)
    return row.model_copy(
        update={
            "belief_alpha": new_alpha,
            "belief_beta": new_beta,
            "sample_count": row.sample_count + 1,
            "success_count": row.success_count + (1 if success else 0),
            "failure_count": row.failure_count + (0 if success else 1),
            "token_cost_delta_sum": row.token_cost_delta_sum + int(token_cost_delta),
        }
    )


# --------------------------------------------------------------------------- #
# Exploration decision (Phase 9 plan 09-01) — D9-EVO-01..06                  #
# --------------------------------------------------------------------------- #


def _surface_matches(row: DeltaPortfolioRow, applicable_surface: list[str]) -> bool:
    return not row.applicable_surface or any(
        surface in row.applicable_surface for surface in applicable_surface
    )


def _wilson_lcb(success: int, total: int, *, z: float = 1.96) -> float:
    if total <= 0:
        return 0.0
    phat = success / total
    denom = 1 + z * z / total
    centre = phat + z * z / (2 * total)
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * total)) / total)
    return max(0.0, (centre - margin) / denom)


def _information_value_trigger(row: DeltaPortfolioRow) -> TriggerReason | None:
    if row.sample_count < MIN_INFORMATION_SAMPLES:
        return "insufficient_sample_count"

    mean = belief_mean(row)
    if abs(mean - DECISION_BOUNDARY_MEAN) <= NEAR_BOUNDARY_MARGIN:
        return "posterior_near_boundary"

    lower_bound = _wilson_lcb(row.success_count, row.sample_count)
    if (
        row.sample_count < EVIDENCE_SUFFICIENT_SAMPLES
        or lower_bound < LOWER_BOUND_CONFIDENCE_MIN
    ):
        return "insufficient_lower_bound_confidence"

    return None


def select_trial_delta(
    portfolio: list[DeltaPortfolioRow],
    *,
    applicable_surface: list[str],
    target_skill: str | None = None,
    blocked_reason: NoTrialReason | None = None,
    rng: _random_module.Random | None = None,
    **_: object,
) -> ExplorationDecision:
    """Return an explicit exploration decision for one request.

    Eligible experimental deltas are filtered by target/applicable surface.
    A trial is triggered only while posterior evidence remains informative;
    when it triggers, the selected delta is the highest Thompson posterior
    sample from ``rng.betavariate(alpha, beta)``.
    """
    if blocked_reason is not None:
        return ExplorationDecision(
            should_trial=False,
            selected_delta_id=None,
            eligible_delta_count=0,
            trigger_reason=None,
            no_trial_reason=blocked_reason,
            posterior_samples={},
        )
    if rng is None:
        rng = _random_module.Random()

    applicable_rows = [
        row
        for row in portfolio
        if _surface_matches(row, applicable_surface)
        and (target_skill is None or row.target_skill == target_skill)
    ]
    if not applicable_rows:
        return ExplorationDecision(
            should_trial=False,
            selected_delta_id=None,
            eligible_delta_count=0,
            trigger_reason=None,
            no_trial_reason="no_eligible_delta",
            posterior_samples={},
        )

    eligible = [row for row in applicable_rows if row.status == "experimental"]
    if not eligible:
        return ExplorationDecision(
            should_trial=False,
            selected_delta_id=None,
            eligible_delta_count=0,
            trigger_reason=None,
            no_trial_reason="all_eligible_deltas_non_experimental",
            posterior_samples={},
        )

    trigger_reasons = [
        reason for row in eligible if (reason := _information_value_trigger(row))
    ]
    if not trigger_reasons:
        return ExplorationDecision(
            should_trial=False,
            selected_delta_id=None,
            eligible_delta_count=len(eligible),
            trigger_reason=None,
            no_trial_reason="all_eligible_deltas_evidence_sufficient",
            posterior_samples={},
        )

    samples = {
        row.delta_id: float(rng.betavariate(row.belief_alpha, row.belief_beta))
        for row in eligible
    }
    selected_delta_id = max(samples, key=samples.get)
    return ExplorationDecision(
        should_trial=True,
        selected_delta_id=selected_delta_id,
        eligible_delta_count=len(eligible),
        trigger_reason=trigger_reasons[0],
        no_trial_reason=None,
        posterior_samples=samples,
    )


# --------------------------------------------------------------------------- #
# Trajectory evidence (Phase 6 plan 06-02 task 03) — D-11..D-15               #
# --------------------------------------------------------------------------- #


_PRIVATE_TRAJECTORY_TERMS: tuple[str, ...] = (
    "private_reasoning",
    "user_state",
    "raw_interest_fragment_private",
    "diagnostic_evidence_refs",
    "blocked_evidence_refs",
    "is_clk_c",
)


class TrajectoryRecord(BaseModel):
    """Compact per-request evidence row.

    A trajectory captures the durable trace fields from one request run:
    request/scenario id, node artifact paths, tool-call count, optional
    token usage, optional trialed delta id, optional failure category, and
    a compact quality outcome supplied by the caller. It deliberately
    omits raw user state, private reasoning, and full provider messages
    (forbid list in the plan).
    """

    request_id: str
    scenario_id: str = ""
    artifact_paths: dict[str, str] = Field(default_factory=dict)
    tool_call_count: int = 0
    token_usage: int | None = None
    trial_delta_id: str | None = None
    failure_category: str | None = None
    success: bool = True
    quality_bucket: str = ""
    token_cost_bucket: str = ""

    model_config = {"extra": "forbid"}


def trajectory_signature(record: TrajectoryRecord) -> str:
    """Deduplication signature.

    Two trajectories collide when they describe the same outcome shape:
    same trialed delta, same target skill set (artifact node ids), same
    success flag, same failure category, same quality bucket, same
    token-cost bucket. Request id is intentionally excluded so repeated
    runs of the same delta with the same outcome dedupe.
    """
    node_ids = ",".join(sorted(record.artifact_paths.keys()))
    return "|".join(
        [
            record.trial_delta_id or "",
            node_ids,
            "S" if record.success else "F",
            record.failure_category or "",
            record.quality_bucket,
            record.token_cost_bucket,
        ]
    )


def buffer_trajectory(
    buffer: list[TrajectoryRecord], record: TrajectoryRecord
) -> list[TrajectoryRecord]:
    """Append ``record`` to ``buffer`` and return the new list.

    The short-term buffer accepts every trajectory (D-12). Filtering is
    deferred to ``sediment_trajectories``.
    """
    return [*buffer, record]


def _has_private_term(record: TrajectoryRecord) -> bool:
    """Reject any record whose flat fields surface known private trace terms."""
    flat: list[str] = [
        record.request_id,
        record.scenario_id,
        record.failure_category or "",
        record.quality_bucket,
        record.token_cost_bucket,
        record.trial_delta_id or "",
    ]
    flat.extend(record.artifact_paths.keys())
    flat.extend(record.artifact_paths.values())
    for s in flat:
        if not isinstance(s, str):
            continue
        for term in _PRIVATE_TRAJECTORY_TERMS:
            if term in s:
                return True
    return False


# --------------------------------------------------------------------------- #
# Portfolio assembly + observability seam (Phase 7 plan 07-01) — D-11, D-22(c) #
# --------------------------------------------------------------------------- #


def assemble_portfolio(
    existing_portfolio: list[DeltaPortfolioRow],
    new_proposals: list[DeltaProposal],
    *,
    events: list[dict] | None = None,
) -> list[DeltaPortfolioRow]:
    """Return the post-evolution portfolio assembled from existing rows + new proposals.

    Pure transform: ``existing_portfolio`` passes through unchanged, then any
    ``DeltaProposal`` whose ``delta_id`` is not already in the portfolio is
    converted into a fresh ``DeltaPortfolioRow`` (seed bandit prior; zero
    sample counts). The function never mutates either input list.

    When ``events`` is ``None``, no side effects occur — this is the byte-
    identical default required by D-11's "no business-logic change" rule
    (the plan also requires that no existing call site needs to change;
    today no caller invokes this function, and the default keeps it inert).

    When ``events`` is supplied, the function appends exactly one
    ``portfolio_assembled`` dict carrying the pre/post delta-id lists and
    counts. The downstream ``write_evolution_snapshot`` writer (see
    ``seers_harness.validation.evolution_snapshot``) reduces these events
    into the VAL-06 evidence shape.
    """
    existing_ids: set[str] = {row.delta_id for row in existing_portfolio}
    assembled: list[DeltaPortfolioRow] = list(existing_portfolio)
    for proposal in new_proposals:
        if proposal.delta_id in existing_ids:
            continue
        assembled.append(
            DeltaPortfolioRow(
                delta_id=proposal.delta_id,
                target_skill=proposal.target_skill,
                change_type=proposal.change_type,
                observation=proposal.observation,
                proposed_change=proposal.proposed_change,
                evidence_refs=list(proposal.evidence_refs),
                applicable_surface=list(proposal.applicable_surface),
                failure_types=list(proposal.failure_types),
            )
        )
        existing_ids.add(proposal.delta_id)

    if events is not None:
        before_ids = [row.delta_id for row in existing_portfolio]
        after_ids = [row.delta_id for row in assembled]
        events.append(
            {
                "type": "portfolio_assembled",
                "delta_portfolio_before": before_ids,
                "delta_portfolio_after": after_ids,
                "counts": {"before": len(before_ids), "after": len(after_ids)},
            }
        )

    return assembled


def sediment_trajectories(
    buffer: list[TrajectoryRecord],
    *,
    max_rows: int,
) -> list[TrajectoryRecord]:
    """Filter and bound the short-term buffer into durable evidence rows.

    Steps (D-14):
      1. Drop records that surface known private trace terms.
      2. Deduplicate by ``trajectory_signature``; first occurrence wins.
      3. Preserve diversity across success/failure/quality/token buckets
         using round-robin across diversity buckets, so a flood of a single
         signature does not crowd out rarer patterns.
      4. Bound output to ``max_rows`` rows.
    """
    if max_rows <= 0:
        return []

    cleaned: list[TrajectoryRecord] = []
    seen_sigs: set[str] = set()
    for rec in buffer:
        if _has_private_term(rec):
            continue
        sig = trajectory_signature(rec)
        if sig in seen_sigs:
            continue
        seen_sigs.add(sig)
        cleaned.append(rec)

    # Bucket by (success, quality_bucket, token_cost_bucket, failure_category) for
    # diversity-preserving round-robin selection.
    buckets: dict[tuple, list[TrajectoryRecord]] = {}
    bucket_order: list[tuple] = []
    for rec in cleaned:
        key = (
            rec.success,
            rec.quality_bucket,
            rec.token_cost_bucket,
            rec.failure_category or "",
        )
        if key not in buckets:
            buckets[key] = []
            bucket_order.append(key)
        buckets[key].append(rec)

    selected: list[TrajectoryRecord] = []
    while len(selected) < max_rows:
        progressed = False
        for key in bucket_order:
            if buckets[key]:
                selected.append(buckets[key].pop(0))
                progressed = True
                if len(selected) >= max_rows:
                    break
        if not progressed:
            break
    return selected
