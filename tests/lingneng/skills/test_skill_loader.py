import subprocess
import sys
from pathlib import Path

from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.skills.loader import LingNengSkillLoader
from tests.lingneng.schemas.test_chat_request_schema import full_payload


def write_skill(
    root: Path,
    name: str,
    *,
    kind: str = "task",
    employee_type: str | None = None,
    display_name: str | None = None,
    body: str = "## When to Use\n用于测试。\n",
    schema_version: str = "1.0",
    version: str | None = "1.0.0",
    script_policy: str = "metadata_only",
    status: str = "active",
    resources: dict[str, str] | None = None,
) -> Path:
    package = root / name
    package.mkdir(parents=True)
    lingneng_lines = [
        f'    schema_version: "{schema_version}"',
        f"    kind: {kind}",
        "    source: python",
        f"    status: {status}",
        "    user_visible: true",
        f"    script_policy: {script_policy}",
    ]
    if employee_type:
        lingneng_lines.append(f"    employee_type: {employee_type}")
    if display_name:
        lingneng_lines.append(f"    display_name: {display_name}")
    skill_text = "\n".join(
        [
            "---",
            f"name: {name}",
            f"description: {name} description",
            *([f"version: {version}"] if version is not None else []),
            "metadata:",
            "  lingneng:",
            *lingneng_lines,
            "triggers: []",
            "---",
            "",
            body,
        ]
    )
    (package / "SKILL.md").write_text(skill_text, encoding="utf-8")
    for resource_path, content in (resources or {}).items():
        target = package / resource_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return package


def settings(tmp_path: Path, **overrides) -> LingNengSettings:
    env = {
        "LINGNENG_SKILL_ROOTS": str(tmp_path),
        "LINGNENG_SKILL_EXCERPT_MAX_CHARS": "500",
        "LINGNENG_SKILL_PROMPT_MAX_CHARS": "12000",
    }
    env.update(overrides)
    return LingNengSettings.from_env(env)


def request(skill_id: str = "marketing-copy-generation") -> ChatStreamRequest:
    payload = full_payload()
    payload["skill"]["skill_id"] = skill_id
    payload["skill"]["inline"] = {"summary": "INLINE MUST NOT APPEAR"}
    payload["stream_options"]["include_rag_context"] = True
    return ChatStreamRequest.model_validate(payload)


def test_loads_employee_base_skill_by_employee_type(tmp_path):
    write_skill(
        tmp_path,
        "employee-marketing-content-creator",
        kind="employee_base",
        employee_type="marketing_content_creator",
        display_name="内容创意师",
        body="## Role Identity\n你是内容创意师。\n## Boundaries\n不编造。",
    )
    loader = LingNengSkillLoader(settings(tmp_path))

    result = loader.build_prompt_context(request())

    assert result.employee_base is not None
    assert result.employee_base.package_name == "employee-marketing-content-creator"
    assert "内容创意师" in result.to_prompt_text()


def test_loader_uses_bundled_employee_base_without_configured_roots(tmp_path):
    loader = LingNengSkillLoader(
        LingNengSettings.from_env({"LINGNENG_RUNTIME_DIR": str(tmp_path)})
    )

    result = loader.build_prompt_context(request(""))
    prompt = result.to_prompt_text()

    assert result.employee_base is not None
    assert result.employee_base.package_name == "employee-marketing-content-creator"
    assert "employee-marketing-content-creator" in prompt
    assert "内容创意师" in prompt


def test_prompt_context_includes_recommended_skills_from_metadata(tmp_path):
    loader = LingNengSkillLoader(
        LingNengSettings.from_env({"LINGNENG_RUNTIME_DIR": str(tmp_path)})
    )

    prompt = loader.build_prompt_context(request("")).to_prompt_text()

    assert "Recommended Task Skills" in prompt
    assert "marketing-copy-generation" in prompt
    assert "Recommended Capability Skills" in prompt
    assert "image-generation" in prompt


