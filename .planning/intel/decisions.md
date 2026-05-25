# Decisions (Synthesized from ADRs)

All decisions below are LOCKED unless noted. ADRs in this set have precedence=0 (highest) and =1; they outrank any contradicting SPEC/PRD/DOC statement in C17.

---

## ADR-01-PRINCIPLE-01 — Tools as hand/eye/mirror, not brain

**Source**: `docs/methodology.md` §1
**Status**: locked
**Precedence**: 0

Tools serve three roles only: **hand** (`record_*` writes agent output to state to enforce thinking cadence between calls; returns no accumulated state), **eye** (rare; projects only what agent cannot see in its own reasoning context; never re-projects payload fields), **mirror** (`reflect_*` returns a fixed question checklist; never returns verdicts, answers, or facts). Tools hold no domain knowledge (no static lexicons, no scoring rules, no right/wrong returns). The judge is the rubric; SKILL.md describes patterns.

**Scope**: every tool handler in C17 must classify as one of {hand, eye, mirror}; if none, delete.

---

## ADR-01-PRINCIPLE-02 — SKILL is language-built function approximation

**Source**: `docs/methodology.md` §2
**Status**: locked
**Precedence**: 0

Every SKILL prose sentence must answer "deleting it loses which *transferable* pattern?". Reference: Matt Pocock SKILL form — `zoom-out` is one sentence, `grill-me` two sentences; each sentence describes a general pattern, not a checklist, not a number, not a case.

**Scope**: all three C17 SKILL.md files (discover-personalization-factors, generate-copy-candidates, personalized-copy-rubric-judge).

---

## ADR-01-PRINCIPLE-03 — No internal-meme examples / no patch lists / no enumerations

**Source**: `docs/methodology.md` §3
**Status**: locked
**Precedence**: 0

SKILL prose forbids: conversation-distilled concrete examples (艾灸→维生素, 下午加片B族, 维C升级), static word lists (低价/实惠/划算...), numbered enumerations (5-class anchor: cat3/brand/role/scene/verb), numeric thresholds (≥3 drafts, floor=4 axes). Reason: these all patch one specific case, violating "reusable transferable pattern" requirement.

**Scope**: SKILL prose; tool schema enums allowed (e.g., direction trichotomy A6); handler regex for structural numerics allowed (per ADR-03 §B2).

---

## ADR-01-PRINCIPLE-04 — Anti-sycophancy / 90% confidence / judge the user

**Source**: `docs/methodology.md` §4
**Status**: locked
**Precedence**: 0

Before each reply, self-audit each load-bearing claim ≥90% verified; if not, say so. When user is wrong, say "this is wrong" directly with rebuttal. User design may have blind spots; surface them, don't humor.

**Scope**: agent behavior at every prompt.

---

## ADR-01-PRINCIPLE-05 — Engineering hygiene

**Source**: `docs/methodology.md` §5
**Status**: locked
**Precedence**: 0

One line over five; unified management over scattered dirs; clean redundancy and zombie code; YAGNI (no "future extension" hooks); no defensive `if` for invariants already guaranteed by internal code.

**Scope**: every C17 code file.

---

## ADR-01-PRINCIPLE-06 — Real system runs over simulation

**Source**: `docs/methodology.md` §6
**Status**: locked
**Precedence**: 0

Always real LLM calls (not in-context simulation); always real data (not toy cases); mark uncertainty when API outcome is unpredictable, never fake certainty.

**Scope**: all validation and integration tests against real DeepSeek API.

---

## ADR-01-PRINCIPLE-07 — Don't lose methodology / distill into new SKILL

**Source**: `docs/methodology.md` §7
**Status**: locked
**Precedence**: 0

Load-bearing methodology in old SKILLs (transferable disposition, critique-before-verdict, anchor literal requirement, user-history token ban) must be **distilled** into new SKILLs — not copy-pasted, re-expressed in more precise language as a pattern. See ADR-01-METHODOLOGY-MAPPING (`docs/methodology.md`) for the per-method keep/drop table.

---

## ADR-01-PRINCIPLE-08 — Goal first, change size second

**Source**: `docs/methodology.md` §8
**Status**: locked
**Precedence**: 0

