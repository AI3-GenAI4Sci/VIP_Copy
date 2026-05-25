"""DATA-05 schema invariants for PerAxisVerdict + PersonalizedCopyRubricJudgment.

Critique fields (`verbatim_candidate_quote`, `bridge_to_anchor`, `templated_flag`)
MUST appear before `verdict` so DeepSeek emits them first (RESEARCH Open Q2).
"""

from __future__ import annotations

from seers_harness.domain.models import PerAxisVerdict, PersonalizedCopyRubricJudgment


def test_per_axis_field_order_critique_before_verdict() -> None:
    """DATA-05 — critique-before-verdict field ordering is preserved (ADR-03 §C2)."""
    field_order = list(PerAxisVerdict.model_fields.keys())
    assert field_order.index("verbatim_candidate_quote") < field_order.index("verdict"), field_order
    assert field_order.index("bridge_to_anchor") < field_order.index("verdict"), field_order
    assert field_order.index("templated_flag") < field_order.index("verdict"), field_order


def test_seven_axes_no_d4() -> None:
    """DATA-05 — c17 7-axis surface is constructible; no d4 field is hardcoded."""
    for axis in ("d1", "d2", "d3", "d5", "d6", "d7", "d8"):
        v = PerAxisVerdict(axis_id=axis, verdict="pass")
        assert v.axis_id == axis
    assert "d4" not in PersonalizedCopyRubricJudgment.model_fields


def test_rubric_judgment_has_seven_axis_capable_per_axis_list() -> None:
    """DATA-05 — per_axis carries the 7 axes that survive D4 deletion."""
    judgment = PersonalizedCopyRubricJudgment(
        candidate_id="c0",
        per_axis=[PerAxisVerdict(axis_id=a) for a in ("d1", "d2", "d3", "d5", "d6", "d7", "d8")],
    )
    assert len(judgment.per_axis) == 7
    seen = {v.axis_id for v in judgment.per_axis}
    assert seen == {"d1", "d2", "d3", "d5", "d6", "d7", "d8"}


def test_legacy_rubric_fields_absent() -> None:
    """DATA-05 — c15 legacy aggregate fields removed (PATTERNS line 169)."""
    forbidden = {
        "scores",
        "total_score",
        "core_floor_failed",
        "evidence_per_axis",
        "axes",
        "failed_axes",
    }
    overlap = set(PersonalizedCopyRubricJudgment.model_fields) & forbidden
    assert not overlap, f"PersonalizedCopyRubricJudgment still declares c15 fields: {overlap}"
