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
from dataclasses import dataclass
from typing import IO


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
    ) -> None:
        self.enabled = enabled
        self.stream = stream if stream is not None else sys.stdout
        self.ci_plain = _detect_ci_default() if ci_plain is None else ci_plain

    def update(self, state: ProgressState) -> None:
        """Write one progress line to ``self.stream`` (or no-op when disabled)."""

        if not self.enabled:
            return
        line = render_progress_line(state)
        if self.ci_plain:
            line = f"[progress] {line}"
        self.stream.write(line + "\n")
        # Flushing is best-effort: stdout-like streams in tests (StringIO)
        # do not require it, but real terminals/CI pipelines benefit from
        # immediate visibility under long-running fake or real chains.
        flush = getattr(self.stream, "flush", None)
        if callable(flush):
            flush()
