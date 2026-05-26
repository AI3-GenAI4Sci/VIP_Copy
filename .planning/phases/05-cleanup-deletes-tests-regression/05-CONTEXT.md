# Phase 5: Cleanup, Deletes, Tests, Regression - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 5 makes the workspace harness coherent under the new C17 tool-use form:

1. Remove all c14/c15/c16 carryover (legacy-tolerance posture, inline comments, copy-from-old-source markers, internal-meme tokens) from `workspace/seers_harness/`, `workspace/tests/`, and `workspace/workflow-skills/current/`.
2. Tighten Pydantic schemas to fail loudly when LLM output drifts from the new tool-call shape.
3. Stand up the **end-to-end smoke link** `data_100k.csv → intake → tool_loop → DAG → stable artifact`, exercised on ≤ 20 requests with FakeProvider, single-threaded, stdout logging only.
4. Verify CLEAN-03 (no surviving hard-check gates outside tool handlers / rubric judge).
5. Pass the existing 122-test baseline plus whatever new tests the smoke link demands.

`harness-runtime/` is **out of scope** for this phase. Workspace = development line; runtime = release line; runtime promotion is a separate, reviewed step that does not happen here. Concurrency, terminal progress UX, and real-LLM batches stay in Phase 6 / Phase 7 — Phase 5 keeps the link single-threaded.

</domain>

<decisions>
## Implementation Decisions

### Architecture posture
- **D-01:** Workspace is the single development line. All C17 development happens in `workspace/`. The `harness-runtime/` tree is not edited, copied from, or compared against during Phase 5. Anything that previously read "promote to runtime" is rewritten as "land in workspace."
- **D-02:** History (c14, c15, c16, prior candidates, prior research branches) contributes **methodology only**, never code. No verbatim re-use, no provenance comments, no "kept for trace" slots. The authoritative residue lives in `docs/methodology.md`, `docs/memory.md`, `docs/rubrics.md`, `docs/design.md`, `docs/history.md` and `.planning/intel/decisions.md` — code must be re-derived from those, not copied from older trees.

