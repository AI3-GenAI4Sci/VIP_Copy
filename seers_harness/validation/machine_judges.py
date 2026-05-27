"""Machine judges + column extractors — Phase 7 plan 07-03 (D-12, D-16, D-22d).

This module is the pure-function layer that the index writer
(``index_writer.py``) calls once per request to produce the per-row
machine-judged booleans for VAL-01 / VAL-02 / VAL-04 and the four
sortable columns required by CONTEXT D-16.

E-dimension → column mapping (verbatim contract):

    E1 ↔ len_covers_product_ids                                       (sort desc — longest)
    E2 ↔ len_transferable_disposition_text                            (sort asc  — shortest)
    E3 ↔ len_transferable_disposition_text                            (sort desc — longest)
         — SAME column as E2, opposite sort direction (D-16)
    E4 ↔ literal_overlap_user_signal_vs_transferable_disposition     (sort desc — highest)

The raw-text passthrough column ``transferable_disposition_text`` is a
fidelity field so the human auditor can read the disposition text after
navigating by E2 or E3. It is NOT an E-dimension — E2 and E3 share the
single ``len_transferable_disposition_text`` integer column at opposite
sort directions; the raw text rides along for inspection only.

VAL-03 is intentionally absent from this module — D-13 / D-14 require
manual case-reading confirmed by the user, so the index writer emits
``VAL-03_pass = null`` and the batch_summary writer routes such rows
into ``manual_review_queue``.

Per D-22(d) this file is part of the *writer layer* and MUST NOT
import / instrument the capture layer (recording_provider /
evidence_writer). All functions are pure: they read a parsed artifact
dict (already on disk via ``flush_evidence`` in plan 07-02) and return
either a ``(bool, str)`` verdict or a primitive numeric / string column
value.

Per D-12 every judge tolerates an artifact of ``None`` by returning
``(False, "no artifact")`` so the index writer can still produce a
fully populated row even when reflow fired before the artifact landed
on disk.
"""

from __future__ import annotations

import json
import statistics
from itertools import combinations
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# VAL judges (VAL-01 / VAL-02 / VAL-04)
# ---------------------------------------------------------------------------


def judge_val01(artifact: dict[str, Any] | None) -> tuple[bool, str]:
    """VAL-01: structural shape — required keys present in the artifact.

    Required keys: ``covers_product_ids``, ``transferable_disposition_text``,
    ``user_signal``. Missing key → False with the missing key in the
    reason (one-line, machine-friendly).

    A ``None`` artifact returns ``(False, "no artifact")`` so the index
    writer can still emit a row for the failed request (D-12 reflow flow
    requires every submitted request to have a row regardless of whether
    the artifact landed on disk).
    """
    if artifact is None:
        return False, "no artifact"
    if not isinstance(artifact, dict):
        return False, "artifact is not a dict"
    for key in ("covers_product_ids", "transferable_disposition_text", "user_signal"):
        if key not in artifact:
            return False, f"missing {key}"
    return True, "ok"


def judge_val02(artifact: dict[str, Any] | None) -> tuple[bool, str]:
    """VAL-02: ``covers_product_ids`` is a non-empty list of ints/strs.

    No null entries, no empty strings. A list of mixed ints and strings
    is allowed (the underlying domain model declares ``list[str]`` but
    the upstream models may emit either; the structural backstop is
    pydantic ``extra="forbid"`` validation, not this judge — this judge
    only checks "is the list usable as a covers list").
    """
    if artifact is None:
        return False, "no artifact"
    if not isinstance(artifact, dict):
        return False, "artifact is not a dict"
    covers = artifact.get("covers_product_ids")
    if not isinstance(covers, list):
        return False, "covers_product_ids is not a list"
    if len(covers) == 0:
        return False, "covers_product_ids is empty"
    for index, item in enumerate(covers):
        if item is None:
            return False, f"covers_product_ids[{index}] is null"
        if isinstance(item, bool):
            return False, f"covers_product_ids[{index}] is bool"
        if isinstance(item, str) and item == "":
            return False, f"covers_product_ids[{index}] is empty string"
        if not isinstance(item, (int, str)):
            return False, f"covers_product_ids[{index}] not int/str"
    return True, "ok"


