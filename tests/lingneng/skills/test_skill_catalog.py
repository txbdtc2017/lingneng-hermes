import subprocess
from pathlib import Path

from lingneng.config.settings import LingNengSettings
from lingneng.skills.catalog import LingNengSkillCatalog, bundled_lingneng_skill_root
from tests.lingneng.skills.test_skill_loader import write_skill


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


def _settings(tmp_path: Path, **overrides: str) -> LingNengSettings:
    env = {
        "LINGNENG_APP_ENV": "test",
        "LINGNENG_RUNTIME_DIR": str(tmp_path / ".runtime-test"),
    }
    env.update(overrides)
    return LingNengSettings.from_env(env)


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


def test_bundled_lingneng_skill_root_helper_points_to_repo_root():
    root = bundled_lingneng_skill_root()
    assert root == LINGNENG_SKILLS_ROOT
    assert root.is_dir()


def test_catalog_loads_bundled_employee_base_without_env_roots(tmp_path):
    catalog = LingNengSkillCatalog(_settings(tmp_path))

    package = catalog.get_package("employee-marketing-content-creator")

    assert package is not None
    assert package.metadata.lingneng.kind.value == "employee_base"
    assert package.metadata.lingneng.employee_type == "marketing_content_creator"


def test_catalog_configured_root_overrides_bundled_package(tmp_path):
    write_skill(
        tmp_path,
        "marketing-copy-generation",
        body="## When to Use\nOVERRIDE BODY\n",
    )
    catalog = LingNengSkillCatalog(
        _settings(tmp_path, LINGNENG_SKILL_ROOTS=str(tmp_path))
    )

    package = catalog.get_package("marketing-copy-generation")

    assert package is not None
    assert "OVERRIDE BODY" in package.body


def test_catalog_list_filters_by_kind_and_employee_type(tmp_path):
    catalog = LingNengSkillCatalog(_settings(tmp_path))

    task_items = catalog.list_skills(
        kind="task",
        employee_type="marketing_planner",
    )
    names = {item.package_name for item in task_items}

    assert "restaurant-campaign-planning" in names
    assert all(item.kind.value == "task" for item in task_items)


def test_catalog_search_matches_triggers_and_descriptions(tmp_path):
    catalog = LingNengSkillCatalog(_settings(tmp_path))

    results = catalog.search_skills(
        "小红书文案",
        employee_type="marketing_content_creator",
    )
    names = [item.package_name for item in results]

    assert "marketing-copy-generation" in names
    assert results[0].score is not None
    assert results[0].score >= results[-1].score


def test_catalog_read_skill_returns_bounded_body_and_manifest(tmp_path):
    catalog = LingNengSkillCatalog(_settings(tmp_path))

    result = catalog.read_skill("restaurant-campaign-planning", max_chars=800)

    assert result.success is True
    assert result.skill is not None
    assert result.skill.package_name == "restaurant-campaign-planning"
    assert len(result.body) <= 820
    assert any(
        resource.path == "references/marketing-nodes.md"
        for resource in result.resource_manifest.resources
    )


def test_catalog_resource_read_rejects_path_traversal(tmp_path):
    catalog = LingNengSkillCatalog(_settings(tmp_path))

    result = catalog.read_skill_resource(
        "restaurant-campaign-planning",
        "../SKILL.md",
    )

    assert result.success is False
    assert result.code == "RESOURCE_NOT_ALLOWED"
