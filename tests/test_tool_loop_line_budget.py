"""LOOP-04 — tool_loop.py is 50-100 visible (non-blank, non-pure-comment) lines.

Pure file-read assertion; no python import of the target module so this RED
test fails with FileNotFoundError BEFORE Task 3 lands the impl.

Phase-08 plan 08-08 (D8-B) raised the upper bound from 80 to 100 to
accommodate the charter-mandated ``_TRANSIENT_BACKOFF_SECONDS`` module-level
constant + docstring + the ``if attempt > 0: time.sleep(...)`` backoff
guard inside the existing transient-retry loop. The plan's ``forbid_list``
explicitly bars hardcoding the sequence into the for-loop literal, which
forces the constant + docstring footprint. Lower bound (50) is unchanged;
the small-module intent of LOOP-04 is preserved.
"""

from __future__ import annotations

import pathlib

_SOURCE_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "seers_harness/agentic/tool_loop.py"
)


def test_tool_loop_visible_line_count_in_50_to_100():
    """LOOP-04 — 50 ≤ visible-line count ≤ 100 (D8-B headroom)."""
    text = _SOURCE_PATH.read_text(encoding="utf-8")
    count = sum(
        1 for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )
    assert 50 <= count <= 100, (
        f"agentic/tool_loop.py has {count} visible lines (budget 50-100)"
    )
