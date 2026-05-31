from __future__ import annotations

import csv
import json

from seers_harness.validation.offline_export import (
    admitted_copy_rows,
    write_offline_copy_assets,
)


def test_admitted_copy_rows_export_user_request_copy_with_provenance() -> None:
    rows = admitted_copy_rows(
        scenario={
            "request_id": "req-1",
            "user_state": {"user_id": "user-1"},
        },
        generation_artifact={
            "candidates": [
                {
                    "candidate_id": "c-admit",
                    "product_id": "p1",
                    "source_user_factor_id": "uf1",
                    "text": "牙齿敏感选冷酸灵",
                },
                {
                    "candidate_id": "c-hold",
                    "product_id": "p1",
                    "source_user_factor_id": "uf2",
                    "text": "口碑爆款好评如潮",
                },
            ]
        },
        rubric_artifact={
            "judgments": [
                {
                    "candidate_id": "c-admit",
                    "product_id": "p1",
                    "copy_text": "牙齿敏感选冷酸灵",
                    "user_factor_id": "uf1",
                    "total_score": 22,
                    "decision": "admit",
                },
                {
                    "candidate_id": "c-hold",
                    "product_id": "p1",
                    "copy_text": "口碑爆款好评如潮",
                    "user_factor_id": "uf2",
                    "total_score": 20,
                    "decision": "hold",
                },
            ]
        },
    )

    assert rows == [
        {
            "user_id": "user-1",
            "request_id": "req-1",
            "copy": "牙齿敏感选冷酸灵",
            "product_id": "p1",
            "candidate_id": "c-admit",
            "user_factor_id": "uf1",
            "total_score": 22,
            "decision": "admit",
        }
    ]


def test_write_offline_copy_assets_writes_csv_and_jsonl(tmp_path) -> None:
    rows = [
        {
            "user_id": "user-1",
            "request_id": "req-1",
            "copy": "牙齿敏感选冷酸灵",
            "product_id": "p1",
            "candidate_id": "c1",
            "user_factor_id": "uf1",
            "total_score": 22,
            "decision": "admit",
        }
    ]

    write_offline_copy_assets(rows, tmp_path)

    with (tmp_path / "offline_copy_assets.csv").open(encoding="utf-8", newline="") as f:
        csv_rows = list(csv.DictReader(f))
    assert csv_rows[0]["user_id"] == "user-1"
    assert csv_rows[0]["request_id"] == "req-1"
    assert csv_rows[0]["copy"] == "牙齿敏感选冷酸灵"

    jsonl_rows = [
        json.loads(line)
        for line in (tmp_path / "offline_copy_assets.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert jsonl_rows == rows