Do not retreat to conservative minimal-delta when the goal demands restructuring. True implementation beats minimum-change approximation. But: deleted code must be cleanly removed — no "half-rewrite, leave the old path" residue. C17 carries no c14/c15 compatibility baggage.

**Scope**: deletion list (§6 of master_plan); BridgeLogic deletes c15 slots.

---

## ADR-01-PRINCIPLE-09 — JSON output is a tool; one provider path

**Source**: `docs/methodology.md` §9
**Status**: locked
**Precedence**: 0

Do not maintain both `generate_json` and `generate_with_tools`. Final JSON emit is itself a `submit_*_final` tool call — schema enforced via tool args. One path end-to-end.

**Scope**: `provider_runtime/openai_compatible.py` exposes only `generate_with_tools`.

---

## ADR-01-PRINCIPLE-10 — No LLM self-rated metrics

**Source**: `docs/methodology.md` §10
**Status**: locked
**Precedence**: 0

No `strength / confidence / uncertainty / probability / score` fields anywhere in tool schemas. Self-rated metrics are unreliable and produce false positives.

**Scope**: all Pydantic schemas, all tool args specs.

---

## ADR-01-PRINCIPLE-11 — Offline-asset / U2U/U2I retrieval semantics — copy must contain no user-specific token

**Source**: `docs/methodology.md` §11
**Status**: locked
**Precedence**: 0

Final delivery is offline asset table served via U2U/U2I retrieval to users who may not share the current user's history tokens.
- Copy text MUST NOT contain user-history cat3/brand/search tokens (no `艾灸 / 连衣裙 / 维C` from current user state)
- Copy text MAY contain target-product tokens
- Factor mines **transferable disposition** (中年自我保健 / 内外联动 / 单一补剂升级), not literal token bridge

**Scope**: `record_candidate` handler enforces dynamic projection of user-history tokens from `payload.user_state.behavior.*cat3*/*brand*/*search*` and rejects literal leaks.

---

## ADR-01-PRINCIPLE-12 — Ralph-loop spirit: mechanism enforces reflection

**Source**: `docs/methodology.md` §12
**Status**: locked
**Precedence**: 0

Telling an agent to reflect or loop does not work. Required: deterministic verify + bounded retry, external judge, visible state, minimal mechanism. C17's `reflect_*` tools are a lightweight version — mechanism lets agent see itself, but agent decides whether to call. Tool is on the table; calling or not is the agent's responsibility.

**Scope**: `reflect_on_coverage`, `reflect_on_diversity` are non-mandatory; no harness pressure to force-call them (ADR-01-Q8 confirms optional).

---

## ADR-01-PRINCIPLE-13 — Don't modify system primitives; add tools on top

**Source**: `docs/methodology.md` §13
**Status**: locked
**Precedence**: 0

agent_loop / tool loading / hook system are given. Innovation lives in **tool form and responsibility**, not in plumbing. Provider path (JSON mode → tool mode) is tool-layer and may change.

**Scope**: C17 may rewrite `tools/skill_tools.py`, `agentic/tool_loop.py`, `provider_runtime/openai_compatible.py`; may NOT modify Claude Code hook / SDK / agent_loop primitives.

---

## ADR-01-PRINCIPLE-14 — Implementation self-audit 4 questions

**Source**: `docs/methodology.md` §14
**Status**: locked
**Precedence**: 0

Every code file passes 4 questions:
1. Does the form match requirements — soul landed, not replacing agent thinking, no payload redundancy?
2. Is this the most minimal form — fewest lines, no filler, no defensive `if`?
3. Does this use minimum code with zero compromise on function — no hooks for "future extension"?
4. Is this over-designed — no abstraction layer, no configurability, no "flexibility"?

Any file over budget: stop, reread 4 questions.

**Scope**: every C17 code file at submit time.

---

## ADR-01-PRINCIPLE-15 — Restate before action

**Source**: `docs/methodology.md` §15
**Status**: locked
**Precedence**: 0

Before major direction change, restate user's intent and obtain confirmation before typing code.

**Scope**: any architecture-level decision in C17 implementation.

---

## ADR-03-METHODOLOGY-MAPPING — Keep/Drop/Defer-to-handler decisions from C16 SKILLs

**Source**: `docs/methodology.md`
**Status**: locked
**Precedence**: 1

