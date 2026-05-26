"""Evolution snapshot writer — Phase 7 plan 07-01 (D-11, VAL-06).

Reduces an event list produced by the optional observability hooks in
``seers_harness.evolution.delta_portfolio`` and
``seers_harness.evolution.trial_runner`` into a single JSON object on
disk. The output is the canonical ``evolution_snapshot.json`` shape that
Phase 7's per-request evidence layer writes alongside the per-node
artifact / messages / tool-call / usage files.

Schema (locked by plan 07-01 must-haves):

```json
{
  "delta_portfolio_before": ["delta-id", ...],
  "delta_portfolio_after":  ["delta-id", ...],
  "trials": [
    {"trial_id": "...", "status": "succeeded"},
    {"trial_id": "...", "status": "failed",
     "exception_class": "ValueError",
     "exception_message": "..."}
  ]
}
```

Degradation rules (D-11 — no business-logic change, snapshot must NOT
crash on partial event streams):

* Missing ``portfolio_assembled`` event → ``delta_portfolio_before`` and
  ``delta_portfolio_after`` are emitted as empty lists.
* Stray ``trial_started`` events with no matching outcome are ignored;
  only ``trial_succeeded`` / ``trial_failed`` records produce ``trials``
  rows. This keeps the snapshot a description of *observed outcomes*,
  not in-flight state.
* Unknown event ``type`` values are silently skipped — the writer is a
  reducer, not a validator.

The writer creates parent directories, writes UTF-8 JSON with
``indent=2`` and a trailing newline, matching the shared JSON-defaults
pattern in ``seers_harness/evolution/promotion_smoke.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from seers_harness.validation._secrets import _safe_message


def write_evolution_snapshot(
    events: list[dict],
    out_path: str | Path,
) -> None:
    """Write the reduced ``evolution_snapshot.json`` to ``out_path``.

    The snapshot has three top-level keys: ``delta_portfolio_before``,
    ``delta_portfolio_after``, and ``trials``. See module docstring for
    the full shape and degradation rules.
    """
    delta_portfolio_before: list[Any] = []
    delta_portfolio_after: list[Any] = []
    trials: list[dict[str, Any]] = []

    for event in events:
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        if event_type == "portfolio_assembled":
            # Last write wins — if a request emits multiple
            # portfolio_assembled events the most recent reflects the
            # final state visible to the per-request snapshot.
            before = event.get("delta_portfolio_before")
            after = event.get("delta_portfolio_after")
            if isinstance(before, list):
                delta_portfolio_before = list(before)
            if isinstance(after, list):
                delta_portfolio_after = list(after)
        elif event_type == "trial_succeeded":
            trial_id = event.get("trial_id", "")
            trials.append({"trial_id": trial_id, "status": "succeeded"})
        elif event_type == "trial_failed":
            trial_id = event.get("trial_id", "")
            entry: dict[str, Any] = {"trial_id": trial_id, "status": "failed"}
            exc_class = event.get("exception_class")
            if exc_class is not None:
                entry["exception_class"] = exc_class
            exc_msg = event.get("exception_message")
            if exc_msg is not None:
                # CR-03: redact secrets / cap length before persisting.
                # The reducer is the last write barrier before evidence
                # lands on disk; even if an upstream emitter forgets to
                # sanitise, we catch it here.
                entry["exception_message"] = _safe_message(str(exc_msg))
            trials.append(entry)
        # trial_started and any unknown type are intentionally ignored
        # (reducer scope per D-11 degradation rules).

    snapshot = {
        "delta_portfolio_before": delta_portfolio_before,
        "delta_portfolio_after": delta_portfolio_after,
        "trials": trials,
    }

    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
