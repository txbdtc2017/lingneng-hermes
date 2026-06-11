from __future__ import annotations

from dataclasses import dataclass
import mimetypes
from pathlib import Path, PurePosixPath
import re
from typing import Any

import yaml
from pydantic import ValidationError

from agent.skill_utils import EXCLUDED_SKILL_DIRS
from lingneng.config.settings import LingNengSettings
from lingneng.skills.models import (
    LoadedSkillPackage,
    SkillCatalogItem,
    SkillKind,
    SkillLifecycle,
    SkillPackageError,
    SkillPackageMetadata,
    SkillPromptWarning,
    SkillReadResult,
    SkillResource,
    SkillResourceManifest,
    SkillResourceReadResult,
)


_ALLOWED_RESOURCE_DIRS = {"references", "templates", "examples", "assets"}
_EXCLUDED_SCAN_DIRS = set(EXCLUDED_SKILL_DIRS) | {
    ".cache",
    ".codex",
    ".hypothesis",
    ".pytest-cache",
    ".uv-cache",
    "cache",
    "dist",
    "build",
}
_KIND_ORDER = {
    SkillKind.EMPLOYEE_BASE: 0,
    SkillKind.TASK: 1,
    SkillKind.CAPABILITY: 2,
    SkillKind.INFRASTRUCTURE: 3,
}
_PACKAGE_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_WORD_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]")
_TRUNCATION_MARKER = "\n...[truncated]"

_DEFAULT_SKILL_READ_MAX_CHARS = 12000
_DEFAULT_SKILL_RESOURCE_MAX_CHARS = 12000
_DEFAULT_SKILL_RESOURCE_MAX_BYTES = 262144


@dataclass(frozen=True)
class SkillCatalogIndex:
    packages: dict[str, LoadedSkillPackage]
    warnings: list[SkillPromptWarning]


def bundled_lingneng_skill_root() -> Path:
    return Path(__file__).resolve().parents[2] / "skills" / "lingneng"


