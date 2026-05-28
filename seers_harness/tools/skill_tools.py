"""Skill tools — pure-function tool handlers for the c17 true-tool-use loop.

Every handler signature is universal: ``def fn(args: dict, state: dict) -> str``.
Handlers return literal strings (``"recorded"``, ``"finalized"``, or the fixed
reflect prompt) and raise ``ToolValidationError`` on any structural failure.
No counts, no aggregated state, no judgments in return values — Principle 1
(tools are hand / eye / mirror, not brain).
"""

# ROLE CLASSIFICATION (TOOL-09 + ADR-01-PRINCIPLE-01..03)
# record_factor             hand
# submit_factors_final      hand
# record_candidate          hand
# submit_copies_final       hand
# judge_candidate           hand
# submit_judgments_final    hand
# reflect_on_coverage       mirror
# reflect_on_diversity      mirror
# (eye count: 0 — additions require written justification)

from __future__ import annotations

import re
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError

from seers_harness.core.errors import ToolValidationError
from seers_harness.domain.models import (
    CopyGenerationArtifact,
    FactorDiscoveryArtifact,
    PersonalizedCopyRubricArtifact,
    PersonalizedCopyRubricJudgment,
)


# Pure-function helpers for evidence-path resolution, Chinese-digit detection,
# and ad-copy character counting — used by record_factor / record_candidate /
# judge_candidate below.


_ARABIC_DIGIT = re.compile(r"\d")
# Chinese-digit-as-number patterns: digit immediately preceding a unit word
# (折/元/件/瓶/盒/支/月/年/天/秒/小时/折扣/号 etc) or a digit followed by 块/钱.
# Bare 一/二/三 in compounds like 一支/一族/一点/一道 are language tokens,
# not numeric values, and must not trip this check.
_CN_NUM_AS_VALUE = re.compile(
    r"[一二三四五六七八九十零百千万]"
    r"(?:折|元|件|瓶|盒|份|月|年|天|号|块|毛|分钟|小时|秒|百分|倍)"
)
_DIGIT_UNIT = re.compile(r"\d\s*(?:折|元|件|瓶|盒|份|月|年|天|号|%)")

_CN_TOKEN_RE = re.compile(r"[一-鿿]{2,}")
_CAT3_BRAND_SEARCH_KEY_RE = re.compile(r"(cat3|brand|search)", re.IGNORECASE)
_FACTOR_TEXT_FIELD_DESCRIPTION = (
    "Free-text reasoning field. Avoid ASCII double quote characters inside "
    "the value; use Chinese quote marks or paraphrase instead so strict "
    "tool-call JSON remains valid."
)


def _resolve_path(payload: dict[str, Any], dotted_path: str) -> bool:
    """Walk a ``a.b.c`` (or ``a[0].b``) path; return True iff terminal value
    is not None."""
    if not dotted_path:
        return False
    cur: Any = payload
    parts = re.findall(r"[^.\[\]]+", dotted_path)
    for part in parts:
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return False
        else:
            return False
        if cur is None:
            return False
    return cur is not None


def _visible_chinese_chars(s: str) -> int:
    """Approximate visible character count for ad copy — strip ASCII spaces
    and punctuation; count remaining unicode code points."""
    cleaned = re.sub(r"[\s　，。、；：！？“”‘’（）【】「」《》—…·.,;:!?\"'(){}<>\-]", "", s)
    return len(cleaned)


# --------------------------------------------------------------------------- #
# Reflect constants (ADR-Q-RESOLUTIONS Q2 — Python, not SKILL.md)             #
# --------------------------------------------------------------------------- #


_REFLECT_COVERAGE = """\
Answer each question IN THIS turn, in writing, before deciding whether to call submit_factors_final:

1. Re-read user_state.behavior in the payload. Name every distinct behavior-signal field.
   For each: did you mine a factor from it, or write one sentence explaining why you intentionally skipped it?

2. Look at the factors you have recorded. Do they collapse onto one user-side signal class
   (all click history / all profile / all derived)? If yes, what other class of latent
   user-product relation could surface a factor you have not yet recorded?

3. Pick any recorded factor. Imagine a different user who shares the underlying disposition
   but NOT the literal behavior tokens of this user. Could the factor still honestly describe
   that user? If not, the factor is overfit — re-record it.
"""


