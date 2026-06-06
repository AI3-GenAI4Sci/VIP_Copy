"""Production batch runner for VIP COPY.

The runner drives the formal three-node production DAG over a batch of requests:

1. ``personalized-user-mining`` (JSON mode, no tools)
2. ``personalized-copy-generation`` (JSON mode, no tools)
3. ``personalized-copy-rubric-judge`` (JSON mode, no tools)

Evolution remains embedded in production traffic. Each concurrency wave routes
a bounded subset of real request slots through temporary skill delta patches
and scores them against comparable formal-version requests from the same wave.

Post-wave distillation is lazy, pipeline-scoped, and backgrounded: successful
trajectories with rubric ``reject``/``hold`` decisions are accumulated per
pipeline before the evolution skill is called, while delta posterior state
remains shared by ``delta_id`` and merged by the main runner.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import random
import sys
import threading
import time
import traceback
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from seers_harness.domain.models import (
    CopyGenerationArtifact,
    PersonalizedCopyRubricArtifact,
    UserPersonalizationArtifact,
)
from seers_harness.evolution.delta_portfolio import (
    ACTIVE_PORTFOLIO_TARGETS,
    DeltaDistillationArtifact,
    DeltaPortfolioRow,
    DeltaProposal,
    ExplorationDecision,
    assemble_portfolio,
    load_portfolio_jsonl,
    write_portfolio_jsonl,
)
from seers_harness.evolution.patchability import patchability_for_delta
from seers_harness.evolution.portfolio_journal import (
    PortfolioJournalEntry,
    append_journal_entry,
    read_journal_entries,
)
from seers_harness.evolution.scheduler import (
    DistillBundlePlan,
    DistillPlanningResult,
    DistillationScheduler,
    EvolutionBudgetPolicy,
    ExplorationPlanner,
    PortfolioCoordinator,
    build_trajectory_bundle_payload,
    safe_request_dirname,
)
from seers_harness.evolution.skill_patch import sha256_of_text
from seers_harness.evolution.traffic_exploration import ExplorationAssignment
from seers_harness.evolution.trial_signal import ProductionSignalWindow
from seers_harness.evolution.trial_runner import (
    CompiledDelta,
    DeltaCompiler,
    TrialWorkspaceCache,
)
from seers_harness.evolution.uplift import (
    BaselineReference,
    compute_uplift_against_reference,
    mean_total_score,
)
from seers_harness.validation._secrets import safe_exc
from seers_harness.validation.batch_dashboard import BatchDashboard
from seers_harness.validation.batch_summary_writer import write_batch_summary
from seers_harness.validation.evidence_writer import flush_evidence
from seers_harness.validation.evolution_snapshot import write_evolution_snapshot
from seers_harness.validation.exception_classifier import (
    TrialFailure,
    classify,
    failure_class,
    is_request_output_failure,
    is_trial_failure,
)
from seers_harness.validation.index_writer import write_index
from seers_harness.validation.machine_judges import (
    extract_len_need_or_pain_text,
    extract_len_user_factor_ids,
    judge_val01,
    judge_val02,
    judge_val04,
)
from seers_harness.validation.offline_export import (
    offline_copy_rows,
    write_offline_copy_table,
)
from seers_harness.validation.recording_provider import (
    RecordingProvider,
    set_current_node_id,
)
from seers_harness.validation.request_factor_copy_index import (
    write_request_factor_copy_index,
)
from seers_harness.validation.run_ledger import (
    RunConfig,
    RunLedger,
    completed_slot_id,
)
from seers_harness.validation.scenario_source import (
    ScenarioLoader,
    default_request_ids,
    default_scenario_loader,
)
from seers_harness.workflow.dag_runner import ArtifactCache, NodeSpec, WorkflowRuntime
from seers_harness.workflow.progress import CliReporter, render_cli_event, write_cli_line


ProviderFactory = Callable[[], Any]
NodesFactory = Callable[[], Sequence[NodeSpec]]

DEFAULT_BATCH_REQUESTS = 15
DEFAULT_CONCURRENCY = 3
DEFAULT_NODE_MAX_ATTEMPTS = 3
DEFAULT_REQUEST_RERUN_ATTEMPTS = 3
_USER_MINING_ARTIFACT_CACHE = ArtifactCache()
DEFAULT_RUNS_ROOT = Path(".runs")
LIVE_SKILL_ROOT: Path = Path(__file__).resolve().parents[2] / "workflow-skills"

_signal_window = ProductionSignalWindow(max_size=50)
_inflight_lock = threading.Lock()
_inflight_count = 0


@dataclass
class BatchResult:
    """Outcome of one production batch."""

    passed: bool
    records: list[dict[str, Any]] = field(default_factory=list)
    batch_dir: Path = field(default_factory=Path)
    started_at: str = ""
    finished_at: str = ""
    exception: BaseException | None = None
    portfolio: list[DeltaPortfolioRow] = field(default_factory=list)


@dataclass(frozen=True)
class FormalBaselineObservation:
    """One formal-version request outcome used to estimate trial baselines."""

    request_id: str
    mean_rubric_score: float
    token_cost_observed: int
    similarity_keys: tuple[str, ...]


@dataclass(frozen=True)
class _PendingDistillationJob:
    """Background distillation task awaiting main-thread portfolio merge."""

    plan: DistillBundlePlan
    future: Future[list[DeltaProposal]]


def _cli_event(scope: str, message: str = "", **fields: Any) -> None:
    write_cli_line(
        sys.stderr,
        render_cli_event(
            scope,
            message,
            styled=True,
            use_color=True,
            **fields,
        ),
        allow_ansi=True,
    )


def _cli_line(line: str) -> None:
    write_cli_line(sys.stderr, line)


def _utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_timestamp_for_dir() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _journal_entry_count_since(path: Path, entries_seen_at_start: int) -> int:
    """Return the number of trial posterior updates recorded by this run."""
    return max(0, len(read_journal_entries(path)) - int(entries_seen_at_start))


def _env_first(primary: str, legacy: str | None = None) -> str | None:
    value = os.environ.get(primary)
    if value is not None:
        return value
    if legacy is not None:
        return os.environ.get(legacy)
    return None


def _make_trial_rng() -> random.Random:
    raw_seed = _env_first("VIP_COPY_TRIAL_RNG_SEED", "SEERS_TRIAL_RNG_SEED")
    if raw_seed is None:
        return random.Random()
    try:
        return random.Random(int(raw_seed))
    except ValueError:
        return random.Random(raw_seed)


_trial_rng = _make_trial_rng()


def _trial_budget_fraction_from_env() -> float:
    raw = _env_first("VIP_COPY_TRIAL_BUDGET_FRACTION", "SEERS_TRIAL_BUDGET_FRACTION")
    if raw is None:
        return 0.02
    try:
        value = float(raw)
    except ValueError:
        return 0.02
    return min(1.0, max(0.0, value))


def _trial_budget_fraction(value: float | None) -> float:
    if value is None:
        return _trial_budget_fraction_from_env()
    return min(1.0, max(0.0, float(value)))


def _promotion_min_ready_from_env() -> int:
    raw = _env_first("VIP_COPY_PROMOTION_MIN_READY", "SEERS_PROMOTION_MIN_READY")
    if raw is None:
        return 3
    try:
        value = int(raw)
    except ValueError:
        return 3
    return max(1, value)


def _distill_threshold_override_from_env() -> int | None:
    raw = _env_first("VIP_COPY_DISTILL_MIN_TRAJECTORIES", "SEERS_DISTILL_MIN_TRAJECTORIES")
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return max(1, value)


def _distill_threshold_override(value: int | None) -> int | None:
    if value is None:
        return _distill_threshold_override_from_env()
    return max(1, int(value))


def _int_env(
    name: str,
    default: int | None = None,
    *,
    minimum: int = 1,
    legacy_name: str | None = None,
) -> int | None:
    raw = _env_first(name, legacy_name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, value)


def _evolution_budget_policy(
    *,
    trial_budget_fraction: float | None,
    distill_min_trajectories: int | None,
) -> EvolutionBudgetPolicy:
    return EvolutionBudgetPolicy(
        trial_budget_fraction=_trial_budget_fraction(trial_budget_fraction),
        max_trial_slots=_int_env(
            "VIP_COPY_EVOLUTION_MAX_TRIAL_SLOTS",
            None,
            minimum=0,
            legacy_name="SEERS_EVOLUTION_MAX_TRIAL_SLOTS",
        ),
        min_distill_eligible_trajectories=_int_env(
            "VIP_COPY_EVOLUTION_MIN_DISTILL_ELIGIBLE",
            EvolutionBudgetPolicy.min_distill_eligible_trajectories,
            minimum=1,
            legacy_name="SEERS_EVOLUTION_MIN_DISTILL_ELIGIBLE",
        ) or EvolutionBudgetPolicy.min_distill_eligible_trajectories,
        target_distill_calls_per_batch=_int_env(
            "VIP_COPY_EVOLUTION_TARGET_DISTILL_CALLS",
            EvolutionBudgetPolicy.target_distill_calls_per_batch,
            minimum=1,
            legacy_name="SEERS_EVOLUTION_TARGET_DISTILL_CALLS",
        ) or EvolutionBudgetPolicy.target_distill_calls_per_batch,
        distill_threshold_override=_distill_threshold_override(
            distill_min_trajectories
        ),
    )


def _node_max_attempts_from_env() -> int:
    raw = _env_first("VIP_COPY_NODE_MAX_ATTEMPTS", "SEERS_NODE_MAX_ATTEMPTS")
    if raw is None:
        return DEFAULT_NODE_MAX_ATTEMPTS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_NODE_MAX_ATTEMPTS
    return max(1, value)


def _node_max_attempts(value: int | None) -> int:
    if value is None:
        return _node_max_attempts_from_env()
    return max(1, int(value))


def _load_env_file(path: Path) -> int:
    """Parse KEY=VALUE lines into this process environment."""
    if not path.exists():
        raise RuntimeError(f"--env-file path not found: {path}")
    merged = 0
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        os.environ[key] = value
        merged += 1
    return merged


def _default_deepseek_factory(
    *,
    timeout_seconds: float | None = None,
    call_deadline_seconds: float | None = None,
    max_inflight_calls: int | None = None,
) -> DistillPlanningResult:
    from seers_harness.provider_runtime.openai_compatible import (
        deepseek_provider_from_env,
    )

    return deepseek_provider_from_env(
        timeout_seconds=timeout_seconds,
        max_retries=0,
        call_deadline_seconds=call_deadline_seconds,
        max_inflight_calls=max_inflight_calls,
    )


def _default_provider_factory(
    *,
    timeout_seconds: float | None = None,
    call_deadline_seconds: float | None = None,
    max_inflight_calls: int | None = None,
) -> ProviderFactory:
    return lambda: _default_deepseek_factory(
        timeout_seconds=timeout_seconds,
        call_deadline_seconds=call_deadline_seconds,
        max_inflight_calls=max_inflight_calls,
    )


def _default_nodes_factory(
    *,
    node_max_attempts: int | None = None,
) -> Sequence[NodeSpec]:
    max_attempts = _node_max_attempts(node_max_attempts)
    return [
        NodeSpec(
            id="personalized_user_mining",
            skill_name="personalized-user-mining",
            output_model=UserPersonalizationArtifact,
            max_attempts=max_attempts,
        ),
        NodeSpec(
            id="personalized_copy_generation",
            skill_name="personalized-copy-generation",
            output_model=CopyGenerationArtifact,
            max_attempts=max_attempts,
        ),
        NodeSpec(
            id="personalized_copy_rubric",
            skill_name="personalized-copy-rubric-judge",
            output_model=PersonalizedCopyRubricArtifact,
            max_attempts=max_attempts,
        ),
    ]


def _make_workflow_runtime(
    *,
    provider: Any,
    output_dir: Path,
    cli: CliReporter | None = None,
) -> WorkflowRuntime:
    kwargs: dict[str, Any] = {
        "provider": provider,
        "output_dir": output_dir,
        "artifact_cache": _USER_MINING_ARTIFACT_CACHE,
    }
    if cli is not None:
        kwargs["cli"] = cli
    try:
        return WorkflowRuntime(**kwargs)
    except TypeError as exc:
        if "artifact_cache" not in str(exc) and "cli" not in str(exc):
            raise
        kwargs.pop("artifact_cache", None)
        if "cli" in str(exc):
            kwargs.pop("cli", None)
        return WorkflowRuntime(**kwargs)


def _safe_request_dirname(request_id: str) -> str:
    return safe_request_dirname(request_id)


def _distill_from_request(
    *,
    request_dir: Path,
    provider_factory: ProviderFactory,
    current_portfolio: list[DeltaPortfolioRow],
    live_skill_root: Path | None = None,
) -> list[DeltaPortfolioRow]:
    return _distill_from_trajectory_dirs(
        request_dirs=[request_dir],
        evidence_dir=request_dir / "distill_evidence",
        provider_factory=provider_factory,
        current_portfolio=current_portfolio,
        live_skill_root=live_skill_root,
    )


def _distill_from_trajectory_dirs(
    *,
    request_dirs: Sequence[Path],
    evidence_dir: Path,
    provider_factory: ProviderFactory,
    current_portfolio: list[DeltaPortfolioRow],
    pipeline_id: str = "production",
    live_skill_root: Path | None = None,
) -> list[DeltaPortfolioRow]:
    proposals = _distill_proposals_from_trajectory_dirs(
        request_dirs=request_dirs,
        evidence_dir=evidence_dir,
        provider_factory=provider_factory,
        pipeline_id=pipeline_id,
        live_skill_root=live_skill_root,
    )
    return assemble_portfolio(current_portfolio, proposals, events=None)


def _distill_proposals_from_trajectory_dirs(
    *,
    request_dirs: Sequence[Path],
    evidence_dir: Path,
    provider_factory: ProviderFactory,
    pipeline_id: str = "production",
    live_skill_root: Path | None = None,
) -> list[DeltaProposal]:
    trajectory_payload = build_trajectory_bundle_payload(
        request_dirs,
        pipeline_id=pipeline_id,
        target_skill_snapshots=(
            _target_skill_snapshots(live_skill_root) if live_skill_root else None
        ),
    )
    from seers_harness.workflow.skill_loader import load_skill_prose

    skill_bundle = load_skill_prose("distill-skill-deltas")
    from seers_harness.agentic.tool_loop import run_skill_via_tools
    from seers_harness.tools.evolution_tools import (
        EVOLUTION_TOOL_HANDLERS,
        EVOLUTION_TOOLS_SPEC,
        finalize_delta_distillation_state,
    )

    distill_provider = RecordingProvider(provider_factory(), [])
    _cli_event(
        "runner",
        "distill_start",
        request_id=trajectory_payload["request_id"],
        pipeline_id=pipeline_id,
        trajectories=trajectory_payload["trajectory_count"],
    )
    result = None
    try:
        result = run_skill_via_tools(
            skill_name="distill-skill-deltas",
            skill_bundle=skill_bundle,
            payload=trajectory_payload,
            tools_spec=EVOLUTION_TOOLS_SPEC["distill-skill-deltas"],
            tool_handlers=EVOLUTION_TOOL_HANDLERS,
            provider=distill_provider,
            node_id="distill_after_production_request",
            finalize_state=finalize_delta_distillation_state,
        )
    finally:
        if result is not None:
            _attach_final_artifact_to_request_log(
                distill_provider.request_log,
                node_id="distill_after_production_request",
                artifact=result.artifact,
            )
        try:
            flush_evidence(
                distill_provider.request_log,
                evidence_dir,
            )
        except Exception as cleanup_exc:
            _cli_event(
                "runner",
                "distill_evidence flush failed",
                error=safe_exc(cleanup_exc),
            )
    artifact = DeltaDistillationArtifact.model_validate(result.artifact)
    _cli_event(
        "runner",
        "distill_done",
        pipeline_id=pipeline_id,
        proposals=len(artifact.deltas),
        trajectories=trajectory_payload["trajectory_count"],
        delta_ids=",".join(p.delta_id for p in artifact.deltas),
    )
    return _patchable_delta_proposals(
        artifact.deltas,
        live_skill_root=live_skill_root,
    )


def _attach_final_artifact_to_request_log(
    request_log: list[dict[str, Any]],
    *,
    node_id: str,
    artifact: dict[str, Any],
) -> None:
    for record in reversed(request_log):
        if record.get("node_id") == node_id:
            record["final_artifact"] = artifact
            return


def _target_skill_snapshots(live_skill_root: Path) -> list[dict[str, Any]]:
    """Return live skill text snapshots for distillation patch grounding."""
    snapshots: list[dict[str, Any]] = []
    for target_skill in sorted(ACTIVE_PORTFOLIO_TARGETS):
        target = live_skill_root / target_skill
        if not target.exists():
            continue
        text = target.read_text(encoding="utf-8")
        snapshots.append(
            {
                "target_skill": target_skill,
                "sha256": sha256_of_text(text),
                "content": text,
            }
        )
    return snapshots


def _patchable_delta_proposals(
    proposals: Sequence[DeltaProposal],
    *,
    live_skill_root: Path | None,
) -> list[DeltaProposal]:
    """Keep only proposals whose structured edits apply to the live skill source."""
    if live_skill_root is None:
        return list(proposals)
    kept: list[DeltaProposal] = []
    for proposal in proposals:
        report = patchability_for_delta(proposal, live_skill_root)
        if report.patchable and report.patch is not None:
            kept.append(
                proposal.model_copy(
                    update={
                        "patch": proposal.patch.model_copy(
                            update={"edits": report.patch.edits}
                        )
                    }
                )
            )
            continue
        _cli_event(
            "runner",
            "delta_proposal_rejected",
            delta_id=proposal.delta_id,
            reason=report.reason,
            target_skill=proposal.target_skill,
            detail=report.message,
        )
    return kept


def _applicable_surface_for(
    nodes: Sequence[Any],
    delta_portfolio: list[DeltaPortfolioRow],
) -> list[str]:
    surfaces = [
        str(getattr(node, "skill_name", "") or getattr(node, "id", ""))
        for node in nodes
    ]
    surfaces = [surface for surface in surfaces if surface]
    if any(
        surface in {"personalized-copy-generation", "personalized_copy_generation"}
        for surface in surfaces
    ):
        surfaces.extend(["product_detail_card", "recommendation_feed"])
    for row in delta_portfolio:
        if _target_skill_matches_surface(row.target_skill, surfaces):
            surfaces.extend(row.applicable_surface)
    if surfaces:
        return sorted(set(surfaces))
    fallback: list[str] = []
    for row in delta_portfolio:
        fallback.extend(row.applicable_surface)
    return sorted(set(fallback))


def _target_skill_matches_surface(target_skill: str, surfaces: Sequence[str]) -> bool:
    target = str(target_skill or "").replace("\\", "/")
    if not target:
        return False
    candidates: set[str] = set()
    for surface in surfaces:
        if not surface:
            continue
        candidates.add(surface)
        candidates.add(surface.replace("_", "-"))
        candidates.add(surface.replace("-", "_"))
    for candidate in candidates:
        if (
            target == candidate
            or target.endswith(f"/{candidate}")
            or target.endswith(f"/{candidate}/SKILL.md")
        ):
            return True
    return False


def _target_skills_for_nodes(nodes: Sequence[Any]) -> list[str] | None:
    targets: list[str] = []
    for node in nodes:
        skill_name = getattr(node, "skill_name", None)
        if isinstance(skill_name, str) and skill_name:
            targets.append(f"current/{skill_name}/SKILL.md")
    return targets or None


def _trialable_portfolio(
    portfolio: Sequence[DeltaPortfolioRow],
    *,
    live_skill_root: Path,
) -> list[DeltaPortfolioRow]:
    """Return portfolio rows that can safely consume a trial slot now."""
    compiled = _compiled_trial_deltas(portfolio, live_skill_root=live_skill_root)
    return [row for row in portfolio if row.delta_id in compiled]


def _compiled_trial_deltas(
    portfolio: Sequence[DeltaPortfolioRow],
    *,
    live_skill_root: Path,
) -> dict[str, CompiledDelta]:
    """Compile portfolio rows that can safely consume a trial slot now."""
    compiler = DeltaCompiler(live_skill_root=live_skill_root)
    compiled: dict[str, CompiledDelta] = {}
    for row in portfolio:
        item, report = compiler.compile_with_report(row)
        if item is not None:
            compiled[row.delta_id] = item
            continue
        _cli_event(
            "runner",
            "delta_not_trialable",
            delta_id=row.delta_id,
            reason=report.reason,
            target_skill=row.target_skill,
            detail=report.message,
        )
    return compiled


def _prepare_trial_skill_roots_for_wave(
    *,
    assignments: Sequence[ExplorationAssignment],
    compiled_trial_deltas: Mapping[str, CompiledDelta],
    workspace_cache: TrialWorkspaceCache,
) -> dict[str, Path]:
    """Materialize one shared patched skill root per selected delta."""
    selected_delta_ids = sorted(
        {
            str(assignment.delta_id)
            for assignment in assignments
            if assignment.delta_id is not None
        }
    )
    roots: dict[str, Path] = {}
    for delta_id in selected_delta_ids:
        compiled = compiled_trial_deltas.get(delta_id)
        if compiled is None:
            _cli_event(
                "runner",
                "trial_workspace_unavailable",
                delta_id=delta_id,
                reason="delta_not_compiled",
            )
            continue
        try:
            roots[delta_id] = workspace_cache.prepare(compiled)
        except Exception as exc:
            _cli_event(
                "runner",
                "trial_workspace_unavailable",
                delta_id=delta_id,
                reason=type(exc).__name__,
                detail=safe_exc(exc),
            )
    return roots


def _record_host_baseline_outcome(record: dict[str, Any], runtime: WorkflowRuntime) -> None:
    total_tokens = sum(
        int((event.get("usage") or {}).get("total_tokens") or 0)
        for event in runtime.trace
        if event.get("type") == "tool_loop_summary"
    )
    _signal_window.record_baseline_outcome(
        success=record.get("exception") is None,
        total_tokens=total_tokens,
    )


def _artifact_behavioral_metrics(
    outcome_artifact_paths: dict[str, Path],
) -> dict[str, float]:
    user_path = outcome_artifact_paths.get("personalized_user_mining")
    if user_path is None or not Path(user_path).exists():
        return {}
    raw = json.loads(Path(user_path).read_text(encoding="utf-8"))
    user_factors = raw.get("user_factors") or [] if isinstance(raw, dict) else []
    first_factor = user_factors[0] if user_factors else {}
    artifact = {
        "user_factor_ids": [
            str(f.get("user_factor_id"))
            for f in user_factors
            if isinstance(f, dict) and f.get("user_factor_id")
        ],
        "need_or_pain_text": first_factor.get("need_or_pain", ""),
        "signal_basis": first_factor.get("signal_basis", "") or "",
    }
    val01, _ = judge_val01(artifact)
    val02, _ = judge_val02(artifact)
    val04, _ = judge_val04(artifact)
    return {
        "val01_pass": float(val01),
        "val02_pass": float(val02),
        "val04_pass": float(val04),
        "user_factor_count": float(extract_len_user_factor_ids(artifact)),
        "need_or_pain_length": float(extract_len_need_or_pain_text(artifact)),
    }


def _load_rubric_artifact(
    outcome_artifact_paths: dict[str, Path],
) -> PersonalizedCopyRubricArtifact:
    rubric_path = outcome_artifact_paths.get("personalized_copy_rubric")
    if rubric_path is None or not Path(rubric_path).exists():
        return PersonalizedCopyRubricArtifact(judgments=[])
    raw = json.loads(Path(rubric_path).read_text(encoding="utf-8"))
    return PersonalizedCopyRubricArtifact.model_validate(raw)


def _artifact_paths_for_request_dir(request_dir: Path) -> dict[str, Path] | None:
    evidence_dir = request_dir / "evidence"
    artifact_paths = {
        node_id: evidence_dir / node_id / "artifact.json"
        for node_id in (
            "personalized_user_mining",
            "personalized_copy_generation",
            "personalized_copy_rubric",
        )
    }
    if not all(path.exists() for path in artifact_paths.values()):
        return None
    return artifact_paths


def _artifact_paths_for_record(
    *,
    batch_dir: Path,
    record: Mapping[str, Any],
) -> dict[str, Path] | None:
    output_id = str(record.get("node_id") or record.get("request_id") or "")
    if not output_id:
        return None
    return _artifact_paths_for_request_dir(batch_dir / _safe_request_dirname(output_id))


def _formal_baseline_observation(
    *,
    batch_dir: Path,
    record: Mapping[str, Any],
    scenario: Mapping[str, Any],
) -> FormalBaselineObservation | None:
    if _is_trial_record(record):
        return None
    if record.get("exception") is not None or record.get("skipped") is True:
        return None
    artifact_paths = _artifact_paths_for_record(batch_dir=batch_dir, record=record)
    if artifact_paths is None:
        return None
    return FormalBaselineObservation(
        request_id=str(record.get("request_id") or record.get("node_id") or ""),
        mean_rubric_score=mean_total_score(_load_rubric_artifact(artifact_paths)),
        token_cost_observed=_token_cost_from_artifact_paths(artifact_paths),
        similarity_keys=_scenario_similarity_keys(scenario),
    )


def _baseline_reference_for_trial(
    *,
    scenario: Mapping[str, Any],
    observations: Sequence[FormalBaselineObservation],
) -> BaselineReference | None:
    if not observations:
        return None
    trial_keys = _scenario_similarity_keys(scenario)
    strategies = (
        "same_wave:category_count_user",
        "same_wave:category_count",
        "same_wave:category",
        "same_wave:count",
    )
    for level, (strategy, key) in enumerate(zip(strategies, trial_keys, strict=True)):
        matched = [
            item
            for item in observations
            if level < len(item.similarity_keys) and item.similarity_keys[level] == key
        ]
        if matched:
            return _baseline_reference_from_observations(
                matched,
                strategy=strategy,
                cohort_key=key,
            )
    return _baseline_reference_from_observations(
        observations,
        strategy="same_wave:all",
        cohort_key="all",
    )


def _baseline_reference_from_observations(
    observations: Sequence[FormalBaselineObservation],
    *,
    strategy: str,
    cohort_key: str,
) -> BaselineReference:
    count = len(observations)
    return BaselineReference(
        mean_rubric_score=sum(item.mean_rubric_score for item in observations) / count,
        mean_token_cost=sum(item.token_cost_observed for item in observations) / count,
        sample_count=count,
        strategy=strategy,
        cohort_key=cohort_key,
    )


def _scenario_similarity_keys(scenario: Mapping[str, Any]) -> tuple[str, ...]:
    categories = _scenario_category_signature(scenario)
    product_count = _product_count_band(scenario.get("target_product_count"))
    user_density = _user_state_density_band(scenario.get("user_state"))
    return (
        f"cat={categories}|count={product_count}|user={user_density}",
        f"cat={categories}|count={product_count}",
        f"cat={categories}",
        f"count={product_count}",
    )


def _scenario_category_signature(scenario: Mapping[str, Any]) -> str:
    products = scenario.get("target_products") or scenario.get("products") or []
    values: list[str] = []
    if isinstance(products, list):
        for product in products:
            if isinstance(product, Mapping):
                category = product.get("category")
                if category not in (None, ""):
                    values.append(str(category))
    if not values:
        list_context = scenario.get("list_context")
        if isinstance(list_context, Mapping):
            categories = list_context.get("target_categories")
            if isinstance(categories, list):
                values.extend(str(item) for item in categories if item not in (None, ""))
    return ",".join(sorted(set(values))) or "unknown"


def _product_count_band(value: Any) -> str:
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = 0
    if count <= 1:
        return "1"
    if count <= 3:
        return "2-3"
    if count <= 6:
        return "4-6"
    return "7+"


def _user_state_density_band(value: Any) -> str:
    density = _nonempty_leaf_count(value)
    if density <= 2:
        return "sparse"
    if density <= 6:
        return "medium"
    return "rich"


def _nonempty_leaf_count(value: Any) -> int:
    if isinstance(value, Mapping):
        return sum(_nonempty_leaf_count(item) for item in value.values())
    if isinstance(value, list):
        return sum(_nonempty_leaf_count(item) for item in value)
    return 0 if value in (None, "") else 1


def _write_request_factor_copy_index_from_paths(
    *,
    request_id: str,
    scenario_id: str,
    user_path: Path,
    copy_path: Path,
    out_path: Path,
    skip_invalid: bool = False,
) -> bool:
    user_artifact = json.loads(user_path.read_text(encoding="utf-8"))
    copy_artifact = json.loads(copy_path.read_text(encoding="utf-8"))
    try:
        UserPersonalizationArtifact.model_validate(user_artifact)
        CopyGenerationArtifact.model_validate(copy_artifact)
    except Exception:
        if skip_invalid:
            return False
        raise
    write_request_factor_copy_index(
        request_id=request_id,
        scenario_id=scenario_id,
        user_artifact=user_artifact,
        copy_artifact=copy_artifact,
        out_path=out_path,
    )
    return True


def _exploration_decision_event(decision: ExplorationDecision) -> dict[str, Any]:
    payload = decision.model_dump()
    payload["type"] = "exploration_decision"
    return {
        key: payload[key]
        for key in (
            "type",
            "should_trial",
            "selected_delta_id",
            "eligible_delta_count",
            "trigger_reason",
            "no_trial_reason",
            "posterior_samples",
        )
    }


def _run_assigned_request_once(
    *,
    runtime: WorkflowRuntime,
    scenario: dict[str, Any],
    nodes: list[Any],
    live_skill_root: Path,
    request_dir: Path,
    delta_portfolio: list[DeltaPortfolioRow],
    selected_delta_id: str | None,
    request_id: str,
    events: list[dict],
    journal_path: Path,
    trial_skill_roots: Mapping[str, Path] | None = None,
    trial_id: str | None = None,
) -> dict[str, Path]:
    if selected_delta_id is None:
        return runtime.run_request(scenario=scenario, nodes=nodes)

    portfolio_row = next(
        (row for row in delta_portfolio if row.delta_id == selected_delta_id),
        None,
    )
    if portfolio_row is None:
        _record_trial_patch_failure(
            request_id=request_id,
            trial_id=trial_id or request_id,
            delta_id=selected_delta_id,
            reason="delta_not_in_portfolio",
            events=events,
            journal_path=journal_path,
        )
        return {}
    if trial_skill_roots is None:
        compiled = DeltaCompiler(live_skill_root=live_skill_root).compile(portfolio_row)
        if compiled is None:
            trial_skill_root = None
        else:
            trial_skill_root = TrialWorkspaceCache(
                live_skill_root=live_skill_root,
                cache_dir=request_dir / "trial_workspace",
            ).prepare(compiled)
    else:
        trial_skill_root = trial_skill_roots.get(selected_delta_id)
    if trial_skill_root is None:
        _record_trial_patch_failure(
            request_id=request_id,
            trial_id=trial_id or request_id,
            delta_id=selected_delta_id,
            reason="trial_workspace_unavailable",
            events=events,
            journal_path=journal_path,
        )
        return {}

    previous_skill_root = getattr(runtime, "skill_root", None)
    events.append(
        {
            "type": "trial_started",
            "trial_id": trial_id or request_id,
            "request_id": request_id,
            "delta_id": selected_delta_id,
            "skill_root": str(trial_skill_root),
        }
    )
    try:
        if hasattr(runtime, "skill_root"):
            runtime.skill_root = trial_skill_root
        result_paths = runtime.run_request(scenario=scenario, nodes=nodes)
    except Exception as exc:
        if classify(exc) == "provider_error":
            raise
        events.append(
            {
                "type": "trial_failed",
                "trial_id": trial_id or request_id,
                "request_id": request_id,
                "delta_id": selected_delta_id,
                "exception_class": type(exc).__name__,
                "exception_message": safe_exc(exc),
            }
        )
        append_journal_entry(
            journal_path,
            PortfolioJournalEntry(
                request_id=request_id,
                delta_id=selected_delta_id,
                success=False,
                score_delta=0.0,
                token_cost_delta=0,
                ts=_utc_now_iso(),
            ),
        )
        raise TrialFailure(
            f"trial {selected_delta_id} failed for request {request_id}"
        ) from exc
    finally:
        if hasattr(runtime, "skill_root"):
            runtime.skill_root = previous_skill_root

    events.append(
        {
            "type": "trial_succeeded",
            "trial_id": trial_id or request_id,
            "request_id": request_id,
            "delta_id": selected_delta_id,
        }
    )
    return result_paths


def _record_trial_patch_failure(
    *,
    request_id: str,
    trial_id: str | None = None,
    delta_id: str,
    reason: str,
    events: list[dict],
    journal_path: Path,
) -> None:
    events.append(
        {
            "type": "trial_failed",
            "trial_id": trial_id or request_id,
            "request_id": request_id,
            "delta_id": delta_id,
            "exception_class": "PatchUnavailable",
            "exception_message": reason,
        }
    )


def _record_trial_uplift_from_reference(
    *,
    request_id: str,
    selected_delta_id: str,
    baseline_reference: BaselineReference,
    trial_artifact_paths: dict[str, Path],
    trial_tokens: int,
    journal_path: Path,
) -> None:
    if not trial_artifact_paths:
        return
    uplift = compute_uplift_against_reference(
        _load_rubric_artifact(trial_artifact_paths),
        baseline_reference,
        token_cost_delta=round(trial_tokens - baseline_reference.mean_token_cost),
    )
    append_journal_entry(
        journal_path,
        PortfolioJournalEntry(
            request_id=request_id,
            delta_id=selected_delta_id,
            success=uplift.is_positive,
            baseline_mean_rubric_score=uplift.baseline_mean_rubric_score,
            trial_mean_rubric_score=uplift.trial_mean_rubric_score,
            score_delta=uplift.score_delta,
            token_cost_delta=uplift.token_cost_delta,
            behavioral_metric_lift=uplift.behavioral_metric_lift,
            baseline_reference_strategy=uplift.baseline_reference_strategy,
            baseline_reference_sample_count=uplift.baseline_reference_sample_count,
            baseline_reference_cohort_key=uplift.baseline_reference_cohort_key,
            ts=_utc_now_iso(),
        ),
    )


def _token_cost_from_artifact_paths(artifact_paths: dict[str, Path]) -> int:
    total = 0
    for artifact_path in artifact_paths.values():
        usage_path = Path(artifact_path).parent / "usage.json"
        if not usage_path.exists() and Path(artifact_path).name == "artifact.json":
            node_id = Path(artifact_path).parent.name
            request_dir = Path(artifact_path).parent.parent
            if request_dir.name == "_artifacts":
                usage_path = request_dir.parent / "evidence" / node_id / "usage.json"
        if not usage_path.exists():
            continue
        try:
            usage = json.loads(usage_path.read_text(encoding="utf-8"))
            total += int(usage.get("total_tokens") or 0)
        except Exception:
            continue
    return total


def _token_cost_from_request_log(request_log: Sequence[Mapping[str, Any]]) -> int:
    total = 0
    for record in request_log:
        usage = record.get("last_usage") or {}
        if not isinstance(usage, Mapping):
            continue
        try:
            total += int(usage.get("total_tokens") or 0)
        except (TypeError, ValueError):
            continue
    return total


def _run_one_request(
    *,
    request_id: str,
    scenario: dict[str, Any],
    nodes: Sequence[Any],
    provider_factory: ProviderFactory,
    request_dir: Path,
    events: list[dict],
    delta_portfolio: list[DeltaPortfolioRow],
    live_skill_root: Path,
    assignment: ExplorationAssignment | None = None,
    journal_path: Path | None = None,
    trial_skill_roots: Mapping[str, Path] | None = None,
    max_concurrent: int = DEFAULT_CONCURRENCY,
    cli: CliReporter | None = None,
) -> dict[str, Any]:
    """Drive one production request end-to-end through the harness chain."""
    global _inflight_count

    inner_provider = provider_factory()
    request_log: list[dict] = []
    proxy = RecordingProvider(inner_provider, request_log)

    request_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = request_dir / "_artifacts"
    runtime = _make_workflow_runtime(
        provider=proxy,
        output_dir=artifacts_dir,
        cli=cli,
    )
    assignment = assignment or ExplorationAssignment(
        request_id=request_id,
        original_request_id=request_id,
    )
    selected_delta_id = assignment.delta_id
    run_id = assignment.run_id
    if hasattr(runtime, "display_request_id"):
        runtime.display_request_id = run_id

    record: dict[str, Any] = {
        "node_id": _safe_request_dirname(run_id),
        "request_id": request_id,
        "original_request_id": assignment.original_request_id,
        "record_kind": "trial" if selected_delta_id is not None else "production",
        "artifact": None,
        "reflow_triggered": False,
        "trial_selected_delta_id": selected_delta_id,
        "trial_patch_applied": None,
        "exception": None,
        "failure_class": "ok",
    }

    token = set_current_node_id(run_id)
    with _inflight_lock:
        _inflight_count += 1
    try:
        portfolio_ids = [row.delta_id for row in delta_portfolio]
        events.append(
            {
                "type": "portfolio_assembled",
                "delta_portfolio_before": portfolio_ids,
                "delta_portfolio_after": portfolio_ids,
                "counts": {"before": len(portfolio_ids), "after": len(portfolio_ids)},
            }
        )
        if assignment.decision is not None:
            events.append(_exploration_decision_event(assignment.decision))
        result_paths = _run_assigned_request_once(
            runtime=runtime,
            scenario=scenario,
            nodes=list(nodes),
            live_skill_root=live_skill_root,
            request_dir=request_dir,
            delta_portfolio=delta_portfolio,
            selected_delta_id=selected_delta_id,
            request_id=request_id,
            events=events,
            journal_path=journal_path or (request_dir.parent / "portfolio_journal.jsonl"),
            trial_skill_roots=trial_skill_roots,
            trial_id=run_id,
        )
        if selected_delta_id is not None and not result_paths:
            record["skipped"] = True
            record["failure_class"] = "trial_patch_unavailable"
            record["trial_patch_applied"] = False
            return record
        if selected_delta_id is not None:
            record["trial_patch_applied"] = True

        user_factor_path = result_paths.get("personalized_user_mining")
        if user_factor_path is not None and Path(user_factor_path).exists():
            try:
                raw = json.loads(Path(user_factor_path).read_text(encoding="utf-8"))
                UserPersonalizationArtifact.model_validate(raw)
                user_factors = raw.get("user_factors") or []
                first_factor = user_factors[0] if user_factors else {}
                record["artifact"] = {
                    "user_factor_ids": [
                        str(f.get("user_factor_id"))
                        for f in user_factors
                        if isinstance(f, dict) and f.get("user_factor_id")
                    ],
                    "need_or_pain_text": first_factor.get("need_or_pain", ""),
                    "signal_basis": first_factor.get("signal_basis", "") or "",
                }
            except Exception:
                traceback.print_exc(file=sys.stderr)
                raise

        copy_path = result_paths.get("personalized_copy_generation")
        if (
            user_factor_path is not None
            and copy_path is not None
            and Path(user_factor_path).exists()
            and Path(copy_path).exists()
        ):
            _write_request_factor_copy_index_from_paths(
                request_id=request_id,
                scenario_id=str(scenario.get("scenario_id", "")),
                user_path=Path(user_factor_path),
                copy_path=Path(copy_path),
                out_path=request_dir / "request_factor_copy_index.json",
            )

        rubric_artifact: dict[str, Any] | None = None
        for node_id, model in [
            ("personalized_copy_rubric", PersonalizedCopyRubricArtifact),
        ]:
            p = result_paths.get(node_id)
            if p is None or not Path(p).exists():
                raise RuntimeError(f"missing artifact for node {node_id} in {request_id}")
            raw = json.loads(Path(p).read_text(encoding="utf-8"))
            parsed = model.model_validate(raw)
            if node_id == "personalized_copy_rubric":
                rubric_artifact = parsed.model_dump(mode="json")
                record["mean_rubric_score"] = mean_total_score(parsed)

        if copy_path is not None and rubric_artifact is not None:
            generation_artifact = json.loads(Path(copy_path).read_text(encoding="utf-8"))
            record["offline_copy_rows"] = offline_copy_rows(
                scenario=scenario,
                generation_artifact=generation_artifact,
                rubric_artifact=rubric_artifact,
            )

        record["token_cost_observed"] = _token_cost_from_request_log(request_log)
        _record_host_baseline_outcome(record, runtime)

    except BaseException as exc:
        events.append(
            {
                "type": "request_failed",
                "request_id": request_id,
                "failure_class": failure_class(exc),
                "exception": safe_exc(exc),
                "workflow_records": list(getattr(runtime, "records", []) or []),
                "workflow_trace": list(getattr(runtime, "trace", []) or []),
            }
        )
        raise
    finally:
        with _inflight_lock:
            _inflight_count = max(0, _inflight_count - 1)
        try:
            from seers_harness.validation.recording_provider import reset_current_node_id

            reset_current_node_id(token)
        except Exception:
            pass
        evidence_dir = request_dir / "evidence"
        try:
            flush_evidence(request_log, evidence_dir)
        except Exception as cleanup_exc:
            _cli_event(
                "runner",
                f"flush_evidence failed for {request_id}",
                error=safe_exc(cleanup_exc),
            )
        try:
            index_path = request_dir / "request_factor_copy_index.json"
            user_evidence_path = (
                evidence_dir / "personalized_user_mining" / "artifact.json"
            )
            copy_evidence_path = (
                evidence_dir / "personalized_copy_generation" / "artifact.json"
            )
            if (
                not index_path.exists()
                and user_evidence_path.exists()
                and copy_evidence_path.exists()
            ):
                _write_request_factor_copy_index_from_paths(
                    request_id=request_id,
                    scenario_id=str(scenario.get("scenario_id", "")),
                    user_path=user_evidence_path,
                    copy_path=copy_evidence_path,
                    out_path=index_path,
                    skip_invalid=True,
                )
        except Exception as cleanup_exc:
            _cli_event(
                "runner",
                f"write_request_factor_copy_index failed for {request_id}",
                error=safe_exc(cleanup_exc),
            )
        try:
            write_evolution_snapshot(events, request_dir / "evolution_snapshot.json")
        except Exception as cleanup_exc:
            _cli_event(
                "runner",
                f"write_evolution_snapshot failed for {request_id}",
                error=safe_exc(cleanup_exc),
            )

    return record


def _failed_record(
    request_id: str,
    exc: BaseException,
    *,
    node_id: str | None = None,
    original_request_id: str | None = None,
    trial_selected_delta_id: str | None = None,
    skipped: bool = False,
) -> dict[str, Any]:
    return {
        "node_id": _safe_request_dirname(node_id or request_id),
        "request_id": request_id,
        "original_request_id": original_request_id or request_id,
        "record_kind": "trial" if trial_selected_delta_id is not None else "production",
        "artifact": None,
        "reflow_triggered": False,
        "trial_selected_delta_id": trial_selected_delta_id,
        "exception": safe_exc(exc),
        "failure_class": failure_class(exc),
        "skipped": skipped,
    }


def _failure_summary_from_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "node_id": record.get("node_id"),
        "request_id": record.get("request_id"),
        "original_request_id": record.get("original_request_id"),
        "record_kind": record.get("record_kind"),
        "trial_selected_delta_id": record.get("trial_selected_delta_id"),
        "failure_class": record.get("failure_class"),
        "exception": record.get("exception"),
        "skipped": bool(record.get("skipped")),
    }


def _json_safe_payload(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _scenario_payload_for_failure_report(
    *,
    scenario_loader: ScenarioLoader,
    request_id: str,
) -> dict[str, Any]:
    try:
        return {
            "scenario": _json_safe_payload(scenario_loader(request_id)),
            "scenario_load_error": None,
        }
    except BaseException as exc:
        return {
            "scenario": None,
            "scenario_load_error": safe_exc(exc),
        }


def _retryable_failed_record(record: Mapping[str, Any]) -> bool:
    has_failure = record.get("exception") is not None or record.get("skipped") is True
    if not has_failure:
        return False
    if _is_trial_record(record):
        return _is_direct_trial_record(record)
    return True


def _is_trial_record(record: Mapping[str, Any]) -> bool:
    return record.get("record_kind") == "trial" or bool(
        record.get("trial_selected_delta_id")
    )


def _is_direct_trial_record(record: Mapping[str, Any]) -> bool:
    if not _is_trial_record(record):
        return False
    request_id = record.get("request_id")
    original_request_id = record.get("original_request_id")
    return request_id is not None and str(request_id) == str(original_request_id)


def _main_slot_records(
    records: Sequence[Mapping[str, Any]],
    *,
    requested_slot_ids: Sequence[str],
) -> list[Mapping[str, Any]]:
    requested = {str(item) for item in requested_slot_ids}
    output: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        slot = completed_slot_id(record, requested_slot_ids=requested)
        if slot is None or slot in seen:
            continue
        seen.add(slot)
        output.append(record)
    return output


def _retry_failed_request_records(
    *,
    records: list[dict[str, Any]],
    scenario_loader: ScenarioLoader,
    nodes: Sequence[Any],
    provider_factory: ProviderFactory,
    batch_dir: Path,
    state_dir: Path,
    delta_portfolio: list[DeltaPortfolioRow],
    live_skill_root: Path,
    journal_path: Path,
    max_concurrent: int,
    max_attempts: int = DEFAULT_REQUEST_RERUN_ATTEMPTS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Rerun failed production requests after the main batch has completed."""
    max_attempts = max(0, int(max_attempts))
    recovered: list[dict[str, Any]] = []
    final_failures: list[dict[str, Any]] = []
    retry_candidates = [record for record in records if _retryable_failed_record(record)]

    if retry_candidates:
        _cli_event(
            "batch",
            "retry_failed_requests_start",
            requests=len(retry_candidates),
            attempts=max_attempts,
        )

    final_records: list[dict[str, Any]] = []
    for record in records:
        if not _retryable_failed_record(record) or max_attempts <= 0:
            final_records.append(record)
            if _retryable_failed_record(record):
                scenario_payload = _scenario_payload_for_failure_report(
                    scenario_loader=scenario_loader,
                    request_id=str(record.get("request_id") or ""),
                )
                final_failures.append(
                    {
                        "request_id": record.get("request_id"),
                        "original_request_id": record.get("original_request_id"),
                        "initial_failure": _failure_summary_from_record(record),
                        "retry_attempts": [],
                        "final_failure": _failure_summary_from_record(record),
                        **scenario_payload,
                    }
                )
            continue

        request_id = str(record.get("request_id") or "")
        original_request_id = str(record.get("original_request_id") or request_id)
        retry_attempts: list[dict[str, Any]] = []
        last_failure = record
        recovered_record: dict[str, Any] | None = None

        for attempt in range(1, max_attempts + 1):
            assignment = ExplorationAssignment(
                request_id=request_id,
                original_request_id=original_request_id,
                execution_id=f"retry:{attempt}:{request_id}",
            )
            _cli_event(
                "batch",
                "retry_failed_request",
                request_id=request_id,
                attempt=attempt,
                max_attempts=max_attempts,
            )
            try:
                retry_events: list[dict] = []
                retry_record = _run_assignment(
                    assignment=assignment,
                    scenario_loader=scenario_loader,
                    nodes=nodes,
                    provider_factory=provider_factory,
                    batch_dir=batch_dir,
                    state_dir=state_dir,
                    events=retry_events,
                    delta_portfolio=delta_portfolio,
                    live_skill_root=live_skill_root,
                    journal_path=journal_path,
                    max_concurrent=max_concurrent,
                    cli=None,
                    trial_skill_roots=None,
                )
                retry_record["retry_attempts"] = list(retry_attempts)
                retry_record["recovered_after_request_rerun"] = True
                retry_attempts.append(
                    {
                        "attempt": attempt,
                        "status": "succeeded",
                        "node_id": retry_record.get("node_id"),
                        "request_id": retry_record.get("request_id"),
                    }
                )
                retry_record["retry_attempts"] = list(retry_attempts)
                recovered_record = retry_record
                break
            except BaseException as exc:
                retry_failure = _failed_record(
                    request_id,
                    exc,
                    node_id=assignment.run_id,
                    original_request_id=original_request_id,
                )
                retry_attempts.append(
                    {
                        "attempt": attempt,
                        "status": "failed",
                        **_failure_summary_from_record(retry_failure),
                    }
                )
                last_failure = retry_failure
                _failure_event(
                    assignment.run_id,
                    exc,
                    action="retry_recorded",
                )

        if recovered_record is not None:
            recovered.append(
                {
                    "request_id": request_id,
                    "original_request_id": original_request_id,
                    "initial_failure": _failure_summary_from_record(record),
                    "retry_attempts": list(retry_attempts),
                    "final_record_node_id": recovered_record.get("node_id"),
                }
            )
            final_records.append(recovered_record)
            continue

        final_record = dict(last_failure)
        final_record["retry_attempts"] = list(retry_attempts)
        final_record["recovered_after_request_rerun"] = False
        final_records.append(final_record)
        scenario_payload = _scenario_payload_for_failure_report(
            scenario_loader=scenario_loader,
            request_id=request_id,
        )
        final_failures.append(
            {
                "request_id": request_id,
                "original_request_id": original_request_id,
                "initial_failure": _failure_summary_from_record(record),
                "retry_attempts": list(retry_attempts),
                "final_failure": _failure_summary_from_record(final_record),
                **scenario_payload,
            }
        )

    report = {
        "generated_at": _utc_now_iso(),
        "retry_limit": max_attempts,
        "recovered": recovered,
        "failures": final_failures,
    }
    return final_records, report