def judge_val04(artifact: dict[str, Any] | None) -> tuple[bool, str]:
    """VAL-04: ``transferable_disposition_text`` is a non-empty trimmed string.

    The Phase 5 grep gate plus pydantic ``extra="forbid"`` cover token
    leakage / Arabic-digit / state-label leakage at the structural
    level; this judge is the simpler in-row "is the field present and
    not just whitespace" check that surfaces in the per-request boolean.
    """
    if artifact is None:
        return False, "no artifact"
    if not isinstance(artifact, dict):
        return False, "artifact is not a dict"
    text = artifact.get("transferable_disposition_text")
    if not isinstance(text, str):
        return False, "transferable_disposition_text is not a string"
    if text.strip() == "":
        return False, "transferable_disposition_text is empty after strip"
    return True, "ok"


# ---------------------------------------------------------------------------
# Column extractors for D-16 sortable columns
# ---------------------------------------------------------------------------
#
# Each extractor is total — it never raises on a missing/None artifact.
# Fallback values match the index_writer's per-row defaults so a row
# for a failed request still sorts cleanly:
#
#   len_covers_product_ids                                  → 0
#   len_transferable_disposition_text                       → 0
#   transferable_disposition_text                           → ""
#   literal_overlap_user_signal_vs_transferable_disposition → 0.0
#
# E1 (longest covers) sorts descending — failed rows naturally sink
# to the bottom; E2 (shortest text) sorts ascending — failed rows with
# 0-length text show up at the very top of the E2 view, which is the
# right behaviour: "no text at all" is the extreme case of "shortest".
# E3 (longest text) sorts descending — failed rows sink. E4 (highest
# overlap) sorts descending — failed rows sink. (D-16)
# ---------------------------------------------------------------------------


def extract_len_covers_product_ids(artifact: dict[str, Any] | None) -> int:
    """E1 column: integer length of ``covers_product_ids``.

    Sort descending → longest list rises to the top (E1 navigates to
    the request whose factor covers the most products).
    """
    if not isinstance(artifact, dict):
        return 0
    covers = artifact.get("covers_product_ids")
    if not isinstance(covers, list):
        return 0
    return len(covers)


def extract_len_transferable_disposition_text(artifact: dict[str, Any] | None) -> int:
    """E2 + E3 shared column: character count of stripped disposition text.

    SAME column for both E2 and E3 — opposite sort directions:

        * E2 → sort ascending  (shortest text — terse / underdeveloped factor)
        * E3 → sort descending (longest text — verbose / template-heavy factor)

    The auditor reads the same numeric column from two ends; the raw
    text itself lives in the passthrough column (extract_transferable_disposition_text).
    """
    if not isinstance(artifact, dict):
        return 0
    text = artifact.get("transferable_disposition_text")
    if not isinstance(text, str):
        return 0
    return len(text.strip())


def extract_transferable_disposition_text(artifact: dict[str, Any] | None) -> str:
    """Raw-text passthrough column — NOT an E-dimension.

    Fidelity field so the auditor can read the disposition text in-line
    after navigating by E2 or E3. Untrimmed, byte-for-byte from the
    artifact (whitespace preservation matters when the auditor is
    checking template-padding patterns).
    """
    if not isinstance(artifact, dict):
        return ""
    text = artifact.get("transferable_disposition_text")
    if not isinstance(text, str):
        return ""
    return text


