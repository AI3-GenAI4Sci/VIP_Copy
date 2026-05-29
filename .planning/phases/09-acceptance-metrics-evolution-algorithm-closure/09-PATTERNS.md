# Phase 09: Acceptance Metrics & Evolution Algorithm Closure - Pattern Map

**Mapped:** 2026-05-29
**Files analyzed:** 26
**Analogs found:** 26 / 26

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `seers_harness/evolution/delta_portfolio.py` | model + service utility | request-response selection + CRUD-like state transform | same file, `select_trial_delta` / `update_after_trial` | exact-existing-surface |
| `seers_harness/evolution/status_machine.py` | service utility | batch transform | same file, `apply_status_transitions` | exact-existing-surface |
| `seers_harness/evolution/trial_signal.py` | utility | rolling-window transform | same file; use only for observability/failure blocker if retained | role-match |
| `seers_harness/evolution/portfolio_journal.py` | model + persistence utility | file-I/O + batch fold | same file, `append_journal_entry` / `fold_portfolio_journal` | exact-existing-surface |
| `seers_harness/evolution/uplift.py` | reward utility | transform | same file, replace `compute_uplift`; `seers_harness/domain/models.py` rubric schema | exact-existing-surface |
| `seers_harness/validation/runner.py` | orchestration service | request-response + file-I/O + concurrent batch | same file, `_run_one_request` and `_run_stage` | exact-existing-surface |
| `seers_harness/validation/evolution_snapshot.py` | writer/reducer | event-driven transform + file-I/O | same file, `write_evolution_snapshot` | exact-existing-surface |
| `seers_harness/validation/machine_judges.py` | metrics utility | batch file-I/O transform | same file, `build_behavioral_report` / `compute_belief_update_count` | exact-existing-surface |
| `seers_harness/validation/batch_summary_writer.py` | summary writer | file-I/O batch transform | same file, `write_batch_summary` | exact-existing-surface |
| `seers_harness/domain/models.py` | model | validation transform | rubric models in same file | exact-existing-surface |
| `workflow-skills/current/personalized-copy-generation/SKILL.md` | skill prompt | request-response artifact generation | same file, Phase 1/Phase 2 staged artifact guidance | exact-existing-surface |
| `workflow-skills/current/personalized-copy-rubric-judge/SKILL.md` | skill prompt | request-response scoring artifact | same file, scored rubric workflow | exact-existing-surface |
| `tests/test_delta_portfolio.py` | unit test | selection + state transform | same file; mirror helper `_make_row` and deterministic RNG style | exact-existing-test |
| `tests/test_validation_runner.py` | integration test | runner request-response + file-I/O | same file; mirror skip/fire/journal/snapshot tests | exact-existing-test |
| `tests/test_uplift.py` | unit test | reward transform | same file; rewrite around typed rubric artifact means | exact-existing-test |
| `tests/test_portfolio_journal.py` | unit test | JSONL file-I/O + fold | same file; mirror append/read/fold assertions | exact-existing-test |
| `tests/test_08_07_behavioral_metrics.py` | unit/integration test | batch file-I/O summary metrics | same file; mirror behavioral report and summary tests | exact-existing-test |
| `tests/test_batch_summary_writer.py` | unit test | batch summary file-I/O | same file; mirror `_write_summary` helper | role-match |
| `tests/test_status_machine.py` | unit test | status batch transform | same file; update token-cost blocking expectation | exact-existing-test |
| `tests/test_trial_runner.py` | integration test | trial workspace request-response | same file; update selection call signature in integration path | role-match |
| `tests/test_models_rubric.py` | unit test | schema validation | same file; mirror typed rubric artifact construction | role-match |
| `tests/test_phase09_acceptance_gates.py` | source anti-cheat test | production source scan | `tests/test_workflow_progress.py`, `tests/test_promotion_smoke.py`, `tests/test_models_no_self_rated_fields.py` | role-match |
| `tests/test_phase09_skill_contract.py` | skill prose contract test | file text scan | `tests/test_skill_loader.py`, `tests/test_evolution_tools.py`, `tests/test_models_no_self_rated_fields.py` | role-match |
| `.planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-ACCEPTANCE-EVIDENCE.md` | phase evidence ledger | command/result file-I/O | `.planning/phases/07-real-llm-validation/07-EXECUTION-LOG.md`, `.planning/phases/08-evolution-wiring-and-runner-debt/08-VERIFICATION.md` | role-match |
| `.planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-CASE-READING.md` | manual evidence artifact | human review file-I/O | `.planning/phases/07-real-llm-validation/case_analysis_template.md` | role-match |
| `.planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-MERGED-NODE-ASSESSMENT.md` | assessment artifact | human review synthesis | `.planning/phases/07-real-llm-validation/case_analysis.md`, `.planning/phases/07-real-llm-validation/07-WRIN-TRIAGE.md` | role-match |

## Pattern Assignments

### `seers_harness/evolution/delta_portfolio.py` (model + selection service, request-response transform)

**Analog:** `seers_harness/evolution/delta_portfolio.py`

**Imports/model pattern** (lines 24-33):
```python
from __future__ import annotations

import json
import random as _random_module
from pathlib import Path
from typing import Iterable, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from seers_harness.domain.models import EvidenceRef
```