Authoritative per-methodology table: every load-bearing methodology in C16 SKILLs is explicitly classified KEEP (distill into C17 prose), DROP (regression if re-introduced), DEFER-TO-HANDLER (move from prose to tool handler validation), or KEEP-AS-REFLECT-QUESTION (move from prose to `reflect_*` handler string).

**Per-SKILL summary (full table at source §F)**:

### A. discover-personalization-factors

- KEEP: transferable disposition vs literal token bridge (A1); junior-analyst test (A4); transferable-disposition test as reflect Q3 (A5); direction trichotomy as schema enum (A6); references advisory (A10)
- KEEP-IN-HANDLER: evidence path resolve (A7); user-narration ban (A8)
- KEEP-STRUCTURALLY: self-rated metrics ban via schema absence (A9)
- DROP: 5-class anchor enumeration (A2); STOP-GATE `considered_user_signals` / `considered_and_rejected` (A3, replaced by reflect Q1)

### B. generate-copy-candidates

- KEEP-IN-HANDLER: user-history token leak ban (B1, CRITICAL, dynamic projection per scenario); number ban (B2); length 10-16 chars (B3); anchor literal in text (B4)
- KEEP-AS-REFLECT-QUESTION: head-collision via reflect Q1 (B6); swap-subjects via reflect Q2 (B7); age-swap via reflect Q3 (B8)
- KEEP-BY-TOOL-DESIGN: schema field order (B13)
- DROP: ≥3 drafts quota (B5, schema allows ≥1 with no upper); 5-class anchor (B9); emotion tail static list (B10, rubric D6 catches); price hint static list (B11, rubric D3 catches); state label leakage static list (B12, replaced by one prose sentence); explanation phrase ban (B14, rubric D5 catches)

### C. personalized-copy-rubric-judge

- KEEP: 7 binary axes (C1); critique-before-verdict schema order (C2); templated_flag enum (C4); floor axes D1/D3/D5/D7 (C5); decision rule admit/hold/reject (C6); group-level D2 (C7); demographic/surveillance principle (C8); why binary not Likert prose (C9)
- KEEP-IN-HANDLER: verbatim quote validation (C3)

### D. Cross-SKILL

- KEEP: schema field order load-bearing (D1); no self-rated metrics (D2, structural); no reasoning traces in artifact (D3, structural); references advisory (D4)

**Open question §G (resolved here)**: handler enforces ONLY structural / scenario-derivable constraints (B1, B2, B3, B4). All domain-knowledge enumerations are removed; rubric catches them downstream. Cost is some wasted tool turns; benefit is principled tool design. Revisit only with a *structural* fix, never with a word list.

---

## ADR-PROBE-7.1 — DeepSeek reasoning_effort + tools compatibility confirmed

**Source**: `research/probe_reasoning_with_tools_result.md` (probe run 2026-05-25)
**Status**: locked (resolved by empirical probe)
**Precedence**: 0 (empirically confirmed)

Three configurations tested with DeepSeek `deepseek-chat` + strict tool spec:
- baseline (no reasoning): tool_call returned, finish_reason=tool_calls
- `api.deepseek.com` + `reasoning_effort=high`: reasoning_content present (63 chars), tool_call returned
- `api.deepseek.com/beta` strict + `reasoning_effort=high`: reasoning_content present (55 chars), tool_call returned

**Decisions unlocked**:
- §9 Q5 resolved: COMPATIBLE; `reasoning_effort=high` runs across all turns (record/reflect/submit). §8.1 fallback ("disable reasoning on record/reflect") not needed.
- §9 Q6 resolved: `/beta` strict mode + reasoning coexist.

**Superseded runtime config**: earlier probe used `reasoning_effort="high"` with thinking enabled at `/beta`. Current runtime config is ADR-PROBE-7.1.1.

**Cost signal**: +40% output tokens per tool call when reasoning enabled (43→60 for 1-arg probe). Realistic factor/copy turns expected 2-3× output token overhead — within accepted P4 budget.

---

## ADR-Q-RESOLUTIONS — §9 Open-question resolutions (this session)

**Source**: user directives 2026-05-25 in C17 design session, applied to `master_plan.md` §9
**Status**: locked (user-decided this session)
**Precedence**: 1

Master plan §9 listed 10 open questions; all decided this session:

- **Q1** (overall direction: true tool-use loop + delete + C17 rewrite) — YES (confirmed in master_plan)
- **Q2** (reflect questions live in Python handler constant vs SKILL.md) — **Python handler** (`tools/skill_tools.py` string constants); SKILL.md only one-sentence pointer
- **Q3** (engineering effort 2-3 days acceptable) — quality first, time-box is advisory
- **Q4** (cost 3-10× acceptable) — ACCEPT
- **Q5** (reasoning + tools compatibility) — RESOLVED by §7.1 probe: compatible, `reasoning_effort=high` always on
- **Q6** (DeepSeek `/beta` strict mode) — ENABLE
- **Q7** (keep c15 BridgeLogic slot for trace) — DO NOT KEEP (confirmed in master_plan, principle 8: no c14/c15 compat baggage)
- **Q8** (reflect mandatory or optional) — OPTIONAL (confirmed in master_plan; matches Principle 12)
- **Q9** (SKILL.md keep ✗/✓ anti-pattern examples) — KEEP with placeholder examples (`<cat3>`, `<brand>`, NOT 艾灸/维C); honor Principle 3 (no internal-meme leaks)
- **Q10** (`research/phase8_fix/*` delete or archive) — ARCHIVE to `C17/research/archived_c16_phase8/`

---

## ADR-RUNTIME-BATCH — Batch size 20 requests per validation run

**Source**: user directive 2026-05-25
**Status**: locked
**Precedence**: 1

Validation batch size = **20 requests** (not 100). Applies to the §7.10 real-LLM validation phase and subsequent end-to-end batches in the active workspace. Constrains cost and iteration speed during probe-and-validate cycles.

---

## ADR-PROCESS-PROACTIVE-RESEARCH — Verify external specs before writing code

**Source**: user directive 2026-05-25 + [[feedback-ralph-loop-and-active-skill-invocation]] + docs/methodology.md self-prompts
**Status**: locked
**Precedence**: 2

When implementation touches an external API, library, or specification (e.g., OpenAI tool spec, DeepSeek `/beta` mode, openai SDK reasoning_effort coupling, `rich.Progress` API), the implementer MUST verify the spec against current docs (WebSearch, Context7, Anthropic claude-api SKILL, gsd-phase-researcher subagent) before writing code. Training-data guesses are forbidden; outdated parameters / removed flags / renamed fields surface only by reading current docs.

**Scope**: every C17 phase; especially Phase 2 (DeepSeek provider), Phase 6 (rich progress + rate limit + concurrency primitives), Phase 7 (real-LLM behavior).

**Anti-pattern**: writing `response_format=...` because "OpenAI used to accept it" — verify what `deepseek-chat` strict mode at `/beta` accepts THIS WEEK before coding.

---

## ADR-PROCESS-SKILL-ORCHESTRATION — Each phase plan lists which local skills it uses

**Source**: user directive 2026-05-25 + [[feedback-ralph-loop-and-active-skill-invocation]] + [[feedback-thinking-depth-and-subagent-fanout-discipline]]
**Status**: locked
**Precedence**: 2

Each phase, before starting implementation, the PLAN.md (or equivalent) MUST enumerate the local Claude Code skills it will invoke and what each will do. Skills are not optional decoration — they are the harness for the agent's own work.

**Standard skill bundle (use as fits)**:
- **writing-skills** / **writing-a-skill** — when (re)writing SKILL.md prose (Matt-style discipline)
- **brainstorming** — before non-trivial implementation choices
- **grill-with-docs** / **grill-me** — stress-test plan against existing domain language
- **tdd** / **test-driven-development** — every new module starts with red test
- **systematic-debugging** / **diagnose** / **gsd-debug** — bug investigation discipline
- **verify** / **verification-before-completion** — manual UAT before claiming complete
- **dispatching-parallel-agents** / **subagent-driven-development** — when ≥2 independent subtasks
- **using-git-worktrees** — when needed for isolation
- **error-analysis** / **eval-audit** — Phase 7 real-LLM analysis
- **claude-api** — any Anthropic SDK touchpoint
- **finishing-a-development-branch** — phase wrap-up
- **gsd-code-review** / **gsd-secure-phase** / **gsd-verify-work** — pre-merge
- **caveman** mode when token budget tight

**Anti-pattern**: silently writing code without listing the skills used / orchestrating subagents only mentally. Make it explicit in PLAN.md.