_REFLECT_DIVERSITY = """\
Answer each question IN THIS turn before submit_copies_final:

1. Read the first 3 characters of every candidate text you have recorded.
   List the heads. Are 3 or more starting with the same product anchor?
   If yes, your structural variety is fake — re-record those candidates with different anchor heads.

2. Imagine a retrieved user who does NOT share the literal behavior tokens of the current user.
   For each candidate, would the line still feel honest to that user, or does it pretend to
   know something specific about them? Re-record any candidate that fails this test.

3. Read each candidate as a 22-year-old, a 35-year-old, and a 55-year-old.
   Does it land for at least two of the three? If only one, the line is over-fit to one age
   band — broaden or drop.
"""


# --------------------------------------------------------------------------- #
# record_factor (hand) — TOOL-01                                              #
# --------------------------------------------------------------------------- #


class _RecordFactorArgs(BaseModel):
    factor_id: str
    user_side_signal: str
    direction: str  # JSON-Schema enum constraint applied at the spec layer
    evidence_paths: list[str]
    bridge_to_product: str
    transferable_disposition: str  # DATA-01 — required
    covers_product_ids: list[str]
    model_config = {"extra": "forbid"}


def _ensure_evidence_paths_resolve(paths: list[str], payload: dict) -> None:
    if not paths:
        raise ToolValidationError(
            message="record_factor requires at least one evidence_paths entry",
            tool_name="record_factor",
            arg_path="evidence_paths",
        )
    for p in paths:
        if not _resolve_path(payload, p):
            raise ToolValidationError(
                message=f"evidence_paths entry does not resolve against payload: {p!r}",
                tool_name="record_factor",
                arg_path="evidence_paths",
            )


def record_factor(args: dict, state: dict) -> str:
    """Hand. Append one personalization factor to state['factors']."""
    try:
        parsed = _RecordFactorArgs.model_validate(args)
    except ValidationError as exc:
        raise ToolValidationError(
            message=f"record_factor args invalid: {exc.errors()[:3]}",
            tool_name="record_factor",
        ) from exc
    _ensure_evidence_paths_resolve(parsed.evidence_paths, state.get("payload", {}))
    state.setdefault("factors", []).append(parsed.model_dump())
    return "recorded"


# --------------------------------------------------------------------------- #
# submit_factors_final (hand) — TOOL-02                                       #
# --------------------------------------------------------------------------- #


def submit_factors_final(args: dict, state: dict) -> str:
    """Hand. Validate the FactorDiscoveryArtifact and hand it off."""
    try:
        artifact = FactorDiscoveryArtifact.model_validate(args)
    except ValidationError as exc:
        raise ToolValidationError(
            message=f"FactorDiscoveryArtifact schema invalid: {exc.errors()[:3]}",
            tool_name="submit_factors_final",
        ) from exc
    state["final_artifact"] = artifact.model_dump()
    return "finalized"


# --------------------------------------------------------------------------- #
# record_candidate (hand) — TOOL-03                                           #
# Validation order (contractual; tested in test_skill_tools_record_candidate):#
#   (1) drafts integrity   — index in range AND text == drafts[index]        #
#   (2) Arabic-digit       — _ARABIC_DIGIT.search(text) must be None         #
#   (3) CN-num-as-value    — _CN_NUM_AS_VALUE.search(text) must be None      #
#   (4) length             — 10 <= _visible_chinese_chars(text) <= 16         #
#   (5) anchor literal     — product_anchor + relation_anchor both in text    #
#   (6) user-history leak  — dynamic projection from payload.user_state       #
# --------------------------------------------------------------------------- #


class _RecordCandidateArgs(BaseModel):
    candidate_id: str
    target_product_id: str
    source_factor_id: str
    text: str
    considered_drafts: list[str]
    chosen_draft_index: int
    bridge_logic: dict
    used_copyable_hooks: list[str] = Field(default_factory=list)
    intended_effect: str = ""
    model_config = {"extra": "forbid"}


def _project_user_history_tokens(payload: dict) -> set[str]:
    behavior = (payload.get("user_state") or {}).get("behavior") or {}
    tokens: set[str] = set()
    for key, val in behavior.items():
        if not isinstance(key, str) or not _CAT3_BRAND_SEARCH_KEY_RE.search(key):
            continue
        text_v = val if isinstance(val, str) else ",".join(str(x) for x in (val or []))
        tokens.update(_CN_TOKEN_RE.findall(text_v))
    return tokens


