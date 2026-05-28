from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from seers_harness.evolution.trial_signal import (
    ProductionSignalWindow,
    concurrency_pressure,
)


def test_failure_rate_cold_start_returns_zero() -> None:
    window = ProductionSignalWindow(max_size=50)
    for _ in range(9):
        window.record_baseline_outcome(success=False, total_tokens=100)

    assert window.failure_rate() == 0.0


def test_failure_rate_steady_state() -> None:
    window = ProductionSignalWindow(max_size=50)
    for _ in range(12):
        window.record_baseline_outcome(success=False, total_tokens=100)
    for _ in range(18):
        window.record_baseline_outcome(success=True, total_tokens=100)

    assert window.failure_rate() == pytest.approx(0.4)


def test_token_pressure_clipped_to_one() -> None:
    window = ProductionSignalWindow(max_size=50)
    for _ in range(5):
        window.record_baseline_outcome(success=True, total_tokens=10_000)

    assert window.token_pressure(budget_per_request=5_000) == 1.0


def test_concurrency_pressure_handles_zero_max() -> None:
    assert concurrency_pressure(inflight=10, max_concurrent=0) == 0.0
    assert concurrency_pressure(inflight=10, max_concurrent=20) == 0.5
    assert concurrency_pressure(inflight=-5, max_concurrent=20) == 0.0
    assert concurrency_pressure(inflight=25, max_concurrent=20) == 1.0


def test_record_baseline_outcome_thread_safe() -> None:
    window = ProductionSignalWindow(max_size=50)

    def append_many() -> None:
        for _ in range(100):
            window.record_baseline_outcome(success=True, total_tokens=1)

    with ThreadPoolExecutor(max_workers=20) as pool:
        list(pool.map(lambda _: append_many(), range(20)))

    assert window.count == 50
    assert window.failure_rate() == 0.0