**Portfolio row / posterior state pattern** (lines 83-111):
```python
class DeltaPortfolioRow(BaseModel):
    delta_id: str
    target_skill: str
    change_type: ChangeType
    observation: str
    proposed_change: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    applicable_surface: list[str] = Field(default_factory=list)
    failure_types: list[str] = Field(default_factory=list)
    belief_alpha: float = 1.0
    belief_beta: float = 1.0
    sample_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    token_cost_delta_sum: int = 0
    status: DeltaStatus = "experimental"

    model_config = {"extra": "forbid"}
```

**Pure posterior update pattern** (lines 193-220):
```python
def update_after_trial(
    row: DeltaPortfolioRow,
    *,
    success: bool,
    token_cost_delta: int = 0,
) -> DeltaPortfolioRow:
    new_alpha = row.belief_alpha + (1.0 if success else 0.0)
    new_beta = row.belief_beta + (0.0 if success else 1.0)
    return row.model_copy(
        update={
            "belief_alpha": new_alpha,
            "belief_beta": new_beta,
            "sample_count": row.sample_count + 1,
            "success_count": row.success_count + (1 if success else 0),
            "failure_count": row.failure_count + (0 if success else 1),
            "token_cost_delta_sum": row.token_cost_delta_sum + int(token_cost_delta),
        }
    )
```

**Selection pattern to replace, not copy** (lines 228-293):
```python
def select_trial_delta(
    portfolio: list[DeltaPortfolioRow],
    *,
    applicable_surface: list[str],
    recent_failure_rate: float,
    token_budget_pressure: float,
    production_pressure: float,
    rng: _random_module.Random | None = None,
) -> Optional[str]:
    ...
    trial_prob = (1.0 - rfr) * (1.0 - tbp) * (1.0 - pp)
    if rng.random() >= trial_prob:
        return None
```

**Phase 9 direction:** Keep the model/pure-update style. Replace the selector with an explicit exploration-decision result, eligibility filtering by `status == "experimental"` and surface overlap, information-value trigger, and Thompson sampling via injected `random.Random`. Do not keep `token_budget_pressure`, `production_pressure`, `trial_prob`, static probability skip, random skip, or `no_trial` as a bandit arm.

---

### `seers_harness/evolution/status_machine.py` (status service, batch transform)

**Analog:** `seers_harness/evolution/status_machine.py`

**Imports and lower-bound helper** (lines 1-18):
```python
"""Delta portfolio status transitions."""

from __future__ import annotations

import math

from seers_harness.evolution.delta_portfolio import DeltaPortfolioRow


def wilson_lcb(success: int, total: int, *, z: float = 1.96) -> float:
    if total <= 0:
        return 0.0
    ...
    return max(0.0, (centre - margin) / denom)
```

**Status transition pattern** (lines 36-70):
```python
def apply_status_transitions(
    portfolio: list[DeltaPortfolioRow],
    *,
    lcb_promote: float = 0.6,
    lcb_reject: float = 0.2,
    samples_promote: int = 5,
    samples_reject: int = 10,
    token_cost_p95_max: int = 2_000,
    token_cost_deltas_by_delta: dict[str, list[int]] | None = None,
) -> list[DeltaPortfolioRow]:
    transitioned: list[DeltaPortfolioRow] = []
    for row in portfolio:
        if row.status != "experimental":
            transitioned.append(row)
            continue

        lcb = wilson_lcb(row.success_count, row.sample_count)
        ...
        if (
            lcb >= lcb_promote
            and row.sample_count >= samples_promote
            and token_cost_p95 <= token_cost_p95_max
        ):
            transitioned.append(row.model_copy(update={"status": "ready_for_review"}))
        elif lcb <= lcb_reject and row.sample_count >= samples_reject:
            transitioned.append(row.model_copy(update={"status": "rejected"}))
        else:
            transitioned.append(row)
    return transitioned
```

**Phase 9 direction:** Keep `wilson_lcb`, explicit threshold parameters, `model_copy`, and list-in/list-out transform. Revisit token-cost promotion blocking: D9 says lifecycle thresholds are rubric win/loss evidence only, so token cost should be removed or recorded outside the transition decision.

---

### `seers_harness/evolution/portfolio_journal.py` (journal persistence, file-I/O + fold)

**Analog:** `seers_harness/evolution/portfolio_journal.py`

**Entry model and JSONL append pattern** (lines 15-31):
```python
class PortfolioJournalEntry(BaseModel):
    request_id: str
    delta_id: str
    success: bool
    token_cost_delta: int = 0
    behavioral_metric_lift: dict[str, float] = Field(default_factory=dict)
    ts: str = ""

    model_config = {"extra": "forbid"}


def append_journal_entry(journal_path: Path | str, entry: PortfolioJournalEntry) -> None:
    path = Path(journal_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(entry.model_dump_json())
        f.write("\n")
```

**Read/fold pattern** (lines 34-64):
```python
def read_journal_entries(journal_path: Path | str) -> list[PortfolioJournalEntry]:
    path = Path(journal_path)
    if not path.exists():
        return []
    entries: list[PortfolioJournalEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(PortfolioJournalEntry.model_validate_json(line))
    return entries


def fold_portfolio_journal(
    journal_path: Path | str,
    portfolio: list[DeltaPortfolioRow],
) -> list[DeltaPortfolioRow]:
    entries = read_journal_entries(journal_path)
    if not entries:
        return portfolio
    ...
        folded[index] = update_after_trial(
            folded[index],
            success=entry.success,
            token_cost_delta=entry.token_cost_delta,
        )
    return folded
```

