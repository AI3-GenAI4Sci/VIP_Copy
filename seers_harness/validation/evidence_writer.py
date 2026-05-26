"""Per-node JSONL evidence writer — Phase 7 plan 07-02 (D-22b).

Flushes the captured ``request_log`` produced by
:class:`seers_harness.validation.recording_provider.RecordingProvider`
to disk in the canonical per-node layout that every downstream
validator (07-03 batch index, 07-04 stage runner, case-analysis read)
depends on.

Per-record output layout::

    out_dir / <node_id> /
        ├── messages.jsonl      # one JSON object per request message
        ├── tool_calls.jsonl    # one JSON object per observed tool_call
        ├── artifact.json       # the final structured output
        └── usage.json          # prompt/completion/total tokens + model

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
* ``usage.json`` — ``record["last_usage"]`` (carries
  ``prompt_tokens``, ``completion_tokens``, ``total_tokens``,
  ``model``).

Per D-22b the writer is best-effort post-mortem: a single malformed
record logs to ``stderr`` and continues, because the stage runner has
already failed-fast at request level (D-02). Files are written once
per flush; no append-mode is needed.

JSON style follows the workspace pattern from
``seers_harness/evolution/promotion_smoke.py``: ``indent=2`` for
``*.json``, compact newline-delimited JSON for ``*.jsonl``.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any


def flush_evidence(request_log: list[dict], out_dir: str | Path) -> None:
    """Write per-node evidence files for every record in ``request_log``.

    See module docstring for the layout, naming rules, and degradation
    behaviour (single bad record logs and is skipped, not raised).
    """
    base = Path(out_dir)
    base.mkdir(parents=True, exist_ok=True)

    for index, record in enumerate(request_log):
        try:
            _flush_one(record, base, index)
        except Exception:
            # Best-effort post-mortem (D-22b): print to stderr and
            # continue. The stage runner already failed-fast at request
            # level (D-02), so a write failure here must not eclipse
            # the genuine evidence on disk.
            sys.stderr.write(
                f"[evidence_writer] failed to flush record index={index} "
                f"node_id={_safe_str(record, 'node_id')}\n"
            )
            traceback.print_exc(file=sys.stderr)


def _flush_one(record: dict, base: Path, index: int) -> None:
    node_id = record.get("node_id")
    if not isinstance(node_id, str) or not node_id:
        node_id = f"req_{index:04d}"

    node_dir = base / node_id
    node_dir.mkdir(parents=True, exist_ok=True)

    # messages.jsonl — one line per request message
    messages = record.get("messages") or []
    _write_jsonl(node_dir / "messages.jsonl", messages)

    # tool_calls.jsonl — one line per observed tool_call. Empty file
    # when the response had no tool_calls (the auditor expects the file
    # to exist regardless so the per-node layout is uniform).
    tool_calls = record.get("tool_calls") or []
    _write_jsonl(node_dir / "tool_calls.jsonl", tool_calls)

    # artifact.json — final structured output, with fallback
    artifact = _resolve_artifact(record)
    _write_json(node_dir / "artifact.json", artifact)

    # usage.json — prompt_tokens / completion_tokens / total_tokens / model
    usage = record.get("last_usage") or {}
    _write_json(node_dir / "usage.json", usage)


def _resolve_artifact(record: dict) -> Any:
    """Best-effort artifact extraction.

    Order:
      1. Explicit ``record["final_artifact"]`` if non-None.
      2. Last tool_call's already-parsed ``arguments`` dict (the proxy
         pre-parsed JSON via the inner provider's ``_parse_args``).
      3. ``raw_response_text`` parsed as JSON if it is a JSON string.
      4. The raw response dict so the auditor still has *something*.
    """
    final = record.get("final_artifact")
    if final is not None:
        return final

    tool_calls = record.get("tool_calls") or []
    if tool_calls:
        last_call = tool_calls[-1]
        if isinstance(last_call, dict):
            args = last_call.get("arguments")
            if isinstance(args, dict):
                return args

    response = record.get("response") or {}
    if isinstance(response, dict):
        raw_text = response.get("raw_response_text")
        if isinstance(raw_text, str) and raw_text.strip():
            try:
                return json.loads(raw_text)
            except json.JSONDecodeError:
                pass
        return response

    return {}


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
