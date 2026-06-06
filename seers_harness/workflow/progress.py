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
import re
import sys
import threading
import unicodedata
from dataclasses import dataclass
from typing import IO, Any


_CLI_WRITE_LOCK = threading.Lock()
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_RESET = "\x1b[0m"
_DIM = "\x1b[2m"
_BOLD = "\x1b[1m"
_CYAN = "\x1b[36m"
_BRIGHT_CYAN = "\x1b[96m"
_GREEN = "\x1b[32m"
_BRIGHT_GREEN = "\x1b[92m"
_YELLOW = "\x1b[33m"
_BRIGHT_YELLOW = "\x1b[93m"
_RED = "\x1b[31m"
_BRIGHT_RED = "\x1b[91m"
_MAGENTA = "\x1b[35m"
_BRIGHT_MAGENTA = "\x1b[95m"
_BLUE = "\x1b[34m"
_WHITE = "\x1b[97m"


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
    banner_lines: list[str] | None = None
    use_color: bool = False
    title: str = "VIP COPY production run"
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
        write_cli_block(self.stream, block, allow_ansi=state.use_color and not self.ci_plain)


def _clean_cli_text(value: Any) -> str:
    """Render a value as one compact, ANSI-free CLI field fragment."""

    text = str(value)
    return " ".join(_clean_cli_line_text(text).split())


def _clean_cli_line_text(value: Any) -> str:
    """Render a preformatted CLI line without terminal-control bytes."""

    text = str(value)
    return text.replace("\x1b", "?").replace("\r", " ").replace("\n", " ")


def render_cli_event(
    scope: str,
    message: str = "",
    *,
    styled: bool = False,
    use_color: bool = False,
    **fields: Any,
) -> str:
    """Return a compact keyed CLI event line.

    The format is intentionally plain text so concurrent and CI runs can
    consume it without terminal state:

        ``[production batch] done status=PASSED completed=15/15 failures=0``
    """

    clean_scope = _clean_cli_text(scope)
    prefix = f"[{clean_scope}]"
    if styled:
        icon = _event_icon(clean_scope, message, fields)
        prefix = f"{icon} {prefix}"
        if use_color:
            prefix = _color(prefix, _event_color(message, fields), True)
    parts = [prefix]
    if message:
        message_text = _clean_cli_text(message)
        parts.append(_color(message_text, _BOLD, use_color and styled))
    for key, value in fields.items():
        if value is None:
            continue
        key_text = _clean_cli_text(key)
        if key_text.endswith("_"):
            key_text = key_text[:-1]
        field_text = f"{key_text}={_clean_cli_text(value)}"
        parts.append(_color(field_text, _DIM, use_color and styled))
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
    use_color = bool(state.use_color)
    border = _color(_border(width), _CYAN, use_color)
    divider = _color(_divider(width), _CYAN, use_color)
    lines = [border]
    if state.banner_lines:
        banner_colors = [_BRIGHT_CYAN, _CYAN, _BRIGHT_MAGENTA, _MAGENTA, _BRIGHT_CYAN]
        for line in state.banner_lines:
            color = banner_colors[len(lines) % len(banner_colors)]
            lines.append(_row(_color(_center_line(line, inner), color, use_color), width))
        lines.append(divider)
    title_right = f"elapsed {state.elapsed}"
    title = _color(state.title, _BOLD + _BRIGHT_CYAN, use_color)
    elapsed = _color(title_right, _BRIGHT_YELLOW, use_color)
    lines.append(_row(_split_line(title, elapsed, inner), width))
    if state.subtitle:
        lines.append(_row(_color(_fit(state.subtitle, inner), _DIM, use_color), width))
    lines.append(
        _row(
            _fit_line(
                "  ".join(
                    [
                        _color(f"📦 total {state.total}", _WHITE, use_color),
                        _color(f"✅ done {state.completed}", _BRIGHT_GREEN, use_color),
                        _color(f"⚙️ running {len(running)}", _BRIGHT_CYAN, use_color),
                        _color(f"⏳ queued {state.queued}", _YELLOW, use_color),
                        _color(f"🟢 ok {state.ok}", _GREEN, use_color),
                        _color(f"🔴 failed {state.failed}", _BRIGHT_RED, use_color),
                        _color(f"🧪 trials {state.trials}", _MAGENTA, use_color),
                    ]
                ),
                inner,
            ),
            width,
        )
    )
    progress = _progress_bar(
        state.completed,
        state.total,
        width=28,
        use_color=use_color,
    )
    lines.append(_row(f"📈 progress {progress} {_color(str(pct) + '%', _BRIGHT_YELLOW, use_color)}", width))
    lines.append(divider)
    shown = running[: max(1, max_running)]
    lines.append(
        _row(
            _color(
                f"⚡ Running ({len(running)}"
            + (f", showing {len(shown)}" if len(running) > len(shown) else "")
                + ")",
                _BRIGHT_CYAN,
                use_color,
            ),
            width,
        )
    )
    if shown:
        for idx, task in enumerate(shown, start=1):
            lines.append(_row(_task_line(idx, task, inner, use_color=use_color), width))
        hidden = len(running) - len(shown)
        if hidden > 0:
            lines.append(_row(_color(f"  +{hidden} more running", _YELLOW, use_color), width))
    else:
        lines.append(_row(_color("  no active requests", _DIM, use_color), width))
    lines.append(divider)
    lines.append(_row(_color("🧾 Recent", _BRIGHT_MAGENTA, use_color), width))
    if recent:
        for item in recent[:3]:
            lines.append(_row(_recent_line(item, inner, use_color=use_color), width))
    else:
        lines.append(_row(_color("  no completions yet", _DIM, use_color), width))
    lines.append(border)
    return "\n".join(lines)