def extract_literal_overlap(artifact: dict[str, Any] | None) -> float:
    """E4 column: codepoint-set Jaccard between user_signal and disposition text.

    Sort descending → highest overlap rises to the top (E4 navigates to
    the request whose disposition text most literally echoes the
    user-side signal — a classic "fake-transferable" smell per CONTEXT
    F1/F2/F3).

    Tokenisation rule (IN-03 fix — was whitespace.split, which collapsed
    all CJK requests to 0.0 because Chinese has no whitespace separators
    so the entire string became one giant unsplittable token):

        * lowercase (case-insensitive overlap on Latin scripts)
        * strip ASCII whitespace (so " a b " and "a  b" agree)
        * iterate codepoints — Latin letters and CJK ideographs alike
          enter the set as single-char tokens

    Trade-off: English overlap is now char-level, not word-level. "the"
    vs "they" share {t,h,e} so two Latin strings will tend to score
    higher than under the previous word-level rule. E4 is a *sort-only*
    column — absolute values are not load-bearing; only the descending
    order matters for the case-reading workflow, and char-level Jaccard
    preserves the relative order of "high-overlap echo" vs "low-overlap
    distinct prose" for both English and CJK.

    Returns 0.0 when either side is empty after tokenisation.
    """
    if not isinstance(artifact, dict):
        return 0.0
    user_signal = artifact.get("user_signal")
    disposition = artifact.get("transferable_disposition_text")
    if not isinstance(user_signal, str) or not isinstance(disposition, str):
        return 0.0

    left_tokens = {ch for ch in user_signal.lower() if not ch.isspace()}
    right_tokens = {ch for ch in disposition.lower() if not ch.isspace()}
    if not left_tokens or not right_tokens:
        return 0.0

    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    if union == 0:
        return 0.0
    return intersection / union


# ---------------------------------------------------------------------------
# Phase 8 behavioral metrics (M1-M5)
# ---------------------------------------------------------------------------


def compute_factor_count_p50(all_factor_artifacts: list[dict]) -> float:
    """M1: median number of discovered factors per request; threshold >= 3."""
    counts = [len(d.get("factors", [])) for d in all_factor_artifacts if isinstance(d, dict)]
    return float(statistics.median(counts)) if counts else 0.0


def compute_factor_diversity(all_factor_artifacts: list[dict]) -> float:
    """M2: mean Jaccard distance across covers-product ids and disposition text."""
    factors = [
        f
        for d in all_factor_artifacts
        if isinstance(d, dict)
        for f in d.get("factors", [])
        if isinstance(f, dict)
    ]
    if len(factors) < 2:
        return 0.0
    id_sets = [frozenset(f.get("covers_product_ids", [])) for f in factors]
    text_sets = [
        _tokenize(str(f.get("transferable_disposition", "") or ""))
        for f in factors
    ]
    return (_mean_jaccard_distance(id_sets) + _mean_jaccard_distance(text_sets)) / 2


def compute_copy_candidate_count_p50(all_copy_artifacts: list[dict]) -> float:
    """M3a: median considered-draft count per copy candidate; threshold >= 2."""
    counts: list[int] = []
    for artifact in all_copy_artifacts:
        if not isinstance(artifact, dict):
            continue
        candidates = artifact.get("candidates")
        if isinstance(candidates, list):
            counts.extend(
                len(c.get("considered_drafts", []))
                for c in candidates
                if isinstance(c, dict)
            )
        elif "considered_drafts" in artifact:
            counts.append(len(artifact.get("considered_drafts", [])))
    return float(statistics.median(counts)) if counts else 0.0


def compute_reflection_trigger_rate(per_request: list[tuple[int, list[str]]]) -> float:
    """M3b: share of underspecified requests (factor_count < 3) that called reflect_*."""
    underspec = [tools for factor_count, tools in per_request if factor_count < 3]
    if not underspec:
        return 1.0
    triggered = sum(
        1 for tools in underspec if any(str(tool).startswith("reflect_") for tool in tools)
    )
    return triggered / len(underspec)


def compute_delta_diversity(proposals: list[Any]) -> dict[str, int]:
    """M4: count distinct delta proposals, targets, and change types."""
    return {
        "count": len(proposals),
        "unique_targets": len({_field(p, "target_skill") for p in proposals if _field(p, "target_skill")}),
        "unique_change_types": len({_field(p, "change_type") for p in proposals if _field(p, "change_type")}),
    }


def compute_belief_update_count(final_portfolio: list[Any]) -> int:
    """M5: count portfolio rows with at least one observed trial folded in."""
    return sum(1 for row in final_portfolio if int(_field(row, "sample_count", 0) or 0) > 0)


