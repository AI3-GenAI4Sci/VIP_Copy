"""End-to-end smoke link for the default split DAG.

Drives 20 unique request_ids from ``data_100k.csv`` through the default
3-node DAG using a
ScriptedProvider. Verifies every artifact passes its ``extra="forbid"``
schema. Single-threaded by D-11 contract — no asyncio / concurrent.futures /
threading / multiprocessing. Stdout only — no logging / rich / tqdm.

Performance note: ``preprocess_request_from_csv`` scans the entire CSV
once per call. Calling it 20× on the full 2.3 GB ``data_100k.csv`` would
take many minutes. Instead, the smoke does ONE pass over the first
``_HEADER_SCAN_LIMIT`` rows, captures both (a) the first 20 unique
request_ids in file order and (b) the raw CSV lines belonging to those
request_ids, then writes a small scratch CSV. Each request is then
preprocessed against the scratch CSV — fast.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from seers_harness.domain.models import (
    CopyGenerationArtifact,
    PersonalizedCopyRubricArtifact,
    UserPersonalizationArtifact,
)
from seers_harness.intake.request_preprocessor import (
    detect_delimiter,
    preprocess_request_from_csv,
)

from tests.smoke.scripted_full_chain import (
    build_full_chain_script,
    make_nodes,
    make_runtime,
)


_CSV_PATH = Path(__file__).parents[2] / "data_100k.csv"
_NUM_REQUESTS = 20
_HEADER_SCAN_LIMIT = 1000


def _select_requests_and_build_scratch(
    csv_path: Path, scratch_path: Path, limit: int
) -> list[str]:
    """One-pass scan of the first ~1000 rows of ``csv_path``: pick the
    first ``limit`` unique request_ids in file order and write a scratch
    CSV (header + relevant rows only) to ``scratch_path``.

    Returns the chosen request_ids in file order.
    """
    delimiter = detect_delimiter(csv_path)
    seen: set[str] = set()
    chosen_order: list[str] = []
    captured_lines: list[str] = []

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        header_line = f.readline()
        if not header_line:
            raise RuntimeError("empty CSV")
        header = next(csv.reader([header_line], delimiter=delimiter))
        try:
            request_id_idx = header.index("request_id")
        except ValueError as exc:
            raise RuntimeError(
                f"data_100k.csv missing 'request_id' column; header={header[:5]}..."
            ) from exc

        for row_no in range(_HEADER_SCAN_LIMIT):
            line = f.readline()
            if not line:
                break
            parsed = next(csv.reader([line], delimiter=delimiter), None)
            if parsed is None or request_id_idx >= len(parsed):
                continue
            rid = parsed[request_id_idx].strip()
            if not rid:
                continue
            if rid in seen:
                # Row belongs to a request we've already chosen — keep its raw line.
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


def test_e2e_smoke_20_requests(tmp_path: Path) -> None:
    if not _CSV_PATH.exists():
        pytest.skip(
            f"data_100k.csv not present at {_CSV_PATH}; smoke skipped in this environment"
        )

    scratch_csv = tmp_path / "scratch.csv"
    request_ids = _select_requests_and_build_scratch(
        _CSV_PATH, scratch_csv, _NUM_REQUESTS
    )
    assert len(request_ids) == _NUM_REQUESTS, (
        f"expected {_NUM_REQUESTS} unique request_ids in first {_HEADER_SCAN_LIMIT}"
        f" rows, got {len(request_ids)}"
    )

    all_paths: list[Path] = []
    for i, request_id in enumerate(request_ids):
        print(f"smoke {i + 1}/{_NUM_REQUESTS}: {request_id}")

        scenario = preprocess_request_from_csv(scratch_csv, request_id=request_id)

        provider = build_full_chain_script()
        # Sanitize request_id for filesystem use (some IDs may contain ':' etc.).
        safe = request_id.replace("/", "_").replace(":", "_")
        request_output_dir = tmp_path / safe
        runtime = make_runtime(request_output_dir, provider)

        result = runtime.run_request(scenario=scenario, nodes=make_nodes())

        assert set(result.keys()) == {
            "personalized_user_mining",
            "personalized_copy_generation",
            "personalized_copy_rubric",
        }, f"unexpected node keys for {request_id}: {sorted(result.keys())}"

        # Per-node artifact existence + forbid-schema validation.
        for node_id, model in [
            ("personalized_user_mining", UserPersonalizationArtifact),
            ("personalized_copy_generation", CopyGenerationArtifact),
            ("personalized_copy_rubric", PersonalizedCopyRubricArtifact),
        ]:
            path = result[node_id]
            assert path.exists(), f"{node_id} artifact missing for {request_id}: {path}"
            text = path.read_text(encoding="utf-8")
            assert text.strip(), f"{node_id} artifact empty for {request_id}: {path}"
            raw = json.loads(text)
            # forbid-schema validation — raises ValidationError on any unknown field.
            model.model_validate(raw)
            all_paths.append(path)

    # Aggregate: 20 × 3 = 60, all unique.
    assert len(all_paths) == _NUM_REQUESTS * 3
    assert len(set(all_paths)) == len(all_paths), "artifact path collision across requests"