def _percent(done: int, total: int) -> int:
    if total <= 0:
        return 0
    return max(0, min(100, round((done / total) * 100)))


def _progress_bar(
    done: int,
    total: int,
    width: int = 20,
    *,
    use_color: bool = False,
) -> str:
    if total <= 0:
        filled = 0
    else:
        filled = round((max(0, min(done, total)) / total) * width)
    filled_text = "█" * filled
    empty_text = "░" * (width - filled)
    if use_color:
        filled_text = _color(filled_text, _BRIGHT_GREEN, True)
        empty_text = _color(empty_text, _DIM, True)
    return "[" + filled_text + empty_text + "]"


def _border(width: int) -> str:
    return "+" + "-" * (width - 2) + "+"


def _divider(width: int) -> str:
    return "|" + "-" * (width - 2) + "|"


def _row(text: str, width: int) -> str:
    inner = width - 4
    clipped = _fit_line(text, inner)
    pad = max(0, inner - _display_width(clipped))
    return f"| {clipped}{' ' * pad} |"


def _fit(text: Any, width: int) -> str:
    cleaned = _clean_cli_text(text)
    if _display_width(cleaned) <= width:
        return cleaned
    if width <= 1:
        return cleaned[:width]
    return _truncate_visible(cleaned, width - 1) + "."


def _fit_line(text: Any, width: int) -> str:
    cleaned = _clean_cli_line_text_allow_ansi(text)
    if _display_width(cleaned) <= width:
        return cleaned
    if width <= 1:
        return _truncate_visible(cleaned, width)
    return _truncate_visible(cleaned, width - 1) + "."


def _center_line(text: Any, width: int) -> str:
    fitted = _fit_line(text, width)
    pad = max(0, width - _display_width(fitted))
    left = pad // 2
    right = pad - left
    return " " * left + fitted + " " * right


def _split_line(left: str, right: str, width: int) -> str:
    left = _clean_cli_line_text_allow_ansi(left)
    right = _clean_cli_line_text_allow_ansi(right)
    if _display_width(left) + _display_width(right) + 1 > width:
        return _fit(left, width)
    return left + " " * (width - _display_width(left) - _display_width(right)) + right


def _task_line(index: int, task: DashboardTask, width: int, *, use_color: bool = False) -> str:
    request_id = _pad_visible(_fit(task.request_id, 18), 18)
    prefix = f"  {_color(f'{index:02d}', _BRIGHT_YELLOW, use_color)} {request_id}"
    node = _color(_pad_visible(_fit(task.node, 30), 30), _BRIGHT_CYAN, use_color)
    elapsed = _pad_visible(_fit(task.elapsed, 8), 8, align="right") if task.elapsed else " " * 8
    elapsed = _color(elapsed, _YELLOW, use_color)
    detail_width = max(
        8,
        width
        - _display_width(prefix)
        - _display_width(node)
        - _display_width(elapsed)
        - 3,
    )
    detail = _pad_visible(_fit(task.detail or "-", detail_width), detail_width)
    return f"{prefix} {node} {detail} {elapsed}"


