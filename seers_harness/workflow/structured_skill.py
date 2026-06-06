"""Structured skill source and deterministic Markdown rendering.

``SKILL.json`` is the structured source shape used by evolution edits.
``SKILL.md`` is the human-readable deployable artifact consumed by the
runtime. The renderer is deliberately small: it preserves ordered
frontmatter fields and Markdown section bodies, so existing skill prose can be
represented without inventing a new prose DSL.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class FrontmatterField(BaseModel):
    key: str
    value: str

    model_config = {"extra": "forbid"}


class StructuredSkillSection(BaseModel):
    level: int = Field(ge=1, le=6)
    heading: str
    body: str = ""

    model_config = {"extra": "forbid"}


class StructuredSkill(BaseModel):
    schema_version: int = 1
    frontmatter: list[FrontmatterField] = Field(default_factory=list)
    preamble: str = ""
    sections: list[StructuredSkillSection] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class JsonSkillEdit(BaseModel):
    op: Literal["add", "replace", "remove"]
    path: str
    value: Any = None

    model_config = {"extra": "forbid"}

    @field_validator("path")
    @classmethod
    def _path_must_be_pointer(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("JSON edit path must be an absolute JSON Pointer")
        return value


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_NUMERIC_SECTION_PATH_RE = re.compile(r"^/sections/\d+(?:/|$)")


def uses_numeric_section_index(path: str) -> bool:
    """Return whether a JSON Pointer addresses ``sections`` by array index."""
    return bool(_NUMERIC_SECTION_PATH_RE.match(path))


def parse_skill_markdown(text: str) -> StructuredSkill:
    frontmatter: list[FrontmatterField] = []
    body_start = 0
    lines = text.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            line = lines[index]
            if line.strip() == "---":
                body_start = index + 1
                break
            key, sep, value = line.partition(":")
            if sep:
                frontmatter.append(
                    FrontmatterField(key=key.strip(), value=value.strip())
                )

    sections: list[StructuredSkillSection] = []
    current_level: int | None = None
    current_heading: str | None = None
    current_body: list[str] = []
    preamble: list[str] = []
    for line in lines[body_start:]:
        match = _HEADING_RE.match(line.rstrip("\n"))
        if match:
            if current_level is not None and current_heading is not None:
                sections.append(
                    StructuredSkillSection(
                        level=current_level,
                        heading=current_heading,
                        body="".join(current_body),
                    )
                )
            current_level = len(match.group(1))
            current_heading = match.group(2)
            current_body = []
            continue
        if current_level is not None:
            current_body.append(line)
        else:
            preamble.append(line)

    if current_level is not None and current_heading is not None:
        sections.append(
            StructuredSkillSection(
                level=current_level,
                heading=current_heading,
                body="".join(current_body),
            )
        )

    return StructuredSkill(
        frontmatter=frontmatter,
        preamble="".join(preamble),
        sections=sections,
    )


def render_structured_skill(skill: StructuredSkill) -> str:
    chunks: list[str] = []
    if skill.frontmatter:
        chunks.append("---\n")
        for item in skill.frontmatter:
            chunks.append(f"{item.key}: {item.value}\n")
        chunks.append("---\n")
    chunks.append(skill.preamble)
    for section in skill.sections:
        if chunks and chunks[-1] and not chunks[-1].endswith("\n"):
            chunks.append("\n")
        chunks.append(f"{'#' * section.level} {section.heading}\n")
        chunks.append(section.body)
    return "".join(chunks)


def load_structured_skill(path: Path) -> StructuredSkill:
    return StructuredSkill.model_validate_json(path.read_text(encoding="utf-8"))


def render_structured_skill_file(path: Path) -> str:
    return render_structured_skill(load_structured_skill(path))


def write_structured_skill(path: Path, skill: StructuredSkill) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        skill.model_dump_json(indent=2),
        encoding="utf-8",
    )


def apply_json_skill_edits(
    value: StructuredSkill | dict[str, Any],
    edits: list[JsonSkillEdit],
) -> StructuredSkill:
    data = (
        value.model_dump(mode="json")
        if isinstance(value, StructuredSkill)
        else copy.deepcopy(value)
    )
    for edit in edits:
        _apply_one_edit(data, edit)
    return StructuredSkill.model_validate(data)


def skill_source_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def _apply_one_edit(document: Any, edit: JsonSkillEdit) -> None:
    parts = _pointer_parts(edit.path)
    if not parts:
        raise ValueError("JSON edit cannot replace the document root")
    if len(parts) >= 3 and parts[0] == "sections" and parts[1] == "by_heading":
        _apply_section_heading_edit(document, parts, edit)
        return
    parent = _resolve_parent(document, parts)
    key = parts[-1]
    if isinstance(parent, list):
        _apply_list_edit(parent, key, edit)
        return
    if isinstance(parent, dict):
        _apply_dict_edit(parent, key, edit)
        return
    raise ValueError(f"JSON edit parent at {edit.path!r} is not mutable")


def _apply_section_heading_edit(
    document: dict[str, Any],
    parts: list[str],
    edit: JsonSkillEdit,
) -> None:
    if not isinstance(document, dict):
        raise ValueError("section heading edit requires an object document")
    sections = document.get("sections")
    if not isinstance(sections, list):
        raise ValueError("section heading edit requires a sections array")
    section_index = _find_unique_section_index(sections, parts[2])
    if len(parts) == 3:
        _apply_list_edit(sections, str(section_index), edit)
        return
    section = sections[section_index]
    parent = _resolve_parent(section, parts[3:])
    key = parts[-1]
    if isinstance(parent, list):
        _apply_list_edit(parent, key, edit)
        return
    if isinstance(parent, dict):
        _apply_dict_edit(parent, key, edit)
        return
    raise ValueError(f"JSON edit parent at {edit.path!r} is not mutable")


def _find_unique_section_index(sections: list[Any], heading: str) -> int:
    matches = [
        index
        for index, section in enumerate(sections)
        if isinstance(section, dict) and section.get("heading") == heading
    ]
    if not matches:
        raise ValueError(f"section heading {heading!r} does not exist")
    if len(matches) > 1:
        raise ValueError(f"section heading {heading!r} is ambiguous")
    return matches[0]


def _apply_list_edit(parent: list[Any], key: str, edit: JsonSkillEdit) -> None:
    if edit.op == "add" and key == "-":
        parent.append(edit.value)
        return
    try:
        index = int(key)
    except ValueError as exc:
        raise ValueError(f"array path segment {key!r} is not an integer") from exc
    if edit.op == "add":
        if index < 0 or index > len(parent):
            raise ValueError(f"array add index {index} out of range")
        parent.insert(index, edit.value)
        return
    if index < 0 or index >= len(parent):
        raise ValueError(f"array index {index} out of range")
    if edit.op == "replace":
        parent[index] = edit.value
    elif edit.op == "remove":
        parent.pop(index)


def _apply_dict_edit(parent: dict[str, Any], key: str, edit: JsonSkillEdit) -> None:
    if edit.op == "add":
        if key in parent:
            raise ValueError(f"object key {key!r} already exists")
        parent[key] = edit.value
        return
    if key not in parent:
        raise ValueError(f"object key {key!r} does not exist")
    if edit.op == "replace":
        parent[key] = edit.value
    elif edit.op == "remove":
        parent.pop(key)


def _resolve_parent(document: Any, parts: list[str]) -> Any:
    cur = document
    for part in parts[:-1]:
        if isinstance(cur, list):
            try:
                index = int(part)
            except ValueError as exc:
                raise ValueError(f"array path segment {part!r} is not an integer") from exc
            if index < 0 or index >= len(cur):
                raise ValueError(f"array index {index} out of range")
            cur = cur[index]
        elif isinstance(cur, dict):
            if part not in cur:
                raise ValueError(f"object key {part!r} does not exist")
            cur = cur[part]
        else:
            raise ValueError(f"path segment {part!r} resolves to a scalar")
    return cur


def _pointer_parts(path: str) -> list[str]:
    if path == "":
        return []
    if not path.startswith("/"):
        raise ValueError("JSON Pointer must start with '/'")
    return [part.replace("~1", "/").replace("~0", "~") for part in path[1:].split("/")]
