"""Minimal terminal progress for long fake or real runs (D-20, D-27, TERM-01/02).

Phase-6 contract:

- No new third-party dependency.
- ``--no-progress`` and CI mode produce plain or no output suitable for
  pipelines (writes a bare ``\\n``-terminated line — no ANSI, no carriage
  return, no spinner).
- The visible fields per update are exactly: ``completed/total``,
  ``current``, ``failures``, and ``delta_trials`` (the Phase-6 progress
  contract from 06-CONTEXT.md D-20).
- Disabled mode is a true no-op: no writes to the supplied stream.

The progress reporter is intentionally a thin function-and-state surface
rather than a "manager" service. Callers own ``ProgressState`` and mutate
it between calls.
"""

from __future__ import annotations

import os
import sys
import threading
from dataclasses import dataclass
from typing import IO, Any


_CLI_WRITE_LOCK = threading.Lock()


@dataclass
class ProgressState:
    """Mutable counters surfaced by the Phase-6 progress contract.

    Fields:
      - ``completed``: number of requests/scenarios completed so far.
      - ``total``: total number of requests/scenarios planned for the run.
      - ``current``: identifier of the request/scenario currently in flight
        (empty string when no request is currently active).
      - ``failures``: cumulative failure count across the run.
      - ``delta_trials``: cumulative count of trial-applied deltas across
        the run (Phase-6 evolution surface; safe to leave at 0 when no
        trial is wired).
    """

    completed: int = 0
    total: int = 0
    current: str = ""
    failures: int = 0
    delta_trials: int = 0


@dataclass(frozen=True)
class DashboardTask:
    request_id: str
    node: str
    detail: str = ""
    elapsed: str = ""


@dataclass(frozen=True)
class DashboardRecent:
    status: str
    request_id: str
    detail: str = ""


@dataclass
class DashboardState:
    title: str = "SEERS production run"
    subtitle: str = ""
    total: int = 0
    completed: int = 0
    running: list[DashboardTask] | None = None
    queued: int = 0
    ok: int = 0
    failed: int = 0
    trials: int = 0
    elapsed: str = "00:00"
    recent: list[DashboardRecent] | None = None


def render_progress_line(state: ProgressState) -> str:
    """Return the canonical one-line progress string.

    Format (stable across CI/non-CI; tests pin the exact shape):

        ``[<completed>/<total>] current=<current> failures=<failures> delta_trials=<delta_trials>``

    ``current`` is rendered as ``-`` when empty so the line never contains a
    bare trailing equals sign that would break log parsers.
    """

    current_disp = state.current if state.current else "-"
    return (
        f"[{state.completed}/{state.total}] "
        f"current={current_disp} "
        f"failures={state.failures} "
        f"delta_trials={state.delta_trials}"
    )


def _detect_ci_default() -> bool:
    """Return ``True`` when the environment looks like a CI runner.

    Honors the de-facto-standard ``CI`` env var. ``"true"``, ``"1"``, and
    ``"yes"`` (case-insensitive) all read as CI. Anything else (including
    unset) reads as non-CI.
    """

    val = os.environ.get("CI", "")
    return val.strip().lower() in {"true", "1", "yes"}


