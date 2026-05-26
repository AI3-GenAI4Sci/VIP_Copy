# Phase 7: Real-LLM Validation - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 7 produces evidence-grade real-LLM validation against DeepSeek
`deepseek-v4-pro` at `/beta` with `reasoning_effort="max"` + thinking
enabled. The harness is built (Phases 1-6); this phase **generates
auditable evidence** that VAL-01..06 (REQUIREMENTS.md L107-112) actually
hold under model unpredictability.

Phase 7 delivers:

1. A three-stage real-LLM run mechanism (single-request bring-up → 20×
   serial main evidence → real-concurrency sample) wired to
   `data_100k.csv` via the existing `intake.preprocess_request_from_csv`
   path.
2. Per-request, per-node evidence capture: full message trajectory
   (with `reasoning_content` echoes), tool-call sequence, final
   artifact, `last_usage` snapshot, and evolution-system state snapshot
   (trial-selection, reflow events, `delta_portfolio` before/after).
3. A machine-readable batch index (`index.json` / `batch_summary.json`)
   that lets downstream case-analysis navigate to specific requests by
   VAL-relevant criteria.
4. A `case_analysis.md` audit artifact in
   `.planning/phases/07-real-llm-validation/` that records **only
   user-confirmed conclusions** for VAL-03 / VAL-05 / VAL-06.
5. Validation that the Phase 6 evolution chain (delta portfolio,
   trial scheduler, reflow cadence) reaches its full path under real
   LLM behavior — including the case where the seed-from-buffer flow
   produces zero trials in 20 requests.

`harness-runtime/` is **out of scope**. Phase 7 does not edit or
import from runtime. Phase 7 also does NOT tune real-DeepSeek
concurrency limiters or build a circuit breaker — D-19 / D-21 from
Phase 6 hold; Phase 7's stage 3 only **observes** real-concurrency
behavior, it does not stabilise it.

</domain>

<decisions>
## Implementation Decisions

### Run mechanics — concurrency, retry, fail-fast

- **D-01:** Phase 7 runs in three stages, in order:
  - **Stage 1**: N=1, concurrency=1 — single-request bring-up. Proves
    one real DeepSeek request completes the 3-node DAG with all
    `submit_*_final` reached and artifacts validating under
    `extra="forbid"`. Failure ⇒ stop, do not advance.
  - **Stage 2**: N=20, concurrency=1 — serial main evidence set. This
    is the **principal evidence** for VAL-01..05.
  - **Stage 3**: N=20, real concurrency targeting 20 (or stepped
    4 → 8 → 20 inside the stage if planner judges intermediate
    samples are needed). Validates that Phase 6's FakeProvider-verified
    concurrency safety holds under real provider behavior, and surfaces
    real DeepSeek rate-limit ceilings as observable facts.
- **D-02:** **Fail-fast at request level.** Any single request that is
  judged "failed" terminates the current stage immediately; partial
  artifacts already on disk are kept as the failure scene. Acceptance
  is anchored to **20/20 clean** for stages 2 and 3.
- **D-03:** **SDK retry budget = 3** (`max_retries=3` on the OpenAI
  client). The OpenAI SDK's exponential backoff absorbs transient
  429 / 5xx within this budget. Exceeding the budget ⇒ request judged
  failed ⇒ stage stops (D-02). No additional wrapper retry on top.
- **D-04:** Stage 3 may mask real concurrency-induced rate ceilings
  because `max_retries=3` runs per-request and 20 concurrent requests
  collectively get 60 retries of slack. This is acknowledged
  explicitly: Phase 7 stage 3 is observation, not stabilisation. Real
  concurrency tuning is deferred.
- **D-05:** **No additional pre-flight gating** beyond Stage 1. Stage 1
  passing is the only checkpoint before Stages 2 and 3.
