from __future__ import annotations

import json

from seers_harness.validation.batch_summary_writer import write_batch_summary
from seers_harness.validation.machine_judges import (
    build_behavioral_report,
    compute_belief_update_count,
    compute_copy_candidate_count_p50,
    compute_delta_diversity,
    compute_factor_count_p50,
    compute_factor_diversity,
    compute_reflection_trigger_rate,
)


def test_machine_judges_factor_count_p50() -> None:
    artifacts = [{"factors": [{}] * n} for n in [1, 2, 3, 4, 5, 6]]
    assert compute_factor_count_p50(artifacts) == 3.5
    assert compute_factor_count_p50([{"factors": [{}] * n} for n in [2, 2, 3, 3, 3, 3]]) == 3.0


def test_machine_judges_factor_diversity_jaccard() -> None:
    diverse = [
        {
            "factors": [
                {"covers_product_ids": ["p1", "p2"], "claim": "甲乙"},
                {"covers_product_ids": ["p3", "p4"], "claim": "丙丁"},
            ]
        }
    ]
    identical = [
        {
            "factors": [
                {"covers_product_ids": ["p1"], "claim": "甲乙"},
                {"covers_product_ids": ["p1"], "claim": "甲乙"},
            ]
        }
    ]

    assert compute_factor_diversity(diverse) == 1.0
    assert compute_factor_diversity(identical) == 0.0
    assert compute_factor_diversity([]) == 0.0
    assert compute_factor_diversity([{"factors": [{}]}]) == 0.0


def test_machine_judges_copy_candidate_count_p50() -> None:
    artifacts = [
        {"candidates": [{}] * n}
        for n in [1, 2, 2, 3, 4]
    ]
    assert compute_copy_candidate_count_p50(artifacts) == 2.0


def test_machine_judges_reflection_trigger_rate() -> None:
    assert compute_reflection_trigger_rate(
        [(2, ["reflect_on_coverage"]), (2, []), (5, [])]
    ) == 0.5
    assert compute_reflection_trigger_rate([(5, []), (10, [])]) == 1.0


def test_machine_judges_delta_diversity_and_belief_updates() -> None:
    proposals = [
        {"delta_id": "D1", "target_skill": "A", "change_type": "modify_skill"},
        {"delta_id": "D2", "target_skill": "B", "change_type": "modify_skill"},
    ]
    portfolio = [
        {"delta_id": "D1", "sample_count": 0},
        {"delta_id": "D2", "sample_count": 3},
        {"delta_id": "D3", "sample_count": 1},
    ]

    assert compute_delta_diversity(proposals) == {
        "count": 2,
        "unique_targets": 2,
        "unique_change_types": 1,
    }
    assert compute_delta_diversity([]) == {
        "count": 0,
        "unique_targets": 0,
        "unique_change_types": 0,
    }
    assert compute_belief_update_count(portfolio) == 2
    assert compute_belief_update_count([]) == 0


def test_build_behavioral_report_happy_path(tmp_path) -> None:
    stage_dir = tmp_path / "stage1"
    _write_index(stage_dir, ["req-1", "req-2"])
    _write_request(
        stage_dir,
        "req-1",
        factors=[
            {"covers_product_ids": ["p1"], "claim": "甲"},
            {"covers_product_ids": ["p2"], "claim": "乙"},
        ],
        candidate_counts=2,
        tool_names=["reflect_on_coverage"],
    )
    _write_request(
        stage_dir,
        "req-2",
        factors=[
            {"covers_product_ids": ["p3"], "claim": "丙"},
            {"covers_product_ids": ["p4"], "claim": "丁"},
            {"covers_product_ids": ["p5"], "claim": "戊"},
            {"covers_product_ids": ["p6"], "claim": "己"},
        ],
        candidate_counts=3,
        portfolio=[
            {
                "delta_id": "D1",
                "target_skill": "current/a/SKILL.md",
                "change_type": "modify_skill",
                "sample_count": 1,
            }
        ],
    )

    report = build_behavioral_report(stage_dir)

    assert set(report) == {
        "factor_count_p50",
        "factor_diversity_score",
        "copy_candidate_count_p50",
        "reflection_triggered_when_underspec_rate",
        "delta_diversity_score",
        "trial_belief_update_count",
    }
    assert report["factor_count_p50"] == 3.0
    assert report["factor_diversity_score"] == 1.0
    assert report["copy_candidate_count_p50"] == 2.5
    assert report["reflection_triggered_when_underspec_rate"] == 1.0
    assert report["delta_diversity_score"] == {
        "count": 1,
        "unique_targets": 1,
        "unique_change_types": 1,
    }
    assert report["trial_belief_update_count"] == 1