**Phase 9 direction:** Keep append-only JSONL and replay fold. If reward provenance needs richer persisted evidence, extend the entry minimally with rubric mean fields or score delta while preserving `model_config = {"extra": "forbid"}` and fold compatibility.

---

### `seers_harness/evolution/uplift.py` (reward utility, transform)

**Analog:** `seers_harness/evolution/uplift.py` plus rubric schema in `seers_harness/domain/models.py`

**Current reward pattern to replace** (lines 10-25, 37-50):
```python
@dataclass(frozen=True)
class TrialUplift:
    success_lift: int
    token_cost_delta: int
    behavioral_metric_lift: dict[str, float] = field(default_factory=dict)
    is_positive: bool = False


def compute_uplift(
    baseline: TrialOutcome,
    trial: TrialOutcome,
    *,
    budget_tolerance: int = 1_000,
    behavioral_metrics_baseline: dict[str, float] | None = None,
    behavioral_metrics_trial: dict[str, float] | None = None,
) -> TrialUplift:
    ...
    return TrialUplift(..., is_positive=is_positive)
```

**Rubric artifact schema to copy from** (`seers_harness/domain/models.py` lines 64-76, 89-96, 115-117):
```python
class PersonalizedCopyRubricJudgment(BaseModel):
    candidate_id: str
    candidate_index: int | None = None
    product_id: str = ""
    copy_text: str = ""
    factor_id: str = ""
    axis_scores: list[RubricAxisScore] = Field(default_factory=list)
    total_score: int = Field(default=0, ge=0, le=25)
    main_strength: str = ""
    main_weakness: str = ""
    failure_tags: list[str] = Field(default_factory=list)
    decision: RubricDecision = "hold"
    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _check_total_score(self):
        expected = sum(axis.score for axis in self.axis_scores)
        if self.total_score != expected:
            raise ValueError(...)
        return self

class PersonalizedCopyRubricArtifact(BaseModel):
    judgments: list[PersonalizedCopyRubricJudgment] = Field(default_factory=list)
    model_config = {"extra": "forbid"}
```

**Phase 9 direction:** Keep frozen dataclass/simple function style if retaining an output type, but reward success must be `trial_mean_rubric_score > baseline_mean_rubric_score`. Token and behavioral metric deltas can be record-only fields; they must not determine `is_positive`.

---

### `seers_harness/validation/runner.py` (orchestration service, request-response + file-I/O)

**Analog:** `seers_harness/validation/runner.py`

**Imports pattern** (lines 120-183):
```python
import datetime as _dt
import json
import os
import random
import sys
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from seers_harness.domain.models import (
    CopyGenerationArtifact,
    FactorDiscoveryArtifact,
    PersonalizedCopyGenerationArtifact,
    PersonalizedCopyRubricArtifact,
)
from seers_harness.evolution.delta_portfolio import (
    DeltaDistillationArtifact,
    DeltaPortfolioRow,
    assemble_portfolio,
    select_trial_delta,
)
...
from seers_harness.validation.batch_summary_writer import write_batch_summary
```

**Current trial-gate event to replace** (lines 690-719):
```python
def _trial_gate_event(
    *,
    portfolio: list[DeltaPortfolioRow],
    applicable_surface: list[str],
    recent_failure_rate: float,
    token_budget_pressure: float,
    production_pressure: float,
    selected_delta_id: str | None,
) -> dict[str, Any]:
    ...
    return {
        "type": "trial_gate",
        "recent_failure_rate": rfr,
        "token_budget_pressure": tbp,
        "production_pressure": pp,
        "trial_prob": (1.0 - rfr) * (1.0 - tbp) * (1.0 - pp),
        "eligible_delta_count": eligible_count,
        "selected_delta_id": selected_delta_id,
    }
```

**Main request flow pattern** (lines 761-825):
```python
record: dict[str, Any] = {
    "node_id": _safe_request_dirname(request_id),
    "request_id": request_id,
    "artifact": None,
    "reflow_triggered": False,
    "trial_selected_delta_id": None,
    "exception": None,
    "failure_class": "ok",
}
...
result_paths = runtime.run_request(scenario=scenario, nodes=list(nodes))
...
raw = json.loads(Path(p).read_text(encoding="utf-8"))
model.model_validate(raw)
```

**Trial workspace + journal pattern** (lines 839-921):
```python
selected_delta_id = select_trial_delta(
    portfolio=delta_portfolio,
    applicable_surface=applicable_surface,
    recent_failure_rate=recent_failure_rate,
    token_budget_pressure=token_budget_pressure,
    production_pressure=production_pressure,
    rng=_trial_rng,
)
events.append(_trial_gate_event(...))
if selected_delta_id is not None:
    ...
    baseline_outcome = run_request_baseline(...)
    trial_outcome = run_request_trial(...)
    uplift = compute_uplift(...)
    record["trial_selected_delta_id"] = selected_delta_id
    append_journal_entry(
        journal_path or (request_dir.parent / "portfolio_journal.jsonl"),
        PortfolioJournalEntry(
            request_id=request_id,
            delta_id=selected_delta_id,
            success=uplift.is_positive,
            token_cost_delta=uplift.token_cost_delta,
            behavioral_metric_lift=uplift.behavioral_metric_lift,
            ts=_utc_now_iso(),
        ),
    )
```

**Stage ordering bug pattern** (lines 1175-1198):
```python
write_index(...)
write_batch_summary(stage_dir / "index.json")
journal_path = out_dir / "portfolio_journal.jsonl"
if journal_path.exists():
    entries = read_journal_entries(journal_path)
    ...
    delta_portfolio[:] = fold_portfolio_journal(journal_path, delta_portfolio)
    delta_portfolio[:] = apply_status_transitions(...)
```

