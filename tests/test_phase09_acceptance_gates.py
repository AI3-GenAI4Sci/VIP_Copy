"""Phase 09 source-level acceptance anti-cheat gates."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVOLUTION_FILES = (
    ROOT / "seers_harness/evolution/delta_portfolio.py",
    ROOT / "seers_harness/evolution/portfolio_journal.py",
    ROOT / "seers_harness/validation/runner.py",
    ROOT / "seers_harness/validation/evolution_snapshot.py",
)
REWARD_FILE = ROOT / "seers_harness/evolution/uplift.py"
ACCEPTANCE_FILES = (
    ROOT / "seers_harness/validation/runner.py",
    ROOT / "seers_harness/validation/machine_judges.py",
    ROOT / "seers_harness/validation/batch_summary_writer.py",
)


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _identifiers(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
    return names


def _string_literals(tree: ast.AST) -> set[str]:
    values: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            values.add(node.value)
    return values


def _without_docstrings(tree: ast.Module) -> ast.Module:
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(body, list)
            and body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body.pop(0)
    return tree


def test_forbidden_exploration_shortcut_identifiers_are_absent() -> None:
    forbidden_identifiers = {
        "".join(parts)
        for parts in (
            ("token", "_budget", "_pressure"),
            ("production", "_pressure"),
            ("trial", "_prob"),
            ("static", "_probability", "_skip"),
            ("random", "_skip"),
            ("hardcoded", "_trial", "_forcing"),
            ("force", "_trial"),
            ("artificial", "_prior"),
            ("manual", "_prior"),
        )
    }
    forbidden_reasons = {
        "".join(parts)
        for parts in (
            ("token", "_pressure"),
            ("concurrency", "_pressure"),
            ("static", "_probability", "_miss"),
            ("random", "_skip"),
            ("hardcoded", "_trial", "_suppression"),
            ("artificial", "_prior"),
            ("manual", "_prior"),
        )
    }

    offenders: dict[str, list[str]] = {}
    for path in EVOLUTION_FILES:
        tree = _without_docstrings(_parse(path))
        present = (_identifiers(tree) & forbidden_identifiers) | (
            _string_literals(tree) & forbidden_reasons
        )
        if present:
            offenders[str(path.relative_to(ROOT))] = sorted(present)

    assert offenders == {}


def test_reward_provenance_is_rubric_artifact_only() -> None:
    text = REWARD_FILE.read_text(encoding="utf-8")
    for required in (
        "PersonalizedCopyRubricArtifact",
        "baseline_mean_rubric_score",
        "trial_mean_rubric_score",
    ):
        assert required in text

    forbidden_reward_names = {
        "".join(parts)
        for parts in (
            ("confidence",),
            ("probability",),
            ("quality", "_score"),
            ("agent", "_judgment"),
            ("self", "_rating"),
        )
    }
    tree = _without_docstrings(_parse(REWARD_FILE))
    present = _identifiers(tree) & forbidden_reward_names
    assert present == set()


def test_mechanism_evidence_identifiers_are_present() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in EVOLUTION_FILES)
    batch_source = (ROOT / "seers_harness/validation/batch_summary_writer.py").read_text(
        encoding="utf-8"
    )
    judges_source = (ROOT / "seers_harness/validation/machine_judges.py").read_text(
        encoding="utf-8"
    )

    required = {
        "exploration_decision": source,
        "selected_delta_id": source,
        "trial_workspace": source,
        "append_journal_entry": source,
        "belief_alpha": source,
        "belief_beta": source,
        "sample_count": source,
        "trial_belief_update_count": batch_source + judges_source,
    }
    missing = [name for name, haystack in required.items() if name not in haystack]
    if "fold_portfolio_journal" not in source and "fold_portfolio_entries" not in source:
        missing.append("fold_portfolio_journal_or_entries")
    assert missing == []


def test_record_only_metrics_are_not_acceptance_threshold_gates() -> None:
    metric_terms = (
        "factor_count_p50",
        "prompt_cache_miss",
        "cache_miss",
        "token_use",
        "total_tokens",
        "completion_tokens",
        "trial_count",
        "trial_selected_count",
    )
    numeric_gate_nodes: list[str] = []

    for path in ACCEPTANCE_FILES:
        text = path.read_text(encoding="utf-8")
        tree = _without_docstrings(ast.parse(text, filename=str(path)))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            snippet = ast.get_source_segment(text, node) or ""
            if any(term in snippet for term in metric_terms):
                numeric_gate_nodes.append(f"{path.relative_to(ROOT)}: {snippet}")

    assert numeric_gate_nodes == []