def _write_failed_requests_report(
    *,
    batch_dir: Path,
    report: Mapping[str, Any],
) -> Path:
    path = batch_dir / "failed_requests.json"
    path.write_text(
        json.dumps(_json_safe_payload(dict(report)), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _write_run_portfolio_journal(
    *,
    batch_dir: Path,
    journal_path: Path,
    entries_seen_at_start: int,
) -> Path | None:
    """Write only this run's portfolio journal entries into ``batch_dir``."""
    if not journal_path.exists():
        return None
    entries = read_journal_entries(journal_path)
    run_entries = entries[max(0, int(entries_seen_at_start)) :]
    if not run_entries:
        return None
    out_path = batch_dir / "portfolio_journal.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for entry in run_entries:
            f.write(entry.model_dump_json())
            f.write("\n")
    return out_path


def _evolution_policy_snapshot(policy: EvolutionBudgetPolicy) -> dict[str, Any]:
    return {
        "trial_budget_fraction": policy.trial_budget_fraction,
        "max_trial_slots": policy.max_trial_slots,
        "min_distill_eligible_trajectories": policy.min_distill_eligible_trajectories,
        "target_distill_calls_per_batch": policy.target_distill_calls_per_batch,
        "distill_threshold_override": policy.distill_threshold_override,
    }


def _provider_config_snapshot(
    *,
    timeout_seconds: float | None = None,
    call_deadline_seconds: float | None = None,
    max_inflight_calls: int | None = None,
) -> dict[str, Any]:
    return {
        "timeout_seconds": timeout_seconds,
        "call_deadline_seconds": call_deadline_seconds,
        "max_inflight_calls": max_inflight_calls,
    }


def _failure_event(request_id: str, exc: BaseException, *, action: str) -> None:
    _cli_event(
        "batch",
        "error",
        request_id=request_id,
        class_=failure_class(exc),
        action=action,
        error=safe_exc(exc),
    )


def _run_assignment(
    *,
    assignment: ExplorationAssignment,
    scenario_loader: ScenarioLoader,
    nodes: Sequence[Any],
    provider_factory: ProviderFactory,
    batch_dir: Path,
    state_dir: Path,
    events: list[dict],
    delta_portfolio: list[DeltaPortfolioRow],
    live_skill_root: Path,
    journal_path: Path,
    max_concurrent: int,
    cli: CliReporter | None,
    trial_skill_roots: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    return _run_one_request(
        request_id=assignment.request_id,
        scenario=scenario_loader(assignment.request_id),
        nodes=nodes,
        provider_factory=provider_factory,
        request_dir=batch_dir / _safe_request_dirname(assignment.run_id),
        events=events,
        delta_portfolio=delta_portfolio,
        live_skill_root=live_skill_root,
        assignment=assignment,
        journal_path=journal_path,
        trial_skill_roots=trial_skill_roots,
        max_concurrent=max_concurrent,
        cli=cli,
    )


def _settle_wave_trial_uplifts(
    *,
    batch_dir: Path,
    wave_records: Sequence[dict[str, Any]],
    scenario_loader: ScenarioLoader,
    journal_path: Path,
) -> None:
    baseline_observations: list[FormalBaselineObservation] = []
    for record in wave_records:
        if not isinstance(record, dict):
            continue
        try:
            scenario = scenario_loader(str(record.get("request_id") or ""))
        except Exception:
            continue
        observation = _formal_baseline_observation(
            batch_dir=batch_dir,
            record=record,
            scenario=scenario,
        )
        if observation is not None:
            baseline_observations.append(observation)

    for record in wave_records:
        if not isinstance(record, dict):
            continue
        selected_delta_id = record.get("trial_selected_delta_id")
        if not selected_delta_id:
            continue
        if record.get("exception") is not None or record.get("skipped") is True:
            continue
        artifact_paths = _artifact_paths_for_record(batch_dir=batch_dir, record=record)
        if artifact_paths is None:
            continue
        request_id = str(record.get("request_id") or "")
        try:
            scenario = scenario_loader(request_id)
        except Exception as exc:
            _cli_event(
                "runner",
                "trial_uplift_deferred",
                request_id=request_id,
                delta_id=selected_delta_id,
                reason="scenario_unavailable",
                error=safe_exc(exc),
            )
            continue
        baseline_reference = _baseline_reference_for_trial(
            scenario=scenario,
            observations=baseline_observations,
        )
        if baseline_reference is None:
            _cli_event(
                "runner",
                "trial_uplift_deferred",
                request_id=request_id,
                delta_id=selected_delta_id,
                reason="no_baseline_reference",
            )
            continue
        trial_tokens = int(record.get("token_cost_observed") or 0)
        _record_trial_uplift_from_reference(
            request_id=request_id,
            selected_delta_id=str(selected_delta_id),
            baseline_reference=baseline_reference,
            trial_artifact_paths=artifact_paths,
            trial_tokens=trial_tokens,
            journal_path=journal_path,
        )
        _cli_event(
            "runner",
            "trial_uplift_recorded",
            request_id=request_id,
            delta_id=selected_delta_id,
            baseline=f"{baseline_reference.mean_rubric_score:.2f}",
            baseline_n=baseline_reference.sample_count,
            strategy=baseline_reference.strategy,
        )


def _distill_successful_wave_requests(
    *,
    batch_dir: Path,
    wave_records: list[dict[str, Any]],
    provider_factory: ProviderFactory,
    portfolio: list[DeltaPortfolioRow],
    live_skill_root: Path | None = None,
    distill_min_trajectories: int | None = None,
    budget_policy: EvolutionBudgetPolicy | None = None,
    distillation_scheduler: DistillationScheduler | None = None,
) -> list[DeltaPortfolioRow]:
    planning = _plan_distillation_for_wave(
        batch_dir=batch_dir,
        wave_records=wave_records,
        distill_min_trajectories=distill_min_trajectories,
        budget_policy=budget_policy,
        distillation_scheduler=distillation_scheduler,
    )
    updated_portfolio = portfolio
    for plan in planning.plans:
        try:
            updated_portfolio = _distill_from_trajectory_dirs(
                request_dirs=plan.request_dirs,
                evidence_dir=plan.evidence_dir,
                provider_factory=provider_factory,
                current_portfolio=updated_portfolio,
                pipeline_id=plan.pipeline_id,
                live_skill_root=live_skill_root,
            )
        except Exception as exc:
            _cli_event(
                "runner",
                "distill_skipped",
                request_id=plan.evidence_dir.name,
                pipeline_id=plan.pipeline_id,
                error=safe_exc(exc),
            )
    return updated_portfolio


def _plan_distillation_for_wave(
    *,
    batch_dir: Path,
    wave_records: list[dict[str, Any]],
    distill_min_trajectories: int | None = None,
    budget_policy: EvolutionBudgetPolicy | None = None,
    distillation_scheduler: DistillationScheduler | None = None,
) -> Any:
    if budget_policy is None:
        budget_policy = EvolutionBudgetPolicy(
            distill_threshold_override=_distill_threshold_override(
                distill_min_trajectories
            ),
        )
    if distillation_scheduler is None:
        distillation_scheduler = DistillationScheduler(policy=budget_policy)
    planning = distillation_scheduler.plan_wave(
        batch_dir=batch_dir,
        wave_records=wave_records,
    )
    if not planning.plans:
        for deferral in planning.deferrals:
            _cli_event(
                "runner",
                "distill_deferred",
                pipeline_id=deferral.pipeline_id,
                trajectories=deferral.trajectories,
                threshold=deferral.threshold,
                reject=deferral.reject_count,
                hold=deferral.hold_count,
                reason=deferral.reason,
            )
        return planning

    for deferral in planning.deferrals:
        _cli_event(
            "runner",
            "distill_deferred",
            pipeline_id=deferral.pipeline_id,
            trajectories=deferral.trajectories,
            threshold=deferral.threshold,
            reject=deferral.reject_count,
            hold=deferral.hold_count,
            reason=deferral.reason,
        )
    return planning


class _DistillationJobQueue:
    """Run distillation calls off the production wave and merge proposals later."""

    def __init__(
        self,
        *,
        provider_factory: ProviderFactory,
        live_skill_root: Path,
        max_workers: int = 1,
    ) -> None:
        self._provider_factory = provider_factory
        self._live_skill_root = live_skill_root
        self._pool = ThreadPoolExecutor(max_workers=max(1, int(max_workers)))
        self._pending: list[_PendingDistillationJob] = []

    def submit(self, plan: DistillBundlePlan) -> None:
        _cli_event(
            "runner",
            "distill_queued",
            pipeline_id=plan.pipeline_id,
            trajectories=len(plan.request_dirs),
            reject=plan.reject_count,
            hold=plan.hold_count,
        )
        future = self._pool.submit(
            _distill_proposals_from_trajectory_dirs,
            request_dirs=plan.request_dirs,
            evidence_dir=plan.evidence_dir,
            provider_factory=self._provider_factory,
            pipeline_id=plan.pipeline_id,
            live_skill_root=self._live_skill_root,
        )
        self._pending.append(_PendingDistillationJob(plan=plan, future=future))

    def harvest(
        self,
        portfolio: list[DeltaPortfolioRow],
        *,
        block: bool = False,
    ) -> list[DeltaPortfolioRow]:
        updated_portfolio = portfolio
        remaining: list[_PendingDistillationJob] = []
        for job in self._pending:
            if not block and not job.future.done():
                remaining.append(job)
                continue
            try:
                proposals = job.future.result()
            except Exception as exc:
                _cli_event(
                    "runner",
                    "distill_skipped",
                    request_id=job.plan.evidence_dir.name,
                    pipeline_id=job.plan.pipeline_id,
                    error=safe_exc(exc),
                )
                continue
            updated_portfolio = assemble_portfolio(
                updated_portfolio,
                proposals,
                events=None,
            )
            _cli_event(
                "runner",
                "distill_merged",
                pipeline_id=job.plan.pipeline_id,
                proposals=len(proposals),
                delta_ids=",".join(proposal.delta_id for proposal in proposals),
            )
        self._pending = remaining
        return updated_portfolio

    def shutdown(self) -> None:
        self._pool.shutdown(wait=True)


@dataclass(frozen=True)
class _PortfolioSettlement:
    portfolio: list[DeltaPortfolioRow]
    entries_seen: int


def _emit_promotion_event(promoted: Any) -> None:
    if (
        promoted.promotion is not None
        and (promoted.promotion.promoted_delta_ids or promoted.promotion.skipped)
    ):
        _cli_event(
            "runner",
            "promotion_done",
            promoted=",".join(promoted.promotion.promoted_delta_ids),
            skipped=len(promoted.promotion.skipped),
            manifest=promoted.promotion.manifest_path,
        )


def _settle_portfolio_state(
    *,
    batch_dir: Path,
    state_dir: Path,
    batch_id: str,
    portfolio: list[DeltaPortfolioRow],
    entries_seen: int,
    portfolio_coordinator: PortfolioCoordinator,
    distillation_jobs: _DistillationJobQueue | None = None,
    block_distillation: bool = False,
) -> _PortfolioSettlement:
    folded = portfolio_coordinator.fold_new_entries(
        portfolio=portfolio,
        entries_seen=entries_seen,
    )
    settled_portfolio = folded.portfolio
    settled_entries_seen = folded.entries_seen
    if distillation_jobs is not None:
        settled_portfolio = distillation_jobs.harvest(
            settled_portfolio,
            block=block_distillation,
        )
    settled_portfolio = portfolio_coordinator.apply_status(settled_portfolio)
    promoted = portfolio_coordinator.promote_if_ready(
        portfolio=settled_portfolio,
        batch_id=batch_id,
    )
    settled_portfolio = promoted.portfolio
    _emit_promotion_event(promoted)
    _persist_portfolio_snapshot(
        batch_dir=batch_dir,
        state_dir=state_dir,
        portfolio=settled_portfolio,
    )
    return _PortfolioSettlement(
        portfolio=settled_portfolio,
        entries_seen=settled_entries_seen,
    )


def _chunks(items: Sequence[str], size: int) -> list[list[str]]:
    size = max(1, int(size))
    return [list(items[index : index + size]) for index in range(0, len(items), size)]


def _persist_portfolio_snapshot(
    *,
    batch_dir: Path,
    state_dir: Path,
    portfolio: Sequence[DeltaPortfolioRow],
) -> Path:
    """Durably snapshot the current delta portfolio for resume/promotion."""
    batch_portfolio_path = batch_dir / "portfolio.jsonl"
    write_portfolio_jsonl(batch_portfolio_path, list(portfolio))
    state_portfolio_path = state_dir / "portfolio.jsonl"
    if state_portfolio_path.resolve() != batch_portfolio_path.resolve():
        write_portfolio_jsonl(state_portfolio_path, list(portfolio))
    return batch_portfolio_path


def _prime_scenario_loader(
    scenario_loader: ScenarioLoader,
    request_ids: Sequence[str],
) -> None:
    prime = getattr(scenario_loader, "prime", None)
    if callable(prime):
        prime(list(request_ids))


def run_batch(
    *,
    request_ids: Sequence[str],
    scenario_loader: ScenarioLoader,
    nodes: Sequence[Any],
    provider_factory: ProviderFactory,
    batch_dir: Path,
    state_dir: Path,
    batch_id: str,
    delta_portfolio: list[DeltaPortfolioRow],
    live_skill_root: Path,
    num_requests: int | None = None,
    concurrency: int = DEFAULT_CONCURRENCY,
    enable_distillation: bool = True,
    distill_min_trajectories: int | None = None,
    trial_budget_fraction: float | None = None,
    resume: bool = False,
    provider_config: Mapping[str, Any] | None = None,
) -> BatchResult:
    """Run one production batch and write index/summary/offline assets."""
    n = int(num_requests if num_requests is not None else len(request_ids))
    if n < 0:
        raise ValueError("num_requests must be non-negative")
    if len(request_ids) < n:
        raise RuntimeError(f"production batch requires {n} request_ids, got {len(request_ids)}")
    batch_request_ids = list(request_ids[:n])
    ledger = RunLedger(batch_dir)
    ledger.prepare(resume=resume)
    state_dir.mkdir(parents=True, exist_ok=True)
    journal_path = state_dir / "portfolio_journal.jsonl"
    portfolio_coordinator = PortfolioCoordinator(
        journal_path=journal_path,
        live_skill_root=live_skill_root,
        promotion_min_ready=_promotion_min_ready_from_env(),
        timestamp_factory=_utc_timestamp_for_dir,
    )
    entries_before = portfolio_coordinator.entry_count()
    entries_seen_at_start = entries_before

    started_at = _utc_now_iso()
    started_monotonic = time.monotonic()
    budget_policy = _evolution_budget_policy(
        trial_budget_fraction=trial_budget_fraction,
        distill_min_trajectories=distill_min_trajectories,
    )
    resumed_records = ledger.load_resumable_records(
        requested_slot_ids=batch_request_ids,
    ) if resume else []
    completed_slots = {
        slot
        for record in resumed_records
        for slot in [
            completed_slot_id(record, requested_slot_ids=batch_request_ids)
        ]
        if slot is not None
    }
    pending_request_ids = [
        request_id for request_id in batch_request_ids if request_id not in completed_slots
    ]
    records: list[dict[str, Any]] = list(resumed_records)
    ledger.start(
        config=RunConfig(
            batch_id=batch_id,
            request_ids=batch_request_ids,
            num_requests=n,
            concurrency=concurrency,
            state_dir=str(state_dir),
            resume=resume,
            enable_distillation=enable_distillation,
            distill_min_trajectories=distill_min_trajectories,
            trial_budget_fraction=trial_budget_fraction,
            provider=dict(provider_config or {}),
            evolution_policy=_evolution_policy_snapshot(budget_policy),
        ),
        started_at=started_at,
        resumed_records=resumed_records,
    )

    dashboard = BatchDashboard(
        total=n,
        concurrency=concurrency,
        out_dir=batch_dir,
        stream=sys.stderr,
        max_running=5 if concurrency >= 5 else 3,
    )
    chain_cli = dashboard
    dashboard.start()
    for record in resumed_records:
        dashboard.complete_request(str(record.get("node_id") or record.get("request_id")), record)

    portfolio = list(delta_portfolio)
    exploration_planner = ExplorationPlanner(
        policy=budget_policy,
        rng=_trial_rng,
    )
    distillation_scheduler = DistillationScheduler(policy=budget_policy)
    distillation_jobs = (
        _DistillationJobQueue(
            provider_factory=provider_factory,
            live_skill_root=live_skill_root,
        )
        if enable_distillation
        else None
    )
    trial_workspace_cache = TrialWorkspaceCache(
        live_skill_root=live_skill_root,
        cache_dir=batch_dir / "_trial_skill_workspaces",
    )
    for wave_ids in _chunks(pending_request_ids, concurrency):
        if distillation_jobs is not None:
            settled = _settle_portfolio_state(
                batch_dir=batch_dir,
                state_dir=state_dir,
                batch_id=batch_id,
                portfolio=portfolio,
                entries_seen=entries_before,
                portfolio_coordinator=portfolio_coordinator,
                distillation_jobs=distillation_jobs,
                block_distillation=False,
            )
            portfolio = settled.portfolio
            entries_before = settled.entries_seen
        compiled_trial_deltas = _compiled_trial_deltas(
            portfolio,
            live_skill_root=live_skill_root,
        )
        trialable_portfolio = [
            row for row in portfolio if row.delta_id in compiled_trial_deltas
        ]
        applicable_surface = _applicable_surface_for(nodes, trialable_portfolio)
        target_skills = _target_skills_for_nodes(nodes)
        exploration_plan = exploration_planner.plan_wave(
            request_ids=wave_ids,
            portfolio=trialable_portfolio,
            applicable_surface=applicable_surface,
            target_skills=target_skills,
        )
        assignments = list(exploration_plan.assignments)
        trial_skill_roots = _prepare_trial_skill_roots_for_wave(
            assignments=assignments,
            compiled_trial_deltas=compiled_trial_deltas,
            workspace_cache=trial_workspace_cache,
        )
        _prime_scenario_loader(
            scenario_loader,
            [assignment.request_id for assignment in assignments],
        )
        per_request_events: dict[str, list[dict]] = {
            assignment.run_id: [] for assignment in assignments
        }
        wave_records: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=max(1, int(concurrency))) as pool:
            future_to_assignment = {
                pool.submit(
                    _run_assignment,
                    assignment=assignment,
                    scenario_loader=scenario_loader,
                    nodes=nodes,
                    provider_factory=provider_factory,
                    batch_dir=batch_dir,
                    state_dir=state_dir,
                    events=per_request_events[assignment.run_id],
                    delta_portfolio=portfolio,
                    live_skill_root=live_skill_root,
                    journal_path=journal_path,
                    max_concurrent=concurrency,
                    cli=chain_cli,
                    trial_skill_roots=trial_skill_roots,
                ): assignment
                for assignment in assignments
            }
            for fut in as_completed(future_to_assignment):
                assignment = future_to_assignment[fut]
                rid = assignment.run_id
                try:
                    record = fut.result()
                    records.append(record)
                    wave_records.append(record)
                    ledger.append_record(record)
                    dashboard.complete_request(rid, record)
                except BaseException as exc:
                    fail_record = _failed_record(
                        assignment.request_id,
                        exc,
                        node_id=assignment.run_id,
                        original_request_id=assignment.original_request_id,
                        trial_selected_delta_id=assignment.delta_id,
                    )
                    if is_trial_failure(exc):
                        records.append(fail_record)
                        wave_records.append(fail_record)
                        ledger.append_record(fail_record)
                        dashboard.complete_request(rid, fail_record)
                        _cli_event("batch", "trial_failure", request_id=rid, action="continuing")
                        continue
                    if is_request_output_failure(exc):
                        fail_record["skipped"] = True
                        records.append(fail_record)
                        wave_records.append(fail_record)
                        ledger.append_record(fail_record)
                        dashboard.complete_request(rid, fail_record)
                        _failure_event(rid, exc, action="recording")
                        continue
                    records.append(fail_record)
                    wave_records.append(fail_record)
                    ledger.append_record(fail_record)
                    dashboard.complete_request(rid, fail_record)
                    _failure_event(rid, exc, action="recording")
        _settle_wave_trial_uplifts(
            batch_dir=batch_dir,
            wave_records=wave_records,
            scenario_loader=scenario_loader,
            journal_path=journal_path,
        )
        settled = _settle_portfolio_state(
            batch_dir=batch_dir,
            state_dir=state_dir,
            batch_id=batch_id,
            portfolio=portfolio,
            entries_seen=entries_before,
            portfolio_coordinator=portfolio_coordinator,
        )
        portfolio = settled.portfolio
        entries_before = settled.entries_seen
        if enable_distillation:
            planning = _plan_distillation_for_wave(
                batch_dir=batch_dir,
                wave_records=wave_records,
                distill_min_trajectories=distill_min_trajectories,
                budget_policy=budget_policy,
                distillation_scheduler=distillation_scheduler,
            )
            if distillation_jobs is not None:
                for plan in planning.plans:
                    distillation_jobs.submit(plan)

    if distillation_jobs is not None:
        settled = _settle_portfolio_state(
            batch_dir=batch_dir,
            state_dir=state_dir,
            batch_id=batch_id,
            portfolio=portfolio,
            entries_seen=entries_before,
            portfolio_coordinator=portfolio_coordinator,
            distillation_jobs=distillation_jobs,
            block_distillation=True,
        )
        portfolio = settled.portfolio
        entries_before = settled.entries_seen
        distillation_jobs.shutdown()

    records, failed_requests_report = _retry_failed_request_records(
        records=records,
        scenario_loader=scenario_loader,
        nodes=nodes,
        provider_factory=provider_factory,
        batch_dir=batch_dir,
        state_dir=state_dir,
        delta_portfolio=portfolio,
        live_skill_root=live_skill_root,
        journal_path=journal_path,
        max_concurrent=concurrency,
    )
    ledger.write_records(records)
    finished_at = _utc_now_iso()
    failed_requests_path = _write_failed_requests_report(
        batch_dir=batch_dir,
        report=failed_requests_report,
    )
    main_slot_records = list(
        _main_slot_records(records, requested_slot_ids=batch_request_ids)
    )
    trial_record_count = sum(1 for record in records if _is_trial_record(record))
    passed = (len(main_slot_records) == n) and all(
        r.get("exception") is None and r.get("skipped") is not True
        for r in main_slot_records
    )

    write_index(
        records=records,
        out_dir=batch_dir,
        batch_id=batch_id,
        started_at=started_at,
        finished_at=finished_at,
        n=n,
        concurrency=concurrency,
    )
    batch_portfolio_path = _persist_portfolio_snapshot(
        batch_dir=batch_dir,
        state_dir=state_dir,
        portfolio=portfolio,
    )
    write_batch_summary(
        batch_dir / "index.json",
        final_portfolio=portfolio,
        trial_belief_update_count=_journal_entry_count_since(
            journal_path,
            entries_seen_at_start,
        ),
    )
    offline_rows: list[dict[str, Any]] = []
    for record in main_slot_records:
        offline_rows.extend(record.get("offline_copy_rows") or [])
    write_offline_copy_table(offline_rows, batch_dir)
    run_journal_path = _write_run_portfolio_journal(
        batch_dir=batch_dir,
        journal_path=journal_path,
        entries_seen_at_start=entries_seen_at_start,
    )
    ledger.finish(
        status="PASSED" if passed else "FAILED",
        finished_at=finished_at,
        records=records,
        failed_requests_path=failed_requests_path,
        portfolio_path=batch_portfolio_path,
        run_journal_path=run_journal_path,
    )

    _cli_event(
        "batch",
        "done",
        status="PASSED" if passed else "FAILED",
        completed=f"{len(main_slot_records)}/{n}",
        failures=sum(
            1
            for row in main_slot_records
            if row.get("exception") is not None or row.get("skipped") is True
        ),
        trials=trial_record_count,
        failed_requests=failed_requests_path,
        duration=f"{time.monotonic() - started_monotonic:.1f}s",
        out_dir=batch_dir,
    )
    dashboard.finish()

    return BatchResult(
        passed=passed,
        records=records,
        batch_dir=batch_dir,
        started_at=started_at,
        finished_at=finished_at,
        exception=None if passed else RuntimeError("one or more requests failed"),
        portfolio=portfolio,
    )


def run(
    *,
    out_dir: Path | None = None,
    state_dir: Path | None = None,
    csv: Path | None = None,
    num_requests: int | None = None,
    request_ids: Sequence[str] | None = None,
    scenario_loader: ScenarioLoader | None = None,
    nodes_factory: NodesFactory | None = None,
    provider_factory: ProviderFactory | None = None,
    concurrency: int | None = None,
    timeout_seconds: float | None = None,
    call_deadline_seconds: float | None = None,
    max_inflight_calls: int | None = None,
    node_max_attempts: int | None = None,
    enable_distillation: bool = True,
    distill_min_trajectories: int | None = None,
    trial_budget_fraction: float | None = None,
    resume: bool = False,
) -> int:
    """Programmatic production entry point. Returns a process exit code."""
    if num_requests is None and request_ids is not None:
        n = len(request_ids)
    else:
        n = int(num_requests if num_requests is not None else DEFAULT_BATCH_REQUESTS)
    c = int(concurrency if concurrency is not None else DEFAULT_CONCURRENCY)
    if out_dir is None:
        out_dir = DEFAULT_RUNS_ROOT / _utc_timestamp_for_dir()
    out_dir = Path(out_dir)
    if state_dir is None:
        state_dir = out_dir
    state_dir = Path(state_dir)
    batch_id = out_dir.name

    if request_ids is None:
        request_ids = default_request_ids(csv=csv, num_requests=n)
    if scenario_loader is None:
        scenario_loader = default_scenario_loader(
            csv=csv,
            num_requests=n,
            request_ids=request_ids,
        )
    if nodes_factory is None:
        nodes = list(_default_nodes_factory(node_max_attempts=node_max_attempts))
    else:
        nodes = list(nodes_factory())
    if provider_factory is None:
        provider_factory = _default_provider_factory(
            timeout_seconds=timeout_seconds,
            call_deadline_seconds=call_deadline_seconds,
            max_inflight_calls=max_inflight_calls,
        )

    portfolio_path = state_dir / "portfolio.jsonl"
    delta_portfolio = load_portfolio_jsonl(portfolio_path)

    _cli_event(
        "runner",
        "start",
        batch_id=batch_id,
        request_ids=len(request_ids),
        n=n,
        concurrency=c,
        out_dir=out_dir,
        state_dir=state_dir,
    )

    result = run_batch(
        request_ids=request_ids,
        scenario_loader=scenario_loader,
        nodes=nodes,
        provider_factory=provider_factory,
        batch_dir=out_dir,
        state_dir=state_dir,
        batch_id=batch_id,
        delta_portfolio=delta_portfolio,
        live_skill_root=LIVE_SKILL_ROOT,
        num_requests=n,
        concurrency=c,
        enable_distillation=enable_distillation,
        distill_min_trajectories=distill_min_trajectories,
        trial_budget_fraction=trial_budget_fraction,
        resume=resume,
        provider_config=_provider_config_snapshot(
            timeout_seconds=timeout_seconds,
            call_deadline_seconds=call_deadline_seconds,
            max_inflight_calls=max_inflight_calls,
        ),
    )
    if not result.passed:
        _cli_event("runner", "done", status="FAILED")
        return 1
    _cli_event("runner", "done", status="PASSED")
    return 0


def main(argv: list[str] | None = None) -> int:
    """argparse entry point. Returns process exit code."""
    parser = argparse.ArgumentParser(
        prog="python -m seers_harness.validation.runner",
        description="VIP COPY production batch runner.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory for run artifacts. Defaults to .runs/<utc-timestamp>/.",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=None,
        help="Directory for portfolio.jsonl and portfolio_journal.jsonl. Defaults to --out-dir.",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Override the default data_100k.csv path.",
    )
    parser.add_argument(
        "--num-requests",
        type=int,
        default=None,
        help=f"Number of request_ids to run. Defaults to {DEFAULT_BATCH_REQUESTS}.",
    )
    parser.add_argument(
        "--request-id",
        dest="request_ids",
        action="append",
        default=None,
        help="Explicit request_id to run. Repeat to run multiple selected requests.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"Production request parallelism. Defaults to {DEFAULT_CONCURRENCY}.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Provider SDK/read timeout seconds; overrides DEEPSEEK_TIMEOUT_SECONDS.",
    )
    parser.add_argument(
        "--call-deadline",
        type=float,
        default=None,
        help="Per-call wall-clock deadline during streaming; overrides DEEPSEEK_CALL_DEADLINE_SECONDS.",
    )
    parser.add_argument(
        "--max-inflight-calls",
        type=int,
        default=None,
        help="Global provider API call limit; overrides DEEPSEEK_MAX_INFLIGHT_CALLS.",
    )
    parser.add_argument(
        "--node-max-attempts",
        type=int,
        default=None,
        help=(
            "Max attempts per production DAG node. Defaults to "
            "VIP_COPY_NODE_MAX_ATTEMPTS, legacy SEERS_NODE_MAX_ATTEMPTS, or 3."
        ),
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Path to KEY=VALUE env file (no shell expansion).",
    )
    parser.add_argument(
        "--no-distill",
        action="store_true",
        help="Disable post-wave evolution distillation for this production run.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume an existing --out-dir using completed_records.jsonl.",
    )
    parser.add_argument(
        "--distill-min-trajectories",
        type=int,
        default=None,
        help=(
            "Optional fixed minimum reject/hold successful trajectories per "
            "pipeline before lazy evolution distillation. By default the "
            "scheduler derives this from the evolution budget policy; "
            "VIP_COPY_DISTILL_MIN_TRAJECTORIES may also override it."
        ),
    )
    parser.add_argument(
        "--trial-budget-fraction",
        type=float,
        default=None,
        help=(
            "Maximum fraction of a concurrency wave that may be assigned to "
            "delta trials. Defaults to VIP_COPY_TRIAL_BUDGET_FRACTION or 0.02."
        ),
    )
    args = parser.parse_args(argv)

    if args.env_file is not None:
        count = _load_env_file(args.env_file)
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        suffix = api_key[-4:] if api_key else "<unset>"
        _cli_line(f"[runner] env-file: loaded {count} keys from {args.env_file}")
        _cli_line(f"[runner] env-file: DEEPSEEK_API_KEY suffix=****{suffix}")

    return run(
        out_dir=args.out_dir,
        state_dir=args.state_dir,
        csv=args.csv,
        num_requests=args.num_requests,
        request_ids=args.request_ids,
        concurrency=args.concurrency,
        timeout_seconds=args.timeout,
        call_deadline_seconds=args.call_deadline,
        max_inflight_calls=args.max_inflight_calls,
        node_max_attempts=args.node_max_attempts,
        enable_distillation=not args.no_distill,
        distill_min_trajectories=args.distill_min_trajectories,
        trial_budget_fraction=args.trial_budget_fraction,
        resume=args.resume,
    )


if __name__ == "__main__":
    sys.exit(main())