**Phase 9 direction:** Keep the existing `_run_one_request` integration point and paired baseline/trial workspace flow. Replace `_trial_gate_event` with an `exploration_decision` event. Move journal fold/status transition before `write_batch_summary`, or pass folded portfolio explicitly into the summary path. Extract rubric artifacts from `baseline_outcome.artifact_paths` and `trial_outcome.artifact_paths`; do not use run success, token delta, or behavioral metric lift as reward.

---

### `seers_harness/validation/evolution_snapshot.py` (event reducer, file-I/O)

**Analog:** `seers_harness/validation/evolution_snapshot.py`

**Reducer and safe-write pattern** (lines 51-73, 74-96, 124-133):
```python
def write_evolution_snapshot(
    events: list[dict],
    out_path: str | Path,
) -> None:
    if not isinstance(events, list):
        events = []

    delta_portfolio_before: list[Any] = []
    delta_portfolio_after: list[Any] = []
    trials: list[dict[str, Any]] = []
    trial_gate: dict[str, Any] = {}

    for event in events:
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        ...
        elif event_type == "trial_gate":
            trial_gate = {
                "recent_failure_rate": event.get("recent_failure_rate"),
                "token_budget_pressure": event.get("token_budget_pressure"),
                "production_pressure": event.get("production_pressure"),
                "trial_prob": event.get("trial_prob"),
                "eligible_delta_count": event.get("eligible_delta_count"),
                "selected_delta_id": event.get("selected_delta_id"),
            }

    snapshot = {
        "delta_portfolio_before": delta_portfolio_before,
        "delta_portfolio_after": delta_portfolio_after,
        "trial_gate": trial_gate,
        "trials": trials,
    }

    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
```

**Error handling pattern** (lines 104-120):
```python
elif event_type == "trial_failed":
    trial_id = event.get("trial_id", "")
    entry: dict[str, Any] = {"trial_id": trial_id, "status": "failed"}
    ...
    if exc_msg is not None:
        entry["exception_message"] = _safe_message(str(exc_msg))
    trials.append(entry)
```

**Phase 9 direction:** Preserve reducer degradation rules: ignore malformed events, last-write wins for state, redact exception messages, create parent directory, trailing newline. Replace `trial_gate` with `exploration_decision` containing selected delta, eligible count, trigger/no-trigger decision, and allowed `no_trial_reason`. Snapshot tests should assert forbidden fields are absent.

---

### `seers_harness/validation/batch_summary_writer.py` (summary writer, file-I/O batch transform)

**Analog:** `seers_harness/validation/batch_summary_writer.py`

**Writer-layer imports** (lines 54-60):
```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from seers_harness.validation.machine_judges import build_behavioral_report
```

**Index read / manual review queue pattern** (lines 70-86, 136-153):
```python
def write_batch_summary(
    index_path: str | Path,
    out_path: str | Path | None = None,
) -> None:
    index_path_p = Path(index_path)
    out_path_p = (
        Path(out_path) if out_path is not None else index_path_p.parent / "batch_summary.json"
    )

    index_doc = json.loads(index_path_p.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = index_doc.get("requests") or []
    ...
    needs_review = False
    if row.get("VAL-03_pass") is None:
        text_len = row.get("len_claim_text", 0)
        if isinstance(text_len, int) and text_len > 0:
            needs_review = True
    if row.get("reflow_triggered") is True:
        needs_review = True
    if row.get("trial_selected_delta_id"):
        needs_review = True
```

**Summary write pattern** (lines 160-183):
```python
summary: dict[str, Any] = {
    "stage": index_doc.get("stage"),
    "batch_id": index_doc.get("batch_id"),
    "totals": {...},
    "fail_lists": {...},
    "by_failure_class": by_failure_class,
    "behavioral_metrics": build_behavioral_report(index_path_p.parent),
    "manual_review_queue": queue,
}

out_path_p.parent.mkdir(parents=True, exist_ok=True)
out_path_p.write_text(
    json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
```

**Phase 9 direction:** Keep the writer-layer separation. For M5, either add an optional `final_portfolio` argument and pass it into `build_behavioral_report`, or write/read a stage-level folded portfolio artifact before summary. Do not let `factor_count_p50`, token, or cache become pass/fail gates here; they are records/navigation evidence only.

---

### `seers_harness/validation/machine_judges.py` (metrics utility, batch file-I/O transform)

**Analog:** `seers_harness/validation/machine_judges.py`

**M5 helper pattern** (lines 305-307):
```python
def compute_belief_update_count(final_portfolio: list[Any]) -> int:
    """M5: count portfolio rows with at least one observed trial folded in."""
    return sum(1 for row in final_portfolio if int(_field(row, "sample_count", 0) or 0) > 0)
```

**Behavioral report aggregation pattern** (lines 310-360):
```python
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
        generation_artifact = _read_json_if_present(
            request_dir / "evidence/personalized_copy_generation/artifact.json"
        )
        ...
        snapshot = _read_json_if_present(request_dir / "evolution_snapshot.json")
        if isinstance(snapshot, dict):
            portfolio_rows = _portfolio_rows_from_snapshot(snapshot)
            if portfolio_rows:
                final_portfolio = portfolio_rows
                proposals = [...]

    return {
        "factor_count_p50": compute_factor_count_p50(factor_artifacts),
        ...
        "trial_belief_update_count": compute_belief_update_count(final_portfolio),
    }
```

