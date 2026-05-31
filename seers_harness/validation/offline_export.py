"""Export admitted personalized copy rows for offline serving tables."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


OFFLINE_COPY_COLUMNS = [
    "user_id",
    "request_id",
    "copy",
    "product_id",
    "candidate_id",
    "user_factor_id",
    "total_score",
    "decision",
]


def admitted_copy_rows(
    *,
    scenario: dict[str, Any],
    generation_artifact: dict[str, Any],
    rubric_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build offline rows from admitted rubric judgments.

    The serving contract is keyed by ``user_id, request_id, copy``. Additional
    columns preserve enough provenance to audit which product/user-factor/judgment
    produced the row.
    """
    request_id = str(scenario.get("request_id") or scenario.get("scenario_id") or "")
    user_state = scenario.get("user_state") if isinstance(scenario.get("user_state"), dict) else {}
    user_id = str(user_state.get("user_id") or "")

    candidates = generation_artifact.get("candidates") or []
    text_by_candidate_id = {
        str(candidate.get("candidate_id")): str(candidate.get("text") or "")
        for candidate in candidates
        if isinstance(candidate, dict)
    }

    rows: list[dict[str, Any]] = []
    for judgment in rubric_artifact.get("judgments") or []:
        if not isinstance(judgment, dict) or judgment.get("decision") != "admit":
            continue
        candidate_id = str(judgment.get("candidate_id") or "")
        copy_text = str(judgment.get("copy_text") or text_by_candidate_id.get(candidate_id) or "")
        if not copy_text:
            continue
        rows.append(
            {
                "user_id": user_id,
                "request_id": request_id,
                "copy": copy_text,
                "product_id": str(judgment.get("product_id") or ""),
                "candidate_id": candidate_id,
                "user_factor_id": str(judgment.get("user_factor_id") or ""),
                "total_score": judgment.get("total_score", ""),
                "decision": judgment.get("decision", ""),
            }
        )
    return rows


def write_offline_copy_assets(rows: list[dict[str, Any]], out_dir: Path) -> None:
    """Write CSV and JSONL copies of the admitted-copy offline table."""
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "offline_copy_assets.csv"
    jsonl_path = out_dir / "offline_copy_assets.jsonl"

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OFFLINE_COPY_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in OFFLINE_COPY_COLUMNS})

    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps({key: row.get(key, "") for key in OFFLINE_COPY_COLUMNS}, ensure_ascii=False))
            f.write("\n")
