"""Validation package — Phase 7 real-LLM evidence helpers.

Plan 07-01 seeds this package with the ``evolution_snapshot`` writer that
reduces observability hook events into the canonical
``evolution_snapshot.json`` shape required for VAL-06 evidence (see
``.planning/phases/07-real-llm-validation/07-CONTEXT.md`` D-11).

Subsequent Phase 7 plans (07-02 onward) extend this package with the
evidence-capture wrapper, batch index/summary writers, and stage runner
glue. Exports here only enumerate what 07-01 itself provides; new
exports append below as later plans land.
"""

from seers_harness.validation.evolution_snapshot import write_evolution_snapshot

__all__ = [
    "write_evolution_snapshot",
]