def build_behavioral_report(stage_dir: str | Path) -> dict[str, Any]:
    """Aggregate M1-M5 from a stage directory without calling capture code."""
    stage_path = Path(stage_dir)
    request_dirs = _request_dirs_from_index(stage_path)
    factor_artifacts: list[dict] = []
    copy_artifacts: list[dict] = []
    reflection_inputs: list[tuple[int, list[str]]] = []
    proposals: list[Any] = []
    final_portfolio: list[Any] = []

    for request_dir in request_dirs:
        factor_artifact = _read_json_if_present(
            request_dir / "evidence/factor_discovery/artifact.json"
        )
        if isinstance(factor_artifact, dict):
            factor_artifacts.append(factor_artifact)
            factor_count = len(factor_artifact.get("factors", []))
            tools = _tool_names_from_jsonl(
                request_dir / "evidence/factor_discovery/tool_calls.jsonl"
            )
            reflection_inputs.append((factor_count, tools))
        copy_artifact = _read_json_if_present(
            request_dir / "evidence/copy_generation/artifact.json"
        )
        if isinstance(copy_artifact, dict):
            copy_artifacts.append(copy_artifact)

        snapshot = _read_json_if_present(request_dir / "evolution_snapshot.json")
        if isinstance(snapshot, dict):
            portfolio_rows = _portfolio_rows_from_snapshot(snapshot)
            if portfolio_rows:
                final_portfolio = portfolio_rows
                proposals = [
                    {
                        "delta_id": _field(row, "delta_id"),
                        "target_skill": _field(row, "target_skill"),
                        "change_type": _field(row, "change_type"),
                    }
                    for row in portfolio_rows
                ]
            elif not proposals:
                proposals = [{"delta_id": delta_id} for delta_id in snapshot.get("delta_portfolio_after", [])]

    return {
        "factor_count_p50": compute_factor_count_p50(factor_artifacts),
        "factor_diversity_score": compute_factor_diversity(factor_artifacts),
        "copy_candidate_count_p50": compute_copy_candidate_count_p50(copy_artifacts),
        "reflection_triggered_when_underspec_rate": compute_reflection_trigger_rate(reflection_inputs),
        "delta_diversity_score": compute_delta_diversity(proposals),
        "trial_belief_update_count": compute_belief_update_count(final_portfolio),
    }


def _tokenize(text: str) -> frozenset[str]:
    return frozenset(ch for ch in text.lower() if not ch.isspace())


def _mean_jaccard_distance(sets: list[frozenset]) -> float:
    distances = [
        1 - len(a & b) / len(a | b)
        for a, b in combinations(sets, 2)
        if a or b
    ]
    return sum(distances) / len(distances) if distances else 0.0


def _field(value: Any, name: str, default: Any = "") -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _read_json_if_present(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _request_dirs_from_index(stage_dir: Path) -> list[Path]:
    index_doc = _read_json_if_present(stage_dir / "index.json")
    if not isinstance(index_doc, dict):
        return [p for p in stage_dir.iterdir() if p.is_dir()] if stage_dir.exists() else []
    dirs: list[Path] = []
    for row in index_doc.get("requests", []):
        if isinstance(row, dict) and row.get("node_id"):
            dirs.append(stage_dir / str(row["node_id"]))
    return dirs


def _tool_names_from_jsonl(path: Path) -> list[str]:
    if not path.exists():
        return []
    names: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        names.extend(_tool_names(item))
    return names


def _tool_names(value: Any) -> list[str]:
    if isinstance(value, dict):
        out: list[str] = []
        if isinstance(value.get("name"), str):
            out.append(value["name"])
        fn = value.get("function")
        if isinstance(fn, dict) and isinstance(fn.get("name"), str):
            out.append(fn["name"])
        for nested in value.values():
            out.extend(_tool_names(nested))
        return out
    if isinstance(value, list):
        return [name for item in value for name in _tool_names(item)]
    return []


def _portfolio_rows_from_snapshot(snapshot: dict[str, Any]) -> list[Any]:
    for key in ("portfolio", "final_portfolio", "delta_portfolio"):
        rows = snapshot.get(key)
        if isinstance(rows, list):
            return rows
    return []
