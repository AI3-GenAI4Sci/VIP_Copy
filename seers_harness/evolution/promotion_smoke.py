"""Phase 6 plan 06-05 — promotion public-entry smoke (dry-run only).

This module proves the workspace can import, build, and write a dry-run
promotion-smoke report against current-schema artifacts without touching
live skill files, without touching ``../harness-runtime/``, and without
ever recording a winning-delta registry, live promotion record, or
release artifact.

The public entry point is :func:`build_promotion_smoke_report`. It reads
the names and SHA-256 hashes of every ``SKILL.md`` under a caller-supplied
``skills_root``, optionally reads a portfolio JSONL artifact if its path
exists, writes a JSON dry-run report to ``output_path``, and returns the
report as a dict.

Phase 6 boundary (D-22 / D-24): the report explicitly sets
``live_skill_writes_enabled`` and ``runtime_touched`` to ``False``. Any
future plan that promotes deltas into live skills must change those
fields, and must do so behind a review/approval/rollback gate. This file
is **not** that gate; it is a public-entry smoke proving the current
schema imports cleanly and writes a dry-run artifact.

Forbid list:

* Does not write to ``workflow-skills/current/``.
* Does not read or write any path under ``../harness-runtime/``.
* Does not write a winning-delta registry, live promotion record, or
  release artifact.
* Does not import any module from ``harness-runtime``.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from seers_harness.evolution.delta_portfolio import load_portfolio_jsonl


SCHEMA_VERSION = "promotion-smoke.v1"
"""Schema marker for the dry-run report.

A future plan that promotes deltas must bump this and document the
migration. Tests pin the literal so silent schema drift surfaces.
"""

_DRY_RUN_DECISION = "dry_run_only"
"""The only decision Phase 6 ever writes.

A future plan that introduces real promotion must add new decisions
(``promoted`` / ``rejected`` / ``held_for_review``) and a review gate.
"""


def _sha256_of(path: Path) -> str:
    """Return the SHA-256 hex digest of ``path``'s bytes."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _collect_skill_files(skills_root: Path) -> list[dict[str, Any]]:
    """Return one record per ``SKILL.md`` found under ``skills_root``.

    Records are sorted by relative path so the report is deterministic.
    Each record carries the path (relative to ``skills_root``), the
    SHA-256 of the file's bytes, and the size in bytes. The function
    does not read or recurse into ``../harness-runtime/``: it walks
    only the caller-supplied root.
    """
    if not skills_root.exists() or not skills_root.is_dir():
        return []

    records: list[dict[str, Any]] = []
    for skill_md in sorted(skills_root.rglob("SKILL.md")):
        rel = skill_md.relative_to(skills_root).as_posix()
        records.append(
            {
                "path": rel,
                "sha256": _sha256_of(skill_md),
                "size_bytes": skill_md.stat().st_size,
            }
        )
    return records


def build_promotion_smoke_report(
    *,
    skills_root: Path | str,
    portfolio_path: Path | str | None,
    output_path: Path | str,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Build and write a dry-run promotion-smoke report.

    Parameters:
        skills_root: directory whose ``SKILL.md`` files the smoke audits.
            Typically the workspace ``workflow-skills/current`` tree, but
            tests pass a ``tmp_path`` copy so the live root stays unread
            and unwritten.
        portfolio_path: optional path to a ``DeltaPortfolioRow`` JSONL
            artifact. ``None`` (or a non-existent path) counts as zero
            portfolio rows — a fresh portfolio is the natural starting
            state and the smoke must still produce a valid report.
        output_path: where the JSON report is written. Parent directories
            are created. The caller owns this path; the smoke never
            writes anywhere else.
        run_id: optional stable identifier. ``None`` derives a
            ``dryrun-<unix_seconds>`` token so two consecutive calls
            without a caller-supplied id still produce distinct reports.

    Returns:
        The report as a dict. Always includes:

        * ``schema_version``: the literal :data:`SCHEMA_VERSION`.
        * ``run_id``: caller-supplied or auto-derived.
        * ``skill_files``: deterministic list of skill records.
        * ``portfolio_count``: count of portfolio rows (``0`` when no
          portfolio path or the file is missing).
        * ``live_skill_writes_enabled``: ``False`` (Phase 6 D-22).
        * ``runtime_touched``: ``False`` (Phase 6 D-23 / D-24).
        * ``decision``: :data:`_DRY_RUN_DECISION`.

    Side effects:
        Writes the JSON report to ``output_path``. Reads only files under
        ``skills_root`` plus the optional ``portfolio_path``. Never
        writes under ``skills_root``. Never reads or writes any path
        under ``../harness-runtime/``.
    """
    skills_root_p = Path(skills_root)
    output_path_p = Path(output_path)

    run_id_value = run_id if run_id is not None else f"dryrun-{int(time.time())}"

    skill_files = _collect_skill_files(skills_root_p)

    portfolio_count = 0
    if portfolio_path is not None:
        pp = Path(portfolio_path)
        if pp.exists():
            portfolio_count = len(load_portfolio_jsonl(pp))

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id_value,
        "skill_files": skill_files,
        "portfolio_count": portfolio_count,
        "live_skill_writes_enabled": False,
        "runtime_touched": False,
        "decision": _DRY_RUN_DECISION,
    }

    output_path_p.parent.mkdir(parents=True, exist_ok=True)
    output_path_p.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