class ProgressReporter:
    """Plain-stdout progress writer with disabled and CI-safe modes.

    Construction options:
      - ``enabled``: when ``False``, every ``update`` call is a no-op (this is
        the ``--no-progress`` and ``disabled`` path).
      - ``stream``: file-like sink for the rendered line. Defaults to
        ``sys.stdout``. Tests pass a ``io.StringIO`` to assert exact bytes.
      - ``ci_plain``: when ``True``, the rendered line is prefixed with
        ``[progress] `` so log scrapers can pick it out unambiguously. When
        ``False``, the bare line is written. Either mode writes a single
        ``\\n``-terminated line — no carriage-return overwrites, no ANSI,
        no spinner.
      - ``ci_plain`` defaults to environment-detected CI mode so callers in
        CI inherit log-friendly output without having to pass the flag.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        stream: IO[str] | None = None,
        ci_plain: bool | None = None,
        label: str = "",
    ) -> None:
        self.enabled = enabled
        self.stream = stream if stream is not None else sys.stdout
        self.ci_plain = _detect_ci_default() if ci_plain is None else ci_plain
        self.label = label

    def update(self, state: ProgressState) -> None:
        """Write one progress line to ``self.stream`` (or no-op when disabled)."""

        if not self.enabled:
            return
        line = render_progress_line(state)
        if self.label:
            line = f"[{_clean_cli_text(self.label)}] {line}"
        if self.ci_plain:
            line = f"[progress] {line}"
        write_cli_line(self.stream, line)


class CliReporter:
    """Small structured CLI reporter for production workflow events."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        stream: IO[str] | None = None,
        ci_plain: bool | None = None,
    ) -> None:
        self.enabled = enabled
        self.stream = stream if stream is not None else sys.stdout
        self.ci_plain = _detect_ci_default() if ci_plain is None else ci_plain

    def event(self, scope: str, message: str = "", **fields: Any) -> None:
        if not self.enabled:
            return
        line = render_cli_event(scope, message, **fields)
        if self.ci_plain:
            line = f"[info] {line}"
        write_cli_line(self.stream, line)

    def progress(self, label: str, state: ProgressState) -> None:
        if not self.enabled:
            return
        ProgressReporter(
            enabled=True,
            stream=self.stream,
            ci_plain=self.ci_plain,
            label=label,
        ).update(state)


