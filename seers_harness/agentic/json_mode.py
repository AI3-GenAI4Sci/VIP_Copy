"""Single-turn JSON-mode skill execution."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from seers_harness.core.errors import SchemaValidationHarnessError


@dataclass(frozen=True)
class JsonModeResult:
    artifact: dict[str, Any]
    usage: dict[str, Any] = field(default_factory=dict)
    reasoning_content: str | None = None
    raw_response_text: str = ""


def run_skill_via_json(
    *,
    skill_bundle: str,
    payload: Mapping[str, Any],
    provider: Any,
    node_id: str,
) -> JsonModeResult:
    """Run one production skill through provider JSON mode."""
    messages = [
        {
            "role": "system",
            "content": (
                f"{skill_bundle}\n\n"
                "Output exactly one valid JSON object. Do not use tool calls. "
                "Do not wrap the JSON in Markdown."
            ),
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    result = provider.generate_json(
        node_id=node_id,
        skill_bundle=skill_bundle,
        messages=messages,
    )
    raw = str(getattr(result, "raw_response_text", "") or "")
    try:
        artifact = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SchemaValidationHarnessError(
            f"{node_id} returned malformed JSON content"
        ) from exc
    if not isinstance(artifact, dict):
        raise SchemaValidationHarnessError(
            f"{node_id} JSON content must be an object"
        )
    return JsonModeResult(
        artifact=artifact,
        usage=dict(getattr(result, "usage", {}) or {}),
        reasoning_content=getattr(result, "reasoning_content", None),
        raw_response_text=raw,
    )