class LingNengSkillCatalog:
    def __init__(self, settings: LingNengSettings) -> None:
        self.settings = settings
        self._index: SkillCatalogIndex | None = None

    @property
    def warnings(self) -> list[SkillPromptWarning]:
        return list(self.index().warnings)

    def roots(self) -> list[Path]:
        return [bundled_lingneng_skill_root(), *self.settings.skill_roots]

    def index(self) -> SkillCatalogIndex:
        if self._index is None:
            self._index = self._build_index()
        return self._index

    def packages(self) -> dict[str, LoadedSkillPackage]:
        return self.index().packages

    def get_package(self, name: str) -> LoadedSkillPackage | None:
        if not _PACKAGE_NAME_RE.fullmatch(name or ""):
            return None
        return self.packages().get(name)

    def list_skills(
        self,
        kind: str | SkillKind | None = None,
        employee_type: str | None = None,
        include_infrastructure: bool = False,
        limit: int | None = None,
    ) -> list[SkillCatalogItem]:
        items = [
            _catalog_item(package)
            for package in self.packages().values()
            if _matches_kind(package, kind, include_infrastructure)
            and _matches_employee(package, employee_type)
        ]
        items.sort(key=lambda item: (_KIND_ORDER[item.kind], item.package_name))
        return items[: _limit(limit, default=20, maximum=50)]

    def search_skills(
        self,
        query: str,
        employee_type: str | None = None,
        kind: str | SkillKind | None = None,
        limit: int | None = None,
    ) -> list[SkillCatalogItem]:
        terms = _query_terms(query)
        if not terms:
            return []
        results: list[SkillCatalogItem] = []
        for package in self.packages().values():
            if not _matches_kind(package, kind, include_infrastructure=True):
                continue
            if not _matches_employee(package, employee_type):
                continue
            score, matched_terms = _score_package(package, terms)
            if score <= 0:
                continue
            item = _catalog_item(package)
            item.score = score
            item.matched_terms = matched_terms
            results.append(item)
        results.sort(key=lambda item: (-(item.score or 0), item.package_name))
        return results[: _limit(limit, default=10, maximum=20)]

    def read_skill(
        self,
        skill_id: str,
        max_chars: int | None = None,
    ) -> SkillReadResult:
        package = self.get_package(skill_id)
        if package is None:
            return SkillReadResult(
                success=False,
                code="NOT_FOUND",
                message="Skill not found.",
            )
        read_max = _setting_int(
            self.settings,
            "skill_read_max_chars",
            _DEFAULT_SKILL_READ_MAX_CHARS,
        )
        default_chars = _setting_int(
            self.settings,
            "skill_excerpt_max_chars",
            min(4000, read_max),
        )
        limit = _limit(max_chars, default=default_chars, maximum=read_max)
        body, truncated = _bounded_text(package.body, limit)
        return SkillReadResult(
            success=True,
            skill=_catalog_item(package),
            body=body,
            body_truncated=truncated,
            resource_manifest=package.resource_manifest,
            warnings=self.warnings,
        )

    def read_skill_resource(
        self,
        skill_id: str,
        resource_id: str,
        max_chars: int | None = None,
        max_bytes: int | None = None,
    ) -> SkillResourceReadResult:
        public_skill_id = _public_skill_id(skill_id)
        package = self.get_package(skill_id)
        if package is None:
            return SkillResourceReadResult(
                success=False,
                skill_id=public_skill_id,
                resource_id=_public_resource_id(resource_id),
                code="NOT_FOUND",
                message="Skill not found.",
            )
        resource_path = _safe_resource_path(resource_id)
        if resource_path is None:
            return _resource_error(skill_id, resource_id, "RESOURCE_NOT_ALLOWED")
        manifest_resource = _manifest_resource(package, resource_path)
        if manifest_resource is None:
            return _resource_error(skill_id, resource_id, "RESOURCE_NOT_ALLOWED")

        target = (package.package_dir / resource_path).resolve()
        package_root = package.package_dir.resolve()
        if not _is_relative_to(target, package_root) or not target.is_file():
            return _resource_error(skill_id, resource_id, "RESOURCE_NOT_ALLOWED")

        try:
            size = target.stat().st_size
        except OSError:
            return _resource_error(skill_id, resource_id, "RESOURCE_UNREADABLE")

        configured_max_bytes = _setting_int(
            self.settings,
            "skill_resource_max_bytes",
            _DEFAULT_SKILL_RESOURCE_MAX_BYTES,
        )
        effective_max_bytes = _max_bytes(max_bytes, configured_max_bytes)
        if size > effective_max_bytes:
            return _resource_error(
                skill_id,
                resource_id,
                "RESOURCE_TOO_LARGE",
                size_bytes=size,
            )
        try:
            content = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return _resource_error(
                skill_id,
                resource_id,
                "RESOURCE_UNREADABLE",
                size_bytes=size,
            )

        configured_max_chars = _setting_int(
            self.settings,
            "skill_resource_max_chars",
            _DEFAULT_SKILL_RESOURCE_MAX_CHARS,
        )
        limit = _limit(
            max_chars,
            default=configured_max_chars,
            maximum=configured_max_chars,
        )
        bounded_content, truncated = _bounded_text(content, limit)
        resource_posix = resource_path.as_posix()
        return SkillResourceReadResult(
            success=True,
            skill_id=package.package_name,
            resource_id=resource_posix,
            content=bounded_content,
            content_truncated=truncated,
            size_bytes=manifest_resource.size_bytes,
            mime_type=mimetypes.guess_type(resource_posix)[0] or "text/plain",
        )

    def _build_index(self) -> SkillCatalogIndex:
        packages: dict[str, LoadedSkillPackage] = {}
        warnings: list[SkillPromptWarning] = []
        for root in self.roots():
            try:
                root_exists = root.exists()
                root_is_dir = root.is_dir()
            except OSError:
                warnings.append(
                    SkillPromptWarning(
                        code="SKILL_ROOT_INVALID",
                        message="Skill root could not be inspected.",
                    )
                )
                continue
            if not root_exists:
                warnings.append(
                    SkillPromptWarning(
                        code="SKILL_ROOT_MISSING",
                        message="Skill root does not exist.",
                    )
                )
                continue
            if not root_is_dir:
                warnings.append(
                    SkillPromptWarning(
                        code="SKILL_ROOT_INVALID",
                        message="Skill root is not a directory.",
                    )
                )
                continue
            for skill_file in _iter_skill_files(root):
                try:
                    package = _load_package_from_skill_file(skill_file)
                except SkillPackageError as exc:
                    warnings.append(
                        SkillPromptWarning(
                            code=exc.code,
                            message=str(exc),
                            package_name=_public_package_name(exc.package_name),
                        )
                    )
                    continue
                except Exception:
                    warnings.append(
                        SkillPromptWarning(
                            code="SKILL_PACKAGE_INVALID",
                            message="Skill package could not be loaded.",
                            package_name=_public_package_name(skill_file.parent.name),
                        )
                    )
                    continue
                packages[package.package_name] = package
        return SkillCatalogIndex(packages=packages, warnings=warnings)