**Phase 9 direction:** The M5 computation is adequate if fed folded state. Keep batch aggregation pure and capture-free. Add folded portfolio input/read path rather than trying to infer posterior updates from raw journal rows inside per-request snapshots.

---

### `workflow-skills/current/personalized-copy-generation/SKILL.md` (skill prompt, request-response artifact generation)

**Analog:** same file.

**Merged-node contract** (lines 10-18):
```markdown
Run the default merged generation path for one request/list group. Mine factors
and write slogans in the same reasoning session so product detail, user scene,
and list context stay alive. Keep the durable artifacts separate: factors carry
the reason a user-product relation matters; copy carries the visible line linked
back to one source factor.

The split factor and copy skills are archived reference material. Do not behave
as if the generation job has two isolated prompts unless the runtime is running
an old compatibility node.
```

**Staged factor/copy pattern** (lines 84-109, 111-139):
```markdown
## Phase 1: Factor Mining

Work product by product, while keeping the whole request in view.
...
Use `maintain_factor_artifact` to read, upsert, replace, validate, and save
factor state when available. ... Call `reflect_on_factor_coverage` when the major tensions,
product fit, or factor separation are uncertain...

## Phase 2: Copy Writing

Treat the factor artifact as the creative brief. Raw product facts remain
available to recover detail and avoid mistakes; they do not replace the factor.
...
Use `maintain_copy_artifact` to read, upsert, replace, validate, and save copy
state when available. Use `reflect_on_copy_quality` when lines start to sound
like paraphrases...
```

**Anti-patterns / red flags** (lines 176-180):
```markdown
- **Signal renamed as factor** -> ask what the signal changes about the user's
  decision.
- **Product-free psychology** -> add the product fact or product result that
```

**Phase 9 direction:** If case-reading finds instability, make lightweight SKILL wording edits only. Preserve plural/distinctness guidance, staged factor-before-copy state, and `source_factor_id` linkage. Do not add hard numeric factor thresholds, JSON skeletons, ellipsis templates, internal examples, enumeration-taxonomy prompting, or new tool mechanisms.

---

### `workflow-skills/current/personalized-copy-rubric-judge/SKILL.md` (skill prompt, scoring artifact)

**Analog:** same file.

**Scored workflow pattern** (lines 50-75):
```markdown
For each candidate:

1. **Reconstruct the brief.** Read the source factor, product facts, and visible
   line together. Judge the line as a user in that scene would receive it.

2. **Score the five axes.** Write a concise diagnostic for each score in the
   candidate's input language. Do not use the score to justify a prechosen
   decision; let the axis evidence lead.

3. **Compute `total_score`.** Sum the five axes for a 0-25 total.

4. **Derive the decision.** `admit` when `total_score >= 21` ...

5. **Write diagnostics.** Record `main_strength`, `main_weakness`, and
   `failure_tags` so evolution can compare deltas by failure type...
```

**Output/provenance pattern** (lines 112-120):
```markdown
`PersonalizedCopyRubricArtifact` per the active domain model. Preferred judgment
fields are the five axis scores, `total_score`, `decision`, and diagnostics with
main strength, main weakness, and failure tags. Compatibility runtimes may store
the same judgment through older fields until the domain model changes.

Upstream personalized copy generation supplies factors and candidates. Downstream
evolution uses score deltas, failure tags, and admit/hold/reject movement to
compare skill changes across real runs.
```

**Phase 9 direction:** Reward provenance should consume this artifact's `judgments[*].total_score` only for mean-score uplift. Do not let the model self-rate delta success outside this typed rubric artifact.

---

### `.planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-ACCEPTANCE-EVIDENCE.md` (phase evidence ledger, command/result file-I/O)

**Analog:** `.planning/phases/07-real-llm-validation/07-EXECUTION-LOG.md` and `.planning/phases/08-evolution-wiring-and-runner-debt/08-VERIFICATION.md`

**Phase 9 direction:** Use this artifact as a concise ledger, not a raw log dump. Required sections: local pytest result, anti-cheat test result, real DeepSeek command, `Real run status`, real run id, `index.json`, `batch_summary.json`, `portfolio_journal.jsonl`, sampled request paths, mechanism evidence checklist, record-only metrics table, and blocker/escalation notes.

Provider/auth/quota/balance failure must be recorded as `Real run status: BLOCKED` with safe error text and failure class. It is not completion evidence. Completed acceptance requires `Real run status: COMPLETED` from a real 30-request concurrency-5 DeepSeek run.

Do not paste API keys, full provider logs, long model messages, or raw request payloads. Store local artifact paths and compact observations.

---

### `.planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-CASE-READING.md` (manual evidence artifact, human review file-I/O)

**Analog:** `.planning/phases/07-real-llm-validation/case_analysis_template.md`

**Manual verdict boundary pattern** (lines 5-13):
```markdown
audience: user (D-13/D-14 — only user-authored verdicts admitted to case_analysis.md)
purpose: |
  Reading guide for trajectory-level case analysis on real-LLM evidence.
  This template instructs the analyst to READ INPUT/OUTPUT CONTENT
  per request, NOT count statistics. The frontmatter columns in
  index.json ... are NAVIGATION AIDS — they tell you WHICH cases to read first; they are NOT the
  verdict.
```

