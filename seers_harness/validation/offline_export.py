"""Export scored personalized copy rows for offline serving tables."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


OFFLINE_COPY_COLUMNS = [
    "request_id",
    "user_id",
    "item_id",
    "copy",
]

MIN_OFFLINE_TOTAL_SCORE = 21


def offline_copy_rows(
    *,
    scenario: dict[str, Any],
    generation_artifact: dict[str, Any],
    rubric_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build offline rows from score-qualified rubric judgments.

    The serving contract is the minimal offline table:
    ``request_id, user_id, item_id, copy``. Provenance stays in request evidence,
    ``index.json``, and summaries instead of widening the serving table.
    """
    request_id = str(scenario.get("request_id") or scenario.get("scenario_id") or "")
    user_state = scenario.get("user_state") if isinstance(scenario.get("user_state"), dict) else {}
    user_id = str(user_state.get("user_id") or "")

    candidates = generation_artifact.get("candidates") or []
    candidate_by_id = {
        str(candidate.get("candidate_id")): candidate
        for candidate in candidates
        if isinstance(candidate, dict)
    }

    rows: list[dict[str, Any]] = []
    for judgment in rubric_artifact.get("judgments") or []:
        if not isinstance(judgment, dict) or not _score_qualifies(judgment):
            continue
        candidate_id = str(judgment.get("candidate_id") or "")
        candidate = candidate_by_id.get(candidate_id) or {}
        copy_text = str(judgment.get("copy_text") or candidate.get("text") or "")
        if not copy_text:
            continue
        item_id = str(
            judgment.get("item_id")
            or judgment.get("product_id")
            or candidate.get("item_id")
            or candidate.get("product_id")
            or ""
        )
        rows.append(
            {
                "request_id": request_id,
                "user_id": user_id,
                "item_id": item_id,
                "copy": copy_text,
            }
        )
    return rows


def _score_qualifies(judgment: dict[str, Any]) -> bool:
    if not _objective_checks_pass(judgment.get("objective_checks")):
        return False
    try:
        return int(judgment.get("total_score") or 0) >= MIN_OFFLINE_TOTAL_SCORE
    except (TypeError, ValueError):
        return False


def _objective_checks_pass(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    return all(isinstance(item, dict) and item.get("passed") is True for item in value)


def write_offline_copy_table(rows: list[dict[str, Any]], out_dir: Path) -> None:
    """Write CSV and JSONL copies of the offline serving table."""
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "offline_copy_table.csv"
    jsonl_path = out_dir / "offline_copy_table.jsonl"

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OFFLINE_COPY_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in OFFLINE_COPY_COLUMNS})

    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps({key: row.get(key, "") for key in OFFLINE_COPY_COLUMNS}, ensure_ascii=False))
            f.write("\n")