def _load_package_from_skill_file(skill_file: Path) -> LoadedSkillPackage:
    front_matter, body = _read_skill_file(skill_file)
    metadata = _metadata_from_front_matter(front_matter)
    if not _PACKAGE_NAME_RE.fullmatch(metadata.name):
        raise SkillPackageError(
            "SKILL_PACKAGE_INVALID",
            "Skill package name must be lower-kebab-case.",
            package_name=metadata.name,
        )
    package_dir = skill_file.parent
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
    if lingneng.kind is SkillKind.EMPLOYEE_BASE and (
        not lingneng.employee_type or not lingneng.display_name
    ):
        raise SkillPackageError(
            "SKILL_PACKAGE_INVALID",
            "Employee base skill must declare employee_type and display_name.",
            package_name=metadata.name,
        )
    return LoadedSkillPackage(
        package_name=metadata.name,
        package_dir=package_dir,
        metadata=metadata,
        body=body,
        resource_manifest=_resource_manifest(package_dir),
    )


def _read_skill_file(skill_file: Path) -> tuple[dict[str, Any], str]:
    try:
        text = skill_file.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise SkillPackageError(
            "SKILL_PACKAGE_INVALID",
            "SKILL.md must be valid UTF-8.",
            package_name=skill_file.parent.name,
        ) from exc
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
        "version": front_matter.get("version"),
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


def _iter_skill_files(root: Path) -> list[Path]:
    candidates: list[Path] = []
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        directory, depth = stack.pop()
        if directory.name in _EXCLUDED_SCAN_DIRS:
            continue
        skill_file = directory / "SKILL.md"
        if skill_file.is_file():
            candidates.append(skill_file)
        if depth >= 3:
            continue
        try:
            children = sorted(directory.iterdir(), key=lambda path: path.name)
        except OSError:
            continue
        for child in reversed(children):
            if not child.is_dir():
                continue
            if child.name in _EXCLUDED_SCAN_DIRS:
                continue
            stack.append((child, depth + 1))
    return sorted(candidates)


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
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if not _is_relative_to(resolved, package_root):
                continue
            try:
                relative = path.relative_to(package_dir)
            except ValueError:
                continue
            if not _resource_relative_path_allowed(relative):
                continue
            try:
                size_bytes = path.stat().st_size
            except OSError:
                continue
            resources.append(
                SkillResource(
                    path=relative.as_posix(),
                    directory=directory,
                    size_bytes=size_bytes,
                )
            )
    return SkillResourceManifest(resources=resources)


