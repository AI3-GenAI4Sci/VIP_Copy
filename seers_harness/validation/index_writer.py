"""index.json writer — Phase 7 plan 07-03 (D-10, D-12, D-16, D-22d).

Materialises one ``index.json`` file per stage run with one row per
submitted request. The schema is the canonical machine-readable navigation
surface for VAL-01..VAL-04 verdicts and the four D-16 sortable
extreme-sample dimensions.

Top-level keys (per D-22d):

    {
      "stage": 1 | 2 | 3,
      "batch_id": str,
      "started_at": str,             # ISO-8601 UTC
      "finished_at": str,            # ISO-8601 UTC
      "n": int,                      # requests submitted (NOT necessarily completed)
      "concurrency": int,
      "requests": [<row>, ...]       # in submission order, no shuffling
    }

Each row carries the following sortable / fidelity columns from D-16:

    len_covers_product_ids                              # int   — E1 sort desc (longest covers)
    len_transferable_disposition_text                   # int   — SHARED column for E2/E3:
                                                                  E2 sort asc  (shortest text)
                                                                  E3 sort desc (longest text)
                                                                  same column, opposite direction
    transferable_disposition_text                       # str   — raw passthrough fidelity
                                                                  (NOT an E-dimension label)
    literal_overlap_user_signal_vs_transferable_disposition  # float — E4 sort desc (highest overlap)

Plus the four VAL booleans and the per-request flags:

    VAL-01_pass / VAL-02_pass / VAL-04_pass             # bool — machine-judged (D-12)
    VAL-03_pass                                         # null — manual review only (D-13/D-14)
    reflow_triggered                                    # bool — D-12 reflow attribution
    trial_selected_delta_id                             # str|null — D-10 trial-selection visibility
    exception                                           # str|null — passthrough for fail-fast scenes

Per D-22(d) this writer is part of the *writer layer* and does not
import or instrument the capture layer. It consumes only:

    * the records list the stage runner builds (each carrying a parsed
      ``artifact`` dict already loaded from disk by the runner via the
      per-node layout from 07-02), and
    * the pure column extractors / VAL judges from
      :mod:`seers_harness.validation.machine_judges`.

JSON style follows the workspace pattern from
``seers_harness/evolution/promotion_smoke.py``: ``indent=2`` + trailing
newline. ``ensure_ascii=False`` so the raw Chinese disposition text
in the passthrough column survives intact for human case-reading
(matches the policy already adopted in 07-02 ``evidence_writer.py``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from seers_harness.validation.machine_judges import (
    extract_len_covers_product_ids,
    extract_len_transferable_disposition_text,
    extract_literal_overlap,
    extract_transferable_disposition_text,
    judge_val01,
    judge_val02,
    judge_val04,
)


def write_index(
    records: list[dict],
    out_dir: str | Path,
    stage: int,
    batch_id: str,
    started_at: str,
    finished_at: str,
    n: int,
    concurrency: int,
) -> None:
    """Write ``index.json`` to ``out_dir / 'index.json'``.

    ``records`` is the list of per-request dicts the stage runner built,
    in submission order. Each record SHOULD carry at least:

        {
            "node_id": str,
            "artifact": dict | None,                # parsed final artifact
            "reflow_triggered": bool,               # D-12
            "trial_selected_delta_id": str | None,  # D-10
            "exception": str | None,                # fail-fast passthrough
        }

    Missing keys are tolerated — the writer fills with safe defaults so
    a partial / failed-mid-batch records list still produces a row per
    request and the failed rows still sort cleanly under E1-E4 (extreme
    samples sink to 0/0/0.0 by construction in machine_judges).
    """
    rows: list[dict[str, Any]] = []
    for record in records:
        artifact = record.get("artifact") if isinstance(record, dict) else None

        # Run the three machine-judged VAL checks. Each returns
        # (bool, reason_str); we keep only the bool here — the reason
        # would clutter index.json (and the auditor reads it from
        # batch_summary.json's fail_lists when triaging).
        val01_pass, _ = judge_val01(artifact)
        val02_pass, _ = judge_val02(artifact)
        val04_pass, _ = judge_val04(artifact)

        # D-16 sortable columns. E2 and E3 share
        # len_transferable_disposition_text — same column, opposite
        # sort direction. The raw text passthrough is fidelity, NOT
        # an E-dimension.
        row: dict[str, Any] = {
            "node_id": _safe_str(record, "node_id"),
            # E1 — sort desc — longest covers_product_ids
            "len_covers_product_ids": extract_len_covers_product_ids(artifact),
            # E2 (asc, shortest) AND E3 (desc, longest) — same column
            "len_transferable_disposition_text": extract_len_transferable_disposition_text(artifact),
            # raw passthrough — NOT an E-dimension
            "transferable_disposition_text": extract_transferable_disposition_text(artifact),
            # E4 — sort desc — highest literal overlap
            "literal_overlap_user_signal_vs_transferable_disposition": extract_literal_overlap(artifact),
            # VAL booleans — D-12 machine-judged subset; VAL-03 is null
            # because per D-13/D-14 only manual case-reading by the user
            # can produce a verdict.
            "VAL-01_pass": val01_pass,
            "VAL-02_pass": val02_pass,
            "VAL-03_pass": None,
            "VAL-04_pass": val04_pass,
            # D-12 reflow attribution + D-10 trial-selection visibility
            "reflow_triggered": bool(record.get("reflow_triggered")) if isinstance(record, dict) else False,
            "trial_selected_delta_id": (
                record.get("trial_selected_delta_id") if isinstance(record, dict) else None
            ),
            # Fail-fast passthrough — exception class/message string the
            # stage runner attaches when a request terminates abnormally.
            "exception": record.get("exception") if isinstance(record, dict) else None,
        }
        rows.append(row)

    index_doc: dict[str, Any] = {
        "stage": stage,
        "batch_id": batch_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "n": n,
        "concurrency": concurrency,
        "requests": rows,
    }

    out_path = Path(out_dir) / "index.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(index_doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _safe_str(record: Any, key: str) -> str:
    if not isinstance(record, dict):
        return ""
    val = record.get(key)
    if val is None:
        return ""
    return str(val)