- **D-06:** **No single-request token hard cap.** `tool_loop`'s existing
  max-iteration guard is the sole death-loop defense. Token usage is
  recorded in evidence (`last_usage`) but not gated.
- **D-07:** **Stages run end-to-end automatically** with no inter-stage
  human checkpoint. Case analysis happens after the full run completes
  (D-19), not between stages. Worst case: a stage-3 failure on request
  N burns ~21 + N real requests of token spend; this is a known
  cost, not a bug.

### Evidence capture — what gets written, where, how

- **D-08:** Each request persists, **per node**: final artifact JSON +
  full `messages[]` trajectory (including echoed `reasoning_content`)
  + extracted `tool_calls[]` sequence + `last_usage` snapshot. Per
  request also persists an `evolution_snapshot.json` covering trial
  selection state, reflow event records, and `delta_portfolio` before/
  after deltas (not just artifacts).
- **D-09:** All run output writes to `tests/smoke/.runs/<timestamp>/`,
  **git-ignored**. No canonical run is copied into the repository.
  Known consequence: deep trajectories live only on the runner's local
  disk; long-after-the-fact full-trajectory audits are not possible
  without re-running.
- **D-10:** Per-request layout uses one directory per request, one file
  per concern (machine-friendly), with separate files for messages,
  tool calls, artifact, usage. Top-level `index.json` and
  `batch_summary.json` are mandatory and machine-first (not Markdown):
  - `index.json` carries stage (1/2/3), concurrency, N, start/end
    timestamps, pass/fail counts, and a path to `batch_summary.json`.
  - `batch_summary.json` carries one row per request with
    `request_id`, per-node pass/fail, token usage, reflow trigger,
    trial-selection flag — sortable by VAL-relevant criteria.
- **D-11:** Phase 6 evolution modules (`delta_portfolio`,
  `trial_scheduler`, `reflow`) need lightweight observability hooks
  (write trial-selection flag, reflow event, portfolio
  before/after to the evidence dir). If those hooks are not yet
  exposed in the Phase 6 implementation, Phase 7 plan **adds the
  hook layer first** (no business-logic change).

### Acceptance shape — what counts as "Phase 7 passed"

- **D-12:** VAL-01 / VAL-02 / VAL-04 are **machine-judged**:
  - VAL-01: `index.json` reports N=20 stage-2 + N=20 stage-3 with all
    real DeepSeek calls accounted for.
  - VAL-02: `batch_summary.json` shows tool-call count ≥ 1 for every
    request.
  - VAL-04: Pydantic `extra="forbid"` validation + Phase 5 workspace-
    wide grep gate (Arabic digits / state-label leakage / user-history
    tokens) cover this; zero exceptions = pass.
- **D-13:** VAL-03 / VAL-05 / VAL-06 are **statistics-then-case-
  analysis**: machine statistics in `batch_summary.json` *navigate* to
  cases that need reading; the verdict is **manual case reading
  confirmed by the user**. No pass-rate threshold. (See
  [[feedback-case-analysis-over-metrics]] for the underlying rule.)
- **D-14:** `.planning/phases/07-real-llm-validation/case_analysis.md`
  is the **sole in-tree audit artifact** (raw `.runs/` is local-only
  per D-09). It contains **only user-confirmed conclusions**. Agents
  may surface observations as "待你确认的观察" in working notes; those
  do not enter `case_analysis.md` until the user agrees explicitly.
- **D-15:** `case_analysis.md` is structured by VAL section. The
  VAL-05 section has **fixed sub-headings for four "fake-transferable"
  failure shapes (F1-F4)**:
  - F1: Specific case wrapped in generic-sounding language.
  - F2: Causal chain broken between `user_side_signal` and
    `bridge_to_product`.
  - F3: Boilerplate-template `transferable_disposition` text untethered
    to a real signal.
  - F4: `covers_product_ids` claims multi-product reach but
    `transferable_disposition` only explains one.
  Additional shapes may be appended at the user's discretion.
