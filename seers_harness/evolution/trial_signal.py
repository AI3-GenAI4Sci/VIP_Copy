"""Runtime-observable signals for trial selection pressure."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class _BaselineRecord:
    success: bool
    total_tokens: int


class ProductionSignalWindow:
    """Rolling baseline-only outcome window used by select_trial_delta."""

    def __init__(self, max_size: int = 50) -> None:
        self._buf: deque[_BaselineRecord] = deque(maxlen=max_size)
        self._lock = Lock()

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._buf)

    def record_baseline_outcome(self, *, success: bool, total_tokens: int) -> None:
        with self._lock:
            self._buf.append(
                _BaselineRecord(success=bool(success), total_tokens=int(total_tokens))
            )

    def failure_rate(self) -> float:
        with self._lock:
            records = list(self._buf)
        if len(records) < 10:
            return 0.0
        failures = sum(1 for record in records if not record.success)
        return failures / len(records)

    def token_pressure(self, *, budget_per_request: int) -> float:
        with self._lock:
            records = list(self._buf)
        if len(records) < 5 or budget_per_request <= 0:
            return 0.0
        mean_tokens = sum(record.total_tokens for record in records) / len(records)
        return min(1.0, max(0.0, mean_tokens / budget_per_request))


def concurrency_pressure(*, inflight: int, max_concurrent: int) -> float:
    if max_concurrent <= 0:
        return 0.0
    return min(1.0, max(0.0, inflight / max_concurrent))