**Navigation pattern** (lines 43-73):
```markdown
## Part 0 — Setup (do this once before reading any case)

1. Identify the run directory: `tests/smoke/.runs/<timestamp>/`.

2. Open the per-stage `index.json` and **use it only for navigation**.
...
3. For each picked request, you'll read this directory:
   ```
   stage{N}/<request_id>/
     ...
     └── evolution_snapshot.json
   ```
```

**Synthesis pattern** (lines 245-257):
```markdown
## Part 4 — synthesis

After all F1..F4 case readings + VAL-03 + VAL-06, write 1-3 paragraphs
of synthesis:

- What pattern did the real-LLM evidence reveal that the machine columns
  in `index.json` did not?
- Are the factors transferable in the project's sense...
- Where does the evidence chain hold tightest, and where does it fray?
- What changes (if any) to the upstream skill prompts would improve the
  next batch?
```

**Phase 9 direction:** Create a smaller Phase 9 artifact that reads 5-8 real Stage 3 requests, including pressure cases. Required columns/sections should capture scenario path, generation artifact path, generation tool calls, rubric artifact path, factor distinctness/product grounding, copy `source_factor_id` linkage, staged tool use, concrete failure modes, and whether lightweight SKILL repair is needed.

This artifact must start from `09-ACCEPTANCE-EVIDENCE.md` only when that ledger says `Real run status: COMPLETED`. If the ledger is blocked or incomplete, the case-reading task is blocked; do not derive quality findings from pytest, FakeProvider, or old Phase 8 runs.

---

### `.planning/phases/09-acceptance-metrics-evolution-algorithm-closure/09-MERGED-NODE-ASSESSMENT.md` (assessment artifact, human review synthesis)

**Analog:** `.planning/phases/07-real-llm-validation/case_analysis.md` and `.planning/phases/07-real-llm-validation/07-WRIN-TRIAGE.md`

**Phase 9 direction:** Summarize the bounded case reading into a concrete merged-node verdict. Preserve the merged `personalized_copy_generation` production path unless a later phase explicitly reopens architecture. If a split-node comparison is used, label it diagnostic-only and keep it out of production DAG wiring.

Allowed repair decisions are: no repair, SKILL wording repair, or diagnostic-only finding. Do not plan tool implementation changes in Phase 09 unless a later plan adds concrete tool implementation files and tests.

The assessment should cite request ids and local evidence paths for every failure mode. Avoid aggregate-only verdicts, old factor-count thresholds, or long raw provider excerpts.

## Test Pattern Assignments

### Selection and posterior tests: `tests/test_delta_portfolio.py`

**Analog:** same file.

**Helper pattern** (lines 34-63):
```python
def _make_row(
    *,
    delta_id: str = "D-1",
    target_skill: str = "personalized-copy-generation",
    applicable_surface: list[str] | None = None,
    sample_count: int = 0,
    success_count: int = 0,
    failure_count: int = 0,
    belief_alpha: float = 1.0,
    belief_beta: float = 1.0,
    token_cost_delta_sum: int = 0,
    status: str = "experimental",
) -> DeltaPortfolioRow:
    return DeltaPortfolioRow(...)
```

**Pure-update assertions** (lines 108-123):
```python
def test_update_after_trial_success_increments_alpha_and_counts() -> None:
    row = _make_row()
    out = update_after_trial(row, success=True, token_cost_delta=12)

    assert out.belief_alpha == pytest.approx(2.0)
    assert out.belief_beta == pytest.approx(1.0)
    assert out.sample_count == 1
    ...
    assert row.sample_count == 0
```

**Phase 9 direction:** Mirror the helper style and deterministic `random.Random` injection. Replace tests asserting token pressure/probability skips with tests for allowed `no_trial_reason`, evidence insufficiency trigger, evidence-sufficient no-trial, and Thompson sampling over eligible experimental deltas. Add anti-cheat assertions that selector signatures/results contain no `token_budget_pressure`, `production_pressure`, or `trial_prob`.

### Runner integration tests: `tests/test_validation_runner.py`

**Analog:** same file.

**Current skip snapshot assertions to replace** (lines 715-722):
```python
assert record["exception"] is None
assert record["trial_selected_delta_id"] is None
assert not (tmp_path / "portfolio_journal.jsonl").exists()
snapshot = _read_snapshot(tmp_path / "req-skip")
assert snapshot["trial_gate"]["selected_delta_id"] is None
assert snapshot["trial_gate"]["eligible_delta_count"] == 1
assert snapshot["trial_gate"]["trial_prob"] == 0.0
```

**Current trial workspace / journal assertions to keep and update** (lines 751-763):
```python
assert record["exception"] is None
assert record["trial_selected_delta_id"] == "D-live"
assert (tmp_path / "req-trial/trial_workspace/_baseline").exists()
assert (tmp_path / "req-trial/trial_workspace/D-live").exists()
entries = read_journal_entries(journal_path)
assert len(entries) == 1
assert entries[0].delta_id == "D-live"
...
snapshot = _read_snapshot(tmp_path / "req-trial")
assert snapshot["trial_gate"]["selected_delta_id"] == "D-live"
```

**Stage fold test pattern** (lines 766-793):
```python
def test_fold_portfolio_journal_at_stage_boundary(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "WorkflowRuntime", _FakeRuntime)
    monkeypatch.setattr(runner, "_signal_window", _AlwaysTrialSignalWindow())
    monkeypatch.setitem(runner._STAGE_CONFIG, 2, (1, 1))
    ...
    result = runner._run_stage(...)

    assert result.passed is True
    assert portfolio[0].sample_count == 1
```

