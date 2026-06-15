from __future__ import annotations

from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.skills.catalog import LingNengSkillCatalog
from lingneng.skills.models import (
    LoadedSkillPackage,
    SkillKind,
    SkillPromptContext,
    SkillPromptFragment,
    SkillResourceManifest,
    SkillPromptWarning,
)


EMPLOYEE_BASE_SKILL_BY_TYPE = {
    "boss_assistant": "employee-boss-assistant",
    "operation_specialist": "employee-operation-specialist",
    "product_combo_advisor": "employee-product-combo-advisor",
    "marketing_planner": "employee-marketing-planner",
    "marketing_content_creator": "employee-marketing-content-creator",
    "member_operator": "employee-member-operator",
}

INFRASTRUCTURE_CONTRACT_PACKAGES = (
    "employee-answer-semantics-contract",
    "business-answer-contract",
    "tool-observation-contract",
    "artifact-output-contract",
    "rag-citation-contract",
)


class LingNengSkillLoader:
    def __init__(self, settings: LingNengSettings) -> None:
        self.settings = settings
        self.catalog = LingNengSkillCatalog(settings)
        self._packages: dict[str, LoadedSkillPackage] | None = None
        self._load_warnings: list[SkillPromptWarning] = []

    def build_prompt_context(self, request: ChatStreamRequest) -> SkillPromptContext:
        packages = self._ensure_packages()
        warnings = list(self._load_warnings)
        employee_base = self._employee_base_fragment(request, packages, warnings)
        selected_skill = self._selected_skill_fragment(request, packages, warnings)
        return SkillPromptContext(
            employee_base=employee_base,
            selected_skill=selected_skill,
            infrastructure_fragments=[
                *self._infrastructure_contract_fragments(packages, warnings),
                _handoff_guidance_fragment(),
            ],
            warnings=warnings,
            prompt_max_chars=self.settings.skill_prompt_max_chars,
        )

    def get_package(self, name: str) -> LoadedSkillPackage | None:
        return self._ensure_packages().get(name)

    def _ensure_packages(self) -> dict[str, LoadedSkillPackage]:
        if self._packages is not None:
            return self._packages
        self._packages = self.catalog.packages()
        self._load_warnings = self.catalog.warnings
        return self._packages

    def _employee_base_fragment(
        self,
        request: ChatStreamRequest,
        packages: dict[str, LoadedSkillPackage],
        warnings: list[SkillPromptWarning],
    ) -> SkillPromptFragment | None:
        employee_type = request.employee.employee_type.value
        package_name = EMPLOYEE_BASE_SKILL_BY_TYPE.get(employee_type)
        if package_name is None:
            return None
        package = packages.get(package_name)
        if package is None:
            warnings.append(
                SkillPromptWarning(
                    code="EMPLOYEE_BASE_SKILL_NOT_FOUND",
                    message="Configured roots do not contain this employee base skill.",
                    package_name=package_name,
                )
            )
            return None
        lingneng = package.metadata.lingneng
        if (
            lingneng.kind is not SkillKind.EMPLOYEE_BASE
            or lingneng.employee_type != employee_type
        ):
            warnings.append(
                SkillPromptWarning(
                    code="EMPLOYEE_BASE_SKILL_INVALID",
                    message="Employee base skill manifest does not match request employee_type.",
                    package_name=package_name,
                )
            )
            return None
        return self._fragment(package)

    def _selected_skill_fragment(
        self,
        request: ChatStreamRequest,
        packages: dict[str, LoadedSkillPackage],
        warnings: list[SkillPromptWarning],
    ) -> SkillPromptFragment | None:
        skill_id = request.skill.skill_id.strip()
        if not skill_id:
            return None
        package = packages.get(skill_id)
        if package is None:
            warnings.append(
                SkillPromptWarning(
                    code="SELECTED_SKILL_NOT_FOUND",
                    message="Selected skill_id does not match a configured package.",
                )
            )
            return None
        return self._fragment(package)

    def _infrastructure_contract_fragments(
        self,
        packages: dict[str, LoadedSkillPackage],
        warnings: list[SkillPromptWarning],
    ) -> list[SkillPromptFragment]:
        fragments: list[SkillPromptFragment] = []
        for package_name in INFRASTRUCTURE_CONTRACT_PACKAGES:
            package = packages.get(package_name)
            if package is None:
                warnings.append(
                    SkillPromptWarning(
                        code="INFRASTRUCTURE_CONTRACT_NOT_FOUND",
                        message="Configured roots do not contain this infrastructure contract.",
                        package_name=package_name,
                    )
                )
                continue
            if package.metadata.lingneng.kind is not SkillKind.INFRASTRUCTURE:
                warnings.append(
                    SkillPromptWarning(
                        code="INFRASTRUCTURE_CONTRACT_INVALID",
                        message="Infrastructure contract package kind must be infrastructure.",
                        package_name=package_name,
                    )
                )
                continue
            fragments.append(self._fragment(package))
        return fragments

    def _fragment(self, package: LoadedSkillPackage) -> SkillPromptFragment:
        excerpt, truncated = _bounded_excerpt(
            package.body,
            self.settings.skill_excerpt_max_chars,
        )
        lingneng = package.metadata.lingneng
        return SkillPromptFragment(
            package_name=package.package_name,
            kind=lingneng.kind,
            version=package.metadata.version,
            description=package.metadata.description,
            body_excerpt=excerpt,
            resource_manifest=package.resource_manifest,
            display_name=lingneng.display_name,
            recommended_task_skills=list(lingneng.recommended_task_skills),
            recommended_capabilities=list(lingneng.recommended_capabilities),
            tools=list(lingneng.tools),
            truncated=truncated,
        )


def _bounded_excerpt(text: str, max_chars: int) -> tuple[str, bool]:
    stripped = text.strip()
    if len(stripped) <= max_chars:
        return stripped, False
    marker = "\n...[truncated]"
    limit = max(0, max_chars - len(marker))
    return stripped[:limit].rstrip() + marker, True


def _handoff_guidance_fragment() -> SkillPromptFragment:
    return SkillPromptFragment(
        package_name="lingneng-employee-handoff-guidance",
        kind=SkillKind.INFRASTRUCTURE,
        version="1.0.0",
        description="员工跳转工具使用边界",
        body_excerpt=(
            "## Employee Handoff Guidance\n"
            "- current employee answers in-scope requests directly.\n"
            "- smalltalk/meta/general tasks do not trigger handoff.\n"
            "- explicit user switch requests use employee_handoff suggest when the target employee is known.\n"
            "- ambiguous ownership can use employee_handoff confirm for 2-4 known employee choices.\n"
            "- boss fallback is guidance, not threshold routing.\n"
            "- After terminal suggest/confirm, reply with public_reply and stop this turn.\n"
            "- No pre-agent router, hidden route scores, invented thresholds, or invented employee types."
        ),
        resource_manifest=SkillResourceManifest(),
        display_name="员工跳转指引",
        recommended_task_skills=[],
        recommended_capabilities=[],
        tools=["employee_handoff", "search_skills", "read_skill"],
        truncated=False,
    )
