"""batch_summary.json writer — Phase 7 plan 07-03 (D-10, D-12, D-13, D-16, D-22d).

Aggregates the per-request rows materialised by
:func:`seers_harness.validation.index_writer.write_index` into a single
stage-level summary that downstream case-analysis reads when picking
which requests to read.

Schema (per D-22d):

    {
        "stage": 1 | 2 | 3,
        "batch_id": str,
        "totals": {
            "requests": int,
            "val01_pass": int,
            "val02_pass": int,
            "val04_pass": int
        },
        "fail_lists": {
            "VAL-01": [node_id, ...],   # rows with VAL-01_pass == False
            "VAL-02": [node_id, ...],
            "VAL-04": [node_id, ...]
        },
        "manual_review_queue": [node_id, ...]   # see "manual review queue" below
    }

VAL-03 is intentionally absent from ``totals`` and ``fail_lists`` —
per D-13 / D-14 the only path to a VAL-03 verdict is manual case
reading confirmed by the user. The rows that need human reading are
routed into ``manual_review_queue`` instead.

manual_review_queue selection rule (D-13, D-12, D-10) — the union of:

    (a) rows where ``VAL-03_pass is None`` AND
        ``len_transferable_disposition_text > 0`` (there is prose to
        judge per D-13);
    (b) rows where ``reflow_triggered`` is True (D-12 reflow event
        surfaces a case worth reading);
    (c) rows where ``trial_selected_delta_id`` is non-null (D-10 trial
        selection — the user wants to see when evolution actually fired).

Per D-16 the case-reading scope is ≈20-30 factors. To keep the queue
bounded we cap at 30 and append a sentinel ``"<truncated: N more>"``
marker rather than silently dropping requests. The auditor sees the
overflow count and can fall back to ``index.json`` for full navigation
when the truncation matters.

Per D-22(d) this writer is part of the *writer layer* — it reads only
``index.json`` (on disk via :func:`write_index`) and writes
``batch_summary.json``. It does not import, instrument, or call back
into the capture layer (``recording_provider`` / ``evidence_writer``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# D-16 reading-scope cap — keep the manual review queue between 20 and 30
# entries TOTAL (queue rows + truncation sentinel together must fit in
# 30). IN-07: previously the cap was 30 + sentinel = 31, exceeding the
# documented 20-30 reading scope by one. Allow at most 29 real rows so
# that with the sentinel appended the published queue is exactly 30.
_MANUAL_REVIEW_QUEUE_CAP = 29


def write_batch_summary(
    index_path: str | Path,
    out_path: str | Path | None = None,
) -> None:
    """Read ``index_path`` and write the aggregated ``batch_summary.json``.

    When ``out_path`` is ``None`` (the default), the summary is written
    next to ``index.json`` at ``index_path.parent / "batch_summary.json"``.
    """
    index_path_p = Path(index_path)
    out_path_p = (
        Path(out_path) if out_path is not None else index_path_p.parent / "batch_summary.json"
    )

    index_doc = json.loads(index_path_p.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = index_doc.get("requests") or []

    val01_pass = 0
    val02_pass = 0
    val04_pass = 0
    fail_val01: list[str] = []
    fail_val02: list[str] = []
    fail_val04: list[str] = []
    # Use a list (not a set) so the auditor sees the queue in row-order,
    # which mirrors the order in which the stage runner submitted them;
    # deduplicate via a parallel seen-set.
    queue: list[str] = []
    seen_in_queue: set[str] = set()

    for row in rows:
        if not isinstance(row, dict):
            continue
        node_id = str(row.get("node_id") or "")

        # Totals + fail_lists. Counted as pass only when the row carries
        # ``True``; ``None`` and ``False`` are NOT counted as pass. Only
        # ``False`` enters the fail_list (a ``None`` would mean "judge
        # could not run" — surfacing it via manual_review_queue is the
        # right routing).
        if row.get("VAL-01_pass") is True:
            val01_pass += 1
        elif row.get("VAL-01_pass") is False:
            fail_val01.append(node_id)

        if row.get("VAL-02_pass") is True:
            val02_pass += 1
        elif row.get("VAL-02_pass") is False:
            fail_val02.append(node_id)

        if row.get("VAL-04_pass") is True:
            val04_pass += 1
        elif row.get("VAL-04_pass") is False:
            fail_val04.append(node_id)

        # manual_review_queue — D-13 / D-12 / D-10 union
        needs_review = False
        # (a) VAL-03 prose-judgement trigger: text present but no verdict
        if row.get("VAL-03_pass") is None:
            text_len = row.get("len_transferable_disposition_text", 0)
            if isinstance(text_len, int) and text_len > 0:
                needs_review = True
        # (b) D-12 reflow attribution
        if row.get("reflow_triggered") is True:
            needs_review = True
        # (c) D-10 trial selection
        if row.get("trial_selected_delta_id"):
            needs_review = True

        if needs_review and node_id and node_id not in seen_in_queue:
            queue.append(node_id)
            seen_in_queue.add(node_id)

    # D-16 cap — keep the queue at ≈20-30 entries, surface overflow.
    overflow = max(0, len(queue) - _MANUAL_REVIEW_QUEUE_CAP)
    if overflow > 0:
        queue = queue[:_MANUAL_REVIEW_QUEUE_CAP]
        queue.append(f"<truncated: {overflow} more>")

    summary: dict[str, Any] = {
        "stage": index_doc.get("stage"),
        "batch_id": index_doc.get("batch_id"),
        "totals": {
            "requests": len(rows),
            "val01_pass": val01_pass,
            "val02_pass": val02_pass,
            "val04_pass": val04_pass,
        },
        "fail_lists": {
            "VAL-01": fail_val01,
            "VAL-02": fail_val02,
            "VAL-04": fail_val04,
        },
        "manual_review_queue": queue,
    }

    out_path_p.parent.mkdir(parents=True, exist_ok=True)
    out_path_p.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