def _project_target_product_tokens(payload: dict, product_id: str) -> set[str]:
    allowed: set[str] = set()
    for prod in payload.get("products") or []:
        if str(prod.get("product_id")) != str(product_id):
            continue
        attrs = prod.get("attributes") or {}
        for k in (
            "item_cat3_name", "cat3_name", "cat3",
            "item_cat2_name", "cat2_name",
            "item_cat1_name", "cat1_name",
            "item_brand_name", "brand_name", "brand",
            "item_name", "title",
        ):
            v = attrs.get(k)
            if not v:
                continue
            v = str(v)
            allowed.add(v)
            for piece in re.split(r"[\s/／、,，()（）]+", v):
                piece = piece.strip()
                if 2 <= len(piece) <= 8:
                    allowed.add(piece)
        gk = prod.get("group_key")
        if gk:
            allowed.add(str(gk))
    return allowed


def _reject_user_history_leak(text: str, payload: dict, product_id: str) -> None:
    user_tokens = _project_user_history_tokens(payload)
    product_tokens = _project_target_product_tokens(payload, product_id)
    leaks = user_tokens - product_tokens
    if not leaks:
        return
    hits = [t for t in leaks if t in text]
    if hits:
        raise ToolValidationError(
            message=f"candidate text contains user-history tokens not present in target product: {hits[:3]}",
            tool_name="record_candidate",
            arg_path="text",
        )


def record_candidate(args: dict, state: dict) -> str:
    """Hand. Append one CopyCandidate after the 6-step validation order."""
    try:
        parsed = _RecordCandidateArgs.model_validate(args)
    except ValidationError as exc:
        raise ToolValidationError(
            message=f"record_candidate args invalid: {exc.errors()[:3]}",
            tool_name="record_candidate",
        ) from exc
    text = parsed.text

    # (1) drafts integrity
    if parsed.chosen_draft_index < 0 or parsed.chosen_draft_index >= len(parsed.considered_drafts):
        raise ToolValidationError(
            message=f"chosen_draft_index {parsed.chosen_draft_index} out of range for {len(parsed.considered_drafts)} drafts",
            tool_name="record_candidate",
            arg_path="chosen_draft_index",
        )
    if text != parsed.considered_drafts[parsed.chosen_draft_index]:
        raise ToolValidationError(
            message="text must equal considered_drafts[chosen_draft_index]",
            tool_name="record_candidate",
            arg_path="text",
        )

    # (2) Arabic digit
    if _ARABIC_DIGIT.search(text):
        raise ToolValidationError(
            message=f"text contains Arabic digit: {text!r}",
            tool_name="record_candidate",
            arg_path="text",
        )

    # (3) CN num-as-value
    if _CN_NUM_AS_VALUE.search(text):
        raise ToolValidationError(
            message=f"text contains Chinese numeral-as-value: {text!r}",
            tool_name="record_candidate",
            arg_path="text",
        )

    # (4) length
    n = _visible_chinese_chars(text)
    if not (10 <= n <= 16):
        raise ToolValidationError(
            message=f"visible Chinese char count {n} not in [10, 16]: {text!r}",
            tool_name="record_candidate",
            arg_path="text",
        )

    # (5) anchor literal
    bl = parsed.bridge_logic or {}
    product_anchor = str(bl.get("product_anchor") or "")
    relation_anchor = str(bl.get("relation_anchor") or "")
    if not product_anchor or product_anchor not in text:
        raise ToolValidationError(
            message=f"bridge_logic.product_anchor must be a literal substring of text; anchor={product_anchor!r} text={text!r}",
            tool_name="record_candidate",
            arg_path="bridge_logic.product_anchor",
        )
    if not relation_anchor or relation_anchor not in text:
        raise ToolValidationError(
            message=f"bridge_logic.relation_anchor must be a literal substring of text; anchor={relation_anchor!r} text={text!r}",
            tool_name="record_candidate",
            arg_path="bridge_logic.relation_anchor",
        )

    # (6) user-history leak
    _reject_user_history_leak(text, state.get("payload", {}), parsed.target_product_id)

    state.setdefault("candidates", []).append(parsed.model_dump())
    return "recorded"


# --------------------------------------------------------------------------- #
# submit_copies_final (hand) — TOOL-04                                        #
# --------------------------------------------------------------------------- #


