"""Production batch dashboard reporting."""

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


VIP_COPY_BANNER = [
    r"__     _____ ____     ____ ___  ______   __",
    r"\ \   / /_ _|  _ \   / ___/ _ \|  _ \ \ / /",
    r" \ \ / / | || |_) | | |  | | | | |_) \ V / ",
    r"  \ V /  | ||  __/  | |__| |_| |  __/ | |  ",
    r"   \_/  |___|_|      \____\___/|_|    |_|  ",
]


class BatchDashboard:
    """Thread-safe production-run dashboard fed by request/node events."""

    def __init__(
        self,
        *,
        total: int,
        concurrency: int,
        out_dir: Path,
        stream: Any = sys.stderr,
        max_running: int = 5,
    ) -> None:
        self.total = total
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
        self._completed_trial_ids: set[str] = set()
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
                    detail = (
                        f"artifacts={fields.get('artifacts', 0)} "
                        f"{fields.get('duration', '')}".strip()
                    )
                    if _is_trial_request_id(request_id):
                        self._running.pop(request_id, None)
                    else:
                        self._complete_locked(
                            request_id,
                            ok=status == "SUCCEEDED",
                            detail=detail,
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
                detail = (
                    f"trial artifacts={1 if record.get('artifact') is not None else 0}"
                    if ok
                    else f"trial {record.get('failure_class') or 'failed'}"
                )
                if _is_direct_trial_record(record):
                    if request_id not in self._completed_ids:
                        self._trials += 1
                    self._complete_locked(request_id, ok=ok, detail=detail)
                else:
                    self._complete_trial_locked(request_id, ok=ok, detail=detail)
            else:
                detail = (
                    f"artifacts={1 if record.get('artifact') is not None else 0}"
                    if ok
                    else str(record.get("failure_class") or "failed")
                )
                self._complete_locked(request_id, ok=ok, detail=detail)
            for alias in _record_alias_ids(record):
                if alias != request_id:
                    self._running.pop(alias, None)
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

    def _complete_trial_locked(self, request_id: str, *, ok: bool, detail: str) -> None:
        if request_id in self._completed_trial_ids:
            return
        self._completed_trial_ids.add(request_id)
        self._running.pop(request_id, None)
        self._trials += 1
        status = "ok" if ok else "failed"
        self._recent.insert(0, DashboardRecent(status, request_id, detail))
        self._recent = self._recent[:3]

    def _render_locked(self) -> None:
        completed = len(self._completed_ids)
        running = list(self._running.values())
        queued = max(0, self.total - completed - len(running))
        self.reporter.update(
            DashboardState(
                banner_lines=VIP_COPY_BANNER,
                use_color=True,
                title="VIP COPY production run",
                subtitle=(
                    f"mode=production concurrency={self.concurrency} "
                    f"table=offline_copy_table out_dir={self.out_dir}"
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


def _record_alias_ids(record: dict[str, Any]) -> set[str]:
    aliases: set[str] = set()
    for key in ("request_id", "original_request_id", "node_id"):
        value = record.get(key)
        if value is not None:
            aliases.add(str(value))
    return aliases


def _is_direct_trial_record(record: dict[str, Any]) -> bool:
    request_id = record.get("request_id")
    original_request_id = record.get("original_request_id")
    return request_id is not None and str(request_id) == str(original_request_id)


def _is_trial_request_id(request_id: str) -> bool:
    return request_id.startswith("trial:")
