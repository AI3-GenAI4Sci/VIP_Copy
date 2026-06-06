"""Patchability checks for skill evolution deltas.

The evolution loop accepts semantic operations (add/modify/delete), but every
operation must still be represented as structured JSON edits against a live
``SKILL.json`` source before it can consume production trial traffic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from seers_harness.evolution.skill_patch import (
    SkillDeltaPatch,
    sha256_of_text,
)
from seers_harness.workflow.structured_skill import (
    JsonSkillEdit,
    StructuredSkill,
    apply_json_skill_edits,
    load_structured_skill,
    render_structured_skill,
    uses_numeric_section_index,
)


PATCHABLE_OPERATIONS: frozenset[str] = frozenset({"add", "modify", "delete"})


@dataclass(frozen=True)
class PatchabilityReport:
    """Result of checking whether one delta can be applied to live skills."""

    delta_id: str
    target_skill: str
    patchable: bool
    reason: str = ""
    message: str = ""
    patch: SkillDeltaPatch | None = None


@dataclass(frozen=True)
class LeadingFence:
    opening: str
    content: str
    closing: str
    after: str


def patchability_for_delta(delta: Any, live_skill_root: Path) -> PatchabilityReport:
    """Return whether ``delta`` can be trialed against ``live_skill_root``."""
    delta_id = str(getattr(delta, "delta_id", "") or "")
    target_skill = str(getattr(delta, "target_skill", "") or "")
    operation = str(getattr(delta, "operation", "") or "")
    if operation not in PATCHABLE_OPERATIONS:
        return PatchabilityReport(
            delta_id=delta_id,
            target_skill=target_skill,
            patchable=False,
            reason="unsupported_operation",
            message=f"unsupported operation {operation!r}",
        )
    try:
        target = safe_live_skill_target(live_skill_root, target_skill)
    except Exception as exc:
        return PatchabilityReport(
            delta_id=delta_id,
            target_skill=target_skill,
            patchable=False,
            reason="target_unresolvable",
            message=str(exc),
        )
    if not target.exists():
        return PatchabilityReport(
            delta_id=delta_id,
            target_skill=target_skill,
            patchable=False,
            reason="target_unresolvable",
            message="target skill file not found",
        )

    try:
        source = structured_skill_source_for_target(live_skill_root, target_skill)
    except ValueError as exc:
        return PatchabilityReport(
            delta_id=delta_id,
            target_skill=target_skill,
            patchable=False,
            reason="target_unresolvable",
            message=str(exc),
        )
    if not source.exists():
        return PatchabilityReport(
            delta_id=delta_id,
            target_skill=target_skill,
            patchable=False,
            reason="target_unresolvable",
            message="structured skill source file not found",
        )

    source_text = source.read_text(encoding="utf-8")
    patch_obj = getattr(delta, "patch", None)
    if isinstance(patch_obj, dict):
        raw_edits = patch_obj.get("edits") or []
    else:
        raw_edits = getattr(patch_obj, "edits", None) or []
    try:
        edits = [
            edit if isinstance(edit, JsonSkillEdit) else JsonSkillEdit.model_validate(edit)
            for edit in raw_edits
        ]
    except Exception as exc:
        return PatchabilityReport(
            delta_id=delta_id,
            target_skill=target_skill,
            patchable=False,
            reason="patch_unavailable",
            message=str(exc),
        )
    if not edits:
        return PatchabilityReport(
            delta_id=delta_id,
            target_skill=target_skill,
            patchable=False,
            reason="patch_unavailable",
            message="patch has no JSON edits",
        )
    numeric_section_paths = [edit.path for edit in edits if uses_numeric_section_index(edit.path)]
    if numeric_section_paths:
        return PatchabilityReport(
            delta_id=delta_id,
            target_skill=target_skill,
            patchable=False,
            reason="patch_unavailable",
            message=(
                "numeric section index paths are not patchable: "
                f"{numeric_section_paths[0]}; use /sections/by_heading/<heading>/..."
            ),
        )
    try:
        structured_source = load_structured_skill(source)
        edits = normalize_section_body_edits(structured_source, edits)
        patched = apply_json_skill_edits(structured_source, edits)
        render_structured_skill(patched)
    except ValueError as exc:
        return PatchabilityReport(
            delta_id=delta_id,
            target_skill=target_skill,
            patchable=False,
            reason="patch_unavailable",
            message=str(exc),
        )

    return PatchabilityReport(
        delta_id=delta_id,
        target_skill=target_skill,
        patchable=True,
        patch=SkillDeltaPatch(
            target_path=target_skill,
            source_path=source.relative_to(live_skill_root.resolve()).as_posix(),
            original_source_sha256=sha256_of_text(source_text),
            edits=edits,
            delta_id=delta_id or None,
        ),
    )


def is_patchable_delta(delta: Any, live_skill_root: Path) -> bool:
    """Return ``True`` when ``delta`` can consume a trial slot now."""
    return patchability_for_delta(delta, live_skill_root).patchable


def safe_live_skill_target(live_skill_root: Path, target_skill: str) -> Path:
    """Resolve a delta target under ``live_skill_root/current/**/SKILL.md``."""
    rel = Path(target_skill)
    if not rel.parts or rel.parts[0] != "current":
        raise ValueError("target skill must be under current/")
    root = live_skill_root.resolve()
    target = (root / rel).resolve()
    if target != root and root not in target.parents:
        raise ValueError("target skill escapes live skill root")
    current_root = root / "current"
    if current_root not in target.parents:
        raise ValueError("target skill must be under current/")
    if target.name != "SKILL.md":
        raise ValueError("target skill must be a SKILL.md file")
    return target


def structured_skill_source_for_target(live_skill_root: Path, target_skill: str) -> Path:
    """Return the structured ``SKILL.json`` source for a deployable skill."""
    target = safe_live_skill_target(live_skill_root, target_skill)
    source = target.with_name("SKILL.json")
    root = live_skill_root.resolve()
    resolved = source.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("structured skill source escapes live skill root")
    return resolved


def normalize_section_body_edits(
    skill: StructuredSkill,
    edits: list[JsonSkillEdit],
) -> list[JsonSkillEdit]:
    """Preserve Markdown containers when deltas replace structured section text."""
    sections = skill.sections or []
    bodies_by_heading = {
        section.heading: section.body
        for section in sections
    }
    normalized: list[JsonSkillEdit] = []
    for edit in edits:
        parts = _json_pointer_parts(edit.path)
        if (
            edit.op != "replace"
            or len(parts) != 4
            or parts[0] != "sections"
            or parts[1] != "by_heading"
            or parts[3] != "body"
        ):
            normalized.append(edit)
            continue
        heading = parts[2]
        original_body = bodies_by_heading.get(heading)
        replacement = edit.value if isinstance(edit.value, str) else None
        if original_body is None or replacement is None:
            normalized.append(edit)
            continue
        normalized.append(
            edit.model_copy(
                update={"value": _normalize_leading_fenced_body(original_body, replacement)}
            )
        )
    return normalized


def _normalize_leading_fenced_body(original_body: str, replacement: str) -> str:
    if replacement.lstrip().startswith(("```", "~~~")):
        return replacement
    fence = _parse_leading_fence(original_body)
    if fence is None:
        return replacement

    replacement_text = replacement.lstrip()
    body_after_fence = fence.after.lstrip()
    if body_after_fence:
        fence_body = _leading_whitespace(fence.after)
        fence_content = fence.content.rstrip("\r\n")
        if fence_content and replacement_text.startswith(fence_content):
            replacement_text = replacement_text[len(fence_content):].lstrip()
        return f"{fence.opening}{fence.content}{fence.closing}{fence_body}{replacement_text}"

    replacement_text = replacement_text.rstrip("\r\n")
    trailing_newline = "\n" if replacement_text else ""
    return f"{fence.opening}{replacement_text}{trailing_newline}{fence.closing}"


def _parse_leading_fence(body: str) -> LeadingFence | None:
    stripped_offset = len(body) - len(body.lstrip())
    if stripped_offset >= len(body):
        return None
    if not body[stripped_offset:].startswith(("```", "~~~")):
        return None

    opening_end = body.find("\n", stripped_offset)
    if opening_end < 0:
        return None
    opening = body[: opening_end + 1]
    fence_marker = body[stripped_offset : stripped_offset + 3]
    close_pattern = f"\n{fence_marker}"
    closing_start = body.find(close_pattern, opening_end + 1)
    if closing_start < 0:
        return None
    closing_start += 1
    closing_end = body.find("\n", closing_start)
    if closing_end < 0:
        closing_end = len(body) - 1

    return LeadingFence(
        opening=opening,
        content=body[opening_end + 1 : closing_start],
        closing=body[closing_start : closing_end + 1],
        after=body[closing_end + 1 :],
    )


def _leading_whitespace(value: str) -> str:
    return value[: len(value) - len(value.lstrip())]


def _json_pointer_parts(path: str) -> list[str]:
    return [
        part.replace("~1", "/").replace("~0", "~")
        for part in path.split("/")[1:]
    ]
