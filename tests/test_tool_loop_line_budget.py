"""LOOP-04 — tool_loop.py is 50-80 visible (non-blank, non-pure-comment) lines.

Pure file-read assertion; no python import of the target module so this RED
test fails with FileNotFoundError BEFORE Task 3 lands the impl.
"""

from __future__ import annotations

import pathlib

_SOURCE_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "seers_harness/agentic/tool_loop.py"
)


def test_tool_loop_visible_line_count_in_50_to_80():
    """LOOP-04 — 50 ≤ visible-line count ≤ 80."""
    text = _SOURCE_PATH.read_text(encoding="utf-8")
    count = sum(
        1 for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )
    assert 50 <= count <= 80, (
        f"agentic/tool_loop.py has {count} visible lines (budget 50-80)"
    )
