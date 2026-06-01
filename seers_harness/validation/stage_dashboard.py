"""Validation stage dashboard reporting."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Any

from seers_harness.validation._secrets import safe_exc
from seers_harness.validation.exception_classifier import classify
from seers_harness.workflow.progress import (
    DashboardRecent,
    DashboardReporter,
    DashboardState,
    DashboardTask,
)


class BatchDashboard:
    """Thread-safe production-run dashboard fed by request/node events."""

    def __init__(
        self,
        *,
        total: int,
        validation_stage: int,
        concurrency: int,
        out_dir: Path,
        stream: Any = sys.stderr,
        max_running: int = 5,
    ) -> None:
        self.total = total
        self.validation_stage = validation_stage
        self.concurrency = concurrency
        self.out_dir = out_dir
        self.reporter = DashboardReporter(
            enabled=True,
            stream=stream,
            ci_plain=False,
            max_running=max_running,
            width=96,
        )
        self.started = time.monotonic()
        self._lock = threading.Lock()
        self._running: dict[str, DashboardTask] = {}
        self._completed_ids: set[str] = set()
        self._ok = 0
        self._failed = 0
        self._trials = 0
        self._recent: list[DashboardRecent] = []

    def start(self) -> None:
        with self._lock:
            self._render_locked()

    def event(self, scope: str, message: str = "", **fields: Any) -> None:
        request_id = str(fields.get("request_id") or _request_id_from_scope(scope))
        if not request_id:
            return
        with self._lock:
            if scope.startswith("request "):
                if message == "start":
                    self._running.setdefault(
                        request_id,
                        DashboardTask(request_id, "workflow", "starting", "00.0s"),
                    )
                elif message == "done":
                    status = str(fields.get("status") or "")
                    self._complete_locked(
                        request_id,
                        ok=status == "SUCCEEDED",
                        detail=(
                            f"artifacts={fields.get('artifacts', 0)} "
                            f"{fields.get('duration', '')}".strip()
                        ),
                    )
            elif scope.startswith("node "):
                node = scope.removeprefix("node ")
                if message == "start":
                    self._running[request_id] = DashboardTask(
                        request_id=request_id,
                        node=node,
                        detail=f"{fields.get('skill', '-')} {fields.get('attempt', '-')}",
                        elapsed="...",
                    )
                elif message == "done":
                    self._running[request_id] = DashboardTask(
                        request_id=request_id,
                        node=node,
                        detail=(
                            f"turn={fields.get('turns', '-')} "
                            f"tools={fields.get('tool_calls', '-')} "
                            f"tokens={fields.get('tokens', '-')}"
                        ),
                        elapsed=str(fields.get("duration") or ""),
                    )
                elif message == "error":
                    self._running[request_id] = DashboardTask(
                        request_id=request_id,
                        node=node,
                        detail=(
                            f"{fields.get('category', 'error')} "
                            f"retryable={fields.get('retryable', '-')}"
                        ),
                        elapsed=str(fields.get("duration") or ""),
                    )
            self._render_locked()

    def complete_request(self, request_id: str, record: dict[str, Any]) -> None:
        with self._lock:
            ok = record.get("exception") is None
            if record.get("trial_selected_delta_id"):
                self._trials += 1
            detail = (
                f"artifacts={1 if record.get('artifact') is not None else 0}"
                if ok
                else str(record.get("failure_class") or "failed")
            )
            self._complete_locked(request_id, ok=ok, detail=detail)
            self._render_locked()

    def fail_request(self, request_id: str, exc: BaseException) -> None:
        with self._lock:
            self._complete_locked(
                request_id,
                ok=False,
                detail=f"{classify(exc)} {safe_exc(exc)}",
            )
            self._render_locked()

    def finish(self) -> None:
        with self._lock:
            self._render_locked()

    def _complete_locked(self, request_id: str, *, ok: bool, detail: str) -> None:
        if request_id in self._completed_ids:
            return
        self._completed_ids.add(request_id)
        self._running.pop(request_id, None)
        if ok:
            self._ok += 1
            status = "ok"
        else:
            self._failed += 1
            status = "failed"
        self._recent.insert(0, DashboardRecent(status, request_id, detail))
        self._recent = self._recent[:3]

    def _render_locked(self) -> None:
        completed = len(self._completed_ids)
        running = list(self._running.values())
        queued = max(0, self.total - completed - len(running))
        self.reporter.update(
            DashboardState(
                title="SEERS production run",
                subtitle=(
                    f"validation_stage={self.validation_stage} "
                    f"concurrency={self.concurrency} out_dir={self.out_dir}"
                ),
                total=self.total,
                completed=completed,
                running=running,
                queued=queued,
                ok=self._ok,
                failed=self._failed,
                trials=self._trials,
                elapsed=format_elapsed(time.monotonic() - self.started),
                recent=list(self._recent),
            )
        )


def format_elapsed(seconds: float) -> str:
    seconds_i = max(0, int(seconds))
    minutes, sec = divmod(seconds_i, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{sec:02d}"
    return f"{minutes:02d}:{sec:02d}"


def _request_id_from_scope(scope: str) -> str:
    if scope.startswith("request "):
        return scope.removeprefix("request ")
    return ""
