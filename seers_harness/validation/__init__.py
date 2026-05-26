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

# Plan 07-02 additions — evidence-capture proxy provider (D-08).
from seers_harness.validation.recording_provider import (
    RecordingProvider,
    get_current_node_id,
    set_current_node_id,
)
from seers_harness.validation.evidence_writer import flush_evidence

# Plan 07-03 additions — batch index + summary writers (D-10, D-12, D-16, D-22d).
from seers_harness.validation.index_writer import write_index
from seers_harness.validation.batch_summary_writer import write_batch_summary
from seers_harness.validation.machine_judges import (
    judge_val01,
    judge_val02,
    judge_val04,
    extract_len_covers_product_ids,
    extract_len_transferable_disposition_text,
    extract_transferable_disposition_text,
    extract_literal_overlap,
)

__all__ = [
    "write_evolution_snapshot",
    # 07-02 additions
    "RecordingProvider",
    "set_current_node_id",
    "get_current_node_id",
    "flush_evidence",
    # 07-03 additions
    "write_index",
    "write_batch_summary",
    "judge_val01",
    "judge_val02",
    "judge_val04",
    "extract_len_covers_product_ids",
    "extract_len_transferable_disposition_text",
    "extract_transferable_disposition_text",
    "extract_literal_overlap",
]
