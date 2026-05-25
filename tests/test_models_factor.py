"""DATA-01 + DATA-02 schema invariants for PersonalizationFactor.

Each test asserts a single invariant. Tests are RED until Task 3 lands
``seers_harness.domain.models``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from seers_harness.domain.models import PersonalizationFactor


def test_transferable_disposition_required() -> None:
    """DATA-01 — Constructing PersonalizationFactor without transferable_disposition fails."""
    with pytest.raises(ValidationError) as exc_info:
        PersonalizationFactor()
    errors = exc_info.value.errors()
    assert any(
        err["type"] == "missing" and err["loc"] == ("transferable_disposition",)
        for err in errors
    ), f"expected missing-field error on transferable_disposition; got {errors}"


def test_factor_constructs_with_disposition() -> None:
    """DATA-01 positive — providing transferable_disposition is sufficient."""
    factor = PersonalizationFactor(transferable_disposition="中年自我保健倾向")
    assert factor.transferable_disposition == "中年自我保健倾向"


def test_stop_gate_fields_absent() -> None:
    """DATA-02 — STOP-GATE residue fields removed."""
    forbidden = {
        "considered_user_signals",
        "considered_and_rejected",
        "factor_count_decision_rationale",
    }
    actual = set(PersonalizationFactor.model_fields)
    overlap = actual & forbidden
    assert not overlap, f"PersonalizationFactor still declares STOP-GATE fields: {overlap}"


def test_c15_legacy_fields_absent() -> None:
    """DATA-02 / Principle 8 — clean delete of c15 legacy plain-text fields."""
    forbidden = {
        "factor",
        "why_it_might_matter",
        "risk",
        "public_copy_brief",
        "sales_bridge_brief",
        "product_hooks",
        "scene_bridges",
        "raw_interest_fragment_private",
        "private_reasoning",
    }
    actual = set(PersonalizationFactor.model_fields)
    overlap = actual & forbidden
    assert not overlap, f"PersonalizationFactor still declares c15 legacy fields: {overlap}"
