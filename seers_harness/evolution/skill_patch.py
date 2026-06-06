"""JSON-edit patch contract for skill evolution trials."""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, field_validator

from seers_harness.workflow.structured_skill import JsonSkillEdit


class SkillDeltaPatch(BaseModel):
    """A single Markdown-derived JSON edit staged for production traffic."""

    target_path: str
    source_path: str
    original_source_sha256: str
    edits: list[JsonSkillEdit]
    delta_id: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("edits")
    @classmethod
    def _edits_must_be_non_empty(cls, value: list[JsonSkillEdit]) -> list[JsonSkillEdit]:
        if not value:
            raise ValueError("edits must be non-empty")
        return value


def sha256_of_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
