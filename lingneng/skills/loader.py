from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.skills.models import (
    LoadedSkillPackage,
    SkillKind,
    SkillLifecycle,
    SkillPackageError,
    SkillPackageMetadata,
    SkillPromptContext,
    SkillPromptFragment,
    SkillPromptWarning,
    SkillResource,
    SkillResourceManifest,
)


EMPLOYEE_BASE_SKILL_BY_TYPE = {
    "boss_assistant": "employee-boss-assistant",
    "operation_specialist": "employee-operation-specialist",
    "product_combo_advisor": "employee-product-combo-advisor",
    "marketing_planner": "employee-marketing-planner",
    "marketing_content_creator": "employee-marketing-content-creator",
    "member_operator": "employee-member-operator",
}

_ALLOWED_RESOURCE_DIRS = {"references", "templates", "examples", "assets"}
_PACKAGE_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class LingNengSkillLoader:
    def __init__(self, settings: LingNengSettings) -> None:
        self.settings = settings
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
            warnings=warnings,
            prompt_max_chars=self.settings.skill_prompt_max_chars,
        )

    def get_package(self, name: str) -> LoadedSkillPackage | None:
        return self._ensure_packages().get(name)

    def _ensure_packages(self) -> dict[str, LoadedSkillPackage]:
        if self._packages is not None:
            return self._packages
        packages: dict[str, LoadedSkillPackage] = {}
        warnings: list[SkillPromptWarning] = []
        for root in self.settings.skill_roots:
            if not root.exists():
                warnings.append(
                    SkillPromptWarning(
                        code="SKILL_ROOT_MISSING",
                        message="Configured skill root does not exist.",
                    )
                )
                continue
            if not root.is_dir():
                warnings.append(
                    SkillPromptWarning(
                        code="SKILL_ROOT_INVALID",
                        message="Configured skill root is not a directory.",
                    )
                )
                continue
            for skill_file in self._iter_skill_files(root):
                try:
                    package = self._load_package(skill_file)
                except SkillPackageError as exc:
                    warnings.append(
                        SkillPromptWarning(
                            code=exc.code,
                            message=str(exc),
                            package_name=exc.package_name,
                        )
                    )
                    continue
                packages[package.package_name] = package
        self._packages = packages
        self._load_warnings = warnings
        return packages

    def _iter_skill_files(self, root: Path) -> list[Path]:
        candidates: list[Path] = []
        root_skill = root / "SKILL.md"
        if root_skill.is_file():
            candidates.append(root_skill)
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            child_skill = child / "SKILL.md"
            if child_skill.is_file():
                candidates.append(child_skill)
            for grandchild in sorted(child.iterdir()):
                if not grandchild.is_dir():
                    continue
                grandchild_skill = grandchild / "SKILL.md"
                if grandchild_skill.is_file():
                    candidates.append(grandchild_skill)
        return candidates

    def _load_package(self, skill_file: Path) -> LoadedSkillPackage:
        package_dir = skill_file.parent
        front_matter, body = _read_skill_file(skill_file)
        metadata = _metadata_from_front_matter(front_matter)
        if not _PACKAGE_NAME_PATTERN.fullmatch(metadata.name):
            raise SkillPackageError(
                "SKILL_PACKAGE_INVALID",
                "Skill package name must be lower-kebab-case.",
                package_name=metadata.name,
            )
        if package_dir.name != metadata.name:
            raise SkillPackageError(
                "SKILL_PACKAGE_INVALID",
                "Skill package directory name must match manifest name.",
                package_name=metadata.name,
            )
        lingneng = metadata.lingneng
        if lingneng.status is not SkillLifecycle.ACTIVE:
            raise SkillPackageError(
                "SKILL_PACKAGE_INACTIVE",
                "Skill package is not active.",
                package_name=metadata.name,
            )
        if lingneng.script_policy != "metadata_only":
            raise SkillPackageError(
                "SKILL_PACKAGE_INVALID",
                "Skill package script_policy must be metadata_only.",
                package_name=metadata.name,
            )
        if lingneng.kind is SkillKind.EMPLOYEE_BASE and not lingneng.employee_type:
            raise SkillPackageError(
                "SKILL_PACKAGE_INVALID",
                "Employee base skill must declare employee_type.",
                package_name=metadata.name,
            )
        return LoadedSkillPackage(
            package_name=metadata.name,
            package_dir=package_dir,
            metadata=metadata,
            body=body,
            resource_manifest=_resource_manifest(package_dir),
        )

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
                    package_name=skill_id,
                )
            )
            return None
        return self._fragment(package)

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
            truncated=truncated,
        )


def _read_skill_file(skill_file: Path) -> tuple[dict[str, Any], str]:
    text = skill_file.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise SkillPackageError(
            "SKILL_PACKAGE_INVALID",
            "SKILL.md must start with YAML front matter.",
            package_name=skill_file.parent.name,
        )
    end_index = next(
        (
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.strip() == "---"
        ),
        None,
    )
    if end_index is None:
        raise SkillPackageError(
            "SKILL_PACKAGE_INVALID",
            "SKILL.md front matter is not closed.",
            package_name=skill_file.parent.name,
        )
    raw_front_matter = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :]).strip()
    try:
        front_matter = yaml.safe_load(raw_front_matter) or {}
    except yaml.YAMLError as exc:
        raise SkillPackageError(
            "SKILL_PACKAGE_INVALID",
            "SKILL.md front matter is not valid YAML.",
            package_name=skill_file.parent.name,
        ) from exc
    if not isinstance(front_matter, dict):
        raise SkillPackageError(
            "SKILL_PACKAGE_INVALID",
            "SKILL.md front matter must be a mapping.",
            package_name=skill_file.parent.name,
        )
    return front_matter, body


def _metadata_from_front_matter(front_matter: dict[str, Any]) -> SkillPackageMetadata:
    metadata = front_matter.get("metadata")
    lingneng_data = metadata.get("lingneng") if isinstance(metadata, dict) else None
    payload = {
        "name": front_matter.get("name"),
        "description": front_matter.get("description"),
        "version": str(front_matter.get("version", "")),
        "lingneng": lingneng_data,
    }
    try:
        return SkillPackageMetadata.model_validate(payload)
    except ValidationError as exc:
        package_name = str(front_matter.get("name") or "")
        raise SkillPackageError(
            "SKILL_PACKAGE_INVALID",
            "Skill package manifest is invalid.",
            package_name=package_name or None,
        ) from exc


def _resource_manifest(package_dir: Path) -> SkillResourceManifest:
    resources: list[SkillResource] = []
    package_root = package_dir.resolve()
    for directory in sorted(_ALLOWED_RESOURCE_DIRS):
        resource_dir = package_dir / directory
        if not resource_dir.is_dir():
            continue
        for path in sorted(resource_dir.rglob("*")):
            if not path.is_file():
                continue
            resolved = path.resolve()
            if not _is_relative_to(resolved, package_root):
                continue
            relative = path.relative_to(package_dir)
            if relative.is_absolute() or ".." in relative.parts:
                continue
            resources.append(
                SkillResource(
                    path=relative.as_posix(),
                    directory=directory,
                    size_bytes=path.stat().st_size,
                )
            )
    return SkillResourceManifest(resources=resources)


def _bounded_excerpt(text: str, max_chars: int) -> tuple[str, bool]:
    stripped = text.strip()
    if len(stripped) <= max_chars:
        return stripped, False
    marker = "\n...[truncated]"
    limit = max(0, max_chars - len(marker))
    return stripped[:limit].rstrip() + marker, True


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
