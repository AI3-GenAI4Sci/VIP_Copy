"""Skill prose loader for production and evolution skills.

Single harness primitive that reads skill prose into ``skill_bundle`` for the
tool loop. ``SKILL.json`` is preferred when present and is rendered
deterministically to the same Markdown surface; ``SKILL.md`` remains the
fallback for skills that have not been moved to structured source. Replaces the
literal placeholder string at
``dag_runner.py:84`` and the parallel inline ``read_text`` in
``validation.runner`` distillation calls.

Architecture (D2 — single primitive + extension layer):

  - ``load_skill_prose(skill_name) -> str`` is the **only** way the harness
    reads skill prose. ``grep 'read_text' over SKILL.md`` outside this module
    must return zero hits.
  - ``NODE_SKILL_BINDING`` + ``resolve_skill_for_node(node_id)`` is the
    extension layer that maps DAG node ids to skill names. It is **not** a
    second loader — it merely names which skill_name to feed the primitive.
  - A module-level cache (``_PROSE_CACHE``) reads each skill source from disk
    exactly once per process; subsequent calls return the cached text.
  - On miss the loader raises ``FileNotFoundError`` — **never** a fallback
    placeholder string. F-08-B was caused by a hard-coded 10-byte string
    masquerading as prose; this module's contract guarantees that bug class
    cannot recur.

Future extension: if "scenario flag selects skill variant" becomes a
requirement, replace ``NODE_SKILL_BINDING`` with a pluggable
``SkillBindingRegistry`` class — but keep the primitive's signature stable.
DO NOT inline a node-id-to-skill dict in ``dag_runner.py`` or
``validation/runner.py``; that is the F-08-B reproduction shape.
"""

from __future__ import annotations

import threading
from pathlib import Path

from seers_harness.workflow.structured_skill import render_structured_skill_file

__all__ = [
    "load_skill_prose",
    "resolve_skill_for_node",
    "NODE_SKILL_BINDING",
]


# Search roots for SKILL.md files. Order matters: the first existing file wins.
# ``current/`` holds production skills; ``evolution/`` holds the distill skill
# (and any future evolution-side skills). Both are siblings under
# ``workflow-skills/`` at the repo root.
_REPO_ROOT: Path = Path(__file__).resolve().parents[2]
_SKILL_ROOTS: tuple[Path, ...] = (
    _REPO_ROOT / "workflow-skills" / "current",
    _REPO_ROOT / "workflow-skills" / "evolution",
)


# Static binding from DAG node id to skill name. Production dispatches through
# the formal three-node DAG:
#   - ``personalized_copy_generation`` is the active generation surface.
#   - ``personalized_copy_rubric`` is the downstream judge surface.
#   - ``distill_after_production_request`` is the evolution distill node
#     invoked from production batch traffic.
#
# Adding a new DAG node = add one row here. **Never** inline a parallel mapping
# at the call site; that violates the D2 single-extension-point invariant.
NODE_SKILL_BINDING: dict[str, str] = {
    "personalized_user_mining": "personalized-user-mining",
    "personalized_copy_generation": "personalized-copy-generation",
    "personalized_copy_rubric": "personalized-copy-rubric-judge",
    "distill_after_production_request": "distill-skill-deltas",
}


# Module-level prose cache. Read once per skill_name per process. Guarded by a
# threading.Lock so concurrent production readers cannot race the cache write —
# load is idempotent
# and the lock is held only across the dict insert, not the disk read.
_PROSE_CACHE: dict[str, str] = {}
_CACHE_LOCK: threading.Lock = threading.Lock()


def load_skill_prose(skill_name: str, *, skill_root: Path | None = None) -> str:
    """Return the full text for ``skill_name`` from ``workflow-skills``.

    The first call for a given ``skill_name`` reads the file from disk; later
    calls return the cached text. Search order is ``_SKILL_ROOTS`` (current
    first, then evolution); the first existing path wins. Passing
    ``skill_root`` treats that path as an isolated ``workflow-skills`` root and
    searches its ``current/`` then ``evolution/`` subtrees without using cache.

    On miss raises ``FileNotFoundError`` with a message that names the missing
    skill and the searched roots — there is no fallback placeholder string,
    by design (F-08-B prevention).
    """
    if skill_root is not None:
        override_roots = (skill_root / "current", skill_root / "evolution")
        for root in override_roots:
            candidate = _skill_source_path(root / skill_name)
            if candidate is not None:
                return _read_skill_source(candidate)
        raise FileNotFoundError(
            f"SKILL.md not found for skill_name={skill_name!r}; "
            f"searched override roots: "
            + ", ".join(str(root) for root in override_roots)
        )

    cached = _PROSE_CACHE.get(skill_name)
    if cached is not None:
        return cached

    for root in _SKILL_ROOTS:
        candidate = _skill_source_path(root / skill_name)
        if candidate is not None:
            text = _read_skill_source(candidate)
            with _CACHE_LOCK:
                _PROSE_CACHE[skill_name] = text
            return text

    raise FileNotFoundError(
        f"SKILL.md not found for skill_name={skill_name!r}; "
        f"searched roots under workflow-skills/: "
        + ", ".join(str(r) for r in _SKILL_ROOTS)
    )


def _skill_source_path(skill_dir: Path) -> Path | None:
    structured = skill_dir / "SKILL.json"
    if structured.exists():
        return structured
    markdown = skill_dir / "SKILL.md"
    if markdown.exists():
        return markdown
    return None


def _read_skill_source(path: Path) -> str:
    if path.name == "SKILL.json":
        return render_structured_skill_file(path)
    return path.read_text(encoding="utf-8")


def resolve_skill_for_node(node_id: str) -> str:
    """Return the skill name bound to ``node_id``.

    Raises ``KeyError`` (with the node_id in the message) when the node is
    not registered. Callers MUST NOT silently fall back to a default skill —
    an unbound node is a configuration bug, not a runtime branch.
    """
    try:
        return NODE_SKILL_BINDING[node_id]
    except KeyError as exc:
        raise KeyError(
            f"no skill binding registered for node_id={node_id!r}; "
            f"known bindings: {sorted(NODE_SKILL_BINDING)}"
        ) from exc


def _clear_cache_for_tests() -> None:
    """Test-only hook to reset the module-level cache.

    Used by the development test suite to make cache-hit assertions
    deterministic. Not part of the public API — production code must not call
    this.
    """
    with _CACHE_LOCK:
        _PROSE_CACHE.clear()