def submit_copies_final(args: dict, state: dict) -> str:
    """Hand. Validate the CopyGenerationArtifact and hand it off.

    Sets BOTH state['final_artifact'] (loop termination signal) AND
    state['copies_artifact'] (read by the rubric SKILL's judge_candidate
    in the next loop iteration). Phase 3 wires these into a fresh state
    dict per skill invocation.
    """
    try:
        artifact = CopyGenerationArtifact.model_validate(args)
    except ValidationError as exc:
        raise ToolValidationError(
            message=f"CopyGenerationArtifact schema invalid: {exc.errors()[:3]}",
            tool_name="submit_copies_final",
        ) from exc
    dumped = artifact.model_dump()
    state["final_artifact"] = dumped
    state["copies_artifact"] = dumped
    return "finalized"


# --------------------------------------------------------------------------- #
# judge_candidate (hand) — TOOL-05                                            #
# --------------------------------------------------------------------------- #


def judge_candidate(args: dict, state: dict) -> str:
    """Hand. Validate one rubric judgment against its candidate.

    Reads candidate text from state['copies_artifact']['candidates'] (set
    by submit_copies_final in the prior loop iteration; see TOOL-04).
    For every per_axis verdict with a non-empty verbatim_candidate_quote,
    asserts the quote is a literal substring of the candidate text.
    """
    try:
        judgment = PersonalizedCopyRubricJudgment.model_validate(args)
    except ValidationError as exc:
        raise ToolValidationError(
            message=f"judgment schema invalid: {exc.errors()[:3]}",
            tool_name="judge_candidate",
        ) from exc
    candidates = (state.get("copies_artifact") or {}).get("candidates") or []
    text_by_id = {c.get("candidate_id"): c.get("text", "") for c in candidates}
    cand_text = text_by_id.get(judgment.candidate_id, "")
    if judgment.candidate_id not in text_by_id:
        # Surface the missing candidate explicitly only when at least one quote
        # would otherwise be checked against an empty string.
        for axis in judgment.per_axis:
            if axis.verbatim_candidate_quote:
                raise ToolValidationError(
                    message=f"candidate_id {judgment.candidate_id!r} not present in state['copies_artifact']['candidates']",
                    tool_name="judge_candidate",
                    arg_path="candidate_id",
                )
    for axis in judgment.per_axis:
        quote = axis.verbatim_candidate_quote
        if not quote:
            continue
        if quote not in cand_text:
            raise ToolValidationError(
                message=f"verbatim_candidate_quote for axis {axis.axis_id!r} not literally in candidate text (candidate_id={judgment.candidate_id!r}, quote={quote!r})",
                tool_name="judge_candidate",
                arg_path=f"per_axis[{axis.axis_id}].verbatim_candidate_quote",
            )
    state.setdefault("judgments", []).append(judgment.model_dump())
    return "recorded"


# --------------------------------------------------------------------------- #
# submit_judgments_final (hand) — TOOL-06                                     #
# --------------------------------------------------------------------------- #


def submit_judgments_final(args: dict, state: dict) -> str:
    """Hand. Validate the PersonalizedCopyRubricArtifact and hand it off."""
    try:
        artifact = PersonalizedCopyRubricArtifact.model_validate(args)
    except ValidationError as exc:
        raise ToolValidationError(
            message=f"PersonalizedCopyRubricArtifact schema invalid: {exc.errors()[:3]}",
            tool_name="submit_judgments_final",
        ) from exc
    state["final_artifact"] = artifact.model_dump()
    return "finalized"


# --------------------------------------------------------------------------- #
# reflect_on_coverage (mirror) — TOOL-07                                      #
# reflect_on_diversity (mirror) — TOOL-08                                     #
# --------------------------------------------------------------------------- #


def reflect_on_coverage(args: dict, state: dict) -> str:
    """Mirror. Surface the fixed three-question coverage prompt."""
    return _REFLECT_COVERAGE


def reflect_on_diversity(args: dict, state: dict) -> str:
    """Mirror. Surface the fixed three-question diversity prompt
    (includes the 22-year-old age-swap canary)."""
    return _REFLECT_DIVERSITY


# --------------------------------------------------------------------------- #
# Tool specs (hand-authored; DeepSeek /beta strict mode)                      #
# Probe-verified shape: 2026-05-25 research/probe_q1_q2.py                    #
# Every property in `required` (strict-mode contract). Critique-style         #
# properties precede verdict-style (RESEARCH §Open Q2 RESOLVED).              #
# --------------------------------------------------------------------------- #


