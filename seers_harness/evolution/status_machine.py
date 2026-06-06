"""Delta portfolio status transitions."""

from __future__ import annotations

import math

from seers_harness.evolution.delta_portfolio import (
    DECISION_BOUNDARY_MEAN,
    POSTERIOR_EVIDENCE_CONFIDENCE,
    DeltaPortfolioRow,
    posterior_probability_above,
)


def wilson_lcb(success: int, total: int, *, z: float = 1.96) -> float:
    if total <= 0:
        return 0.0
    p = success / total
    z2 = z * z
    denom = 1 + z2 / total
    centre = p + z2 / (2 * total)
    margin = z * math.sqrt((p * (1 - p) / total) + (z2 / (4 * total * total)))
    return max(0.0, (centre - margin) / denom)


def apply_status_transitions(
    portfolio: list[DeltaPortfolioRow],
    *,
    decision_boundary: float = DECISION_BOUNDARY_MEAN,
    promote_confidence: float = POSTERIOR_EVIDENCE_CONFIDENCE,
    reject_confidence: float = POSTERIOR_EVIDENCE_CONFIDENCE,
) -> list[DeltaPortfolioRow]:
    """Transition experimental rows from the maintained Beta posterior only."""
    transitioned: list[DeltaPortfolioRow] = []
    for row in portfolio:
        if row.status != "experimental":
            transitioned.append(row)
            continue

        probability_positive = posterior_probability_above(
            row,
            threshold=decision_boundary,
        )
        if probability_positive >= promote_confidence:
            transitioned.append(row.model_copy(update={"status": "ready_for_review"}))
        elif (1.0 - probability_positive) >= reject_confidence:
            transitioned.append(row.model_copy(update={"status": "rejected"}))
        else:
            transitioned.append(row)
    return transitioned