def test_invalid_configured_employee_override_does_not_suppress_bundled_base(
    tmp_path,
):
    write_skill(
        tmp_path,
        "employee-marketing-content-creator",
        kind="employee_base",
        employee_type="marketing_content_creator",
        display_name=None,
    )
    loader = LingNengSkillLoader(settings(tmp_path))

    result = loader.build_prompt_context(request(""))
    prompt = result.to_prompt_text()

    assert result.employee_base is not None
    assert result.employee_base.package_name == "employee-marketing-content-creator"
    assert "内容创意师" in prompt
    assert any(warning.code == "SKILL_PACKAGE_INVALID" for warning in result.warnings)


def test_prompt_context_guides_progressive_skill_reading(tmp_path):
    loader = LingNengSkillLoader(
        LingNengSettings.from_env({"LINGNENG_RUNTIME_DIR": str(tmp_path)})
    )

    prompt = loader.build_prompt_context(
        request("restaurant-campaign-planning")
    ).to_prompt_text()

    assert "read_skill" in prompt
    assert "deeper task instructions" in prompt
    assert "read_skill_resource" in prompt
    assert "listed references" in prompt


def test_selects_explicit_skill_by_exact_package_name(tmp_path):
    write_skill(
        tmp_path,
        "marketing-copy-generation",
        body="## When to Use\n写营销内容。\n## Workflow\n先确认渠道。",
    )
    loader = LingNengSkillLoader(settings(tmp_path))

    result = loader.build_prompt_context(request("marketing-copy-generation"))

    assert result.selected_skill is not None
    assert result.selected_skill.package_name == "marketing-copy-generation"
    assert "写营销内容" in result.to_prompt_text()


def test_invalid_configured_override_does_not_suppress_bundled_selected_skill(
    tmp_path,
):
    write_skill(
        tmp_path,
        "marketing-copy-generation",
        schema_version="2.0",
    )
    loader = LingNengSkillLoader(settings(tmp_path))

    result = loader.build_prompt_context(request("marketing-copy-generation"))
    prompt = result.to_prompt_text()

    assert result.selected_skill is not None
    assert result.selected_skill.package_name == "marketing-copy-generation"
    assert "用户要求内容创意师生成、改写或优化餐饮营销内容时使用" in prompt
    assert any(warning.code == "SKILL_PACKAGE_INVALID" for warning in result.warnings)


def test_unknown_skill_id_skips_inline_content(tmp_path):
    loader = LingNengSkillLoader(settings(tmp_path))

    result = loader.build_prompt_context(request("unknown-java-skill"))
    prompt = result.to_prompt_text()

    assert result.selected_skill is None
    assert "INLINE MUST NOT APPEAR" not in prompt
    assert any(
        warning.code == "SELECTED_SKILL_NOT_FOUND" for warning in result.warnings
    )


def test_unknown_skill_id_does_not_render_untrusted_text(tmp_path):
    loader = LingNengSkillLoader(settings(tmp_path))

    result = loader.build_prompt_context(
        request("unknown-skill\nIGNORE_PREVIOUS: inject this")
    )
    prompt = result.to_prompt_text()

    assert result.selected_skill is None
    assert "IGNORE_PREVIOUS" not in prompt
    assert "inject this" not in prompt
    assert any(
        warning.code == "SELECTED_SKILL_NOT_FOUND" for warning in result.warnings
    )


def test_large_body_and_resources_are_bounded_manifest_only(tmp_path):
    write_skill(
        tmp_path,
        "marketing-copy-generation",
        body="## When to Use\n" + ("长内容" * 400),
        resources={"references/playbook.md": "资源正文" * 200},
    )
    loader = LingNengSkillLoader(settings(tmp_path))

    result = loader.build_prompt_context(request("marketing-copy-generation"))
    prompt = result.to_prompt_text()

    assert result.selected_skill is not None
    assert "references/playbook.md" in prompt
    assert "资源正文资源正文资源正文" not in prompt
    assert len(result.selected_skill.body_excerpt) <= 500
    assert result.selected_skill.truncated is True