RECORD_FACTOR_SPEC: dict = {
    "type": "function",
    "function": {
        "name": "record_factor",
        "description": (
            "Append one personalization factor to the working set. "
            "Call multiple times. Each call records one factor."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "factor_id", "user_side_signal", "direction",
                "evidence_paths", "bridge_to_product",
                "transferable_disposition", "covers_product_ids",
            ],
            "properties": {
                "factor_id": {"type": "string"},
                "user_side_signal": {
                    "type": "string",
                    "description": _FACTOR_TEXT_FIELD_DESCRIPTION,
                },
                "direction": {
                    "type": "string",
                    "enum": ["user_to_need", "item_to_need", "cross"],
                },
                "evidence_paths": {"type": "array", "items": {"type": "string"}},
                "bridge_to_product": {
                    "type": "string",
                    "description": _FACTOR_TEXT_FIELD_DESCRIPTION,
                },
                "transferable_disposition": {
                    "type": "string",
                    "description": _FACTOR_TEXT_FIELD_DESCRIPTION,
                },
                "covers_product_ids": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}


REFLECT_ON_COVERAGE_SPEC: dict = {
    "type": "function",
    "function": {
        "name": "reflect_on_coverage",
        "description": (
            "When unsure whether transferable angles are exhausted, call this "
            "to receive three coverage questions. Answer each in writing in your next turn."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": [],
            "properties": {},
        },
    },
}


SUBMIT_FACTORS_FINAL_SPEC: dict = {
    "type": "function",
    "function": {
        "name": "submit_factors_final",
        "description": "Submit the final FactorDiscoveryArtifact. Run terminates after this call.",
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["factors"],
            "properties": {
                "factors": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "factor_id", "user_side_signal", "direction",
                            "evidence_refs", "bridge",
                            "transferable_disposition", "covers_product_ids",
                        ],
                        "properties": {
                            "factor_id": {"type": "string"},
                            "user_side_signal": {
                                "type": "string",
                                "description": _FACTOR_TEXT_FIELD_DESCRIPTION,
                            },
                            "direction": {
                                "type": "string",
                                "enum": ["user_to_need", "item_to_need", "cross"],
                            },
                            "evidence_refs": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["path", "value"],
                                    "properties": {
                                        "path": {"type": "string"},
                                        "value": {"type": ["string", "number", "boolean", "null"]},
                                    },
                                },
                            },
                            "bridge": {
                                "type": "string",
                                "description": _FACTOR_TEXT_FIELD_DESCRIPTION,
                            },
                            "transferable_disposition": {
                                "type": "string",
                                "description": _FACTOR_TEXT_FIELD_DESCRIPTION,
                            },
                            "covers_product_ids": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
            },
        },
    },
}


_CANDIDATE_ITEM_REQUIRED = [
    "candidate_id", "target_product_id", "source_factor_id",
    "text", "considered_drafts", "chosen_draft_index",
    "bridge_logic", "used_copyable_hooks", "intended_effect",
]
_CANDIDATE_ITEM_PROPERTIES: dict = {
    "candidate_id": {"type": "string"},
    "target_product_id": {"type": "string"},
    "source_factor_id": {"type": "string"},
    "text": {"type": "string"},
    "considered_drafts": {"type": "array", "items": {"type": "string"}},
    "chosen_draft_index": {"type": "integer"},
    "bridge_logic": {
        "type": "object",
        "additionalProperties": False,
        "required": ["product_anchor", "relation_anchor"],
        "properties": {
            "product_anchor": {"type": "string"},
            "relation_anchor": {"type": "string"},
        },
    },
    "used_copyable_hooks": {"type": "array", "items": {"type": "string"}},
    "intended_effect": {"type": "string"},
}


RECORD_CANDIDATE_SPEC: dict = {
    "type": "function",
    "function": {
        "name": "record_candidate",
        "description": (
            "Append one copy candidate to the working set. Validates 6-step "
            "order: drafts integrity, no Arabic digit, no CN numeral-as-value, "
            "length 10..16, anchors literal in text, no user-history token leak."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": list(_CANDIDATE_ITEM_REQUIRED),
            "properties": dict(_CANDIDATE_ITEM_PROPERTIES),
        },
    },
}