**Phase 9 direction:** Keep monkeypatch/FakeRuntime style. Update assertions to `exploration_decision`, `no_trial_reason`, folded M5 visibility in `batch_summary.json`, and rubric-only reward journal fields. Add negative checks for forbidden fields in snapshots.

### Reward tests: `tests/test_uplift.py` and `tests/test_models_rubric.py`

**Analog:** `tests/test_uplift.py`; typed rubric construction from `tests/test_models_rubric.py`.

**Old reward tests to replace** (`tests/test_uplift.py` lines 11-22):
```python
def test_uplift_strict_positive() -> None:
    uplift = compute_uplift(
        _outcome(success=False, tokens=1_200),
        _outcome(success=True, tokens=1_000),
        behavioral_metrics_baseline={"anchor_diversity": 0.2},
        behavioral_metrics_trial={"anchor_diversity": 0.3},
    )

    assert uplift.success_lift == 1
    assert uplift.token_cost_delta == -200
    assert uplift.behavioral_metric_lift == {"anchor_diversity": 0.1}
    assert uplift.is_positive is True
```

**Rubric test construction pattern** (`tests/test_models_rubric.py` lines 31-50):
```python
judgment = PersonalizedCopyRubricJudgment(
    candidate_id="c0",
    candidate_index=0,
    product_id="p1",
    copy_text="带娃晒一天，回家脸也不狼狈",
    factor_id="f1",
    axis_scores=[
        _axis("factor_alignment", 5),
        _axis("personalized_distinction", 4),
        _axis("slogan_quality", 5),
        _axis("product_relevance", 4),
        _axis("naturalness", 5),
    ],
    total_score=23,
    decision="admit",
    main_strength="scene result is vivid",
    main_weakness="product value could be sharper",
    failure_tags=[],
)
```

**Phase 9 direction:** Rewrite reward tests around `PersonalizedCopyRubricArtifact` with candidate total-score means. Include empty-judgment edge case, equal-score no-success case, trial lower-score failure, and token/behavioral metrics proving record-only non-influence.

### Journal tests: `tests/test_portfolio_journal.py`

**Analog:** same file.

**Append/fold pattern** (lines 30-38, 59-73):
```python
def _entry(delta_id: str = "D-1", success: bool = True, token_cost_delta: int = 0) -> PortfolioJournalEntry:
    return PortfolioJournalEntry(
        request_id="R-1",
        delta_id=delta_id,
        success=success,
        token_cost_delta=token_cost_delta,
        behavioral_metric_lift={"m": 0.1},
        ts="2026-05-28T00:00:00Z",
    )

def test_fold_portfolio_journal_replays_in_order(tmp_path) -> None:
    ...
    assert folded[0].sample_count == 3
    assert folded[0].success_count == 2
    assert folded[0].failure_count == 1
    assert folded[0].token_cost_delta_sum == 27
```

**Phase 9 direction:** Keep JSONL atomic append, missing journal, unknown delta, and extra-field tests. If entry model gains rubric score means, add tests proving fold still updates alpha/beta solely from `success`.

### Behavioral/summary tests: `tests/test_08_07_behavioral_metrics.py` and `tests/test_batch_summary_writer.py`

**Analog:** both files.

**Behavioral M5 assertion pattern** (`tests/test_08_07_behavioral_metrics.py` lines 120-139):
```python
report = build_behavioral_report(stage_dir)

assert set(report) == {
    "factor_count_p50",
    "factor_diversity_score",
    "copy_candidate_count_p50",
    "reflection_triggered_when_underspec_rate",
    "delta_diversity_score",
    "trial_belief_update_count",
}
...
assert report["trial_belief_update_count"] == 1
```

**Summary helper pattern** (`tests/test_batch_summary_writer.py` lines 22-37):
```python
def _write_summary(tmp_path, rows):
    index_path = tmp_path / "index.json"
    index_path.write_text(
        json.dumps(
            {
                "stage": 1,
                "batch_id": "batch-test",
                "requests": rows,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    write_batch_summary(index_path)
    return json.loads((tmp_path / "batch_summary.json").read_text(encoding="utf-8"))
```

**Phase 9 direction:** Add a summary-order regression: write a journal row, run/fold stage, then assert `batch_summary.json["behavioral_metrics"]["trial_belief_update_count"] > 0`. Update acceptance expectations so factor count, cache miss, and token use remain reported but are not phase-blocking gates.

### Status tests: `tests/test_status_machine.py`

**Analog:** same file.

**Current token-cost block test to revise** (lines 74-82):
```python
def test_apply_status_transitions_blocks_promotion_on_token_cost() -> None:
    row = _row(sample_count=20, success_count=18, failure_count=2)

    out = apply_status_transitions(
        [row],
        token_cost_deltas_by_delta={"D-1": [5_000, 6_000, 7_000, 8_000, 9_000]},
    )

    assert out[0].status == "experimental"
```

**Phase 9 direction:** Preserve `wilson_lcb`, promote, reject, insufficient-samples tests. Replace or remove token-cost blocking test depending on planner threshold decision; D9 strongly points to token cost as record-only.

### Phase 09 anti-cheat gates: `tests/test_phase09_acceptance_gates.py`

**Analog:** `tests/test_workflow_progress.py`, `tests/test_promotion_smoke.py`, and `tests/test_models_no_self_rated_fields.py`