def _catalog_item(package: LoadedSkillPackage) -> SkillCatalogItem:
    lingneng = package.metadata.lingneng
    return SkillCatalogItem(
        package_name=package.package_name,
        description=package.metadata.description,
        kind=lingneng.kind,
        version=package.metadata.version,
        display_name=lingneng.display_name,
        employee_type=lingneng.employee_type,
        target_employee_types=list(lingneng.target_employee_types),
        tools=list(lingneng.tools),
        recommended_task_skills=list(lingneng.recommended_task_skills),
        recommended_capabilities=list(lingneng.recommended_capabilities),
        tags=list(lingneng.tags),
        domains=list(lingneng.domains),
    )


def _matches_kind(
    package: LoadedSkillPackage,
    kind: str | SkillKind | None,
    include_infrastructure: bool,
) -> bool:
    package_kind = package.metadata.lingneng.kind
    expected = _coerce_kind(kind)
    if expected is not None:
        return package_kind is expected
    if kind is not None:
        return False
    return include_infrastructure or package_kind is not SkillKind.INFRASTRUCTURE


def _matches_employee(
    package: LoadedSkillPackage,
    employee_type: str | None,
) -> bool:
    if not employee_type:
        return True
    lingneng = package.metadata.lingneng
    if lingneng.kind is SkillKind.EMPLOYEE_BASE:
        return lingneng.employee_type == employee_type
    if lingneng.kind is SkillKind.TASK:
        return employee_type in lingneng.target_employee_types
    return True


def _score_package(
    package: LoadedSkillPackage,
    terms: list[str],
) -> tuple[float, list[str]]:
    front_matter = _safe_front_matter(package)
    triggers = _string_list(front_matter.get("triggers"))
    lingneng = package.metadata.lingneng
    weighted_fields = [
        (package.package_name, 35.0),
        (package.metadata.description, 30.0),
        (" ".join(triggers), 30.0),
        (lingneng.display_name or "", 24.0),
        (lingneng.employee_type or "", 16.0),
        (" ".join(lingneng.tags), 14.0),
        (" ".join(lingneng.domains), 14.0),
        (" ".join(lingneng.tools), 12.0),
        (" ".join(lingneng.recommended_task_skills), 12.0),
        (" ".join(lingneng.recommended_capabilities), 12.0),
        (" ".join(lingneng.target_employee_types), 12.0),
        (" ".join(lingneng.supporting_skills), 10.0),
        (_body_search_excerpt(package.body), 4.0),
    ]
    score = 0.0
    matched_terms: list[str] = []
    seen: set[str] = set()
    for term in terms:
        term_score = 0.0
        for value, weight in weighted_fields:
            if _contains_term(value, term):
                term_score += weight if len(term) > 1 else max(1.0, weight / 10.0)
        if term_score <= 0:
            continue
        score += term_score
        if term not in seen:
            matched_terms.append(term)
            seen.add(term)
    return score, matched_terms


def _query_terms(query: str) -> list[str]:
    normalized = _normalize_text(query)
    if not normalized:
        return []
    terms: list[str] = []
    compact = normalized.replace(" ", "")
    if compact:
        terms.append(compact)
    terms.extend(_WORD_RE.findall(normalized))
    deduped: list[str] = []
    seen: set[str] = set()
    for term in terms:
        if not term or term in seen:
            continue
        deduped.append(term)
        seen.add(term)
    return deduped


def _safe_resource_path(resource_id: str) -> Path | None:
    if not resource_id or _text_has_control_chars(resource_id):
        return None
    if "\\" in resource_id:
        return None
    posix_path = PurePosixPath(resource_id)
    if posix_path.is_absolute():
        return None
    parts = posix_path.parts
    if not parts or parts[0] not in _ALLOWED_RESOURCE_DIRS:
        return None
    if any(part in {"", ".", ".."} for part in parts):
        return None
    if any(part.startswith(".") for part in parts):
        return None
    if any(_text_has_control_chars(part) for part in parts):
        return None
    return Path(*parts)


