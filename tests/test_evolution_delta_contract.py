"""Evolution delta contract for function-family operations."""

from __future__ import annotations

import pytest

from seers_harness.core.errors import ToolValidationError
from seers_harness.evolution.delta_portfolio import DeltaProposal
from seers_harness.tools.evolution_tools import record_delta_change


def _args(operation: str = "modify") -> dict:
    return {
        "delta_id": "D-1",
        "target_skill": "current/personalized-copy-generation/SKILL.md",
        "function_id": "f_user_factor_to_product_hook",
        "operation": operation,
        "observation": "copy repeated product names instead of product binding",
        "proposed_change": "modify the copy surface function to express product value through scene result",
        "evidence_refs": [{"path": "request_42.candidates.0", "value": None}],
        "applicable_surface": ["personalized_copy_generation"],
        "failure_types": ["repeated_product_name"],
    }


def test_delta_proposal_uses_function_operation_contract() -> None:
    proposal = DeltaProposal.model_validate(_args("delete"))
    assert proposal.function_id == "f_user_factor_to_product_hook"
    assert proposal.operation == "delete"
    assert "change_type" not in DeltaProposal.model_fields


def test_record_delta_change_accepts_add_modify_delete_operations() -> None:
    for operation in ["add", "modify", "delete"]:
        state: dict = {}
        out = record_delta_change(_args(operation), state)
        assert out == "recorded"
        assert state["delta_changes"][0]["operation"] == operation


def test_record_delta_change_rejects_unknown_operation() -> None:
    state: dict = {}
    args = _args("rewrite")
    with pytest.raises(ToolValidationError) as exc_info:
        record_delta_change(args, state)
    assert exc_info.value.arg_path == "operation"
