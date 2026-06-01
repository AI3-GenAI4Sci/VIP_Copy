"""Default validation scenario loading from raw request CSVs."""

from __future__ import annotations

import csv as _csv
import tempfile
from pathlib import Path
from typing import Any, Callable

from seers_harness.intake.request_preprocessor import (
    detect_delimiter,
    preprocess_request_from_csv,
)


ScenarioLoader = Callable[[str], dict[str, Any]]


DEFAULT_NUM_REQUESTS = 20


def default_scenario_loader(
    csv: Path | None = None,
    num_requests: int | None = None,
) -> ScenarioLoader:
    """Return a loader over a scratch CSV of the first unique request ids."""
    csv_path = resolve_csv_path(csv)
    if not csv_path.exists():
        raise RuntimeError(
            f"data_100k.csv not present at {csv_path}; supply --csv or "
            "inject a scenario_loader for tests"
        )

    limit = num_requests if num_requests is not None else DEFAULT_NUM_REQUESTS
    scratch_csv = _scratch_csv_path("seers-runner-")
    build_scratch_csv(csv_path, scratch_csv, limit)

    def loader(request_id: str) -> dict[str, Any]:
        return preprocess_request_from_csv(scratch_csv, request_id=request_id)

    return loader


def default_request_ids(
    csv: Path | None = None,
    num_requests: int | None = None,
) -> list[str]:
    """Return the first ``num_requests`` unique request ids from a CSV."""
    csv_path = resolve_csv_path(csv)
    if not csv_path.exists():
        raise RuntimeError(
            f"data_100k.csv not present at {csv_path}; pass request_ids explicitly"
        )
    limit = num_requests if num_requests is not None else DEFAULT_NUM_REQUESTS
    scratch_csv = _scratch_csv_path("seers-runner-ids-")
    return build_scratch_csv(csv_path, scratch_csv, limit)


def resolve_csv_path(csv: Path | None = None) -> Path:
    if csv is not None:
        return Path(csv).resolve()
    return Path(__file__).resolve().parents[2] / "data_100k.csv"


def build_scratch_csv(csv_path: Path, scratch_path: Path, limit: int) -> list[str]:
    """Capture all rows for the first ``limit`` unique request ids."""
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


def _scratch_csv_path(prefix: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix)) / "scratch.csv"
