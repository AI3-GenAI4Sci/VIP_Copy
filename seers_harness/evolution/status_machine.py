"""Delta portfolio status transitions."""

from __future__ import annotations

import math

from seers_harness.evolution.delta_portfolio import DeltaPortfolioRow


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
    lcb_promote: float = 0.6,
    lcb_reject: float = 0.2,
    samples_promote: int = 5,
    samples_reject: int = 10,
    token_cost_p95_max: int = 2_000,
    token_cost_deltas_by_delta: dict[str, list[int]] | None = None,
) -> list[DeltaPortfolioRow]:
    """Transition experimental rows from rubric win/loss posterior evidence only.

    Token-cost arguments are retained for compatibility with older callsites, but
    token cost is record-only and never gates promotion or rejection.
    """
    _ = token_cost_p95_max, token_cost_deltas_by_delta
    transitioned: list[DeltaPortfolioRow] = []
    for row in portfolio:
        if row.status != "experimental":
            transitioned.append(row)
            continue

        lcb = wilson_lcb(row.success_count, row.sample_count)
        if lcb >= lcb_promote and row.sample_count >= samples_promote:
            transitioned.append(row.model_copy(update={"status": "ready_for_review"}))
        elif lcb <= lcb_reject and row.sample_count >= samples_reject:
            transitioned.append(row.model_copy(update={"status": "rejected"}))
        else:
            transitioned.append(row)
    return transitioned
