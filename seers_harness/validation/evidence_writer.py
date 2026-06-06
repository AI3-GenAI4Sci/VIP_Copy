"""Per-node JSONL evidence writer.

Flushes the captured ``request_log`` produced by
:class:`seers_harness.validation.recording_provider.RecordingProvider`
to disk in the canonical per-node layout that every downstream validator
(batch index, batch summary, case-analysis readers) depends on.

Per-record output layout::

    out_dir / <node_id> /
        ├── messages.jsonl      # one JSON object per request message
        ├── tool_calls.jsonl    # one JSON object per observed tool_call
        ├── artifact.json       # the final structured output
        ├── usage.json          # aggregate prompt/completion/total tokens + model
        └── usage_turns.jsonl   # one usage row per provider turn

When ``record["node_id"]`` is missing or empty, the writer falls back to
``req_<index:04d>`` (preserving the position of the record in the log).

Per D-22b:

* ``messages.jsonl`` — one line per message in the *request* messages list
  (role, content, optional tool_call_id, etc.); SDK objects are
  serialised via :func:`_jsonable` to keep the writer best-effort.
* ``tool_calls.jsonl`` — one line per parsed tool_call observed across
  the response (the proxy already extracts these in the
  ``{"id", "name", "arguments"}`` shape from the inner provider). When
  the response had no tool_calls the file is created empty.
* ``artifact.json`` — ``record["final_artifact"]`` if non-None;
  otherwise a best-effort fallback that parses the last tool_call's
  ``arguments`` (already a dict) or falls back to the response's
  ``raw_response_text`` parsed as JSON, finally falling back to the raw
  response dict so the auditor still has a starting point.
* ``usage_turns.jsonl`` — one ``record["last_usage"]`` row per provider
  turn for this node.
* ``usage.json`` — aggregate numeric usage across provider turns, plus
  ``first`` / ``last`` turn snapshots. This prevents later submit/reflection
  turns from overwriting the first-turn prompt evidence.

The writer is best-effort post-mortem: a single malformed record logs to
``stderr`` and continues, because the batch runner has already made the
request-level routing decision. Files are written once per flush; no
append-mode is needed.

JSON style follows the workspace pattern from
``seers_harness/evolution/promotion_smoke.py``: ``indent=2`` for
``*.json``, compact newline-delimited JSON for ``*.jsonl``.
"""

from __future__ import annotations

import json
import os.path
import sys
import traceback
from pathlib import Path
from typing import Any

from seers_harness.validation.request_evidence import NodeEvidence, normalize_request_log


def flush_evidence(request_log: list[dict], out_dir: str | Path) -> None:
    """Write per-node evidence files for every record in ``request_log``.

    See module docstring for the layout, naming rules, and degradation
    behaviour (single bad record logs and is skipped, not raised).
    """
    base = Path(out_dir)
    base.mkdir(parents=True, exist_ok=True)

    for evidence in normalize_request_log(request_log):
        try:
            _flush_node(evidence, base)
        except Exception:
            # Best-effort post-mortem: print to stderr and continue. A
            # write failure here must not eclipse the genuine request error.
            first_record = evidence.records[0] if evidence.records else {}
            sys.stderr.write(
                f"[evidence_writer] failed to flush record "
                f"index=<grouped> "
                f"node_id={_safe_str(first_record, 'node_id')}\n"
            )
            traceback.print_exc(file=sys.stderr)


def _flush_one(record: dict, base: Path, index: int) -> None:
    evidence = normalize_request_log([record])[0]
    _flush_node(evidence, base)


def _flush_node(evidence: NodeEvidence, base: Path) -> None:
    node_dir = base / evidence.node_id
    # Defence-in-depth (CR-04): even after _sanitise_node_id, refuse
    # any resolved path that escapes ``base``. commonpath raises
    # ValueError for cross-volume paths on Windows; treat that as a
    # rejection too.
    try:
        common = os.path.commonpath([node_dir.resolve(), base.resolve()])
    except ValueError:
        raise ValueError(f"node_id escaped out_dir: {evidence.node_id!r}")
    if common != str(base.resolve()):
        raise ValueError(f"node_id escaped out_dir: {evidence.node_id!r}")

    node_dir.mkdir(parents=True, exist_ok=True)

    # messages.jsonl — one line per request message
    _write_jsonl(node_dir / "messages.jsonl", evidence.messages)

    # tool_calls.jsonl — one line per observed tool_call. Empty file
    # when the response had no tool_calls (the auditor expects the file
    # to exist regardless so the per-node layout is uniform).
    _write_jsonl(node_dir / "tool_calls.jsonl", evidence.tool_calls)

    # artifact.json — final structured output, with fallback
    _write_json(node_dir / "artifact.json", evidence.artifact)

    # usage_turns.jsonl + usage.json — preserve per-turn evidence while
    # keeping the legacy aggregate file path downstream readers already use.
    _write_jsonl(node_dir / "usage_turns.jsonl", evidence.usage_turns)
    _write_json(node_dir / "usage.json", evidence.usage)


def _write_jsonl(path: Path, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(_jsonable(row), ensure_ascii=False))
            f.write("\n")


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(obj), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _jsonable(obj: Any) -> Any:
    """Recursively coerce SDK / Pydantic objects into JSON-friendly types.

    Best-effort fallback so the writer never explodes on a stray
    non-serialisable value. Falls back to ``repr`` for anything we
    don't recognise.
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    # Pydantic v2
    if hasattr(obj, "model_dump"):
        try:
            return _jsonable(obj.model_dump(mode="json"))
        except Exception:
            pass
    # Dataclass-style
    if hasattr(obj, "__dict__"):
        try:
            return _jsonable(vars(obj))
        except Exception:
            pass
    return repr(obj)


def _safe_str(record: Any, key: str) -> str:
    if not isinstance(record, dict):
        return "<non-dict>"
    val = record.get(key)
    return str(val) if val is not None else "<none>"
