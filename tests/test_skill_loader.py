"""Tests for ``seers_harness.workflow.skill_loader`` — F-08-B fix (Plan 08-G1).

The loader is THE single harness primitive that reads ``SKILL.md`` prose into
``skill_bundle`` for the tool loop. The previous loader was a literal 10-byte
string in ``dag_runner.py:84`` (``skill_bundle="SKILL_BODY"``); these tests
codify the new contract:

  - one entry point: ``load_skill_prose(skill_name)``
  - returns the full SKILL.md text (not a placeholder)
  - module-level cache (one disk read per skill_name)
  - raises ``FileNotFoundError`` on miss (NO silent fallback string)
  - ``resolve_skill_for_node(node_id)`` is the binding extension on top of
    the primitive — KeyError on unknown node, never a fallback skill
  - the literal forbidden placeholder is NOT present in the source

These tests are RED at write time (module does not yet exist); GREEN after the
``skill_loader.py`` module lands.
"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path

import pytest

import seers_harness.workflow.skill_loader as skill_loader_mod
from seers_harness.workflow.skill_loader import (
    NODE_SKILL_BINDING,
    _clear_cache_for_tests,
    load_skill_prose,
    resolve_skill_for_node,
)


# Auto-reset the module-level cache between tests so cache-hit assertions are
# deterministic regardless of test ordering.
@pytest.fixture(autouse=True)
def _reset_cache():
    _clear_cache_for_tests()
    yield
    _clear_cache_for_tests()


# -- Behavior 1: returns SKILL.md prose, not a placeholder ------------------


def test_load_skill_prose_returns_full_skill_md_for_current_skill():
    prose = load_skill_prose("personalized-copy-generation")
    # Must be the real SKILL.md — far longer than the 10-byte placeholder.
    assert len(prose) > 1500, (
        "expected real SKILL.md prose (>1500 bytes), got "
        f"{len(prose)} bytes — loader is returning a placeholder"
    )
    # Re-read the file directly and confirm byte-for-byte equality.
    repo_root = Path(__file__).resolve().parents[1]
    direct = (
        repo_root
        / "workflow-skills"
        / "current"
        / "personalized-copy-generation"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert prose == direct


# -- Behavior 2: evolution-root skill resolves via multi-root search --------


def test_load_skill_prose_finds_skill_in_evolution_root():
    prose = load_skill_prose("distill-skill-deltas")
    repo_root = Path(__file__).resolve().parents[1]
    direct = (
        repo_root
        / "workflow-skills"
        / "evolution"
        / "distill-skill-deltas"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert prose == direct
    assert len(prose) > 1000


# -- Behavior 3: missing skill raises FileNotFoundError, NO fallback string -


def test_load_skill_prose_raises_filenotfound_for_unknown_skill():
    with pytest.raises(FileNotFoundError) as excinfo:
        load_skill_prose("does-not-exist-anywhere")
    msg = str(excinfo.value)
    assert "does-not-exist-anywhere" in msg, (
        "FileNotFoundError must name the missing skill"
    )
    # The message should reference the search roots so a debugger can see what
    # was tried — F-08-B reproduction guard.
    assert "workflow-skills" in msg, (
        "FileNotFoundError must reference the search roots"
    )


# -- Behavior 4: module-level cache — read once, reuse N times --------------


def test_load_skill_prose_caches_after_first_read(monkeypatch):
    call_count = {"n": 0}
    real_read_text = Path.read_text

    def counting_read_text(self, *args, **kwargs):
        call_count["n"] += 1
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting_read_text)

    # First call — reads disk once.
    first = load_skill_prose("personalized-copy-generation")
    assert call_count["n"] == 1, (
        f"expected 1 disk read after first call, got {call_count['n']}"
    )

    # 100 more calls — cache must satisfy all of them.
    for _ in range(100):
        again = load_skill_prose("personalized-copy-generation")
        assert again == first
    assert call_count["n"] == 1, (
        "cache miss: expected exactly 1 disk read for 101 calls, "
        f"got {call_count['n']}"
    )


# -- Behavior 5: resolve_skill_for_node canonical bindings + KeyError -------


def test_resolve_skill_for_node_canonical_bindings():
    assert (
        resolve_skill_for_node("personalized_copy_rubric")
        == "personalized-copy-rubric-judge"
    )
    assert (
        resolve_skill_for_node("personalized_copy_generation")
        == "personalized-copy-generation"
    )
    assert (
        resolve_skill_for_node("distill_after_stage1")
        == "distill-skill-deltas"
    )
    # Exactly the documented bindings are exposed.
    assert set(NODE_SKILL_BINDING.keys()) == {
        "personalized_user_mining",
        "personalized_copy_generation",
        "personalized_copy_rubric",
        "distill_after_stage1",
    }


def test_current_generation_skill_prose_describes_merged_surface():
    merged_prose = load_skill_prose("personalized-copy-generation")

    assert "maintain_copy_artifact" in merged_prose
    assert "user_factors" in merged_prose
    assert "source_user_factor_id" in merged_prose
    assert "product_binding" in merged_prose
    assert "fact_binding" in merged_prose
    assert "商品名" in merged_prose


def test_resolve_skill_for_node_unknown_raises_keyerror():
    with pytest.raises(KeyError) as excinfo:
        resolve_skill_for_node("not_a_real_node")
    # The KeyError must name the unknown node id so callers can debug.
    assert "not_a_real_node" in str(excinfo.value)


# -- Behavior 6: forbidden literal is absent from the loader source ---------


def test_skill_loader_source_does_not_contain_forbidden_literal():
    src = inspect.getsource(skill_loader_mod)
    # The exact placeholder token from F-08-B must not appear anywhere
    # (including as a string constant or comment) in the primitive's source.
    forbidden = "SKILL" + "_BODY"
    assert forbidden not in src, (
        f"{forbidden!r} must not appear in skill_loader.py — that is the "
        "F-08-B regression token; the loader's only output path is the real "
        "SKILL.md content or a FileNotFoundError"
    )
    # Sanity: the primitive's public API is exported.
    assert "load_skill_prose" in src
    assert "NODE_SKILL_BINDING" in src
    assert "resolve_skill_for_node" in src


# -- Bonus: module re-import after _clear_cache_for_tests works -------------


def test_clear_cache_for_tests_resets_cache():
    load_skill_prose("personalized-copy-rubric-judge")
    _clear_cache_for_tests()
    # After clear, the internal cache dict must be empty.
    assert skill_loader_mod._PROSE_CACHE == {}
    # And the loader still works (re-fills the cache).
    prose = load_skill_prose("personalized-copy-rubric-judge")
    assert len(prose) > 1000
    importlib.reload(skill_loader_mod)  # smoke — reload doesn't corrupt state
