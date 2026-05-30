from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = (
    PROJECT_ROOT
    / "workflow-skills"
    / "current"
    / "personalized-copy-generation"
    / "SKILL.md"
)


def _skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def test_generation_skill_preserves_merged_path_and_linkage_contract() -> None:
    text = _skill_text()

    for expected in [
        "default merged generation path",
        "merged generation path",
        "source_factor_id",
        "factor state",
        "copy state",
        "plural distinct user-product tensions",
        "source_factor_id is necessary but not sufficient",
    ]:
        assert expected in text


def test_generation_skill_names_phase09_repair_red_flags() -> None:
    text = _skill_text()

    for expected in [
        "single-angle collapse",
        "duplicate factors",
        "copy-before-factor",
        "role or label renamed as factor",
        "product-grounded scene result",
    ]:
        assert expected in text


def test_generation_skill_avoids_forcing_patterns() -> None:
    text = _skill_text().lower()

    forbidden_phrases = [
        "at least 3 factors",
        "at least three factors",
        "minimum 3 factors",
        "minimum three factors",
        "factor_count_p50",
        "json skeleton",
        "ellipsis template",
        "...",
        "for example:",
        "example:",
        "first, second, third",
        "taxonomy",
        "enumeration",
        "long-term split-node production architecture",
        "restore split-node production",
    ]
    offenders = [phrase for phrase in forbidden_phrases if phrase in text]

    assert offenders == []
