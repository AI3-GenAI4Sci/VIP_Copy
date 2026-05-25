"""DATA-03 schema invariants for BridgeLogic.

c17 BridgeLogic carries only the c16 anchor pair; the c15 slots
(`attractor_signal`, `feature_amplification`) are clean-deleted.
"""

from __future__ import annotations

from seers_harness.domain.models import BridgeLogic


def test_c16_pair_present() -> None:
    """DATA-03 positive — product_anchor + relation_anchor are declared and constructible."""
    fields = set(BridgeLogic.model_fields)
    assert {"product_anchor", "relation_anchor"} <= fields, fields
    bl = BridgeLogic(product_anchor="兰蔻轻盈防晒乳", relation_anchor="清爽适配")
    assert bl.product_anchor == "兰蔻轻盈防晒乳"
    assert bl.relation_anchor == "清爽适配"


def test_c15_slots_absent() -> None:
    """DATA-03 negative — c15 BridgeLogic slots removed (Q7 RESOLVED, Principle 8)."""
    forbidden = {"attractor_signal", "feature_amplification"}
    overlap = set(BridgeLogic.model_fields) & forbidden
    assert not overlap, f"BridgeLogic still declares c15 slots: {overlap}"
