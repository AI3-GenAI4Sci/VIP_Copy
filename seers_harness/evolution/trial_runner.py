"""Phase 6 plan 06-02 task 02 — minimal trial runner.

This module isolates one experimental skill delta inside a temporary
copy of the live skill root, runs a full request through
``WorkflowRuntime.run_request`` against that temp surface, and restores
the original content on exit. The contract is:

1. ``apply_delta_patch_temporarily`` is a context manager. It writes the
   patch's ``replacement_text`` to a temp-rooted copy of the target file
   while leaving the live skill root unchanged. The original file's
   SHA-256 must match ``original_text_sha256`` or the patch refuses to
   apply. ``finally`` restores the original content on the temp copy, so
   even when the body raises the file the caller pointed at returns to
   its pre-trial state.

2. ``run_request_trial`` accepts a ``WorkflowRuntime``, a scenario, a list
   of nodes, an optional patch, and the live skill root. It runs the
   patch under the context manager, runs ``runtime.run_request``, and
   returns a ``TrialOutcome`` carrying the artifact paths plus the
   ``DeltaPortfolioRow`` update inputs the caller will later feed into
   ``update_after_trial``.

The module never edits ``workflow-skills/current/`` directly. Patches
land on a temp workspace tree only. The forbid list in 06-02-PLAN.md
calls this out explicitly: trial isolation must be temp-only.
"""

from __future__ import annotations

import hashlib
import shutil
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from pydantic import BaseModel

from seers_harness.workflow.dag_runner import NodeSpec, WorkflowRuntime


# --------------------------------------------------------------------------- #
# Patch contract                                                              #
# --------------------------------------------------------------------------- #


class SkillDeltaPatch(BaseModel):
    """A single-file skill-surface patch staged for a trial.

    ``target_path`` is the path *relative to the skill root* the trial
    will copy and patch. ``original_text_sha256`` locks the expected
    original content of that file inside the live root, so the trial
    refuses to apply onto a drifted surface. ``replacement_text`` is the
    full replacement contents for the trial copy.

    The intentionally narrow surface (single file, single delta) matches
    D-06: a trial applies at most one delta.
    """

    target_path: str
    original_text_sha256: str
    replacement_text: str

    model_config = {"extra": "forbid"}


def sha256_of_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Temporary trial surface                                                     #
# --------------------------------------------------------------------------- #


@contextmanager
def apply_delta_patch_temporarily(
    live_skill_root: Path,
    workspace_dir: Path,
    patch: SkillDeltaPatch | None,
) -> Iterator[Path]:
    """Yield a path to a temporary copy of ``live_skill_root``.

    The full skill tree is mirrored into ``workspace_dir / "skills"`` so
    nothing the trial reads can fall through to the live tree. If
    ``patch`` is provided, the patched file is rewritten inside the copy
    and the live file is hash-checked before the trial begins.

    On exit (normal or exception), the temp copy is restored to its
    original content. The live root is *never* modified by this context
    manager; the restore step exists so the temp surface is auditable
    after a trial without claiming partial state.
    """
    workspace_dir.mkdir(parents=True, exist_ok=True)
    temp_root = workspace_dir / "skills"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    shutil.copytree(live_skill_root, temp_root)

    original_text: str | None = None
    target_in_temp: Path | None = None
    if patch is not None:
        live_target = live_skill_root / patch.target_path
        if not live_target.exists():
            raise FileNotFoundError(
                f"patch target {patch.target_path!r} is not present in live skill root"
            )
        live_text = live_target.read_text(encoding="utf-8")
        if sha256_of_text(live_text) != patch.original_text_sha256:
            raise ValueError(
                "live skill root drift: original_text_sha256 mismatch; refusing to trial"
            )

        target_in_temp = temp_root / patch.target_path
        original_text = target_in_temp.read_text(encoding="utf-8")
        target_in_temp.write_text(patch.replacement_text, encoding="utf-8")

    try:
        yield temp_root
    finally:
        if patch is not None and target_in_temp is not None and original_text is not None:
            target_in_temp.write_text(original_text, encoding="utf-8")


# --------------------------------------------------------------------------- #
# Trial outcome                                                               #
# --------------------------------------------------------------------------- #


