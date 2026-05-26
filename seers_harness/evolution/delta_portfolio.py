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
import random as _random_module
from pathlib import Path
from typing import Iterable, Literal, Optional

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
# Trial selection (Phase 6 plan 06-02 task 01) — D-09, D-26                   #
# --------------------------------------------------------------------------- #


def select_trial_delta(
    portfolio: list[DeltaPortfolioRow],
    *,
    applicable_surface: list[str],
    recent_failure_rate: float,
    token_budget_pressure: float,
    production_pressure: float,
    rng: _random_module.Random | None = None,
) -> Optional[str]:
    """Return one delta id to trial, or ``None`` to skip the trial.

    Selection is intentionally lightweight (D-25): a deterministic priority
    weight per applicable delta plus an injected ``rng`` for the no-trial
    coin flip. The weight rewards sample scarcity and posterior belief, so
    rarely sampled deltas surface before well-evidenced ones (D-08, D-09).

    Trial probability falls when recent failure rate is high (caller-side
    failure pressure), when token budget is tight, and when production
    pressure is high (D-09). All inputs are clipped to ``[0, 1]``; values
    out of range are coerced rather than raising — selection is best-effort.

    Eligibility:
      * ``status`` must be ``"experimental"``;
      * ``applicable_surface`` must overlap the row's ``applicable_surface``
        (an empty row surface is treated as universally applicable so the
        first proposal can still be trialed before tagging is complete).
    """
    if rng is None:
        rng = _random_module.Random()

    rfr = max(0.0, min(1.0, recent_failure_rate))
    tbp = max(0.0, min(1.0, token_budget_pressure))
    pp = max(0.0, min(1.0, production_pressure))

    # No-trial gate: each pressure independently lowers trial probability.
    trial_prob = (1.0 - rfr) * (1.0 - tbp) * (1.0 - pp)
    if rng.random() >= trial_prob:
        return None

    eligible = [
        row
        for row in portfolio
        if row.status == "experimental"
        and (
            not row.applicable_surface
            or any(s in row.applicable_surface for s in applicable_surface)
        )
    ]
    if not eligible:
        return None

    weights: list[float] = []
    for row in eligible:
        scarcity = 1.0 / (1.0 + row.sample_count)  # >0; scarce rows weighted higher
        weights.append(scarcity * (belief_mean(row) + 0.1))

    total = sum(weights)
    if total <= 0:
        return rng.choice(eligible).delta_id
    pick = rng.random() * total
    acc = 0.0
    for row, w in zip(eligible, weights):
        acc += w
        if pick < acc:
            return row.delta_id
    return eligible[-1].delta_id


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
