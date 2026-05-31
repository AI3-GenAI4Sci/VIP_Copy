"""TOOL-09 — Role classification audit.

ADR-01 Principles 1-3 forbid any handler from acting as a "brain" — every
handler is exactly one of:
    - hand   : appends or finalizes structural state, returns a literal string
    - eye    : projects a narrow view (count must remain 0 in c17 without
               written justification — see skill_tools.py header comment)
    - mirror : returns a fixed self-prompt, no state mutation

The ROLE CLASSIFICATION comment block at the top of skill_tools.py is the
authoritative declaration. These tests parse that block and assert it is
exhaustive, self-consistent, and consistent with handler-side observable
behavior.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from seers_harness.tools.skill_tools import (
    TOOL_HANDLERS,
    reflect_on_copy_quality,
    reflect_on_user_factor_coverage,
)

_SKILL_TOOLS_PATH = (
    Path(__file__).resolve().parent.parent
    / "seers_harness"
    / "tools"
    / "skill_tools.py"
)


def _parse_role_classification() -> dict[str, str]:
    """Parse the ROLE CLASSIFICATION header comment block.

    Format (one per line):
        # <handler_name><spaces><role_word>
    """
    text = _SKILL_TOOLS_PATH.read_text(encoding="utf-8")
    # Slice the block: between "ROLE CLASSIFICATION" and the next "# ---"
    # or end-of-block marker "(eye count:".
    block_start = text.index("ROLE CLASSIFICATION")
    block_end = text.index("(eye count:")
    block = text[block_start:block_end]
    out: dict[str, str] = {}
    pattern = re.compile(r"#\s+(\w+)\s+(hand|eye|mirror)\b")
    for m in pattern.finditer(block):
        out[m.group(1)] = m.group(2)
    return out


def test_role_classification_block_is_exhaustive() -> None:
    roles = _parse_role_classification()
    # Every handler in TOOL_HANDLERS must be classified.
    assert set(roles.keys()) == set(TOOL_HANDLERS.keys())


def test_role_classification_uses_only_hand_eye_mirror() -> None:
    roles = _parse_role_classification()
    assert set(roles.values()) <= {"hand", "eye", "mirror"}


def test_role_classification_eye_count_is_zero() -> None:
    """ADR-01 Principle 2: eye count must remain 0 in c17. Additions require
    written justification per the skill_tools.py header comment."""
    roles = _parse_role_classification()
    eye_handlers = [name for name, role in roles.items() if role == "eye"]
    assert eye_handlers == [], (
        f"unexpected eye handlers: {eye_handlers!r} — see skill_tools.py header"
    )


def test_role_classification_expected_counts() -> None:
    roles = _parse_role_classification()
    counts: dict[str, int] = {"hand": 0, "eye": 0, "mirror": 0}
    for role in roles.values():
        counts[role] += 1
    assert counts == {"hand": 4, "eye": 0, "mirror": 2}


def test_mirror_handlers_do_not_mutate_state() -> None:
    """Mirror role contract: state is untouched by reflect_* handlers."""
    state: dict = {"user_factors": [{"user_factor_id": "UF-1"}], "candidates": []}
    snapshot = {k: list(v) if isinstance(v, list) else v for k, v in state.items()}
    reflect_on_user_factor_coverage({}, state)
    reflect_on_copy_quality({}, state)
    assert state == snapshot


def test_mirror_handlers_return_strings() -> None:
    """Mirror role contract: return value is a non-empty string."""
    out_cov = reflect_on_user_factor_coverage({}, {})
    out_div = reflect_on_copy_quality({}, {})
    assert isinstance(out_cov, str) and len(out_cov) > 0
    assert isinstance(out_div, str) and len(out_div) > 0