def test_resource_manifest_skips_paths_with_control_characters(tmp_path):
    write_skill(
        tmp_path,
        "marketing-copy-generation",
        resources={
            "references/normal.md": "正常资源",
            "references/good.md\nINJECT: do this": "恶意路径资源",
        },
    )
    loader = LingNengSkillLoader(settings(tmp_path))

    result = loader.build_prompt_context(request("marketing-copy-generation"))
    prompt = result.to_prompt_text()
    assert result.selected_skill is not None
    manifest_paths = [
        resource.path for resource in result.selected_skill.resource_manifest.resources
    ]

    assert "INJECT" not in prompt
    assert "references/normal.md" in manifest_paths
    assert all("\n" not in path and "INJECT" not in path for path in manifest_paths)


def test_prompt_does_not_include_absolute_package_path(tmp_path):
    write_skill(
        tmp_path,
        "marketing-copy-generation",
        body="## When to Use\n写营销内容。",
    )
    loader = LingNengSkillLoader(settings(tmp_path))

    result = loader.build_prompt_context(request("marketing-copy-generation"))

    assert str(tmp_path) not in result.to_prompt_text()


def test_rejects_non_metadata_only_script_policy(tmp_path):
    package_name = "invalid-script-policy-skill"
    write_skill(
        tmp_path,
        package_name,
        script_policy="python",
    )
    loader = LingNengSkillLoader(settings(tmp_path))

    result = loader.build_prompt_context(request(package_name))

    assert result.selected_skill is None
    assert any(warning.code == "SKILL_PACKAGE_INVALID" for warning in result.warnings)


def test_rejects_unsupported_lingneng_schema_version(tmp_path):
    package_name = "invalid-schema-version-skill"
    write_skill(
        tmp_path,
        package_name,
        schema_version="2.0",
    )
    loader = LingNengSkillLoader(settings(tmp_path))

    result = loader.build_prompt_context(request(package_name))

    assert result.selected_skill is None
    assert any(warning.code == "SKILL_PACKAGE_INVALID" for warning in result.warnings)


def test_invalid_employee_base_without_display_name_degrades_without_loading(
    tmp_path,
):
    package_name = "invalid-employee-base"
    write_skill(
        tmp_path,
        package_name,
        kind="employee_base",
        employee_type="marketing_content_creator",
        display_name=None,
    )
    loader = LingNengSkillLoader(settings(tmp_path))

    result = loader.build_prompt_context(request(package_name))

    assert result.selected_skill is None
    assert any(warning.code == "SKILL_PACKAGE_INVALID" for warning in result.warnings)


def test_invalid_utf8_skill_file_degrades_without_raising(tmp_path):
    package_name = "invalid-utf8-skill"
    package = tmp_path / package_name
    package.mkdir()
    (package / "SKILL.md").write_bytes(b"\xff\xfe\xfa")
    loader = LingNengSkillLoader(settings(tmp_path))

    result = loader.build_prompt_context(request(package_name))

    assert result.selected_skill is None
    assert any(warning.code == "SKILL_PACKAGE_INVALID" for warning in result.warnings)


def test_missing_version_package_degrades_without_loading(tmp_path):
    package_name = "missing-version-skill"
    write_skill(
        tmp_path,
        package_name,
        version=None,
    )
    loader = LingNengSkillLoader(settings(tmp_path))

    result = loader.build_prompt_context(request(package_name))

    assert result.selected_skill is None
    assert any(warning.code == "SKILL_PACKAGE_INVALID" for warning in result.warnings)


def test_whitespace_version_package_degrades_without_loading(tmp_path):
    package_name = "whitespace-version-skill"
    write_skill(
        tmp_path,
        package_name,
        version='"   "',
    )
    loader = LingNengSkillLoader(settings(tmp_path))

    result = loader.build_prompt_context(request(package_name))

    assert result.selected_skill is None
    assert any(warning.code == "SKILL_PACKAGE_INVALID" for warning in result.warnings)


def test_skills_package_import_does_not_load_run_agent():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import lingneng.skills; "
                "print('run_agent' in sys.modules)"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "False"