- **D-16:** VAL-05 case sampling is **stratified**: at least one factor
  read per request (covers all 20) **plus extreme samples by four
  machine-rankable dimensions (E1-E4)**:
  - E1: longest `covers_product_ids`.
  - E2: shortest `transferable_disposition` text.
  - E3: longest `transferable_disposition` text.
  - E4: highest literal overlap between `user_side_signal` and
    `transferable_disposition`.
  Total reading scope ≈ 20-30 factors. `batch_summary.json` MUST
  expose these four sortable columns.

### Evolution wiring — VAL-06 path under real LLM

- **D-17:** **Evolution system fully ON in Phase 7.** trial_scheduler
  runs, trials apply real deltas, reflow fires by Phase 6 cadence,
  portfolio state updates. VAL-06 evidence is "production-shape"
  evidence, not replay.
- **D-18:** **Portfolio starts empty.** Deltas are produced
  in-flight by `distill-skill-deltas` from the trajectory buffer as
  Stage 2 / Stage 3 proceed. Stage 1 (N=1) and the early requests of
  Stage 2 will almost certainly produce **zero trials** — this is
  expected, not a VAL-06 failure. The plan must state this explicitly,
  and the user-confirmed conclusion in `case_analysis.md` decides
  whether the observed trial count is reasonable for the sequence.
- **D-19:** **Trial failure routing by error class:**
  - Schema / tool-protocol errors inside a trial ⇒ that trial's host
    request is judged failed ⇒ stage stops (D-02). Reason: a
    delta breaking the schema is a real finding, not noise.
  - Rate-limit / transient errors inside a trial ⇒ recorded against
    that delta's `belief` / failure history; host request continues
    on the unmodified main path.
- **D-20:** **Trial trigger uses Phase 6's portfolio-adaptive logic
  unmodified.** No artificial cadence boost for VAL-06 readability;
  zero observed trials in 20 requests is a legitimate observation.
- **D-21:** **Trial isolation reuses Phase 6's existing
  `shutil.copytree` temp-dir mechanism** (`evolution/trial_runner.py`,
  `apply_delta_patch_temporarily`). Phase 7 does **not** rebuild
  isolation. Worktree-based isolation evaluation is deferred to the
  pre-deployment ADR review (see Deferred).

### Claude's Discretion

- **D-22:** Planner chooses (a) Stage 3 stepping policy (one shot at
  c=20 vs intermediate 4 / 8 samples) based on Stage 2 evidence and
  recorded DeepSeek rate-limit facts from Phase 6 (PROD-02 summary);
  (b) exact filenames inside the per-request directory; (c) whether
  the observability hooks (D-11) live in `evolution/` or in a thin
  wrapper module; (d) whether `batch_summary.json` is built
  on-the-fly per request or post-batch from per-request files; (e)
  the runner entry point's location (extension to
  `tests/smoke/test_e2e_smoke.py`, new module under
  `seers_harness/`, or a CLI under `intake/__main__.py`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project authority
- `.planning/PROJECT.md` — workspace-only development; runtime untouched;
  non-negotiable tool-use decisions.
- `.planning/REQUIREMENTS.md` — VAL-01..06 plus Out-of-scope boundary
  (no `generate_json`, no LLM self-rated fields, no roleplay/click-rate
  validation, no reference-v2 emitter).
- `.planning/ROADMAP.md` — Phase 7 acceptance criteria; dependency on
  Phase 6.
- `.planning/STATE.md` — current 251-test baseline and Phase-completion
  log through Phase 6.

