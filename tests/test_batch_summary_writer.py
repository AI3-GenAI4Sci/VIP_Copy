from __future__ import annotations

import json

from seers_harness.validation.batch_summary_writer import write_batch_summary


def _row(node_id: str, failure_class: str) -> dict:
    return {
        "node_id": node_id,
        "VAL-01_pass": True,
        "VAL-02_pass": True,
        "VAL-03_pass": None,
        "VAL-04_pass": True,
        "len_need_or_pain_text": 0,
        "reflow_triggered": False,
        "trial_selected_delta_id": None,
        "failure_class": failure_class,
    }


def _write_summary(tmp_path, rows):
    index_path = tmp_path / "index.json"
    index_path.write_text(
        json.dumps(
            {
                "stage": 1,
                "batch_id": "batch-test",
                "requests": rows,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    write_batch_summary(index_path)
    return json.loads((tmp_path / "batch_summary.json").read_text(encoding="utf-8"))


def test_batch_summary_by_failure_class_aggregation(tmp_path):
    summary = _write_summary(
        tmp_path,
        [
            _row("ok-1", "ok"),
            _row("ok-2", "ok"),
            _row("ok-3", "ok"),
            _row("auth-1", "auth"),
            _row("auth-2", "auth"),
            _row("transient-1", "transient"),
        ],
    )

    assert summary["by_failure_class"] == {"ok": 3, "auth": 2, "transient": 1}


def test_batch_summary_by_failure_class_completeness(tmp_path):
    summary = _write_summary(
        tmp_path,
        [
            _row("ok-1", "ok"),
            _row("auth-1", "auth"),
            _row("rate-1", "rate_limit"),
        ],
    )

    assert sum(summary["by_failure_class"].values()) == summary["totals"]["requests"]