def test_build_behavioral_report_handles_missing_evidence(tmp_path) -> None:
    stage_dir = tmp_path / "stage1"
    _write_index(stage_dir, ["req-missing"])
    (stage_dir / "req-missing").mkdir(parents=True)

    assert build_behavioral_report(stage_dir) == {
        "factor_count_p50": 0.0,
        "factor_diversity_score": 0.0,
        "copy_candidate_count_p50": 0.0,
        "reflection_triggered_when_underspec_rate": 1.0,
        "delta_diversity_score": {
            "count": 0,
            "unique_targets": 0,
            "unique_change_types": 0,
        },
        "trial_belief_update_count": 0,
    }


def test_batch_summary_includes_behavioral_metrics(tmp_path) -> None:
    stage_dir = tmp_path / "stage1"
    _write_index(stage_dir, ["req-1"])
    _write_request(
        stage_dir,
        "req-1",
        factors=[{"covers_product_ids": ["p1"], "claim": "甲"}],
        candidate_counts=2,
    )

    write_batch_summary(stage_dir / "index.json")
    summary = json.loads((stage_dir / "batch_summary.json").read_text(encoding="utf-8"))

    assert "behavioral_metrics" in summary
    assert set(summary["behavioral_metrics"]) == {
        "factor_count_p50",
        "factor_diversity_score",
        "copy_candidate_count_p50",
        "reflection_triggered_when_underspec_rate",
        "delta_diversity_score",
        "trial_belief_update_count",
    }


def _write_index(stage_dir, request_ids: list[str]) -> None:
    stage_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "node_id": request_id,
            "VAL-01_pass": True,
            "VAL-02_pass": True,
            "VAL-03_pass": None,
            "VAL-04_pass": True,
            "len_claim_text": 0,
            "reflow_triggered": False,
            "trial_selected_delta_id": None,
            "failure_class": "ok",
        }
        for request_id in request_ids
    ]
    (stage_dir / "index.json").write_text(
        json.dumps({"stage": 1, "batch_id": "batch-test", "requests": rows}),
        encoding="utf-8",
    )


def _write_request(
    stage_dir,
    request_id: str,
    *,
    factors: list[dict],
    candidate_counts: int,
    tool_names: list[str] | None = None,
    portfolio: list[dict] | None = None,
) -> None:
    request_dir = stage_dir / request_id
    generation_dir = request_dir / "evidence/personalized_copy_generation"
    generation_dir.mkdir(parents=True, exist_ok=True)
    (generation_dir / "artifact.json").write_text(
        json.dumps(
            {
                "factors": factors,
                "candidates": [{"candidate_id": f"c{i}"} for i in range(candidate_counts)],
            }
        ),
        encoding="utf-8",
    )
    (generation_dir / "tool_calls.jsonl").write_text(
        "".join(json.dumps({"name": name}) + "\n" for name in (tool_names or [])),
        encoding="utf-8",
    )
    (request_dir / "evolution_snapshot.json").write_text(
        json.dumps({"portfolio": portfolio or []}),
        encoding="utf-8",
    )
