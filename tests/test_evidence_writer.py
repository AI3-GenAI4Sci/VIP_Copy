from __future__ import annotations

import json

from seers_harness.validation.evidence_writer import flush_evidence


def test_flush_evidence_preserves_turn_usage_and_writes_aggregate(tmp_path):
    request_log = [
        {
            "node_id": "copy_generation",
            "messages": [{"role": "user", "content": "first"}],
            "tool_calls": [{"id": "call-1", "name": "record_candidate"}],
            "last_usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 200,
                "total_tokens": 1200,
                "prompt_cache_miss_tokens": 900,
            },
        },
        {
            "node_id": "copy_generation",
            "messages": [{"role": "user", "content": "second"}],
            "tool_calls": [{"id": "call-2", "name": "submit_copies_final"}],
            "last_usage": {
                "prompt_tokens": 300,
                "completion_tokens": 50,
                "total_tokens": 350,
                "prompt_cache_miss_tokens": 247,
            },
        },
    ]

    flush_evidence(request_log, tmp_path)

    node_dir = tmp_path / "copy_generation"
    usage = json.loads((node_dir / "usage.json").read_text(encoding="utf-8"))
    usage_turns = [
        json.loads(line)
        for line in (node_dir / "usage_turns.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]

    assert usage["turn_count"] == 2
    assert usage["prompt_tokens"] == 1300
    assert usage["completion_tokens"] == 250
    assert usage["total_tokens"] == 1550
    assert usage["prompt_cache_miss_tokens"] == 1147
    assert usage["first"]["prompt_cache_miss_tokens"] == 900
    assert usage["last"]["prompt_cache_miss_tokens"] == 247
    assert [row["prompt_cache_miss_tokens"] for row in usage_turns] == [900, 247]
