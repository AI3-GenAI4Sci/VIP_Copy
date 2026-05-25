"""Plan 03-02 LOOP-06 static audit — pins master_plan §4.5's four invariants.

The source-of-truth file ``project/seers_harness/workflow/payloads.py`` may or
may not exist at any point in c17's history. Tests 2-4 use ``Path.exists()`` to
short-circuit when it is absent (Plan 03-03 will create it later). Test 1's
absence-scan over the whole ``seers_harness/`` tree runs unconditionally.

LOOP-06 coverage:
  Test 1 — three c16 legacy quota fields absent from the whole seers_harness tree
  Test 2 — candidate_generation_policy dict present in payloads.py (when it exists)
  Test 3 — no projection-style key in payloads.py (agent reads user_state.behavior directly)
  Test 4 — narrowed payloads.py-specific guard for the three legacy quota fields
"""

from __future__ import annotations

import pathlib

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
PAYLOADS_PATH = PROJECT_ROOT / "seers_harness/workflow/payloads.py"
SEERS_HARNESS_DIR = PROJECT_ROOT / "seers_harness"

FORBIDDEN_QUOTA_FIELDS = (
    "factor_angles_per_target_product",
    "copy_candidates_per_factor_angle",
    "max_candidates_per_request_formula",
)
_SKIP_MSG = "payloads.py not yet created — Plan 03-03 will activate this test"


def test_legacy_quota_fields_absent_from_entire_project_tree():
    """master_plan §4.5 invariant 1 — no c16 quota fields anywhere under seers_harness/."""
    violations = []
    for py_path in SEERS_HARNESS_DIR.rglob("*.py"):
        text = py_path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for token in FORBIDDEN_QUOTA_FIELDS:
                if token in line:
                    violations.append(f"{py_path.relative_to(PROJECT_ROOT)}:{line_no}: {token}")
    assert not violations, "LOOP-06 violation — legacy c16 quota fields found:\n" + "\n".join(violations)


def test_candidate_generation_policy_present_when_payloads_py_exists():
    """master_plan §4.5 invariant 2 — payloads.py exposes candidate_generation_policy dict."""
    import pytest
    if not PAYLOADS_PATH.exists():
        pytest.skip(_SKIP_MSG)
    text = PAYLOADS_PATH.read_text(encoding="utf-8")
    assert "candidate_generation_policy" in text, "candidate_generation_policy dict missing from payloads.py"
    assert "request/list_group" in text, "unit='request/list_group' string missing from payloads.py"
    assert "score_all_candidates_together_after_hard_rules" in text, (
        "score_all_candidates_together_after_hard_rules key missing from payloads.py"
    )


def test_no_projection_fields_in_payloads_py():
    """master_plan §4.5 invariant 3 — no projection-style keys (agent reads user_state.behavior directly)."""
    import pytest
    import re
    if not PAYLOADS_PATH.exists():
        pytest.skip(_SKIP_MSG)
    text = PAYLOADS_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"\b(projection|projected_\w+|user_history_projection)\b")
    hits = [(i, line) for i, line in enumerate(text.splitlines(), start=1) if pattern.search(line)]
    assert not hits, "LOOP-06 violation — projection-style fields found in payloads.py:\n" + "\n".join(
        f"  payloads.py:{i}: {line.strip()}" for i, line in hits
    )


def test_no_quota_field_references_in_payloads_py_when_exists():
    """master_plan §4.5 invariant 4 — narrowed payloads.py-specific quota-field guard."""
    import pytest
    if not PAYLOADS_PATH.exists():
        pytest.skip(_SKIP_MSG)
    text = PAYLOADS_PATH.read_text(encoding="utf-8")
    found = [token for token in FORBIDDEN_QUOTA_FIELDS if token in text]
    assert not found, f"LOOP-06 violation — legacy quota fields in payloads.py: {found}"


def test_payloads_read_intake_metadata_without_losing_features():
    """Intake may carry derived features/list context in metadata; payloads must not drop them."""
    import pytest
    if not PAYLOADS_PATH.exists():
        pytest.skip(_SKIP_MSG)
    from seers_harness.workflow.payloads import factor_payload_for

    payload = factor_payload_for(
        {
            "scenario_id": "S-1",
            "request_id": "R-1",
            "user_state": {"behavior": {}},
            "products": [{"product_id": "P-1", "group_key": "维生素"}],
            "metadata": {
                "derived_features_by_product": {
                    "P-1": {"cat3_alignment": "aligned"},
                    "P-2": {"cat3_alignment": "mismatch"},
                },
                "list_context": {"target_categories": ["维生素"]},
            },
        }
    )

    assert payload["derived_features_by_product"] == {
        "P-1": {"cat3_alignment": "aligned"}
    }
    assert payload["list_context"] == {"target_categories": ["维生素"]}