**Source-scan hygiene pattern:** Reconstruct forbidden strings from fragments or scan only production files so the test's own explanatory prose cannot trip the gate. Follow the `test_workflow_progress.py` pattern of keeping scanned paths explicit and excluding tests/planning docs when checking production source.

**Phase 9 direction:** Scan `seers_harness/evolution` and `seers_harness/validation` production files for forbidden exploration shortcuts: token pressure as selection input, production/concurrency pressure as selection input, old trial probability field, static probability skip, random skip, hardcoded trial forcing, and artificial/manual priors. Require live identifiers for `exploration_decision`, selected delta evidence, journal append, `fold_portfolio_journal`, and `trial_belief_update_count`.

Reward checks should inspect `seers_harness/evolution/uplift.py` for typed rubric provenance (`PersonalizedCopyRubricArtifact`, `baseline_mean_rubric_score`, `trial_mean_rubric_score`) and absence of self-rated reward names. Factor count, cache miss, token use, and fixed trial count may appear as records, but must not appear as pass/fail acceptance gates.

### Phase 09 SKILL contract gates: `tests/test_phase09_skill_contract.py`

**Analog:** `tests/test_skill_loader.py`, `tests/test_evolution_tools.py`, and `tests/test_models_no_self_rated_fields.py`

**Phase 9 direction:** Scan only `workflow-skills/current/personalized-copy-generation/SKILL.md`. Positive checks should require merged-path language, staged factor/copy state, `source_factor_id` linkage, plural/distinctness guidance, and red flags for single-angle collapse, duplicate factors, and copy-before-factor behavior if a repair is applied.

Negative checks must block hard numeric factor thresholds, internal examples, JSON skeletons, ellipsis templates, enumeration/taxonomy prompting, new tool implementation language, and production split-node rollback. Keep this as a prose-contract test; do not import runtime code or execute model calls.

### Trial runner integration: `tests/test_trial_runner.py`

**Analog:** same file.

**Selection + trial workspace integration pattern** (lines 329-367):
```python
selected = select_trial_delta(
    portfolio=portfolio,
    applicable_surface=["personalized_copy_generation"],
    recent_failure_rate=0.0,
    token_budget_pressure=0.0,
    production_pressure=0.0,
    rng=random.Random(7),
)
assert selected == "D-INT-1"
...
outcome = run_request_trial(...)
updated = update_after_trial(
    portfolio[0],
    success=outcome.success,
    token_cost_delta=outcome.token_cost_observed,
)
assert updated.sample_count == 1
```

**Phase 9 direction:** Update for new selection decision API and keep the invariant that live skill root remains unchanged after trial.

## Shared Patterns

### Pydantic Contract Pattern

**Source:** `seers_harness/evolution/delta_portfolio.py` lines 83-111; `seers_harness/domain/models.py` lines 64-117

Apply `model_config = {"extra": "forbid"}` to durable evolution/rubric payloads. Use typed artifacts for reward provenance; do not persist unvalidated model self-judgment.

### Pure State Transform Pattern

**Source:** `seers_harness/evolution/delta_portfolio.py` lines 193-220; `seers_harness/evolution/status_machine.py` lines 36-70

Return copied rows/lists rather than mutating source rows inside helpers. Runner may assign `delta_portfolio[:] = ...` at orchestration boundaries.

### JSON/JSONL File-I/O Pattern

**Source:** `seers_harness/evolution/portfolio_journal.py` lines 26-42; `seers_harness/validation/batch_summary_writer.py` lines 179-183

Create parent directories, use UTF-8, write indented JSON with trailing newline for summary/snapshot artifacts, and JSONL append for journal events.

### Event Reducer Pattern

**Source:** `seers_harness/validation/evolution_snapshot.py` lines 61-73 and 74-133

Snapshot reducers tolerate missing/malformed event streams, ignore unknown events, and redact exception messages. Add `exploration_decision` as a new reducer branch rather than making snapshot writing validate business logic.

### Trial Workspace Pattern

**Source:** `seers_harness/validation/runner.py` lines 869-898; `seers_harness/evolution/trial_runner.py` lines 185-301

Run baseline and patched trial in sibling workspaces under `request_dir / "trial_workspace"`. Live skill files are not modified; `run_request_trial` restores `runtime.skill_root` in `finally`.

### Manual Case-Reading Pattern

**Source:** `.planning/phases/07-real-llm-validation/case_analysis_template.md` lines 5-13, 43-73, 245-257

Machine columns navigate; human reading supplies verdicts. Phase 9 case reading must open scenario, generation artifact, generation tool calls, rubric artifact, and snapshot/journal evidence for each sampled request.

## No Analog Found

All planned files have usable local analogs. The closest analog for the new Phase 9 case-reading artifact is Phase 7's `case_analysis_template.md`; adapt it down to the 5-8 request scope rather than copying its full VAL-05 structure.

## Metadata

**Analog search scope:** `seers_harness/evolution`, `seers_harness/validation`, `seers_harness/domain`, `workflow-skills/current`, `tests`, `.planning/phases/07-real-llm-validation`

**Files scanned:** 40+ targeted files via `rg --files`, `rg`, `wc -l`, and line-numbered reads.

**Pattern extraction date:** 2026-05-29

**Important negative patterns:** Do not copy `token_budget_pressure`, `production_pressure`, `trial_prob`, token-cost status blocking, behavioral-metric reward, or fixed trial-count acceptance into Phase 9 implementation.
