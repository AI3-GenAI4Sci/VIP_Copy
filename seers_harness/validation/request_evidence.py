"""Normalize captured provider records for evidence writers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NodeEvidence:
    node_id: str
    records: list[dict]
    messages: list[Any]
    tool_calls: list[Any]
    artifact: Any
    usage_turns: list[dict[str, Any]]
    usage: dict[str, Any]


def normalize_request_log(request_log: list[dict]) -> list[NodeEvidence]:
    out: list[NodeEvidence] = []
    for node_id, indexed_records in group_request_log_by_node(request_log).items():
        records = [record for _index, record in indexed_records]
        messages: list[Any] = []
        tool_calls: list[Any] = []
        for record in records:
            messages.extend(record.get("messages") or [])
            tool_calls.extend(record.get("tool_calls") or [])
        usage_turns = [
            usage
            for record in records
            if isinstance((usage := record.get("last_usage") or {}), dict)
        ]
        out.append(
            NodeEvidence(
                node_id=node_id,
                records=records,
                messages=messages,
                tool_calls=tool_calls,
                artifact=resolve_artifact(records[-1] if records else {}),
                usage_turns=usage_turns,
                usage=aggregate_usage(usage_turns),
            )
        )
    return out


def group_request_log_by_node(request_log: list[dict]) -> dict[str, list[tuple[int, dict]]]:
    grouped: dict[str, list[tuple[int, dict]]] = {}
    for index, record in enumerate(request_log):
        fallback = f"req_{index:04d}"
        node_id = sanitise_node_id(record.get("node_id"), fallback)
        grouped.setdefault(node_id, []).append((index, record))
    return grouped


def aggregate_usage(turns: list[dict[str, Any]]) -> dict[str, Any]:
    if not turns:
        return {}
    aggregate: dict[str, Any] = {"turn_count": len(turns)}
    numeric_keys = sorted(
        {
            key
            for turn in turns
            for key, value in turn.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
    )
    for key in numeric_keys:
        aggregate[key] = sum(
            turn.get(key, 0)
            for turn in turns
            if isinstance(turn.get(key), (int, float))
            and not isinstance(turn.get(key), bool)
        )
    model = turns[-1].get("model")
    if model is not None:
        aggregate["model"] = model
    aggregate["first"] = turns[0]
    aggregate["last"] = turns[-1]
    return aggregate


def sanitise_node_id(raw: Any, fallback: str) -> str:
    if not isinstance(raw, str) or not raw:
        return fallback
    cleaned = raw.replace("/", "_").replace("\\", "_").replace(":", "_")
    cleaned = cleaned.lstrip(".")
    if not cleaned or cleaned in {".", ".."}:
        return fallback
    return cleaned


def resolve_artifact(record: dict) -> Any:
    final = record.get("final_artifact")
    if final is not None:
        return final

    tool_calls = record.get("tool_calls") or []
    if tool_calls:
        last_call = tool_calls[-1]
        if isinstance(last_call, dict):
            args = last_call.get("arguments")
            if isinstance(args, dict):
                return args

    response = record.get("response") or {}
    if isinstance(response, dict):
        raw_text = response.get("raw_response_text")
        if isinstance(raw_text, str) and raw_text.strip():
            try:
                return json.loads(raw_text)
            except json.JSONDecodeError:
                pass
        return response

    return {}