### Cleanup scope (CLEAN-01..04, REGRESS-01)
- **D-03:** Inline c14/c15/c16 comments and "verbatim from cN" markers are scrubbed across `workspace/seers_harness/**/*.py` and `workspace/tests/**/*.py`. The `tools/skill_tools.py` "Verbatim helpers from c16 check_tools.py" banner is removed; whatever remains is justified by the current schema, not by historical lineage.
- **D-04:** Internal-meme tokens (Phase 4's lint list — `艾灸 / 维C / B族 / 黄金搭档 / 连衣裙 / 范思哲 / 安热沙 / 维生素 / 钙片 / 鱼油 / 温灸器 / 泡脚` plus the SKILL-level forbidden list) are scrubbed from **all** workspace prose: code comments, docstrings, fixtures, test parametrize labels, and any `docs/` paragraphs that still reference them as live examples. The Phase 4 SKILL lint becomes a workspace-wide grep gate.
- **D-05:** REGRESS-01's literal name list (`storage / assets / evaluation / gates / CLI`) is **not** taken from `harness-runtime/`. The new-architecture form of this sweep is: confirm no module under those names exists in `workspace/seers_harness/` (negative sweep), document that runtime-side equivalents are out of Phase 5 scope, and keep the smoke-link assertion as the positive coverage instead.
- **D-06:** CLEAN-03 hypothesis is taken as the working assumption: no hard-check gate survives outside tool handlers / rubric judge inside `workspace/`. Confirm via single grep pass during research (`STOP_GATE`, `polling`, `self_check`, `hard_check`, `gate_*`); if anything turns up, surface it for explicit delete/keep ruling — do not silently keep.

### Schema discipline
- **D-07:** Every Pydantic BaseModel under `workspace/seers_harness/domain/models.py` (and any other module that builds a tool-arg schema or artifact schema) flips `model_config = {"extra": "ignore"}` → `model_config = {"extra": "forbid"}`. Reasons: (a) ADR-01-PRINCIPLE-08 forbids c14/c15 baggage and `extra="ignore"` *is* that baggage, (b) ADR-01-PRINCIPLE-10 forbids self-rated metric fields and `extra="ignore"` would silently swallow them if a model emits one. Field-set comparison cost is acceptable: SKILL prose was rewritten in Phase 4, so older artifacts are not expected to round-trip; if the 122-test baseline regresses on a forbidden-extra error, the failing fixture is the cleanup target.
- **D-08:** No `strength / confidence / uncertainty / probability / score` field is reintroduced. The `extra="forbid"` flip is the structural enforcement; the rubric is the judgment surface; SKILL prose stays free of self-rating language (already enforced by Phase 4 lint).

### End-to-end smoke link (B1, 20 requests)
- **D-09:** Phase 5 stands up the smoke link `data_100k.csv → intake → tool_loop → DAG → stable artifact` on **≤ 20 requests** with FakeProvider, single-threaded, sequential, stdout logging only. ADR-RUNTIME-BATCH = 20 governs this batch size for both this fake-provider smoke and the real-LLM batch in Phase 7.
- **D-10:** The `intake/` package is **load-bearing**: `categories.py`, `features.py`, `request_preprocessor.py`, `__main__.py` stay. The smoke link wires `preprocess_request_from_csv` into the workflow entry path so `dag_runner` / `tool_loop` consume scenarios produced from the real CSV — not hand-built fixtures. Existing intake tests stay green; new tests cover the wiring point.
- **D-11:** Concurrency, `asyncio.gather`-style fan-out, terminal progress (rich / tqdm), `--no-progress` switches, and any `INFO` / `DEBUG` log routing beyond plain stdout are **deferred to Phase 6** (PROD-01, TERM-01, TERM-02). Phase 5 stays single-threaded — fewer moving parts during the cleanup pass, easier failure attribution, smaller PLAN.md.
- **D-12:** The smoke link surfaces **artifact stability** as its own assertion: 20 sequential requests through FakeProvider must produce 20 final artifacts that pass Pydantic validation under the `extra="forbid"` schema, with no validation errors and no missed `submit_*_final` calls. This is the operational definition of "stable produce."

### Method (skills used at plan time)
- **D-13:** Per ADR-PROCESS-SKILL-ORCHESTRATION, PLAN.md must enumerate which Claude Code skills are used. Phase 5 expects: `verification-before-completion`, `systematic-debugging`, `tdd` for the smoke-link wiring, `dispatching-parallel-agents` if the cleanup grep + scrub fans out across many files independently, `gsd-code-review` and `gsd-verify-work` at wrap-up.

### Claude's Discretion
- **D-14:** Choice of grep tooling, exact deletion order, how cleanup commits are sliced (per file vs per concern), whether scrub passes use `Edit` per file or one `sed`-style pass, where the smoke-link entry point lives (`tests/smoke/`, `seers_harness/intake/__main__.py`, or a new `smoke_runner` module), and whether to use `pytest -m smoke` or a separate runner. Decide during planning based on diff cleanliness.
- **D-15:** The `extra="forbid"` flip can be a single mechanical commit if the 122-test baseline holds, or a series of per-model commits if any test regresses and needs fixture cleanup first. Planner picks based on the actual regression pattern surfaced when the change is made.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` — Phase 5 acceptance criteria; phase split that locks concurrency / progress UX into Phase 6
- `.planning/REQUIREMENTS.md` — CLEAN-01..04, TEST-01..06 (already Complete), REGRESS-01
- `.planning/STATE.md` — current 122-test baseline, watchlist items the phase must close
- `.planning/PROJECT.md` — non-negotiable decisions table; workspace vs runtime boundary

### Locked decisions (read these before writing any code)
- `.planning/intel/decisions.md` — full ADR set; especially:
  - ADR-01-PRINCIPLE-08 (no c14/c15 compat baggage) — drives D-02, D-03, D-07
  - ADR-01-PRINCIPLE-10 (no LLM self-rated metric fields) — drives D-07, D-08
  - ADR-01-METHODOLOGY-MAPPING — DROP list defines what may not reappear
  - ADR-RUNTIME-BATCH — 20-request cap, governs D-09
  - ADR-PROCESS-SKILL-ORCHESTRATION — drives D-13
- `docs/methodology.md` — distilled methodology (transferable disposition, critique-before-verdict, user-history token ban); the only legitimate source for "what the old SKILLs taught us"
- `docs/memory.md`, `docs/rubrics.md` — durable cross-iteration memory and judging standards
- `docs/design.md` — current implementation detail; ADR-PROBE-7.1.1 runtime config
- `docs/history.md` — historical provenance ONLY; not a code source

### Phase 4 outputs (the new SKILL surface that Phase 5 must keep coherent with)
- `workspace/workflow-skills/current/discover-personalization-factors/SKILL.md`
- `workspace/workflow-skills/current/generate-copy-candidates/SKILL.md`
- `workspace/workflow-skills/current/personalized-copy-rubric-judge/SKILL.md`
- `.planning/phases/04-skill-md-prose-rewrites/04-SUMMARY.md` — what was kept / dropped, what the lint enforces

### Workspace code surface that Phase 5 will edit
- `workspace/seers_harness/domain/models.py` — `extra="forbid"` flip target
- `workspace/seers_harness/tools/skill_tools.py` — c16 banner removal, schema re-alignment
- `workspace/seers_harness/agentic/tool_loop.py` — smoke-link consumer
- `workspace/seers_harness/workflow/dag_runner.py`, `workflow/payloads.py` — c16 inline comment removal
- `workspace/seers_harness/provider_runtime/{base.py,openai_compatible.py}` — c16 inline comment removal
- `workspace/seers_harness/intake/{__init__.py,__main__.py,categories.py,features.py,request_preprocessor.py}` — wiring into smoke link
- `workspace/tests/**` — 122-test baseline; cleanup of any test that fed forbidden-extra fixtures
- `workspace/data_100k.csv` — input data for the smoke link

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `intake.preprocess_request_from_csv` — already returns a workflow-ready scenario dict with `user_state`, `products`, `target_products`, `derived_features_by_product`, `list_context`. Phase 5 wires it into the workflow entry point; no rewrite needed.
- `tests/fakes/` (referenced by Phase 3 work) — FakeProvider scripts tool-call sequences (TEST-01 Complete). Phase 5 reuses this as the provider for the 20-request smoke link, not real DeepSeek.
- `dag_runner._run_node` — already validates artifacts via `model_type.model_validate(...)`; the `extra="forbid"` flip strengthens this without changing the call site.
- Phase 4 SKILL lint list (internal-meme tokens, forbidden structural headings, forbidden self-rated tokens, forbidden numeric tokens, forbidden tool-loop diagnostics) — reuse as a workspace-wide grep gate, not just SKILL-file lint.

### Established Patterns
- One provider path: `generate_with_tools` only (PROV-01, ADR-01-PRINCIPLE-09). Smoke link wires FakeProvider through this same surface.
- Tool roles fixed at hand / eye / mirror (ADR-01-PRINCIPLE-01). No new tool handlers in Phase 5.
- Pydantic validation is the artifact contract (LOOP-05). The `extra="forbid"` flip is the natural strengthening of this pattern.
- `model_config` is per-model in `domain/models.py`, not inherited from a base. The flip is a mechanical edit per BaseModel definition.

### Integration Points
- **Smoke-link entry**: a single new module (or new test) reads `data_100k.csv`, picks 20 `request_id`s, calls `preprocess_request_from_csv` per id, hands each scenario to `dag_runner` / `tool_loop`, asserts the final tool-call artifact validates under the new `extra="forbid"` schema. Final artifact is captured to disk for inspection but not stored as a fixture.
- **Cleanup grep gate**: the Phase 4 SKILL lint (currently file-scoped) is generalised to a workspace-wide gate run from `pytest` or a `Makefile` target. Forbidden tokens, c14/c15/c16 markers, forbidden self-rated tokens — all enforced as a single lint pass.

</code_context>

<specifics>
## Specific Ideas

- "workspace = development line, runtime = release line. All development happens in workspace. Runtime promotion is not part of Phase 5." (User, 2026-05-26)
- "intake is load-bearing — `data_100k.csv` is the real data, intake is the CSV → system interface. Phase 5 wires the full chain end-to-end." (User, 2026-05-26)
- "Reconstruct against the new harness form. History only contributes conclusions and meta-strategy, not verbatim code." (User, 2026-05-26)
- "Scrub internal memes thoroughly." (User, 2026-05-26)
- "Compare against runtime to figure out what each name (storage/assets/evaluation/gates/CLI) actually means; everything is judged against the new system form, not the old one." (User, 2026-05-26)
- "End-to-end on ≤ 20 requests" (User confirmed against ADR-RUNTIME-BATCH, 2026-05-26)
- "I understand — because SKILLs were rewritten, the JSON output fields are also re-arranged; older artifacts won't necessarily round-trip into the new schema." (User confirming the `extra="forbid"` flip, 2026-05-26)

</specifics>

<deferred>
## Deferred Ideas

- **Concurrency at batch 20** (PROD-01) — Phase 6.
- **Terminal progress UX** (TERM-01, TERM-02 — `rich.Progress`, `--no-progress`, CI-safe plain output) — Phase 6.
- **Structured `INFO` / `DEBUG` logging routing** beyond plain stdout — Phase 6 alongside the progress display.
- **Real DeepSeek rate-limit verification** (PROD-02) — Phase 6.
- **Promotion-chain smoke against `harness-runtime/`** (PROMOTE-01) — Phase 6.
- **Real-LLM 20-request validation** (VAL-01..06) — Phase 7.
- **Reference v2 schema design / emitter** — Phase 6 design only; emitter implementation is post-Phase-7.
- **Runtime promotion of new SKILL files / schema** — separate reviewed step outside the GSD phase order; not Phase 5.
- **Storage / assets / evaluation / gates / CLI runtime modules** (each is its own subpackage in `harness-runtime/`) — Phase 5 negative-sweeps the workspace; positive sweep against the runtime tree is out of the new architecture's scope unless the user explicitly opens it later.
- **Evolution chain rewrites** (EVO-01..06) — Phase 6.

</deferred>

---

*Phase: 05-cleanup-deletes-tests-regression*
*Context gathered: 2026-05-26*
