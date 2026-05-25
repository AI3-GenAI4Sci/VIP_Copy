"""DATA-04 schema invariants for CopyCandidate.

`considered_drafts` + `chosen_draft_index` are required attributes per c17;
text/draft equality is HANDLER-enforced (Plan 02 TOOL-03), not model-enforced.
"""

from __future__ import annotations

from seers_harness.domain.models import CopyCandidate


def test_considered_drafts_field_present() -> None:
    """DATA-04 positive — considered_drafts + chosen_draft_index are declared."""
    fields = set(CopyCandidate.model_fields)
    assert {"considered_drafts", "chosen_draft_index"} <= fields, fields
    cc = CopyCandidate(
        text="清爽不闷的轻盈防晒",
        target_product_id="P-001",
        source_factor_id="F-1",
        considered_drafts=["a", "b", "c"],
        chosen_draft_index=2,
    )
    assert cc.considered_drafts[2] == "c"
    assert cc.chosen_draft_index == 2


def test_model_does_not_enforce_draft_text_equality() -> None:
    """DATA-04 boundary — model accepts text != considered_drafts[chosen_draft_index].

    Equality is enforced by the record_candidate handler in Plan 02, not by Pydantic.
    """
    cc = CopyCandidate(
        text="清爽不闷的轻盈防晒",
        target_product_id="P-001",
        source_factor_id="F-1",
        considered_drafts=["x"],
        chosen_draft_index=0,
    )
    assert cc.text == "清爽不闷的轻盈防晒"
    assert cc.considered_drafts == ["x"]
