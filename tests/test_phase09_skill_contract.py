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
        "user_factors",
        "source_user_factor_id",
        "product_binding",
        "fact_binding",
        "maintain_copy_artifact",
        "用户因子",
    ]:
        assert expected in text


def test_generation_skill_names_phase09_repair_red_flags() -> None:
    text = _skill_text()

    for expected in [
        "避免重复商品名",
        "动态事实",
        "痛点前置",
        "场景代入",
        "商品承接",
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
