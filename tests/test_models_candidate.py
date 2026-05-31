"""Schema invariants for minimal CopyCandidate artifacts."""

from __future__ import annotations

from seers_harness.domain.models import CopyCandidate


def test_copy_candidate_declares_exact_fields_in_order() -> None:
    assert list(CopyCandidate.model_fields) == [
        "candidate_id",
        "product_id",
        "source_user_factor_id",
        "text",
        "commercial_angle",
        "product_binding",
        "fact_binding",
    ]


def test_copy_candidate_constructs_with_minimal_schema() -> None:
    cc = CopyCandidate(
        candidate_id="C-1",
        product_id="P-001",
        source_user_factor_id="UF-1",
        text="清爽不闷的轻盈防晒",
    )
    assert cc.candidate_id == "C-1"
    assert cc.product_id == "P-001"


def test_copy_candidate_legacy_reasoning_fields_absent() -> None:
    forbidden = {
        "target_product_id",
        "group_key",
        "bridge_logic",
        "considered_drafts",
        "chosen_draft_index",
        "used_copyable_hooks",
        "intended_effect",
    }
    overlap = set(CopyCandidate.model_fields) & forbidden
    assert not overlap, f"CopyCandidate still declares removed fields: {overlap}"
