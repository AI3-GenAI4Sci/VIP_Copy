from __future__ import annotations

import json

from seers_harness.validation.index_writer import write_index


def _write(records, tmp_path):
    write_index(
        records=records,
        out_dir=tmp_path,
        stage=1,
        batch_id="batch-test",
        started_at="2026-05-27T00:00:00Z",
        finished_at="2026-05-27T00:01:00Z",
        n=len(records),
        concurrency=1,
    )
    return json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))


def test_index_writer_includes_failure_class(tmp_path):
    index_doc = _write(
        [
            {
                "node_id": "req-ok",
                "artifact": None,
                "reflow_triggered": False,
                "trial_selected_delta_id": None,
                "exception": None,
                "failure_class": "ok",
            },
            {
                "node_id": "req-auth",
                "artifact": None,
                "reflow_triggered": False,
                "trial_selected_delta_id": None,
                "exception": "ProviderAuthError",
                "failure_class": "auth",
            },
        ],
        tmp_path,
    )

    assert [row["failure_class"] for row in index_doc["requests"]] == ["ok", "auth"]


def test_index_writer_defaults_failure_class_to_ok_when_missing(tmp_path):
    index_doc = _write(
        [
            {
                "node_id": "legacy-row",
                "artifact": None,
                "reflow_triggered": False,
                "trial_selected_delta_id": None,
                "exception": None,
            }
        ],
        tmp_path,
    )

    assert index_doc["requests"][0]["failure_class"] == "ok"