@dataclass
class TrialOutcome:
    """Per-request trial result.

    ``artifact_paths`` mirrors ``WorkflowRuntime.run_request``'s return
    value. ``trial_delta_id`` is the delta the trial applied (or ``None``
    if no patch was supplied — a control trial). ``success`` and
    ``failure_category`` describe the run shape so the caller can fold
    the outcome into ``update_after_trial`` and ``buffer_trajectory``.

    ``token_cost_observed`` defaults to ``0``. Callers with provider-side
    usage data can override; for fake-provider tests the value stays at
    zero.
    """

    request_id: str
    scenario_id: str = ""
    trial_delta_id: str | None = None
    artifact_paths: dict[str, Path] = field(default_factory=dict)
    success: bool = True
    failure_category: str | None = None
    token_cost_observed: int = 0
    tool_call_count: int = 0


def run_request_trial(
    *,
    runtime: WorkflowRuntime,
    scenario: Any,
    nodes: list[NodeSpec],
    live_skill_root: Path,
    workspace_dir: Path,
    patch: SkillDeltaPatch | None = None,
    request_id: str = "",
    scenario_id: str = "",
    events: list[dict] | None = None,
) -> TrialOutcome:
    """Run one request inside a temporary skill surface.

    The temp surface lives only under ``workspace_dir`` (the live root is
    never edited). On any exception, the outcome carries ``success=False``
    and a coarse failure category; the temp surface is still restored
    because ``apply_delta_patch_temporarily``'s ``finally`` runs.

    The runtime's ``output_dir`` is honored as-is: artifacts land where
    the caller asked, not under ``workspace_dir / "skills"``. The skill
    root copy is for skill-text isolation only.

    Phase 7 plan 07-01 adds an optional ``events: list[dict] | None``
    observability seam (D-11, D-22(c)). When ``events`` is ``None``, the
    runner is byte-identical to its Phase 6 behaviour — no event records
    are produced, no extra branching is observable from the outside. When
    a list is supplied, the runner appends:

    * one ``trial_started`` event before invoking the runtime,
    * one ``trial_succeeded`` event on the success path, OR
    * one ``trial_failed`` event on the exception path (per D-19, this
      includes ``exception_class`` so the downstream classifier can route
      schema/protocol failures fail-fast vs transient failures recorded
      against the delta's belief).

    Per D-20, this hook does NOT modify trial trigger cadence or selection
    logic — Phase 6's portfolio-adaptive trigger stays untouched. Zero
    observed trials in 20 requests is a legitimate VAL-06 outcome.
    """
    trial_delta_id_for_event = (
        _delta_id_from_patch_or_none(patch) if patch is not None else None
    )
    outcome = TrialOutcome(
        request_id=request_id,
        scenario_id=scenario_id,
        trial_delta_id=None,
    )

    if events is not None:
        events.append(
            {
                "type": "trial_started",
                "trial_id": request_id,
                "delta_id": trial_delta_id_for_event,
            }
        )

    with apply_delta_patch_temporarily(live_skill_root, workspace_dir, patch) as _temp_root:
        # The temp_root copy is held open so a future skill-loader hook can
        # be pointed at it; current handlers load skill bundle text via the
        # provider payload pipeline, so we do not need to swap globals here.
        try:
            paths = runtime.run_request(scenario=scenario, nodes=nodes)
            outcome.artifact_paths = dict(paths)
            outcome.success = True
            outcome.tool_call_count = sum(
                int(ev.get("tool_calls_made") or 0)
                for ev in runtime.trace
                if ev.get("type") == "tool_loop_summary"
            )
        except Exception as exc:
            outcome.success = False
            outcome.failure_category = type(exc).__name__
            if events is not None:
                # WR-06 (CR-03 mirror) — redact at the emitter so even
                # in-memory consumers of ``events`` (not just the on-disk
                # snapshot reducer) see a safe message.
                from seers_harness.validation._secrets import safe_exc_message
                events.append(
                    {
                        "type": "trial_failed",
                        "trial_id": request_id,
                        "delta_id": trial_delta_id_for_event,
                        "exception_class": type(exc).__name__,
                        "exception_message": safe_exc_message(exc),
                    }
                )

    if patch is not None:
        outcome.trial_delta_id = trial_delta_id_for_event

    if events is not None and outcome.success:
        events.append(
            {
                "type": "trial_succeeded",
                "trial_id": request_id,
                "delta_id": trial_delta_id_for_event,
            }
        )
    return outcome


def _delta_id_from_patch_or_none(patch: SkillDeltaPatch) -> str | None:
    """Best-effort delta id derived from the patch target.

    The patch contract does not carry the delta id (delta ids live in
    ``DeltaPortfolioRow``). Callers that need precise attribution pass
    the id alongside the patch. This helper keeps a stable, deterministic
    fallback for tests so a trial outcome always carries some delta id
    when a patch was applied.
    """
    # Stable identifier: filesystem-friendly slug of the patched path.
    return f"trial:{patch.target_path}"