REFLECT_ON_DIVERSITY_SPEC: dict = {
    "type": "function",
    "function": {
        "name": "reflect_on_diversity",
        "description": (
            "When unsure whether candidates are diverse enough, call this for "
            "three diversity questions (includes the 22-year-old age-swap canary)."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": [],
            "properties": {},
        },
    },
}


SUBMIT_COPIES_FINAL_SPEC: dict = {
    "type": "function",
    "function": {
        "name": "submit_copies_final",
        "description": "Submit the final CopyGenerationArtifact.",
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["candidates"],
            "properties": {
                "candidates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": list(_CANDIDATE_ITEM_REQUIRED),
                        "properties": dict(_CANDIDATE_ITEM_PROPERTIES),
                    },
                },
            },
        },
    },
}


_PER_AXIS_REQUIRED = [
    "axis_id", "verbatim_candidate_quote",
    "bridge_to_anchor", "templated_flag", "verdict",
]
_PER_AXIS_PROPERTIES: dict = {
    # Critique BEFORE verdict — ADR-03 §C2, RESEARCH §Open Q2 RESOLVED.
    "axis_id": {"type": "string"},
    "verbatim_candidate_quote": {"type": "string"},
    "bridge_to_anchor": {"type": "string"},
    "templated_flag": {
        "type": "string",
        "enum": ["ok", "empty", "anchor_echo", "source_path_missing", "quote_too_short"],
    },
    "verdict": {"type": "string", "enum": ["pass", "fail"]},
}

_JUDGMENT_REQUIRED = [
    "candidate_id", "candidate_index", "product_id", "copy_text",
    "factor_id", "per_axis", "floor_violations",
    "primary_strength", "primary_risk", "rationale", "decision",
]
_JUDGMENT_PROPERTIES: dict = {
    "candidate_id": {"type": "string"},
    "candidate_index": {"type": "integer"},
    "product_id": {"type": "string"},
    "copy_text": {"type": "string"},
    "factor_id": {"type": "string"},
    "per_axis": {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": list(_PER_AXIS_REQUIRED),
            "properties": dict(_PER_AXIS_PROPERTIES),
        },
    },
    "floor_violations": {"type": "array", "items": {"type": "string"}},
    "primary_strength": {"type": "string"},
    "primary_risk": {"type": "string"},
    "rationale": {"type": "string"},
    "decision": {"type": "string", "enum": ["admit", "hold", "reject"]},
}


JUDGE_CANDIDATE_SPEC: dict = {
    "type": "function",
    "function": {
        "name": "judge_candidate",
        "description": (
            "Append one rubric judgment for one candidate. Per-axis verdicts "
            "MUST list critique fields BEFORE verdict (the args you emit are "
            "your reasoning record)."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": list(_JUDGMENT_REQUIRED),
            "properties": dict(_JUDGMENT_PROPERTIES),
        },
    },
}


SUBMIT_JUDGMENTS_FINAL_SPEC: dict = {
    "type": "function",
    "function": {
        "name": "submit_judgments_final",
        "description": "Submit the final PersonalizedCopyRubricArtifact.",
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["judgments"],
            "properties": {
                "judgments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": list(_JUDGMENT_REQUIRED),
                        "properties": dict(_JUDGMENT_PROPERTIES),
                    },
                },
            },
        },
    },
}


# --------------------------------------------------------------------------- #
# Registries (TOOL-10)                                                        #
# --------------------------------------------------------------------------- #


TOOLS_SPEC: dict[str, list[dict]] = {
    "discover-personalization-factors": [
        RECORD_FACTOR_SPEC, REFLECT_ON_COVERAGE_SPEC, SUBMIT_FACTORS_FINAL_SPEC,
    ],
    "generate-copy-candidates": [
        RECORD_CANDIDATE_SPEC, REFLECT_ON_DIVERSITY_SPEC, SUBMIT_COPIES_FINAL_SPEC,
    ],
    "personalized-copy-rubric-judge": [
        JUDGE_CANDIDATE_SPEC, SUBMIT_JUDGMENTS_FINAL_SPEC,
    ],
}


TOOL_HANDLERS: dict[str, Callable[[dict, dict], str]] = {
    "record_factor": record_factor,
    "submit_factors_final": submit_factors_final,
    "record_candidate": record_candidate,
    "submit_copies_final": submit_copies_final,
    "judge_candidate": judge_candidate,
    "submit_judgments_final": submit_judgments_final,
    "reflect_on_coverage": reflect_on_coverage,
    "reflect_on_diversity": reflect_on_diversity,
}
