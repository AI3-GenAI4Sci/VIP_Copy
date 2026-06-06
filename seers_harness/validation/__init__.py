"""Validation helpers for the VIP COPY production chain."""

from seers_harness.validation.evolution_snapshot import write_evolution_snapshot

from seers_harness.validation.recording_provider import (
    RecordingProvider,
    get_current_node_id,
    reset_current_node_id,
    set_current_node_id,
)
from seers_harness.validation.evidence_writer import flush_evidence

from seers_harness.validation.index_writer import write_index
from seers_harness.validation.batch_summary_writer import write_batch_summary
from seers_harness.validation.machine_judges import (
    judge_val01,
    judge_val02,
    judge_val04,
    extract_len_user_factor_ids,
    extract_len_need_or_pain_text,
    extract_need_or_pain_text,
    extract_literal_overlap,
)

from seers_harness.validation.exception_classifier import (
    TrialFailure,
    classify,
    is_trial_failure,
)

__all__ = [
    "write_evolution_snapshot",
    "RecordingProvider",
    "set_current_node_id",
    "get_current_node_id",
    "reset_current_node_id",
    "flush_evidence",
    "write_index",
    "write_batch_summary",
    "judge_val01",
    "judge_val02",
    "judge_val04",
    "extract_len_user_factor_ids",
    "extract_len_need_or_pain_text",
    "extract_need_or_pain_text",
    "extract_literal_overlap",
    "TrialFailure",
    "classify",
    "is_trial_failure",
]