### Locked ADRs
- `.planning/intel/decisions.md`:
  - **ADR-PROBE-7.1.1** — current DeepSeek runtime config
    (`deepseek-v4-pro`, `/beta`, `reasoning_effort="max"`, thinking
    enabled, `tool_choice="auto"`, no `temperature`,
    `reasoning_content` must be echoed in multi-turn). MANDATORY for
    Phase 7 — Phase 7 does not change these parameters.
  - **ADR-RUNTIME-BATCH** — batch=20 for §7.10 real-LLM validation.
    Anchors D-01.
  - **ADR-01-PRINCIPLE-06** — real LLM, real data, never fake certainty.
    Anchors D-12 / D-13 (no fabricated pass-rate thresholds).
  - **ADR-01-PRINCIPLE-04** — anti-sycophancy. Anchors D-14 (agent must
    not unilaterally affirm "transferable" verdicts; user confirms).
  - **ADR-01-PRINCIPLE-03** — no internal-meme examples / numeric
    thresholds / enumerations. Backstops VAL-04 + VAL-05 F1-F4
    (D-15) — most "fake-transferable" patterns are violations of this
    principle that escaped grep.
  - **ADR-PROCESS-PROACTIVE-RESEARCH** — verify external API behavior
    against current docs. Phase 7 inherits Phase 6's PROD-02 rate-limit
    fact recording; if anything in DeepSeek `/beta` strict-tools
    behavior has shifted, plan must verify before scheduling Stage 3.
  - **ADR-PROCESS-SKILL-ORCHESTRATION** — PLAN.md must enumerate
    skills used. Phase 7 expects: `verification-before-completion`,
    `error-analysis` / `eval-audit` (case analysis), `claude-api`
    (DeepSeek tool-use behavior), `gsd-verify-work`,
    `using-git-worktrees` (only for the runner's working
    isolation, not for trial isolation per D-21),
    `dispatching-parallel-agents` if stage runners + analysis fan out.

### Prior phase context
- `.planning/phases/05-cleanup-deletes-tests-regression/05-CONTEXT.md` —
  D-09 / D-10 / D-11 (smoke link shape, intake load-bearing, single-
  threaded baseline). Phase 7 is the explicit "real-LLM" follow-up the
  Phase-5 deferred list pointed to.
- `.planning/phases/06-evolution-chain-production-hardening/06-CONTEXT.md`
   — D-17 (trial isolation), D-18 (concurrency safety), D-21 (rate-limit
   facts), D-22 (promotion smoke). Phase 7 consumes Phase 6's evolution
   surface live.

### Workspace code Phase 7 will integrate against
- `tests/smoke/test_e2e_smoke.py` — existing 20-request scratch-CSV
  pattern (FakeProvider). Phase 7 reuses the scenario-selection /
  scratch-CSV approach but swaps the provider and expands evidence
  capture.
- `tests/smoke/test_concurrency_smoke.py` — Phase 6's concurrency-20
  FakeProvider pattern; Stage 3 of Phase 7 mirrors its structure.
- `tests/smoke/scripted_full_chain.py` — full-chain wiring helper. Phase
  7 uses the *real* provider in this position; ScriptedProvider stays
  in fakes.
- `tests/fakes/scripted_provider.py` — out of Phase 7's runtime path
  (real LLM only); referenced for test-side fakes preservation.
- `seers_harness/provider_runtime/openai_compatible.py` — the single
  real-DeepSeek entry point. `last_usage` is already populated per call
  and is a Phase 7 evidence source. `max_retries` is Phase 7's only
  retry knob (D-03).
