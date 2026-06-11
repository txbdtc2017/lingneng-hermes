import subprocess
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

EXPECTED_EVAL_JSON_FILES = {
    "tasks/marketing-copy-generation/examples/evals/content-creator-evals.json",
    "tasks/member-repurchase-campaign/examples/evals/eval-01-rfm-holiday-plan.json",
    "tasks/member-repurchase-campaign/examples/evals/eval-02-vip-recall-message.json",
    "tasks/member-repurchase-campaign/examples/evals/eval-03-new-customer-nurture.json",
    "tasks/restaurant-strategy-planning/examples/evals/operation-strategy-evals.json",
    "tasks/store-operation-analysis/examples/evals/boss-assistant-evals.json",
}


def _bundled_skill_files() -> list[Path]:
    if not LINGNENG_SKILLS_ROOT.exists():
        return []
    return sorted(LINGNENG_SKILLS_ROOT.rglob("SKILL.md"))


def _frontmatter(text: str) -> list[str]:
    lines = text.splitlines()
    assert lines and lines[0] == "---"
    end = next(index for index, line in enumerate(lines[1:], start=1) if line == "---")
    return lines[1:end]


def _frontmatter_name(text: str) -> str:
    name_lines = [line for line in _frontmatter(text) if line.startswith("name: ")]
    assert len(name_lines) == 1
    return name_lines[0].split(":", 1)[1].strip()


def test_bundled_lingneng_skill_root_exists():
    assert LINGNENG_SKILLS_ROOT.is_dir()


def test_bundled_lingneng_skill_packages_are_present():
    package_names = {path.parent.name for path in _bundled_skill_files()}
    assert REQUIRED_PACKAGES <= package_names


def test_bundled_skill_directory_matches_frontmatter_name():
    for skill_file in _bundled_skill_files():
        text = skill_file.read_text(encoding="utf-8")
        assert skill_file.parent.name == _frontmatter_name(text)


def test_bundled_eval_json_files_are_present_and_tracked():
    for relative_path in EXPECTED_EVAL_JSON_FILES:
        path = LINGNENG_SKILLS_ROOT / relative_path
        assert path.is_file()
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(path.relative_to(REPO_ROOT))],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )


def test_bundled_skill_markdown_and_json_do_not_contain_local_absolute_paths():
    leaked_path_markers = ("/Users/", "LingNengAI/app/skills")
    for path in sorted(LINGNENG_SKILLS_ROOT.rglob("*")):
        if path.suffix not in {".md", ".json"}:
            continue
        text = path.read_text(encoding="utf-8")
        for marker in leaked_path_markers:
            assert marker not in text, f"{marker} leaked in {path.relative_to(REPO_ROOT)}"
