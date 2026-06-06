"""Run-local manifest and resumable record ledger."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


_IGNORED_EXISTING_NAMES = {".DS_Store"}


@dataclass(frozen=True)
class RunConfig:
    """Stable runner configuration recorded beside one batch's artifacts."""

    batch_id: str
    request_ids: list[str]
    num_requests: int
    concurrency: int
    state_dir: str
    resume: bool = False
    enable_distillation: bool = True
    distill_min_trajectories: int | None = None
    trial_budget_fraction: float | None = None
    provider: dict[str, Any] = field(default_factory=dict)
    evolution_policy: dict[str, Any] = field(default_factory=dict)


class RunLedger:
    """Own the run-local files that make a batch resumable and auditable."""

    def __init__(self, batch_dir: Path | str) -> None:
        self.batch_dir = Path(batch_dir)
        self.manifest_path = self.batch_dir / "run_manifest.json"
        self.records_path = self.batch_dir / "completed_records.jsonl"

    def prepare(self, *, resume: bool) -> None:
        """Create ``batch_dir`` and guard against accidental artifact reuse."""
        if self.batch_dir.exists():
            entries = [
                item
                for item in self.batch_dir.iterdir()
                if item.name not in _IGNORED_EXISTING_NAMES
            ]
            if entries and not resume:
                raise RuntimeError(
                    f"out_dir already contains artifacts: {self.batch_dir}; "
                    "pass --resume to continue it or choose a fresh --out-dir"
                )
        self.batch_dir.mkdir(parents=True, exist_ok=True)

    def start(
        self,
        *,
        config: RunConfig,
        started_at: str,
        resumed_records: Sequence[Mapping[str, Any]],
    ) -> None:
        manifest = {
            "schema_version": "seers.run.v1",
            "batch_id": config.batch_id,
            "status": "running",
            "started_at": started_at,
            "finished_at": None,
            "resume": bool(config.resume),
            "resumed_record_count": len(resumed_records),
            "config": _json_safe(config),
            "outputs": _output_contract(),
        }
        self._write_manifest(manifest)

    def append_record(self, record: Mapping[str, Any]) -> None:
        self.records_path.parent.mkdir(parents=True, exist_ok=True)
        with self.records_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(_json_safe(record), ensure_ascii=False, sort_keys=True))
            f.write("\n")

    def write_records(self, records: Sequence[Mapping[str, Any]]) -> None:
        self.records_path.parent.mkdir(parents=True, exist_ok=True)
        with self.records_path.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(_json_safe(record), ensure_ascii=False, sort_keys=True))
                f.write("\n")

    def load_resumable_records(
        self,
        *,
        requested_slot_ids: Sequence[str],
    ) -> list[dict[str, Any]]:
        """Return the latest completed records whose production slot is done."""
        requested_order = [str(item) for item in requested_slot_ids]
        latest_by_slot: dict[str, dict[str, Any]] = {}
        for record in self._read_record_lines():
            slot_id = completed_slot_id(record, requested_slot_ids=requested_order)
            if slot_id is None:
                continue
            if record.get("exception") is not None and record.get("skipped") is not True:
                continue
            latest_by_slot[slot_id] = record
        return [latest_by_slot[slot] for slot in requested_order if slot in latest_by_slot]

    def finish(
        self,
        *,
        status: str,
        finished_at: str,
        records: Sequence[Mapping[str, Any]],
        failed_requests_path: Path,
        portfolio_path: Path | None,
        run_journal_path: Path | None,
    ) -> None:
        manifest = self._read_manifest()
        manifest.update(
            {
                "status": status,
                "finished_at": finished_at,
                "record_count": len(records),
                "failed_requests_path": str(failed_requests_path),
                "portfolio_path": None if portfolio_path is None else str(portfolio_path),
                "portfolio_journal_path": None
                if run_journal_path is None
                else str(run_journal_path),
            }
        )
        self._write_manifest(manifest)

    def _read_record_lines(self) -> list[dict[str, Any]]:
        if not self.records_path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in self.records_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                records.append(payload)
        return records

    def _read_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {}
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _write_manifest(self, manifest: Mapping[str, Any]) -> None:
        self.manifest_path.write_text(
            json.dumps(_json_safe(manifest), ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )


def completed_slot_id(
    record: Mapping[str, Any],
    *,
    requested_slot_ids: Iterable[str],
) -> str | None:
    requested = {str(item) for item in requested_slot_ids}
    original = record.get("original_request_id")
    if original is not None and str(original) in requested:
        return str(original)
    request_id = record.get("request_id")
    if request_id is not None and str(request_id) in requested:
        return str(request_id)
    return None


def _output_contract() -> dict[str, str]:
    return {
        "manifest": "run_manifest.json",
        "completed_records": "completed_records.jsonl",
        "index": "index.json",
        "summary": "batch_summary.json",
        "failures": "failed_requests.json",
        "portfolio_snapshot": "portfolio.jsonl",
        "run_journal": "portfolio_journal.jsonl",
        "offline_copy_table_csv": "offline_copy_table.csv",
        "offline_copy_table_jsonl": "offline_copy_table.jsonl",
        "request_dirs": "<safe request or trial execution id>/",
    }


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        if hasattr(value, "__dict__"):
            return _json_safe(value.__dict__)
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