- `seers_harness/agentic/tool_loop.py` — owns max-iteration guard
  (D-06's sole death-loop defense) and the multi-turn `reasoning_content`
  echoing.
- `seers_harness/workflow/dag_runner.py` — `_run_node` boundary; Phase 7
  evidence layer attaches around it without changing it.
- `seers_harness/workflow/payloads.py` — payload construction; not
  modified by Phase 7.
- `seers_harness/domain/models.py` — `extra="forbid"` schemas; the VAL-04
  structural backstop.
- `seers_harness/intake/{request_preprocessor.py,categories.py,
  features.py,__main__.py}` — CSV → scenario path. Phase 7 selects 20
  unique `request_id`s using the existing scratch-CSV technique.
- `seers_harness/evolution/trial_runner.py` —
  `apply_delta_patch_temporarily` is Phase 7's trial isolation surface
  (D-21); not modified.
- `seers_harness/evolution/delta_portfolio.py` — observability hooks
  for D-11 attach here.
- `seers_harness/tools/skill_tools.py` — handler set including
  `reflect_on_coverage` / `reflect_on_diversity` (mirror handlers,
  fixed string returns). VAL-03 evidence comes from observing whether
  the model invokes these in real runs.
- `workflow-skills/current/{discover-personalization-factors,
  generate-copy-candidates,personalized-copy-rubric-judge}/SKILL.md` —
  the SKILL prose that drives real-LLM behavior. Phase 7 must NOT edit
  these (Phase 4 lock); deltas may be proposed via the evolution
  system per D-17 / D-18.
- `data_100k.csv` — input scenarios (Phase 5 D-10 pattern).
- `.env.local` — DeepSeek credentials (`DEEPSEEK_API_KEY`).

### External spec verification
- DeepSeek `/beta` strict-tools + `reasoning_effort=max` + thinking
  behavior — verify against current DeepSeek docs (per
  ADR-PROCESS-PROACTIVE-RESEARCH) before scheduling Stage 2/3 if
  anything in Phase 6's PROD-02 summary is more than a few weeks old.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/smoke/test_e2e_smoke.py` already implements the 20-request
  scratch-CSV pattern (one pass over `data_100k.csv`, capture first 20
  unique `request_id`s, write a small scratch CSV, preprocess each).
  Phase 7 should extend this exactly — do not invent a parallel
  scenario-selection path.
- `tests/smoke/test_concurrency_smoke.py` is the structural template for
  Stage 3. The provider swap is the key change; concurrency primitives
  (Phase 6 work) stay.
- `provider_runtime/openai_compatible.py` already populates `last_usage`
  per call — Phase 7 reads it as the per-call token-usage source. No
  provider rewrite.
- `evolution/trial_runner.apply_delta_patch_temporarily` (`shutil.copytree`
  + SHA-256 lock + finally-restore) already provides trial isolation
  meeting Phase 7's audit needs. D-21 reuses it as-is.
- `tool_loop` already echoes `reasoning_content` across multi-turn calls
  (ADR-PROBE-7.1.1 protocol note); the captured `messages[]` will
  contain reasoning trace as part of evidence.

### Established Patterns
- One provider path: `generate_with_tools` only (Phase 2 lock).
  Phase 7 calls real DeepSeek through this same surface.
- Tool handlers do not contain domain judgment; mirror handlers
  (`reflect_*`) return fixed strings. Phase 7 observes the model's
  *choice* to invoke them — the handlers themselves stay unchanged.
- Pydantic `extra="forbid"` is the artifact contract. VAL-04's
  zero-leakage check is structural — failures are validation
  exceptions, not soft warnings.
- Workspace-wide forbidden-token grep gate (Phase 5) backstops
  internal-meme / numeric-threshold leakage in any prose surface
  (artifact JSON included).

### Integration Points
- **Real-provider entry**: `OpenAICompatibleProvider` instantiated with
  the `.env.local` API key, `model=deepseek-v4-pro`,
  `base_url=https://api.deepseek.com/beta`, `max_retries=3`. Plug into
  the existing `tests/smoke/scripted_full_chain` shape (the runtime
  half) replacing `ScriptedProvider`.
- **Evidence-capture wrapper**: a thin observation layer around
  `dag_runner._run_node` and `tool_loop.run_skill_via_tools` that
  writes `messages.jsonl` / `tool_calls.jsonl` / `artifact.json` /
  `usage.json` per node — without changing the runner contract.
- **Evolution observability**: lightweight hook (event emit + JSON
  append) inside `delta_portfolio` and `trial_runner` recording the
  per-request decision (selected for trial? which delta? trial outcome?
  belief update?). Plus a single `evolution_snapshot.json` per request
  capturing portfolio before/after.
- **Stage runner**: a single CLI/test-runner that takes a `stage`
  argument, builds the appropriate (N, concurrency) configuration, and
  drives the real-LLM batch. Stages run sequentially in the same
  invocation per D-07.

</code_context>

<specifics>
## Specific Ideas

- "C：分阶段。把'跑通'和'压测'拆开" — three-stage execution; one bring-up
  request, then 20 serial, then real concurrency target 20.
  (User, 2026-05-26.)
- "Trial 失败按类型分流" — D-19 was explicitly chosen over both "trial
  failure stops batch" and "trial failure never stops batch"; user wants
  schema/protocol failures inside trials to count, transient ones not.
  (User, 2026-05-26.)
- "首先我要批评 hand eye mirror 这种硬分类设计" — user pushed back on the
  hand/eye/mirror taxonomy in ADR-01-PRINCIPLE-01. Phase 7 is not the
  window to overturn it (precedence-0 lock) but the critique is recorded
  as a future-review candidate for ADR consolidation. See
  [[feedback-flat-design-over-taxonomy]]. (User, 2026-05-26.)
- "比起指标通过率, 我更看重真实case分析" — case analysis over
  pass-rate thresholds is the explicit user-stated principle for VAL-03/
  05/06. See [[feedback-case-analysis-over-metrics]]. (User, 2026-05-26.)
- "可以作为审计证据, 但必须是与我沟通确认的可信结论才能进证据" —
  `case_analysis.md` admits only user-confirmed conclusions. Anchors
  D-14. (User, 2026-05-26.)
- "B (`shutil.copytree`), 但内网部署 A (worktree) 我认为最好" — current
  implementation reused for Phase 7; worktree upgrade deferred to
  pre-deployment ADR review. Anchors D-21 + Deferred entry.
  (User, 2026-05-26.)

</specifics>

<deferred>
## Deferred Ideas

- **Real-DeepSeek concurrency tuning / rate-limit stabilisation** —
  Stage 3 only observes; building a limiter / circuit breaker / adaptive
  concurrency controller is a follow-up phase. Phase 7's `max_retries=3`
  + fail-fast posture explicitly does not address production-grade
  rate-limit absorption.
- **Trial isolation upgrade to git worktree** (with diff history,
  archivable, auditable per-trial commits) — evaluate before internal-
  network deployment. Today's `shutil.copytree` mechanism meets Phase 7
  validation needs but lacks first-class history. Tag as ADR candidate.
- **Hand/eye/mirror taxonomy review** — ADR-01-PRINCIPLE-01 currently
  has an empty `eye` bucket and the underlying rule ("tools must not
  contain domain judgment") is one sentence; review whether the
  three-bucket form earns its overhead vs a single principle. Not
  Phase 7 scope.
- **Fuzzy-match / cross-request cluster sampling for VAL-05** —
  E5(a)/(b) from the discussion (forbid-list near-misses, factor-text
  similarity clusters). Useful enrichment but out of Phase 7 scope;
  E1-E4 are the locked extreme-sample dimensions.
- **In-tree archival of canonical run artifacts** — per D-09 raw
  trajectories live local-only. If Phase 7's case-reading workflow
  later proves we DO want a canonical trajectory archive in-tree,
  revisit the policy.
- **Reference v2 emitter implementation** — Phase 6 design only;
  emitter implementation remains post-Phase-7.
- **Long-running production evolution loop tuning** — Phase 7 only
  validates the loop is *reachable* under real LLM. Tuning trial
  cadence, sedimentation thresholds, and adoption gates is a separate
  follow-up.

</deferred>

---

*Phase: 07-real-llm-validation*
*Context gathered: 2026-05-26*