class DashboardReporter:
    """Plain-text dashboard snapshot writer with bounded running rows."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        stream: IO[str] | None = None,
        ci_plain: bool | None = None,
        max_running: int = 5,
        width: int = 96,
    ) -> None:
        self.enabled = enabled
        self.stream = stream if stream is not None else sys.stdout
        self.ci_plain = _detect_ci_default() if ci_plain is None else ci_plain
        self.max_running = max(1, max_running)
        self.width = max(72, width)

    def update(self, state: DashboardState) -> None:
        if not self.enabled:
            return
        block = render_dashboard(
            state,
            max_running=self.max_running,
            width=self.width,
        )
        if self.ci_plain:
            block = "[dashboard]\n" + block
        write_cli_block(self.stream, block)


def _clean_cli_text(value: Any) -> str:
    """Render a value as one compact, ANSI-free CLI field fragment."""

    text = str(value)
    return " ".join(_clean_cli_line_text(text).split())


def _clean_cli_line_text(value: Any) -> str:
    """Render a preformatted CLI line without terminal-control bytes."""

    text = str(value)
    return text.replace("\x1b", "?").replace("\r", " ").replace("\n", " ")


def render_cli_event(scope: str, message: str = "", **fields: Any) -> str:
    """Return a compact keyed CLI event line.

    The format is intentionally plain text so concurrent and CI runs can
    consume it without terminal state:

        ``[stage 3] done status=PASSED completed=20/20 failures=0``
    """

    parts = [f"[{_clean_cli_text(scope)}]"]
    if message:
        parts.append(_clean_cli_text(message))
    for key, value in fields.items():
        if value is None:
            continue
        key_text = _clean_cli_text(key)
        if key_text.endswith("_"):
            key_text = key_text[:-1]
        parts.append(f"{key_text}={_clean_cli_text(value)}")
    return " ".join(parts)


def render_dashboard(
    state: DashboardState,
    *,
    max_running: int = 5,
    width: int = 96,
) -> str:
    """Return a compact production-run dashboard snapshot."""

    width = max(72, width)
    inner = width - 4
    running = list(state.running or [])
    recent = list(state.recent or [])
    pct = _percent(state.completed, state.total)
    lines = [_border(width)]
    title_right = f"elapsed {state.elapsed}"
    lines.append(_row(_split_line(state.title, title_right, inner), width))
    if state.subtitle:
        lines.append(_row(_fit(state.subtitle, inner), width))
    lines.append(
        _row(
            _fit(
                "  ".join(
                    [
                        f"total {state.total}",
                        f"done {state.completed}",
                        f"running {len(running)}",
                        f"queued {state.queued}",
                        f"ok {state.ok}",
                        f"failed {state.failed}",
                        f"trials {state.trials}",
                    ]
                ),
                inner,
            ),
            width,
        )
    )
    lines.append(_row(f"progress {_progress_bar(state.completed, state.total)} {pct}%", width))
    lines.append(_divider(width))
    shown = running[: max(1, max_running)]
    lines.append(
        _row(
            f"Running ({len(running)}"
            + (f", showing {len(shown)}" if len(running) > len(shown) else "")
            + ")",
            width,
        )
    )
    if shown:
        for idx, task in enumerate(shown, start=1):
            lines.append(_row(_task_line(idx, task, inner), width))
        hidden = len(running) - len(shown)
        if hidden > 0:
            lines.append(_row(f"  +{hidden} more running", width))
    else:
        lines.append(_row("  no active requests", width))
    lines.append(_divider(width))
    lines.append(_row("Recent", width))
    if recent:
        for item in recent[:3]:
            lines.append(_row(_recent_line(item, inner), width))
    else:
        lines.append(_row("  no completions yet", width))
    lines.append(_border(width))
    return "\n".join(lines)


def _percent(done: int, total: int) -> int:
    if total <= 0:
        return 0
    return max(0, min(100, round((done / total) * 100)))


def _progress_bar(done: int, total: int, width: int = 20) -> str:
    if total <= 0:
        filled = 0
    else:
        filled = round((max(0, min(done, total)) / total) * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _border(width: int) -> str:
    return "+" + "-" * (width - 2) + "+"


def _divider(width: int) -> str:
    return "|" + "-" * (width - 2) + "|"


def _row(text: str, width: int) -> str:
    inner = width - 4
    return f"| {_fit_line(text, inner).ljust(inner)} |"


def _fit(text: Any, width: int) -> str:
    cleaned = _clean_cli_text(text)
    if len(cleaned) <= width:
        return cleaned
    if width <= 1:
        return cleaned[:width]
    return cleaned[: width - 1] + "."


def _fit_line(text: Any, width: int) -> str:
    cleaned = _clean_cli_line_text(text)
    if len(cleaned) <= width:
        return cleaned
    if width <= 1:
        return cleaned[:width]
    return cleaned[: width - 1] + "."


def _split_line(left: str, right: str, width: int) -> str:
    left = _clean_cli_text(left)
    right = _clean_cli_text(right)
    if len(left) + len(right) + 1 > width:
        return _fit(left, width)
    return left + " " * (width - len(left) - len(right)) + right


def _task_line(index: int, task: DashboardTask, width: int) -> str:
    prefix = f"  {index:02d} {_fit(task.request_id, 18).ljust(18)}"
    node = _fit(task.node, 30).ljust(30)
    elapsed = _fit(task.elapsed, 8).rjust(8) if task.elapsed else " " * 8
    detail_width = max(8, width - len(prefix) - len(node) - len(elapsed) - 3)
    detail = _fit(task.detail or "-", detail_width).ljust(detail_width)
    return f"{prefix} {node} {detail} {elapsed}"


def _recent_line(item: DashboardRecent, width: int) -> str:
    status = _fit(item.status, 6).ljust(6)
    request = _fit(item.request_id, 18).ljust(18)
    detail_width = max(8, width - len(status) - len(request) - 5)
    return f"  {status} {request} {_fit(item.detail or '-', detail_width)}"


def write_cli_line(stream: IO[str], line: str) -> None:
    """Write one complete CLI line under a process-wide thread lock."""

    with _CLI_WRITE_LOCK:
        stream.write(_clean_cli_line_text(line) + "\n")
        # Flushing is best-effort: stdout-like streams in tests (StringIO)
        # do not require it, but real terminals/CI pipelines benefit from
        # immediate visibility under long-running fake or real chains.
        flush = getattr(stream, "flush", None)
        if callable(flush):
            flush()


def write_cli_block(stream: IO[str], block: str) -> None:
    """Write a multi-line CLI snapshot under a process-wide thread lock."""

    with _CLI_WRITE_LOCK:
        clean_block = "\n".join(_clean_cli_line_text(line) for line in block.splitlines())
        stream.write(clean_block.rstrip("\n") + "\n")
        flush = getattr(stream, "flush", None)
        if callable(flush):
            flush()