def _recent_line(item: DashboardRecent, width: int, *, use_color: bool = False) -> str:
    icon = "✅" if item.status == "ok" else "⚠️"
    color = _BRIGHT_GREEN if item.status == "ok" else _BRIGHT_RED
    status = _color(_pad_visible(_fit(item.status, 6), 6), color, use_color)
    request = _pad_visible(_fit(item.request_id, 18), 18)
    detail_width = max(8, width - _display_width(status) - _display_width(request) - 8)
    return f"  {icon} {status} {request} {_fit(item.detail or '-', detail_width)}"


def write_cli_line(stream: IO[str], line: str, *, allow_ansi: bool = False) -> None:
    """Write one complete CLI line under a process-wide thread lock."""

    with _CLI_WRITE_LOCK:
        cleaner = _clean_cli_line_text_allow_ansi if allow_ansi else _clean_cli_line_text
        stream.write(cleaner(line) + "\n")
        # Flushing is best-effort: stdout-like streams in tests (StringIO)
        # do not require it, but real terminals/CI pipelines benefit from
        # immediate visibility under long-running fake or real chains.
        flush = getattr(stream, "flush", None)
        if callable(flush):
            flush()


def write_cli_block(stream: IO[str], block: str, *, allow_ansi: bool = False) -> None:
    """Write a multi-line CLI snapshot under a process-wide thread lock."""

    with _CLI_WRITE_LOCK:
        cleaner = _clean_cli_line_text_allow_ansi if allow_ansi else _clean_cli_line_text
        clean_block = "\n".join(cleaner(line) for line in block.splitlines())
        stream.write(clean_block.rstrip("\n") + "\n")
        flush = getattr(stream, "flush", None)
        if callable(flush):
            flush()


def _clean_cli_line_text_allow_ansi(value: Any) -> str:
    text = str(value)
    return text.replace("\r", " ").replace("\n", " ")


def _color(text: str, code: str, enabled: bool) -> str:
    if not enabled or not text:
        return text
    return f"{code}{text}{_RESET}"


def _event_icon(scope: str, message: str, fields: dict[str, Any]) -> str:
    status = str(fields.get("status") or "").upper()
    if status == "PASSED" or message in {"done", "stage_passed"}:
        return "✅"
    if status == "FAILED" or "fail" in message.lower() or "error" in message.lower():
        return "⚠️"
    if "runner" in scope and message == "start":
        return "🚀"
    if "env" in message:
        return "🔑"
    if "promotion" in message:
        return "🧬"
    return "ℹ️"


def _event_color(message: str, fields: dict[str, Any]) -> str:
    status = str(fields.get("status") or "").upper()
    lowered = message.lower()
    if status == "PASSED" or message == "done":
        return _BRIGHT_GREEN
    if status == "FAILED" or "fail" in lowered or "error" in lowered:
        return _BRIGHT_RED
    if "promotion" in lowered:
        return _BRIGHT_MAGENTA
    if "start" in lowered:
        return _BRIGHT_CYAN
    return _BRIGHT_YELLOW


def _display_width(text: Any) -> int:
    stripped = _ANSI_RE.sub("", str(text))
    width = 0
    for char in stripped:
        if unicodedata.combining(char):
            continue
        if unicodedata.category(char) in {"Mn", "Me", "Cf"}:
            continue
        width += 2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
    return width


def _truncate_visible(text: str, width: int) -> str:
    if width <= 0:
        return ""
    out: list[str] = []
    visible = 0
    index = 0
    while index < len(text):
        match = _ANSI_RE.match(text, index)
        if match:
            out.append(match.group(0))
            index = match.end()
            continue
        char = text[index]
        char_width = _display_width(char)
        if visible + char_width > width:
            break
        out.append(char)
        visible += char_width
        index += 1
    if _ANSI_RE.search("".join(out)) and not "".join(out).endswith(_RESET):
        out.append(_RESET)
    return "".join(out)


def _pad_visible(text: str, width: int, *, align: str = "left") -> str:
    pad = max(0, width - _display_width(text))
    if align == "right":
        return " " * pad + text
    return text + " " * pad
