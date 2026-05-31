"""Harness-concurrency safety smoke (Phase 6 plan 06-03).

Twenty `DelayedScriptedProvider` request runs execute concurrently through
the 3-node DAG. The test asserts artifact paths, tool-loop state,
provider message snapshots, runtime records, and trajectory records do
not cross-contaminate across simultaneously running requests.

Single-threaded production usage is the documented Phase 5 baseline
(`tests/smoke/test_e2e_smoke.py`). This smoke proves the *harness* — the
runtime, provider, payload builders, tool-loop, and trajectory helpers —
holds no concealed shared mutable state when callers choose to run
multiple requests in their own threads with fresh per-request runtime
and provider instances. Each request gets its own
``DelayedScriptedProvider``, its own ``WorkflowRuntime``, and a unique
output directory; no provider instance is shared across threads
(plan 06-03 forbid list).

Phase 6 D-18 / D-21 scope boundary
==================================

Scope (D-18): fake-provider concurrency safety verification with
synthetic per-call latency. The test proves harness modules — runtime,
provider, payload builders, tool-loop, trajectory helpers — hold no
hidden cross-request mutable state.

Out of scope (D-19, D-21):

  * Real DeepSeek concurrency capacity, headroom, or rate-limit
    behavior. This is not DeepSeek production concurrency tuning. The
    result MUST NOT be cited as evidence about real provider
    concurrency limits.
  * Adding a provider limiter, circuit breaker, retry manager, or
    scheduling machinery on the basis of a fake-provider result.
    D-19 forbids that move; the negative phrasing here exists so the
    intent is unambiguous on review.
  * Modeling DeepSeek production latency. The configurable per-call
    sleep in ``DelayedScriptedProvider`` is synthetic latency only —
    enough to interleave threads, not a latency benchmark.

D-21 keeps real-provider work as fact recording only; this test does
not perform any real-provider work and does not propose any.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from seers_harness.domain.models import (
    PersonalizedCopyGenerationArtifact,
    PersonalizedCopyRubricArtifact,
    UserPersonalizationArtifact,
)
from seers_harness.evolution.delta_portfolio import (
    TrajectoryRecord,
    buffer_trajectory,
)
from seers_harness.workflow.dag_runner import WorkflowRuntime

from tests.smoke.scripted_full_chain import (
    build_full_chain_script,
    make_nodes,
)
from tests.fakes.scripted_provider import DelayedScriptedProvider


_NUM_REQUESTS = 20
_PER_CALL_DELAY_SECONDS = 0.005


def _scenario_for(request_id: str) -> dict[str, Any]:
    """Compact in-memory scenario keyed by ``request_id``.

    Mirrors the shape produced by ``preprocess_request_from_csv`` but
    uses synthetic minimal content so the smoke does not depend on
    ``data_100k.csv`` (not present in every working tree). The user_state
    behavior keys are deliberately empty — merged generation's
    user-history leak check projects tokens from user_state.behavior,
    and empty values keep the leak set empty so the canonical scripted
    candidate text accepts cleanly for every synthetic scenario.
    """
    product_id = f"P-{request_id}"
    return {
        "scenario_id": request_id,
        "request_id": request_id,
        "minimum_semantic_unit": "request/list_group",
        "user_state": {"behavior": {}},
        "products": [
            {
                "product_id": product_id,
                "attributes": {},
            }
        ],
        "target_products": [
            {
                "product_id": product_id,
                "attributes": {},
            }
        ],
        "target_product_count": 1,
        "derived_features_by_product": {product_id: {}},
        "list_context": {},
    }


@dataclass
class _RequestResult:
    request_id: str
    artifact_paths: dict[str, Path]
    provider: DelayedScriptedProvider
    runtime: WorkflowRuntime
    trajectory: TrajectoryRecord


def _run_one_request(request_id: str, tmp_path: Path) -> _RequestResult:
    """Drive one request end-to-end with fresh provider + runtime.

    Each thread builds its own ``DelayedScriptedProvider`` (no shared
    state with sibling threads), its own ``WorkflowRuntime``, and its
    own output directory under ``tmp_path``. A ``TrajectoryRecord`` is
    constructed from the per-request artifact paths so the caller can
    assert trajectory records do not reference any other request's ids.
    """
    scenario = _scenario_for(request_id)
    provider = build_full_chain_script()
    # Replace with the delayed variant while preserving the scripted turns,
    # received_messages capture, and indexing of the base provider.
    delayed = DelayedScriptedProvider(
        script=provider.script,
        delay_seconds=_PER_CALL_DELAY_SECONDS,
    )

    output_dir = tmp_path / f"req-{request_id}"
    runtime = WorkflowRuntime(provider=delayed, output_dir=output_dir)
    artifact_paths = runtime.run_request(scenario=scenario, nodes=make_nodes())

    trajectory = TrajectoryRecord(
        request_id=request_id,
        scenario_id=request_id,
        artifact_paths={k: str(v) for k, v in artifact_paths.items()},
        tool_call_count=sum(
            int(ev.get("tool_calls_made") or 0)
            for ev in runtime.trace
            if ev.get("type") == "tool_loop_summary"
        ),
        success=True,
        quality_bucket="smoke",
        token_cost_bucket="smoke",
    )

    return _RequestResult(
        request_id=request_id,
        artifact_paths=artifact_paths,
        provider=delayed,
        runtime=runtime,
        trajectory=trajectory,
    )


def test_concurrent_fake_provider_requests_do_not_cross_contaminate(
    tmp_path: Path,
) -> None:
    request_ids = [f"R-{i:02d}" for i in range(_NUM_REQUESTS)]

    results: dict[str, _RequestResult] = {}
    with ThreadPoolExecutor(max_workers=_NUM_REQUESTS) as pool:
        futures = {
            pool.submit(_run_one_request, rid, tmp_path): rid for rid in request_ids
        }
        for fut in as_completed(futures):
            rid = futures[fut]
            results[rid] = fut.result()

    assert len(results) == _NUM_REQUESTS, (
        f"expected {_NUM_REQUESTS} completed requests, got {len(results)}"
    )

    # ---- Artifact-count + uniqueness ---------------------------------- #
    all_paths: list[Path] = []
    for rid in request_ids:
        res = results[rid]
        assert set(res.artifact_paths.keys()) == {
            "personalized_user_mining",
            "personalized_copy_generation",
            "personalized_copy_rubric",
        }, f"unexpected node keys for {rid}: {sorted(res.artifact_paths.keys())}"
        for node_id, model in [
            ("personalized_user_mining", UserPersonalizationArtifact),
            ("personalized_copy_generation", PersonalizedCopyGenerationArtifact),
            ("personalized_copy_rubric", PersonalizedCopyRubricArtifact),
        ]:
            path = res.artifact_paths[node_id]
            assert path.exists(), f"{node_id} artifact missing for {rid}: {path}"
            raw = json.loads(path.read_text(encoding="utf-8"))
            model.model_validate(raw)
            all_paths.append(path)

    assert len(all_paths) == _NUM_REQUESTS * 3
    assert len(set(all_paths)) == _NUM_REQUESTS * 3, (
        "artifact path collision across concurrent requests"
    )

    # ---- Cross-request contamination ---------------------------------- #
    # Two-digit zero-padded ids ("R-00".."R-19") avoid the substring
    # ambiguity that would arise with non-padded ids ("R-1" inside
    # "R-10"). Each request's provider messages / runtime records /
    # runtime trace / trajectory must reference only its own id.
    request_id_set = set(request_ids)
    for rid in request_ids:
        res = results[rid]
        provider_blob = json.dumps(res.provider.received_messages, ensure_ascii=False)
        records_blob = json.dumps(res.runtime.records, ensure_ascii=False, default=str)
        trace_blob = json.dumps(res.runtime.trace, ensure_ascii=False, default=str)
        trajectory_blob = res.trajectory.model_dump_json()

        for other in request_id_set - {rid}:
            assert other not in provider_blob, (
                f"provider snapshot for {rid} contains foreign request id {other}"
            )
            assert other not in records_blob, (
                f"runtime records for {rid} contain foreign request id {other}"
            )
            assert other not in trace_blob, (
                f"runtime trace for {rid} contains foreign request id {other}"
            )
            assert other not in trajectory_blob, (
                f"trajectory record for {rid} contains foreign request id {other}"
            )

    # ---- session_id uniqueness across requests ------------------------ #
    # WorkflowRuntime stamps `{node.id}:attempt-{n}:{uuid hex}` per node
    # attempt. The uuid hex must come out unique across all 60 node
    # invocations regardless of thread interleaving, and the same
    # session_id must NOT appear in two different requests' records.
    session_id_to_request: dict[str, str] = {}
    for rid in request_ids:
        res = results[rid]
        for record in res.runtime.records:
            sid = record.get("session_id")
            assert sid, f"runtime record missing session_id for {rid}: {record}"
            prior_owner = session_id_to_request.get(sid)
            if prior_owner is not None and prior_owner != rid:
                raise AssertionError(
                    f"session_id {sid!r} appears in both {prior_owner!r} and {rid!r}"
                )
            session_id_to_request[sid] = rid

    # ---- Artifact filename owner-path check --------------------------- #
    # Per-request output dir is ``tmp_path / f"req-{request_id}"``. Every
    # artifact path must contain that owner segment exactly once and must
    # not reference any sibling request's directory.
    for rid in request_ids:
        res = results[rid]
        owner_segment = f"req-{rid}"
        for node_id, path in res.artifact_paths.items():
            assert owner_segment in path.parts, (
                f"{rid} {node_id} artifact path missing owner segment "
                f"{owner_segment!r}: {path}"
            )
            for other in request_id_set - {rid}:
                assert f"req-{other}" not in str(path), (
                    f"{rid} {node_id} artifact path leaks foreign owner "
                    f"req-{other}: {path}"
                )

    # ---- Trajectory buffer composition -------------------------------- #
    # Fold every per-request trajectory into a shared buffer using the
    # 06-02 helper and assert each row references exactly one request id.
    buffer: list[TrajectoryRecord] = []
    for rid in request_ids:
        buffer = buffer_trajectory(buffer, results[rid].trajectory)
    assert len(buffer) == _NUM_REQUESTS
    for row in buffer:
        owners = [rid for rid in request_ids if rid == row.request_id]
        assert len(owners) == 1, (
            f"trajectory buffer row owns more than one request id: {row}"
        )
        # The row's artifact_paths values are stringified Path objects.
        # Any foreign owner segment in those strings is contamination.
        joined_paths = "|".join(row.artifact_paths.values())
        for other in request_id_set - {row.request_id}:
            assert f"req-{other}" not in joined_paths, (
                f"trajectory for {row.request_id} carries foreign path req-{other}"
            )
