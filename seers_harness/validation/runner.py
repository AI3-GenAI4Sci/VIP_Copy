"""Three-stage real-LLM validation runner — Phase 7 plan 07-04.

CLI entry point::

    python -m seers_harness.validation.runner [--stage {1,2,3}] [--out-dir PATH] \\
                                               [--csv PATH] [--num-requests N]

Default invocation runs Stage 1 -> Stage 2 -> Stage 3 end-to-end in a
single process with NO inter-stage human checkpoint (D-07). The
``--stage`` flag is OPTIONAL; pass it only when re-running a single
stage after fixing a failure.

Stage matrix (D-01)::

    Stage 1 :  N=1   concurrency=1
    Stage 2 :  N=20  concurrency=1
    Stage 3 :  N=20  concurrency=20

Stage 1 is the only pre-flight gate (D-05 read together with D-07): if
Stage 1 fails the run stops; if Stage 1 passes, Stage 2 starts
automatically; if Stage 2 passes, Stage 3 starts automatically. Any
non-trial exception in any stage fails fast at request level (D-02) and
the run exits non-zero without advancing.

Stage 3 stepping policy
=======================

Stage 3 runs concurrency=20 one-shot rather than stepping 4 -> 8 -> 20.
Rationale (planner discretion D-22(a), D-22(e)): Phase 6 PROD-02
confirmed DeepSeek tolerates a 20-request burst at the harness's
per-request payload size; stepping would consume budget without
surfacing a different failure mode. The one-shot c=20 path is the
canonical evidence path. Stepping (4 -> 8 -> 20) is reintroduced only
if a Stage 3 run fails fast on rate-limit before completion.

D-04 acknowledgement: Stage 3 may mask real concurrency-induced rate
ceilings because per-request transient-error budget = 3, and 20
concurrent requests collectively share 60 budgeted re-attempts of
slack. This is observation, not stabilisation (D-04). Real-DeepSeek
concurrency tuning, circuit-breakers, and rate-limit absorption are
deferred to a follow-up phase.

Provider, error budget, token policy
====================================

* Provider: ``OpenAICompatibleProvider`` instantiated via
  ``deepseek_provider_from_env(...)``. The DeepSeek API key is read
  from the ``DEEPSEEK_API_KEY`` environment variable (the existing
  helper also reads ``DEEPSEEK_TIMEOUT_SECONDS`` /
  ``DEEPSEEK_BASE_URL`` / ``DEEPSEEK_MODEL`` /
  ``DEEPSEEK_SDK_MAX_RETRIES``). ``DEEPSEEK_API_KEY`` is mandatory at
  run time; the runner does not bake any key into source.
* Transient-error budget: lives on the underlying ``OpenAI`` client
  ONLY (D-03). The runner has NO wrapper around the provider call —
  no extra re-attempt loop, no extra exception-swallowing layer.
* Token cap: NONE (D-06). ``tool_loop.run_skill_via_tools``'s
  ``max_tool_calls`` ceiling is the sole death-loop defense.

Trial isolation
===============

Trial isolation reuses ``apply_delta_patch_temporarily`` from
``seers_harness/evolution/trial_runner.py`` (D-21). The runner does
NOT reimplement the temp-dir mechanism. In Phase 7 the
``delta_portfolio`` starts EMPTY at process start (D-18) — zero trials
in Stage 1 / early Stage 2 is expected and never a fail-fast trigger.

Output
======

All run output writes under ``tests/smoke/.runs/<utc-timestamp>/`` which
is git-ignored (D-09). Per-stage:

* ``<out_dir>/stage{N}/<safe_request_id>/`` — per-node JSONL via
  ``flush_evidence`` (07-02): ``messages.jsonl`` / ``tool_calls.jsonl`` /
  ``artifact.json`` / ``usage.json``.
* ``<out_dir>/stage{N}/<safe_request_id>/evolution_snapshot.json`` —
  per-request VAL-06 evidence via ``write_evolution_snapshot`` (07-01).
* ``<out_dir>/stage{N}/index.json`` + ``batch_summary.json`` —
  one-row-per-request batch index via ``write_index`` /
  ``write_batch_summary`` (07-03).

Exception routing (D-19)
========================

Exceptions are routed via ``exception_classifier.classify(exc)``:

* ``"trial_failure"`` — host request continues; the trial outcome is
  recorded in ``evolution_snapshot.json`` via the 07-01 hook.
* ``"provider_error"`` / ``"infra_error"`` — fail fast at request
  level: stage stops, exit code non-zero, partial artifacts on disk
  are preserved as the failure scene.

Test isolation
==============

The runner accepts an injectable ``provider_factory`` parameter so
tests can pass a fake provider without hitting real DeepSeek. The
default factory is ``_default_deepseek_factory`` (which calls
``deepseek_provider_from_env`` with the D-03 budget); tests typically
wire in a ``ScriptedProvider`` shaped like
``tests/smoke/scripted_full_chain.build_full_chain_script``.

Forbid list (do not change without re-reading 07-CONTEXT)
=========================================================

* No wrapper around the provider call — D-03 keeps the SDK's
  transient-error budget as the sole resilience surface.
* No single-request token cap (D-06).
* No inter-stage human checkpoint (D-07) — do NOT print
  "Stage N complete - re-invoke with --stage N+1" pause messages.
* No re-implementation of trial isolation (D-21).
* No copy of the chain logic — the runner reuses ``make_nodes`` and
  the canonical scripted-chain shape via dependency injection.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from seers_harness.domain.models import (
    CopyGenerationArtifact,
    FactorDiscoveryArtifact,
    PersonalizedCopyRubricArtifact,
)
from seers_harness.evolution.delta_portfolio import (
    DeltaDistillationArtifact,
    DeltaPortfolioRow,
    assemble_portfolio,
    update_after_trial,
)
from seers_harness.evolution.trial_runner import (
    SkillDeltaPatch,
    run_request_trial,
    sha256_of_text,
)
from seers_harness.workflow.dag_runner import WorkflowRuntime
from seers_harness.validation._secrets import safe_exc
from seers_harness.validation.evidence_writer import flush_evidence
from seers_harness.validation.evolution_snapshot import write_evolution_snapshot
from seers_harness.validation.exception_classifier import (
    classify,
    failure_class,
    is_trial_failure,
)
from seers_harness.validation.index_writer import write_index
from seers_harness.validation.batch_summary_writer import write_batch_summary
from seers_harness.validation.recording_provider import (
    RecordingProvider,
    set_current_node_id,
)


# ---------------------------------------------------------------------------
# Stage matrix (D-01)
# ---------------------------------------------------------------------------

# (n, concurrency) tuples per stage. Locked by D-01 — DO NOT change
# these values without re-reading 07-CONTEXT.md decisions D-01 / D-04 /
# D-05 / D-07. Stepping policy for Stage 3 is one-shot c=20 per the
# plan rationale captured in the module docstring.
_STAGE_CONFIG: dict[int, tuple[int, int]] = {
    1: (1, 1),
    2: (20, 1),
    3: (20, 20),
}


_DEFAULT_RUNS_ROOT = Path("tests/smoke/.runs")
LIVE_SKILL_ROOT: Path = Path(__file__).resolve().parents[2] / "workflow-skills"
_DEFAULT_NUM_REQUESTS = 20


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


ProviderFactory = Callable[[], Any]
"""Zero-arg callable returning a fresh ``OpenAICompatibleProvider``-shaped
object. The default factory is ``_default_deepseek_factory`` which
returns a real-DeepSeek provider; tests inject a fake provider factory
to avoid real network calls. A fresh provider per thread is the
harness-concurrency contract from the Phase 6
``test_concurrency_smoke``.
"""


ScenarioLoader = Callable[[str], dict[str, Any]]
"""Callable mapping ``request_id`` -> scenario dict. The default loader
reads from ``data_100k.csv`` via ``preprocess_request_from_csv``;
tests inject a synthetic loader."""


NodesFactory = Callable[[], Sequence[Any]]
"""Zero-arg callable returning the 3-node DAG spec. Defaults to
``tests.smoke.scripted_full_chain.make_nodes`` (the canonical
3-node DAG that maps factor_discovery -> copy_generation ->
personalized_copy_rubric).
"""


@dataclass
class StageResult:
    """Outcome of one stage run.

    ``passed`` is True iff every submitted request reached all three
    nodes with valid artifacts. ``records`` is the per-request list
    handed to ``write_index``. ``stage_dir`` is the on-disk output
    directory.
    """

    stage: int
    passed: bool
    records: list[dict[str, Any]] = field(default_factory=list)
    stage_dir: Path = field(default_factory=Path)
    started_at: str = ""
    finished_at: str = ""
    exception: BaseException | None = None


# ---------------------------------------------------------------------------
# Default factories — wired only when a test does not inject overrides.
# ---------------------------------------------------------------------------


def _default_deepseek_factory() -> Any:
    # Default provider factory — real DeepSeek via env vars.
    #
    # Reads DEEPSEEK_API_KEY (mandatory) plus the optional
    # DEEPSEEK_BASE_URL / DEEPSEEK_MODEL / DEEPSEEK_TIMEOUT_SECONDS /
    # DEEPSEEK_SDK_MAX_RETRIES. The transient-error budget for the
    # underlying OpenAI client is forced to 3 here per D-03 and
    # overrides the env default of 0. The runner has NO wrapper layer
    # around the provider call (D-03) — the SDK budget is the sole
    # resilience surface, no extra re-attempt loop, no extra
    # exception-swallowing layer.
    #
    # Imported lazily so ``--help`` works even when DEEPSEEK_API_KEY is
    # not set (the helper raises RuntimeError on missing env at
    # construction time).
    from seers_harness.provider_runtime.openai_compatible import (
        deepseek_provider_from_env,
    )

    return deepseek_provider_from_env(max_retries=_RUNNER_PROVIDER_MAX_RETRIES)


# D-03 transient-error budget for the underlying OpenAI client. The
# value 3 is provider-side ONLY (no wrapper layer in this module per
# the runner module-docstring forbid list).
_RUNNER_PROVIDER_MAX_RETRIES: int = 3  # D-03 budget


def _default_scenario_loader(
    csv: Path | None = None,
    num_requests: int | None = None,
) -> ScenarioLoader:
    """Default scenario loader — reads from ``data_100k.csv``.

    Returns a closure over a one-pass scratch CSV containing the first
    ``num_requests`` unique ``request_id``s, mirroring the smoke pattern
    (test_e2e_smoke.py L43-L98). The scratch CSV lives in a temp
    directory that is cleaned up implicitly when the process exits.

    Both ``csv`` and ``num_requests`` are CLI overrides (``--csv``
    / ``--num-requests``); when ``None`` the defaults are
    ``data_100k.csv`` and ``_DEFAULT_NUM_REQUESTS`` respectively.
    """
    # Imported lazily so the runner does not pay the smoke-import cost
    # in unit tests that inject a fake scenario_loader.
    import tempfile
    import csv as _csv

    from seers_harness.intake.request_preprocessor import (
        detect_delimiter,
        preprocess_request_from_csv,
    )

    csv_path = (
        Path(csv).resolve()
        if csv is not None
        else Path(__file__).resolve().parents[2] / "data_100k.csv"
    )
    if not csv_path.exists():
        raise RuntimeError(
            f"data_100k.csv not present at {csv_path}; supply --csv or "
            "inject a scenario_loader for tests"
        )

    limit = num_requests if num_requests is not None else _DEFAULT_NUM_REQUESTS

    scratch_dir = Path(tempfile.mkdtemp(prefix="seers-runner-"))
    scratch_csv = scratch_dir / "scratch.csv"
    _build_scratch_csv(csv_path, scratch_csv, limit)

    def loader(request_id: str) -> dict[str, Any]:
        return preprocess_request_from_csv(scratch_csv, request_id=request_id)

    return loader


def _build_scratch_csv(csv_path: Path, scratch_path: Path, limit: int) -> list[str]:
    """One-pass scan of the first ~1000 rows of ``csv_path`` capturing the
    first ``limit`` unique request_ids (mirrors test_e2e_smoke.py)."""
    import csv as _csv

    delimiter = detect_delimiter(csv_path)
    seen: set[str] = set()
    chosen_order: list[str] = []
    captured_lines: list[str] = []
    header_scan_limit = 1000

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        header_line = f.readline()
        if not header_line:
            raise RuntimeError("empty CSV")
        header = next(_csv.reader([header_line], delimiter=delimiter))
        try:
            request_id_idx = header.index("request_id")
        except ValueError as exc:
            raise RuntimeError(
                f"data_100k.csv missing 'request_id' column; header={header[:5]}..."
            ) from exc

        for _row_no in range(header_scan_limit):
            line = f.readline()
            if not line:
                break
            parsed = next(_csv.reader([line], delimiter=delimiter), None)
            if parsed is None or request_id_idx >= len(parsed):
                continue
            rid = parsed[request_id_idx].strip()
            if not rid:
                continue
            if rid in seen:
                if rid in chosen_order:
                    captured_lines.append(line)
                continue
            if len(chosen_order) >= limit:
                continue
            seen.add(rid)
            chosen_order.append(rid)
            captured_lines.append(line)

    scratch_path.write_text(
        header_line + "".join(captured_lines), encoding="utf-8"
    )
    return chosen_order


def _default_nodes_factory() -> NodesFactory:
    """Default nodes factory — reuses ``tests.smoke.scripted_full_chain.make_nodes``.

    Per D-22(a) the runner reuses the canonical 3-node DAG spec rather
    than copying it. Importing from ``tests.smoke`` keeps a single
    source of truth (``tests/smoke/scripted_full_chain.py``) for the
    workspace-wide chain shape; the import surface is stable across
    Phases 5/6/7. If 07-06 promotes the DAG spec into a shipped
    module, this import will move with it; the runner's seam is
    unchanged.
    """
    from tests.smoke.scripted_full_chain import make_nodes

    return make_nodes


def _default_request_ids_provider(
    csv: Path | None = None,
    num_requests: int | None = None,
) -> list[str]:
    """Default request-id list — first ``num_requests`` unique ids
    from ``csv`` (defaults: ``data_100k.csv``, ``_DEFAULT_NUM_REQUESTS``)."""
    import tempfile
    csv_path = (
        Path(csv).resolve()
        if csv is not None
        else Path(__file__).resolve().parents[2] / "data_100k.csv"
    )
    if not csv_path.exists():
        raise RuntimeError(
            f"data_100k.csv not present at {csv_path}; pass request_ids explicitly"
        )
    limit = num_requests if num_requests is not None else _DEFAULT_NUM_REQUESTS
    scratch_dir = Path(tempfile.mkdtemp(prefix="seers-runner-ids-"))
    scratch_csv = scratch_dir / "scratch.csv"
    return _build_scratch_csv(csv_path, scratch_csv, limit)


# ---------------------------------------------------------------------------
# Stage execution
# ---------------------------------------------------------------------------


def _safe_request_dirname(request_id: str) -> str:
    """Make a ``request_id`` safe for use as a directory name.

    Strips ``/``, ``\\``, ``:`` AND leading dots so ``..`` cannot be
    used to escape the stage directory; empty / single- / double-dot
    inputs fall back to ``"req"``. Matches the
    ``evidence_writer._sanitise_node_id`` rule so both writer layers
    refuse the same shape of malicious ``node_id`` / ``request_id``
    (CR-04 in 07-REVIEW.md).
    """
    if not isinstance(request_id, str) or not request_id:
        return "req"
    cleaned = (
        request_id.replace("/", "_").replace("\\", "_").replace(":", "_")
    )
    cleaned = cleaned.lstrip(".")
    if not cleaned or cleaned in {".", ".."}:
        return "req"
    return cleaned


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


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _build_trajectory_payload(stage1_request_dir: Path) -> dict:
    """Assemble the Stage 1 trace payload handed to distill-skill-deltas."""
    node_ids = (
        "factor_discovery",
        "copy_generation",
        "personalized_copy_rubric",
    )
    evidence_dir = stage1_request_dir / "evidence"
    artifacts: dict[str, Any] = {}
    tool_calls_per_node: dict[str, list[dict]] = {}
    usage_per_node: dict[str, Any] = {}

    for node_id in node_ids:
        node_dir = evidence_dir / node_id
        artifacts[node_id] = _read_json(node_dir / "artifact.json")
        tool_calls_per_node[node_id] = _read_jsonl(node_dir / "tool_calls.jsonl")
        usage_per_node[node_id] = _read_json(node_dir / "usage.json")

    return {
        "request_id": stage1_request_dir.name,
        "factor_discovery": artifacts["factor_discovery"],
        "copy_generation": artifacts["copy_generation"],
        "personalized_copy_rubric": artifacts["personalized_copy_rubric"],
        "tool_calls_per_node": tool_calls_per_node,
        "usage_per_node": usage_per_node,
    }


def _distill_after_stage1(
    *,
    stage1_result: StageResult,
    provider_factory: ProviderFactory,
    current_portfolio: list[DeltaPortfolioRow],
) -> list[DeltaPortfolioRow]:
    rid = stage1_result.records[0]["request_id"]
    stage1_request_dir = stage1_result.stage_dir / _safe_request_dirname(rid)
    trajectory_payload = _build_trajectory_payload(stage1_request_dir)
    skill_bundle = (
        LIVE_SKILL_ROOT / "evolution/distill-skill-deltas/SKILL.md"
    ).read_text(encoding="utf-8")

    from seers_harness.agentic.tool_loop import run_skill_via_tools
    from seers_harness.tools.evolution_tools import (
        EVOLUTION_TOOL_HANDLERS,
        EVOLUTION_TOOLS_SPEC,
    )

    distill_provider = RecordingProvider(provider_factory(), [])
    print(
        f"[runner] distill_after_stage1: starting agent, stage1_request_id={rid}",
        file=sys.stderr,
    )
    result = run_skill_via_tools(
        skill_name="distill-skill-deltas",
        skill_bundle=skill_bundle,
        payload=trajectory_payload,
        tools_spec=EVOLUTION_TOOLS_SPEC["distill-skill-deltas"],
        tool_handlers=EVOLUTION_TOOL_HANDLERS,
        provider=distill_provider,
        node_id="distill_after_stage1",
    )
    artifact = DeltaDistillationArtifact.model_validate(result.artifact)
    print(
        "[runner] distill_after_stage1: "
        f"produced {len(artifact.deltas)} proposals "
        f"(delta_ids={[p.delta_id for p in artifact.deltas]})",
        file=sys.stderr,
    )
    return assemble_portfolio(current_portfolio, artifact.deltas, events=None)


def _patch_from_portfolio_row(
    row: DeltaPortfolioRow, live_skill_root: Path
) -> SkillDeltaPatch | None:
    if row.change_type != "modify_skill":
        return None
    live_target = live_skill_root / row.target_skill
    if not live_target.exists():
        return None
    live_text = live_target.read_text(encoding="utf-8")
    return SkillDeltaPatch(
        target_path=row.target_skill,
        original_text_sha256=sha256_of_text(live_text),
        replacement_text=row.proposed_change,
    )


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
) -> dict[str, Any]:
    """Drive ONE request end-to-end through the harness chain.

    Builds a fresh inner provider via ``provider_factory`` (so threads
    do not share state — see Phase 6 test_concurrency_smoke), wraps it
    in ``RecordingProvider`` with a per-request log, runs the 3-node
    DAG, validates artifacts, and flushes evidence.

    Returns a record dict shaped for ``write_index`` (07-03 contract):
    ``{node_id, artifact, reflow_triggered, trial_selected_delta_id,
    exception}``. The ``node_id`` field carries the safe request id (one
    row per request in the index).

    Raises any exception from the chain unchanged so the caller can
    classify it via ``exception_classifier.classify(exc)`` and decide
    fail-fast vs trial-continue per D-19.
    """
    inner_provider = provider_factory()
    request_log: list[dict] = []
    proxy = RecordingProvider(inner_provider, request_log)

    request_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = request_dir / "_artifacts"
    runtime = WorkflowRuntime(provider=proxy, output_dir=artifacts_dir)

    record: dict[str, Any] = {
        "node_id": _safe_request_dirname(request_id),
        "request_id": request_id,
        "artifact": None,
        "reflow_triggered": False,
        "trial_selected_delta_id": None,
        "exception": None,
        "failure_class": "ok",
    }

    # Stamp the contextvar with a stable per-request id so any
    # generate_with_tools call that omits node_id still gets stamped.
    token = set_current_node_id(request_id)
    try:
        # Drive the canonical 3-node DAG. ``run_request`` raises on any
        # node failure; we let that propagate so the caller can run the
        # D-19 routing.
        result_paths = runtime.run_request(scenario=scenario, nodes=list(nodes))

        # Parse the factor_discovery artifact for the index row's
        # extreme-sample columns. Only the first node's artifact carries
        # the four E1-E4 columns in the current schema (see 07-03
        # machine_judges).
        factor_path = result_paths.get("factor_discovery")
        if factor_path is not None and Path(factor_path).exists():
            try:
                raw = json.loads(Path(factor_path).read_text(encoding="utf-8"))
                FactorDiscoveryArtifact.model_validate(raw)
                # Promote the FIRST factor (or empty dict) so the row's
                # extractors (covers / disposition_text / user_signal)
                # find the right keys at the top level.
                first_factor = (raw.get("factors") or [{}])[0]
                record["artifact"] = {
                    "covers_product_ids": first_factor.get("covers_product_ids", []),
                    "transferable_disposition_text": first_factor.get(
                        "transferable_disposition", ""
                    ),
                    "user_signal": first_factor.get("user_side_signal", "") or "",
                }
            except Exception:
                # Schema validation / JSON parse failure surfaces as a
                # fail-fast in run_request itself (it raises before
                # we get here); a defensive log here keeps the runner
                # informative if someone bypasses run_request later.
                traceback.print_exc(file=sys.stderr)
                raise

        # Validate the other two artifacts so VAL-04 backstop fires.
        for node_id, model in [
            ("copy_generation", CopyGenerationArtifact),
            ("personalized_copy_rubric", PersonalizedCopyRubricArtifact),
        ]:
            p = result_paths.get(node_id)
            if p is None or not Path(p).exists():
                raise RuntimeError(f"missing artifact for node {node_id} in {request_id}")
            raw = json.loads(Path(p).read_text(encoding="utf-8"))
            model.model_validate(raw)

        for index, portfolio_row in enumerate(delta_portfolio):
            patch = _patch_from_portfolio_row(portfolio_row, live_skill_root)
            if patch is None:
                continue
            trial_workspace = request_dir / "trial_workspace" / portfolio_row.delta_id
            trial_outcome = run_request_trial(
                runtime=WorkflowRuntime(
                    provider=proxy,
                    output_dir=trial_workspace / "_artifacts",
                ),
                scenario=scenario,
                nodes=list(nodes),
                live_skill_root=live_skill_root,
                workspace_dir=trial_workspace,
                patch=patch,
                request_id=request_id,
                scenario_id=str(scenario.get("scenario_id", "")),
                events=events,
            )
            if trial_outcome.trial_delta_id is not None:
                record["trial_selected_delta_id"] = trial_outcome.trial_delta_id
            delta_portfolio[index] = update_after_trial(
                portfolio_row,
                success=trial_outcome.success,
                token_cost_delta=trial_outcome.token_cost_observed,
            )

    finally:
        # Always restore the contextvar even on exception, then flush
        # whatever evidence was captured before the failure scene.
        try:
            from seers_harness.validation.recording_provider import reset_current_node_id

            reset_current_node_id(token)
        except Exception:
            pass
        # WR-02 (plan 08-10): best-effort wrap the two writer calls so a
        # cleanup failure (disk full / permission denied) does NOT mask
        # the original try-block exception (Python finally anti-pattern).
        # Each writer is caught at ``Exception`` (NOT BaseException, so
        # KeyboardInterrupt still escapes) and the cleanup exception is
        # rendered via ``safe_exc`` — never via the full-stack printer
        # which could leak ``Authorization: Bearer sk-...`` headers per
        # T-08-10-01. ``request_id`` (not the full path) carries enough
        # audit signal to root-cause via the stage_dir layout.
        #
        # Flush per-node evidence (messages.jsonl / tool_calls.jsonl /
        # artifact.json / usage.json) under request_dir/evidence/.
        evidence_dir = request_dir / "evidence"
        try:
            flush_evidence(request_log, evidence_dir)
        except Exception as cleanup_exc:
            print(
                f"[runner] flush_evidence failed for {request_id}: "
                f"{safe_exc(cleanup_exc)}",
                file=sys.stderr,
            )
        # Flush the per-request VAL-06 evolution snapshot (always —
        # an empty events list still produces an empty-shape snapshot
        # per 07-01's degradation rules; D-18 expects zero trials in
        # Stage 1 / early Stage 2 and the snapshot must still write).
        try:
            write_evolution_snapshot(events, request_dir / "evolution_snapshot.json")
        except Exception as cleanup_exc:
            print(
                f"[runner] write_evolution_snapshot failed for {request_id}: "
                f"{safe_exc(cleanup_exc)}",
                file=sys.stderr,
            )

    return record


def _run_stage(
    *,
    stage: int,
    request_ids: Sequence[str],
    scenario_loader: ScenarioLoader,
    nodes: Sequence[Any],
    provider_factory: ProviderFactory,
    out_dir: Path,
    batch_id: str,
    delta_portfolio: list[DeltaPortfolioRow],
    live_skill_root: Path,
) -> StageResult:
    """Run one stage and write index.json / batch_summary.json.

    Driven by the (n, concurrency) tuple in ``_STAGE_CONFIG``. Stage 1
    and Stage 2 run serially; Stage 3 fans out via ThreadPoolExecutor
    at concurrency=20 (one-shot per the module-docstring rationale).

    Per D-02 any non-trial exception aborts the stage immediately;
    artifacts already on disk are kept as the failure scene. Per D-19,
    ``classify(exc)``-driven routing distinguishes trial-failure (host
    request continues) from provider/infra (fail-fast).
    """
    n, concurrency = _STAGE_CONFIG[stage]
    if len(request_ids) < n:
        raise RuntimeError(
            f"stage {stage} requires {n} request_ids, got {len(request_ids)}"
        )

    stage_request_ids = list(request_ids[:n])
    stage_dir = out_dir / f"stage{stage}"
    stage_dir.mkdir(parents=True, exist_ok=True)

    started_at = _utc_now_iso()
    records: list[dict[str, Any]] = []
    failure_exc: BaseException | None = None

    print(f"[runner] stage {stage}: n={n} concurrency={concurrency}", file=sys.stderr)

    if concurrency == 1:
        # Serial path — Stage 1 (N=1) and Stage 2 (N=20).
        for i, rid in enumerate(stage_request_ids):
            print(f"[runner] stage {stage} req {i + 1}/{n}: {rid}", file=sys.stderr)
            scenario = scenario_loader(rid)
            request_dir = stage_dir / _safe_request_dirname(rid)
            # Per-request evolution events list — D-18 portfolio starts
            # empty, so most/all requests will produce an empty-events
            # snapshot. That is expected, NOT a fail-fast trigger.
            events: list[dict] = []
            try:
                record = _run_one_request(
                    request_id=rid,
                    scenario=scenario,
                    nodes=nodes,
                    provider_factory=provider_factory,
                    request_dir=request_dir,
                    events=events,
                    delta_portfolio=delta_portfolio,
                    live_skill_root=live_skill_root,
                )
                records.append(record)
            except BaseException as exc:
                # D-19 routing: trial_failure -> record + continue;
                # provider_error / infra_error -> fail-fast at request
                # level (D-02). Build a partial record for the failed
                # request so write_index can still produce a row.
                fail_record: dict[str, Any] = {
                    "node_id": _safe_request_dirname(rid),
                    "request_id": rid,
                    "artifact": None,
                    "reflow_triggered": False,
                    "trial_selected_delta_id": None,
                    "exception": safe_exc(exc),
                    "failure_class": failure_class(exc),
                }
                if is_trial_failure(exc):
                    # Trial-context failure: the trial_runner hook from
                    # 07-01 already recorded the outcome via the
                    # trial_failed event in `events`. Host request
                    # continues per D-19.
                    records.append(fail_record)
                    print(
                        f"[runner] stage {stage} req {rid}: trial_failure recorded; continuing",
                        file=sys.stderr,
                    )
                    continue
                # provider_error / infra_error -> stop the stage now.
                records.append(fail_record)
                failure_exc = exc
                print(
                    f"[runner] stage {stage} req {rid}: "
                    f"{classify(exc)} -> fail-fast",
                    file=sys.stderr,
                )
                traceback.print_exc(file=sys.stderr)
                break
    else:
        # Concurrent path — Stage 3 (concurrency=20 one-shot, see
        # module docstring for the PROD-02 rationale and D-04
        # rate-mask acknowledgement). One fresh provider per thread.
        per_request_events: dict[str, list[dict]] = {
            rid: [] for rid in stage_request_ids
        }
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            future_to_rid = {
                pool.submit(
                    _run_one_request,
                    request_id=rid,
                    scenario=scenario_loader(rid),
                    nodes=nodes,
                    provider_factory=provider_factory,
                    request_dir=stage_dir / _safe_request_dirname(rid),
                    events=per_request_events[rid],
                    delta_portfolio=delta_portfolio,
                    live_skill_root=live_skill_root,
                ): rid
                for rid in stage_request_ids
            }
            for fut in as_completed(future_to_rid):
                rid = future_to_rid[fut]
                try:
                    record = fut.result()
                    records.append(record)
                except BaseException as exc:
                    fail_record = {
                        "node_id": _safe_request_dirname(rid),
                        "request_id": rid,
                        "artifact": None,
                        "reflow_triggered": False,
                        "trial_selected_delta_id": None,
                        "exception": safe_exc(exc),
                        "failure_class": failure_class(exc),
                    }
                    if is_trial_failure(exc):
                        records.append(fail_record)
                        print(
                            f"[runner] stage {stage} req {rid}: "
                            "trial_failure recorded; continuing",
                            file=sys.stderr,
                        )
                        continue
                    records.append(fail_record)
                    failure_exc = exc
                    print(
                        f"[runner] stage {stage} req {rid}: "
                        f"{classify(exc)} -> fail-fast",
                        file=sys.stderr,
                    )
                    traceback.print_exc(file=sys.stderr)
                    # WR-01: drain in-flight futures so disk artifacts
                    # and index.json agree on which requests ran.
                    # `future.cancel()` only cancels not-yet-started
                    # futures; already-running workers continue. We
                    # cancel the not-started ones, then wait for the
                    # in-flight ones to finish (success OR failure)
                    # and collect their records. `failure_exc` is NOT
                    # overwritten — the original auth/transient/etc.
                    # cause stays the canonical fail-fast trigger;
                    # drained failures get their own row routed
                    # through plan 08-03's 7-enum failure_class.
                    remaining = [f for f in future_to_rid if not f.done()]
                    for f in remaining:
                        f.cancel()
                    for f in as_completed(remaining):
                        rid_drain = future_to_rid[f]
                        if f.cancelled():
                            # Never-started future: no _run_one_request
                            # body ran, so its `finally` block never
                            # executed, so there is no disk artifact
                            # for this request. Do not synthesise an
                            # index row for it (D-02 partial-on-disk
                            # rule: rows match disk).
                            continue
                        try:
                            record = f.result()
                            records.append(record)
                        except BaseException as drain_exc:
                            records.append(
                                {
                                    "node_id": _safe_request_dirname(rid_drain),
                                    "request_id": rid_drain,
                                    "artifact": None,
                                    "reflow_triggered": False,
                                    "trial_selected_delta_id": None,
                                    "exception": safe_exc(drain_exc),
                                    "failure_class": failure_class(drain_exc),
                                }
                            )
                    break

    finished_at = _utc_now_iso()

    # Flush index.json + batch_summary.json regardless of pass/fail
    # (D-02 partial-artifacts-on-disk rule). The writers tolerate
    # records with artifact=None / exception=str so failed rows still
    # render correctly.
    write_index(
        records=records,
        out_dir=stage_dir,
        stage=stage,
        batch_id=batch_id,
        started_at=started_at,
        finished_at=finished_at,
        n=n,
        concurrency=concurrency,
    )
    write_batch_summary(stage_dir / "index.json")

    # A stage passes only when every submitted request produced a
    # record without an exception (and the run did not abort early).
    passed = (failure_exc is None) and (len(records) == n) and all(
        r.get("exception") is None for r in records
    )

    return StageResult(
        stage=stage,
        passed=passed,
        records=records,
        stage_dir=stage_dir,
        started_at=started_at,
        finished_at=finished_at,
        exception=failure_exc,
    )


def _utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# CLI / public entry point
# ---------------------------------------------------------------------------


def run(
    *,
    stages: Sequence[int] | None = None,
    out_dir: Path | None = None,
    csv: Path | None = None,
    num_requests: int | None = None,
    request_ids: Sequence[str] | None = None,
    scenario_loader: ScenarioLoader | None = None,
    nodes_factory: NodesFactory | None = None,
    provider_factory: ProviderFactory | None = None,
) -> int:
    """Programmatic entry point. Returns a process exit code.

    Default behaviour (matches the CLI no-flag invocation): runs all
    three stages in order with NO inter-stage human checkpoint (D-07).
    Stage 1 is the only pre-flight gate (D-05): if Stage 1 fails the
    run stops; otherwise Stage 2 starts automatically; if Stage 2
    passes Stage 3 starts automatically.

    ``csv`` and ``num_requests`` are CLI overrides (``--csv``
    / ``--num-requests``). They are forwarded to the default scenario
    loader and request-id provider; tests that inject
    ``scenario_loader`` / ``request_ids`` directly bypass them.

    All keyword args are dependency-injection seams for tests; the
    defaults wire the real-DeepSeek path. The runner does NOT call
    DeepSeek when ``provider_factory`` is injected — that is the seam
    Phase 7's unit tests use to exercise the runner without burning
    tokens.
    """
    if stages is None:
        stages = (1, 2, 3)

    if out_dir is None:
        out_dir = _DEFAULT_RUNS_ROOT / _utc_timestamp_for_dir()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    batch_id = out_dir.name

    if scenario_loader is None:
        scenario_loader = _default_scenario_loader(csv=csv, num_requests=num_requests)

    if nodes_factory is None:
        nodes_factory = _default_nodes_factory()
    nodes = list(nodes_factory())

    if provider_factory is None:
        provider_factory = _default_deepseek_factory

    if request_ids is None:
        request_ids = _default_request_ids_provider(csv=csv, num_requests=num_requests)

    # Initialise the delta_portfolio EMPTY at process start (D-18).
    # Stage 1 runs without trials; after Stage 1 passes, distillation may
    # populate this list for Stage 2/3 trials.
    delta_portfolio: list[DeltaPortfolioRow] = []

    print(
        f"[runner] start batch_id={batch_id} stages={list(stages)} "
        f"n_request_ids={len(request_ids)} out_dir={out_dir}",
        file=sys.stderr,
    )

    for stage in stages:
        if stage not in _STAGE_CONFIG:
            raise ValueError(f"unknown stage {stage}; valid: 1, 2, 3")
        result = _run_stage(
            stage=stage,
            request_ids=request_ids,
            scenario_loader=scenario_loader,
            nodes=nodes,
            provider_factory=provider_factory,
            out_dir=out_dir,
            batch_id=batch_id,
            delta_portfolio=delta_portfolio,
            live_skill_root=LIVE_SKILL_ROOT,
        )
        if not result.passed:
            print(
                f"[runner] stage {stage} FAILED — stopping run "
                f"(stages remaining not started)",
                file=sys.stderr,
            )
            return 1
        print(f"[runner] stage {stage} PASSED", file=sys.stderr)
        if stage == 1:
            delta_portfolio = _distill_after_stage1(
                stage1_result=result,
                provider_factory=provider_factory,
                current_portfolio=delta_portfolio,
            )

    print("[runner] all requested stages passed", file=sys.stderr)
    return 0


def _utc_timestamp_for_dir() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main(argv: list[str] | None = None) -> int:
    """argparse entry point. Returns process exit code."""
    parser = argparse.ArgumentParser(
        prog="python -m seers_harness.validation.runner",
        description=(
            "Three-stage real-LLM validation runner (Phase 7 plan 07-04). "
            "Default invocation runs Stages 1 -> 2 -> 3 end-to-end with no "
            "inter-stage human checkpoint (D-07)."
        ),
    )
    parser.add_argument(
        "--stage",
        type=int,
        choices=[1, 2, 3],
        default=None,
        required=False,
        help=(
            "Run only the named stage (used for retries after fixing a "
            "failure). When omitted, all three stages run end-to-end."
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help=(
            "Output directory for run artifacts. Defaults to "
            "tests/smoke/.runs/<utc-timestamp>/ (git-ignored per D-09)."
        ),
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help=(
            "Override the default data_100k.csv path. The first 20 unique "
            "request_ids are used."
        ),
    )
    parser.add_argument(
        "--num-requests",
        type=int,
        default=_DEFAULT_NUM_REQUESTS,
        help=(
            f"Number of request_ids to harvest from the CSV. Defaults to "
            f"{_DEFAULT_NUM_REQUESTS}. Stage 1 only consumes the first id."
        ),
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Path to KEY=VALUE env file (no shell expansion)",
    )
    args = parser.parse_args(argv)

    if args.env_file is not None:
        count = _load_env_file(args.env_file)
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        suffix = api_key[-4:] if api_key else "<unset>"
        print(f"[runner] env-file: loaded {count} keys from {args.env_file}", file=sys.stderr)
        print(f"[runner] env-file: DEEPSEEK_API_KEY suffix=****{suffix}", file=sys.stderr)

    stages: tuple[int, ...]
    if args.stage is None:
        stages = (1, 2, 3)
    else:
        stages = (args.stage,)

    return run(
        stages=stages,
        out_dir=args.out_dir,
        csv=args.csv,
        num_requests=args.num_requests,
    )


if __name__ == "__main__":
    sys.exit(main())
