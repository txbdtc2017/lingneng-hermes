from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class SkillPackageError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        package_name: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.package_name = package_name


class SkillKind(str, Enum):
    EMPLOYEE_BASE = "employee_base"
    TASK = "task"
    CAPABILITY = "capability"
    INFRASTRUCTURE = "infrastructure"


class SkillSource(str, Enum):
    PYTHON = "python"
    IMPORTED = "imported"
    GENERATED = "generated"


class SkillLifecycle(str, Enum):
    ACTIVE = "active"
    DRAFT = "draft"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"


class LingNengSkillMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: str
    kind: SkillKind
    source: SkillSource
    status: SkillLifecycle
    user_visible: bool
    script_policy: str
    employee_type: str | None = None
    display_name: str | None = None


class SkillPackageMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    description: str
    version: str
    lingneng: LingNengSkillMetadata


class SkillResource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    directory: str
    size_bytes: int


class SkillResourceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resources: list[SkillResource] = Field(default_factory=list)

    def to_prompt_lines(self) -> list[str]:
        if not self.resources:
            return ["Resources: none"]
        lines = ["Resources:"]
        for resource in self.resources:
            lines.append(
                f"- {resource.path} ({resource.directory}, {resource.size_bytes} bytes)"
            )
        return lines


class LoadedSkillPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_name: str
    package_dir: Path = Field(repr=False)
    metadata: SkillPackageMetadata
    body: str = Field(repr=False)
    resource_manifest: SkillResourceManifest = Field(
        default_factory=SkillResourceManifest
    )


class SkillPromptWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    package_name: str | None = None


class SkillPromptFragment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_name: str
    kind: SkillKind
    version: str
    description: str
    body_excerpt: str
    resource_manifest: SkillResourceManifest = Field(
        default_factory=SkillResourceManifest
    )
    display_name: str | None = None
    truncated: bool = False

    def to_prompt_lines(self) -> list[str]:
        lines = [
            f"Package: {self.package_name}",
            f"Kind: {self.kind.value}",
            f"Version: {self.version}",
            f"Description: {self.description}",
        ]
        if self.display_name:
            lines.append(f"Display Name: {self.display_name}")
        if self.body_excerpt:
            lines.extend(["Body Excerpt:", self.body_excerpt])
        else:
            lines.extend(["Body Excerpt:", ""])
        if self.truncated:
            lines.append("Body Truncated: true")
        lines.extend(self.resource_manifest.to_prompt_lines())
        return lines


class SkillPromptContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_base: SkillPromptFragment | None = None
    selected_skill: SkillPromptFragment | None = None
    warnings: list[SkillPromptWarning] = Field(default_factory=list)
    prompt_max_chars: int | None = None

    def to_prompt_text(self) -> str:
        sections: list[str] = []
        if self.employee_base is not None:
            sections.append(
                "\n".join(
                    [
                        f"### Employee Base Skill: {self.employee_base.package_name}",
                        *self.employee_base.to_prompt_lines(),
                    ]
                )
            )
        if self.selected_skill is not None:
            sections.append(
                "\n".join(
                    [
                        f"### Selected Skill: {self.selected_skill.package_name}",
                        *self.selected_skill.to_prompt_lines(),
                    ]
                )
            )
        if self.warnings:
            warning_lines = ["### Skill Warnings"]
            for warning in self.warnings:
                package = f" [{warning.package_name}]" if warning.package_name else ""
                warning_lines.append(f"- {warning.code}{package}: {warning.message}")
            sections.append("\n".join(warning_lines))
        if not sections:
            return ""
        text = "## LingNeng Skill Context\n\n" + "\n\n".join(sections)
        if self.prompt_max_chars is None or len(text) <= self.prompt_max_chars:
            return text
        marker = "\n...[truncated]"
        limit = max(0, self.prompt_max_chars - len(marker))
        return text[:limit].rstrip() + marker
