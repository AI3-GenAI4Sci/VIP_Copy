"""Temporary skill patch isolation for production-traffic exploration.

This module has one job: mirror the live ``workflow-skills`` tree into a
request-local workspace, apply structured JSON edits inside that copy,
and yield the copied root to the caller. It never runs a paired baseline, never
schedules an extra request, and never edits ``workflow-skills/current``
directly. Production exploration happens in ``validation.runner`` by routing
budgeted real request slots through this temporary patched skill surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import shutil
import threading
from pathlib import Path

from seers_harness.evolution.patchability import (
    PatchabilityReport,
    patchability_for_delta,
)
from seers_harness.evolution.skill_patch import (
    SkillDeltaPatch,
    sha256_of_text,
)
from seers_harness.workflow.structured_skill import (
    apply_json_skill_edits,
    load_structured_skill,
    render_structured_skill,
    write_structured_skill,
)
from seers_harness.workflow.skill_loader import NODE_SKILL_BINDING


_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SKILL_ROOTS: tuple[Path, ...] = (
    _REPO_ROOT / "workflow-skills" / "current",
    _REPO_ROOT / "workflow-skills" / "evolution",
)


@dataclass(frozen=True)
class CompiledDelta:
    """A portfolio delta proven patchable against one live skill snapshot."""

    delta_id: str
    target_skill: str
    operation: str
    patch: SkillDeltaPatch
    patch_hash: str

    @property
    def cache_key(self) -> str:
        return _safe_path_token(
            f"{self.delta_id}_{self.patch.original_source_sha256[:12]}_{self.patch_hash[:12]}"
        )


@dataclass
class DeltaCompiler:
    """Compile semantic delta rows into deterministic patch executions."""

    live_skill_root: Path

    def compile(self, delta: object) -> CompiledDelta | None:
        compiled, _report = self.compile_with_report(delta)
        return compiled

    def compile_with_report(
        self,
        delta: object,
    ) -> tuple[CompiledDelta | None, PatchabilityReport]:
        report = patchability_for_delta(delta, self.live_skill_root)
        if not report.patchable or report.patch is None:
            return None, report
        return CompiledDelta(
            delta_id=report.delta_id,
            target_skill=report.target_skill,
            operation=str(getattr(delta, "operation", "") or ""),
            patch=report.patch,
            patch_hash=_patch_hash(report.patch),
        ), report

    def compile_many(self, deltas: list[object]) -> dict[str, CompiledDelta]:
        compiled: dict[str, CompiledDelta] = {}
        for delta in deltas:
            item = self.compile(delta)
            if item is not None:
                compiled[item.delta_id] = item
        return compiled


@dataclass
class TrialWorkspaceCache:
    """Materialize patched skill roots once per distinct compiled delta."""

    live_skill_root: Path
    cache_dir: Path
    _prepared: dict[str, Path] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def prepare(self, compiled: CompiledDelta) -> Path:
        """Return a reusable patched skill root for ``compiled``."""
        with self._lock:
            cached = self._prepared.get(compiled.cache_key)
            if cached is not None:
                return cached

            root = self.cache_dir / compiled.cache_key / "skills"
            metadata_path = self.cache_dir / compiled.cache_key / "metadata.json"
            if self._metadata_matches(metadata_path, compiled) and root.exists():
                self._prepared[compiled.cache_key] = root
                return root

            if root.parent.exists():
                shutil.rmtree(root.parent)
            _materialize_skill_root(
                live_skill_root=self.live_skill_root,
                temp_root=root,
                patch=compiled.patch,
            )
            metadata_path.write_text(
                json.dumps(
                    {
                        "delta_id": compiled.delta_id,
                        "target_skill": compiled.target_skill,
                        "operation": compiled.operation,
                        "original_source_sha256": compiled.patch.original_source_sha256,
                        "patch_hash": compiled.patch_hash,
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            self._prepared[compiled.cache_key] = root
            return root

    def prepare_many(self, compiled: list[CompiledDelta]) -> dict[str, Path]:
        """Prepare and return skill roots keyed by delta id."""
        return {item.delta_id: self.prepare(item) for item in compiled}

    def _metadata_matches(self, path: Path, compiled: CompiledDelta) -> bool:
        if not path.exists():
            return False
        try:
            metadata = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return False
        return (
            metadata.get("delta_id") == compiled.delta_id
            and metadata.get("target_skill") == compiled.target_skill
            and metadata.get("operation") == compiled.operation
            and metadata.get("original_source_sha256")
            == compiled.patch.original_source_sha256
            and metadata.get("patch_hash") == compiled.patch_hash
        )


def _materialize_skill_root(
    *,
    live_skill_root: Path,
    temp_root: Path,
    patch: SkillDeltaPatch | None,
) -> None:
    """Copy ``live_skill_root`` and optionally apply one exact patch."""
    if temp_root.exists():
        shutil.rmtree(temp_root)
    temp_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(live_skill_root, temp_root)
    _complete_trial_skill_root(temp_root)

    if patch is None:
        return
    live_source = live_skill_root / patch.source_path
    if not live_source.exists():
        raise FileNotFoundError(
            f"patch source {patch.source_path!r} is not present in live skill root"
        )
    live_source_text = live_source.read_text(encoding="utf-8")
    if sha256_of_text(live_source_text) != patch.original_source_sha256:
        raise ValueError(
            "live skill root drift: original_source_sha256 mismatch; refusing to trial"
        )

    source_in_temp = temp_root / patch.source_path
    target_in_temp = temp_root / patch.target_path
    patched_skill = apply_json_skill_edits(
        load_structured_skill(source_in_temp),
        patch.edits,
    )
    write_structured_skill(source_in_temp, patched_skill)
    target_in_temp.write_text(render_structured_skill(patched_skill), encoding="utf-8")


def _complete_trial_skill_root(temp_root: Path) -> None:
    """Populate missing known skills so trial reads stay inside temp_root."""
    for skill_name in set(NODE_SKILL_BINDING.values()):
        for source_root in _DEFAULT_SKILL_ROOTS:
            source = source_root / skill_name
            target = temp_root / source_root.name / skill_name
            if target.exists():
                break
            if source.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source, target)
                break


def _patch_hash(patch: SkillDeltaPatch) -> str:
    encoded = json.dumps(
        patch.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256_of_text(encoded)


def _safe_path_token(value: str) -> str:
    cleaned = value.replace("/", "_").replace("\\", "_").replace(":", "_")
    cleaned = cleaned.lstrip(".")
    return cleaned or "delta"
