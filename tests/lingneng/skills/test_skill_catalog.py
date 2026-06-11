from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
LINGNENG_SKILLS_ROOT = REPO_ROOT / "skills" / "lingneng"

REQUIRED_PACKAGES = {
    "employee-boss-assistant",
    "employee-operation-specialist",
    "employee-product-combo-advisor",
    "employee-marketing-planner",
    "employee-marketing-content-creator",
    "employee-member-operator",
    "knowledge-base-answer",
    "marketing-copy-generation",
    "member-repurchase-campaign",
    "restaurant-campaign-planning",
    "restaurant-channel-growth-strategy",
    "restaurant-combo-pricing-strategy",
    "restaurant-menu-engineering",
    "restaurant-strategy-planning",
    "store-operation-analysis",
    "training-summary-report",
    "document-generation",
    "image-generation",
    "chart-visualization",
    "report-formatting",
    "artifact-output-contract",
    "business-answer-contract",
    "rag-citation-contract",
    "tool-observation-contract",
}


def _bundled_skill_files() -> list[Path]:
    if not LINGNENG_SKILLS_ROOT.exists():
        return []
    return sorted(LINGNENG_SKILLS_ROOT.rglob("SKILL.md"))


def test_bundled_lingneng_skill_root_exists():
    assert LINGNENG_SKILLS_ROOT.is_dir()


def test_bundled_lingneng_skill_packages_are_present():
    package_names = {path.parent.name for path in _bundled_skill_files()}
    assert REQUIRED_PACKAGES <= package_names


def test_bundled_skill_directory_matches_frontmatter_name():
    for skill_file in _bundled_skill_files():
        text = skill_file.read_text(encoding="utf-8")
        name_line = next(
            line for line in text.splitlines() if line.startswith("name: ")
        )
        package_name = name_line.split(":", 1)[1].strip()
        assert skill_file.parent.name == package_name
