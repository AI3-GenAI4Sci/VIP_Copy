"""Request-level factor-to-copy audit index."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from seers_harness.domain.models import (
    CopyGenerationArtifact,
    UserPersonalizationArtifact,
)


def build_request_factor_copy_index(
    *,
    request_id: str,
    scenario_id: str,
    user_artifact: dict[str, Any],
    copy_artifact: dict[str, Any],
) -> dict[str, Any]:
    user = UserPersonalizationArtifact.model_validate(user_artifact).model_dump(
        mode="json"
    )
    copy = CopyGenerationArtifact.model_validate(copy_artifact).model_dump(
        mode="json"
    )
    user_factors = user["user_factors"]
    candidates = copy["candidates"]
    factor_ids = [factor["user_factor_id"] for factor in user_factors]
    factor_id_set = set(factor_ids)
    unknown = sorted(
        {
            candidate["source_user_factor_id"]
            for candidate in candidates
            if candidate["source_user_factor_id"] not in factor_id_set
        }
    )
    if unknown:
        raise ValueError(f"copy candidates reference unknown user factors: {unknown}")

    copies_by_factor = {factor_id: [] for factor_id in factor_ids}
    for candidate in candidates:
        copies_by_factor[candidate["source_user_factor_id"]].append(candidate)

    factors = [
        {
            "user_factor": factor,
            "copies": copies_by_factor[factor["user_factor_id"]],
        }
        for factor in user_factors
    ]
    return {
        "request_id": str(request_id),
        "scenario_id": str(scenario_id),
        "counts": {
            "user_factors": len(user_factors),
            "copy_candidates": len(candidates),
            "linked_copy_candidates": sum(len(row["copies"]) for row in factors),
        },
        "factors": factors,
    }


def write_request_factor_copy_index(
    *,
    request_id: str,
    scenario_id: str,
    user_artifact: dict[str, Any],
    copy_artifact: dict[str, Any],
    out_path: str | Path,
) -> None:
    artifact = build_request_factor_copy_index(
        request_id=request_id,
        scenario_id=scenario_id,
        user_artifact=user_artifact,
        copy_artifact=copy_artifact,
    )
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
