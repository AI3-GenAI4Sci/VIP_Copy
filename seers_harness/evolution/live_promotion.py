"""Promote ready skill deltas into the live skill tree with archive rollback."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from seers_harness.evolution.delta_portfolio import DeltaPortfolioRow
from seers_harness.evolution.patchability import (
    patchability_for_delta,
    safe_live_skill_target,
    structured_skill_source_for_target,
)
from seers_harness.evolution.skill_patch import sha256_of_text
from seers_harness.workflow.structured_skill import (
    apply_json_skill_edits,
    load_structured_skill,
    render_structured_skill,
    write_structured_skill,
)


@dataclass(frozen=True)
class PromotionResult:
    portfolio: list[DeltaPortfolioRow]
    promoted_delta_ids: list[str] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    manifest_path: Path | None = None


def promote_ready_deltas(
    *,
    live_skill_root: Path,
    archive_root: Path,
    portfolio: list[DeltaPortfolioRow],
    min_ready_count: int,
    run_id: str,
    timestamp: str,
) -> PromotionResult:
    """Apply ready deltas to live skills after archiving current bytes."""
    ready = [row for row in portfolio if row.status == "ready_for_review"]
    if len(ready) < min_ready_count:
        return PromotionResult(portfolio=list(portfolio))

    promoted: list[str] = []
    skipped: list[dict[str, str]] = []
    manifest_files: list[dict[str, Any]] = []
    updated_by_id: dict[str, DeltaPortfolioRow] = {}

    for row in ready:
        try:
            target = safe_live_skill_target(live_skill_root, row.target_skill)
        except ValueError as exc:
            skipped.append(_skip(row, str(exc)))
            updated_by_id[row.delta_id] = row.model_copy(update={"status": "held"})
            continue
        if not target.exists():
            skipped.append(_skip(row, "target skill file not found"))
            updated_by_id[row.delta_id] = row.model_copy(update={"status": "held"})
            continue
        try:
            source = structured_skill_source_for_target(live_skill_root, row.target_skill)
        except ValueError as exc:
            skipped.append(_skip(row, str(exc)))
            updated_by_id[row.delta_id] = row.model_copy(update={"status": "held"})
            continue
        if not source.exists():
            skipped.append(_skip(row, "structured skill source file not found"))
            updated_by_id[row.delta_id] = row.model_copy(update={"status": "held"})
            continue
        patch_report = patchability_for_delta(row, live_skill_root)
        if not patch_report.patchable or patch_report.patch is None:
            skipped.append(_skip(row, patch_report.message or patch_report.reason))
            updated_by_id[row.delta_id] = row.model_copy(update={"status": "held"})
            continue
        compiled_patch = patch_report.patch

        target_skill = target.relative_to(live_skill_root.resolve()).as_posix()
        source_skill = source.relative_to(live_skill_root.resolve()).as_posix()
        before_target_text = target.read_text(encoding="utf-8")
        before_source_text = source.read_text(encoding="utf-8")
        before_target_sha = sha256_of_text(before_target_text)
        before_source_sha = sha256_of_text(before_source_text)
        try:
            patched_skill = apply_json_skill_edits(
                load_structured_skill(source),
                compiled_patch.edits,
            )
            after_target_text = render_structured_skill(patched_skill)
        except Exception as exc:
            skipped.append(_skip(row, str(exc)))
            updated_by_id[row.delta_id] = row.model_copy(update={"status": "held"})
            continue
        after_source_text = patched_skill.model_dump_json(indent=2)
        after_target_sha = sha256_of_text(after_target_text)
        after_source_sha = sha256_of_text(after_source_text)
        target_archive_rel = _archive_relative_path(
            timestamp=timestamp,
            delta_id=row.delta_id,
            target_skill=target_skill,
        )
        source_archive_rel = _archive_relative_path(
            timestamp=timestamp,
            delta_id=row.delta_id,
            target_skill=source_skill,
        )
        target_archive_path = archive_root / target_archive_rel
        source_archive_path = archive_root / source_archive_rel
        target_archive_path.parent.mkdir(parents=True, exist_ok=True)
        source_archive_path.parent.mkdir(parents=True, exist_ok=True)
        target_archive_path.write_text(before_target_text, encoding="utf-8")
        source_archive_path.write_text(before_source_text, encoding="utf-8")

        write_structured_skill(source, patched_skill)
        target.write_text(after_target_text, encoding="utf-8")
        promoted.append(row.delta_id)
        updated_by_id[row.delta_id] = row.model_copy(update={"status": "promoted"})
        manifest_files.append(
            {
                "delta_id": row.delta_id,
                "target_skill": target_skill,
                "source_skill": source_skill,
                "target_archive_path": target_archive_rel.as_posix(),
                "source_archive_path": source_archive_rel.as_posix(),
                "before_target_sha256": before_target_sha,
                "after_target_sha256": after_target_sha,
                "before_source_sha256": before_source_sha,
                "after_source_sha256": after_source_sha,
                "edits": [edit.model_dump(mode="json") for edit in compiled_patch.edits],
            }
        )

    manifest_path: Path | None = None
    if promoted or skipped:
        manifest_path = archive_root / timestamp / "promotion_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": "live-promotion.v1",
                    "run_id": run_id,
                    "timestamp": timestamp,
                    "promoted_delta_ids": promoted,
                    "skipped": skipped,
                    "files": manifest_files,
                },
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    return PromotionResult(
        portfolio=[
            updated_by_id.get(row.delta_id, row)
            for row in portfolio
        ],
        promoted_delta_ids=promoted,
        skipped=skipped,
        manifest_path=manifest_path,
    )


def restore_from_promotion_manifest(
    *,
    manifest_path: Path | None,
    live_skill_root: Path,
    archive_root: Path,
) -> None:
    """Restore archived live files recorded by one promotion manifest."""
    if manifest_path is None:
        raise ValueError("manifest_path is required")
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    for item in reversed(manifest.get("files") or []):
        target_skill = item.get("target_skill")
        source_skill = item.get("source_skill")
        target_archive_path = item.get("target_archive_path")
        source_archive_path = item.get("source_archive_path")
        if not isinstance(target_skill, str) or not isinstance(target_archive_path, str):
            continue
        target = safe_live_skill_target(live_skill_root, target_skill)
        if isinstance(source_skill, str) and isinstance(source_archive_path, str):
            source = live_skill_root / source_skill
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(
                (archive_root / source_archive_path).read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (archive_root / target_archive_path).read_text(encoding="utf-8"),
            encoding="utf-8",
        )


def _skip(row: DeltaPortfolioRow, reason: str) -> dict[str, str]:
    return {
        "delta_id": row.delta_id,
        "target_skill": row.target_skill,
        "reason": reason,
    }


def _archive_relative_path(
    *,
    timestamp: str,
    delta_id: str,
    target_skill: str,
) -> Path:
    safe_delta = _safe_segment(delta_id)
    return Path(timestamp) / safe_delta / target_skill


def _safe_segment(value: str) -> str:
    cleaned = value.replace("/", "_").replace("\\", "_").replace(":", "_")
    cleaned = cleaned.lstrip(".")
    return cleaned or "delta"