def _manifest_resource(
    package: LoadedSkillPackage,
    resource_path: Path,
) -> SkillResource | None:
    resource_id = resource_path.as_posix()
    for resource in package.resource_manifest.resources:
        if resource.path == resource_id:
            return resource
    return None


def _resource_error(
    skill_id: str,
    resource_id: str,
    code: str,
    *,
    size_bytes: int = 0,
) -> SkillResourceReadResult:
    return SkillResourceReadResult(
        success=False,
        skill_id=_public_skill_id(skill_id),
        resource_id=_public_resource_id(resource_id),
        content="",
        content_truncated=False,
        size_bytes=size_bytes,
        code=code,
        message=_resource_error_message(code),
    )


def _resource_error_message(code: str) -> str:
    messages = {
        "NOT_FOUND": "Skill not found.",
        "RESOURCE_NOT_ALLOWED": "Resource is not listed in the skill manifest.",
        "RESOURCE_TOO_LARGE": "Resource exceeds the configured size limit.",
        "RESOURCE_UNREADABLE": "Resource could not be read as UTF-8 text.",
    }
    return messages.get(code, "Resource read failed.")


def _resource_relative_path_allowed(path: Path) -> bool:
    if path.is_absolute() or not path.parts:
        return False
    if path.parts[0] not in _ALLOWED_RESOURCE_DIRS:
        return False
    if ".." in path.parts:
        return False
    if any(part.startswith(".") for part in path.parts):
        return False
    return not _path_has_control_chars(path)


def _coerce_kind(kind: str | SkillKind | None) -> SkillKind | None:
    if kind is None:
        return None
    if isinstance(kind, SkillKind):
        return kind
    try:
        return SkillKind(str(kind))
    except ValueError:
        return None


def _safe_front_matter(package: LoadedSkillPackage) -> dict[str, Any]:
    try:
        front_matter, _body = _read_skill_file(package.package_dir / "SKILL.md")
    except SkillPackageError:
        return {}
    return front_matter


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _body_search_excerpt(body: str) -> str:
    return body[:8000]


def _contains_term(value: str, term: str) -> bool:
    if not value:
        return False
    return term in _normalize_text(value).replace(" ", "")


def _normalize_text(value: str) -> str:
    return " ".join(str(value).lower().split())


def _bounded_text(text: str, max_chars: int) -> tuple[str, bool]:
    stripped = text.strip()
    if len(stripped) <= max_chars:
        return stripped, False
    limit = max(0, max_chars - len(_TRUNCATION_MARKER))
    return stripped[:limit].rstrip() + _TRUNCATION_MARKER, True


def _limit(value: int | None, *, default: int, maximum: int) -> int:
    try:
        raw = default if value is None else int(value)
    except (TypeError, ValueError):
        raw = default
    return max(1, min(raw, maximum))


def _max_bytes(value: int | None, configured_max: int) -> int:
    try:
        raw = configured_max if value is None else int(value)
    except (TypeError, ValueError):
        raw = configured_max
    return max(1, min(raw, configured_max))


def _setting_int(
    settings: LingNengSettings,
    attr: str,
    default: int,
) -> int:
    try:
        return int(getattr(settings, attr, default))
    except (TypeError, ValueError):
        return default


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _path_has_control_chars(path: Path) -> bool:
    return any(_text_has_control_chars(part) for part in path.parts)


def _text_has_control_chars(value: str) -> bool:
    return any(ord(char) < 32 or ord(char) == 127 for char in value)


def _public_package_name(package_name: str | None) -> str | None:
    if not package_name:
        return None
    if not _PACKAGE_NAME_RE.fullmatch(package_name):
        return None
    return package_name


def _public_skill_id(skill_id: str) -> str:
    return skill_id if _PACKAGE_NAME_RE.fullmatch(skill_id or "") else ""


def _public_resource_id(resource_id: str) -> str:
    if not resource_id or _text_has_control_chars(resource_id):
        return ""
    if PurePosixPath(resource_id).is_absolute():
        return ""
    return resource_id[:200]
