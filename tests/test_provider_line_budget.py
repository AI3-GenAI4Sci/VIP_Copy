"""Plan 02-02 static-file assertions — line budget + symbol absences.

NO import of the target module — every test reads the source file as text and
asserts via grep-style ``in`` checks plus a non-blank non-comment line count.
Keeps the line-budget enforcement decoupled from import-time side effects.

PROV-* coverage:
  PROV-01 — generate_with_tools present, generate_json absent
  PROV-02 — response_format absent
  PROV-03 — NodeGenerationPolicy / policy_for_node absent; locked runtime strings present
  PROV-06 — line budget ≤ 150
"""

from __future__ import annotations

import pathlib

_SOURCE_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "seers_harness/provider_runtime/openai_compatible.py"
)
_SOURCE_TEXT = _SOURCE_PATH.read_text(encoding="utf-8")
_NONCOMMENT_LINE_COUNT = sum(
    1 for line in _SOURCE_TEXT.splitlines() if line.strip() and not line.strip().startswith("#")
)


def test_openai_compatible_line_count_at_most_150():
    """PROV-06 — ≤ 150 visible (non-blank, non-pure-comment) lines."""
    assert _NONCOMMENT_LINE_COUNT <= 150, (
        f"openai_compatible.py has {_NONCOMMENT_LINE_COUNT} visible lines (budget 150)"
    )


def test_openai_compatible_does_not_reference_response_format():
    """PROV-02 — no JSON-mode kwarg anywhere in source."""
    assert "response_format" not in _SOURCE_TEXT


def test_openai_compatible_does_not_define_generate_json():
    """PROV-01 — the c16 dual entry point is deleted."""
    assert "def generate_json" not in _SOURCE_TEXT


def test_openai_compatible_defines_generate_with_tools():
    """PROV-01 — the single tool-use entry point is present."""
    assert "def generate_with_tools" in _SOURCE_TEXT


def test_openai_compatible_does_not_define_node_generation_policy_class():
    """PROV-03 — no per-node branching machinery."""
    assert "class NodeGenerationPolicy" not in _SOURCE_TEXT
    assert "policy_for_node" not in _SOURCE_TEXT


def test_openai_compatible_locked_runtime_strings_in_source():
    """PROV-03 — the 4 locked runtime params appear as literal strings."""
    assert any(
        s in _SOURCE_TEXT for s in ('tool_choice="auto"', "tool_choice='auto'")
    )
    assert any(
        s in _SOURCE_TEXT for s in ('reasoning_effort="max"', "reasoning_effort='max'")
    )
    assert any(
        s in _SOURCE_TEXT
        for s in (
            '"thinking": {"type": "enabled"}',
            "'thinking': {'type': 'enabled'}",
        )
    )
