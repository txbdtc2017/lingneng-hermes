from __future__ import annotations

import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Literal

from pydantic import BaseModel

from lingneng.config.settings import LingNengSettings
from lingneng.skills.catalog import LingNengSkillCatalog


ToolStatus = Literal["succeeded", "failed"]

_CURRENT_SETTINGS: ContextVar[LingNengSettings | None] = ContextVar(
    "lingneng_skill_tool_settings",
    default=None,
)
_PACKAGE_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
_LOCAL_URI_RE = re.compile(r"\b(?:file|local)://[^\s\"'<>),;，。]+", re.IGNORECASE)
_LOCAL_ABSOLUTE_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9._~-])"
    r"(?:"
    r"/(?:Users|home|private|tmp|var|etc|opt|root|workspace)\b"
    r"[^\s\"'<>),;，。]*"
    r"|~[\\/][^\s\"'<>),;，。]*"
    r"|[A-Za-z]:[\\/][^\s\"'<>),;，。]*"
    r")"
)
_FORBIDDEN_KEY_PARTS = (
    "api_key",
    "args",
    "authorization",
    "bearer",
    "credential",
    "exception",
    "history",
    "password",
    "passwd",
    "payload",
    "request",
    "secret",
    "token",
    "traceback",
)
_FORBIDDEN_TEXT_PARTS = (
    "api_key",
    "authorization",
    "bearer ",
    "credential",
    "password",
    "passwd",
    "secret",
    "token",
    "traceback",
)
_PUBLIC_MESSAGE_BY_CODE = {
    "INVALID_ARGUMENT": "LingNeng skill tool arguments are invalid.",
    "NOT_CONFIGURED": "LingNeng skill tool context is not configured.",
    "NOT_FOUND": "LingNeng skill was not found.",
    "RESOURCE_NOT_ALLOWED": "LingNeng skill resource is not allowed.",
    "RESOURCE_TOO_LARGE": "LingNeng skill resource exceeds the configured limit.",
    "RESOURCE_UNREADABLE": "LingNeng skill resource could not be read.",
    "SKILL_CATALOG_EMPTY": "LingNeng skill catalog is empty.",
    "SKILL_CATALOG_ERROR": "LingNeng skill catalog failed safely.",
}
_MAX_PUBLIC_DEPTH = 6
_MAX_PUBLIC_ITEMS = 100
SEARCH_SKILLS_QUERY_MAX_CHARS = 500


@contextmanager
def skill_tool_context(settings: LingNengSettings) -> Iterator[None]:
    settings_token = _CURRENT_SETTINGS.set(settings)
    try:
        yield
    finally:
        _CURRENT_SETTINGS.reset(settings_token)


def list_skills_handler(args: dict[str, Any] | None = None, **kwargs: Any) -> str:
    del kwargs
    settings = _CURRENT_SETTINGS.get()
    if settings is None:
        return _failure("list_skills", "NOT_CONFIGURED")
    raw_args, error = _args(args)
    if error is not None:
        return _failure("list_skills", error)

    employee_type, employee_type_error = _optional_text_arg(
        raw_args.get("employee_type")
    )
    if employee_type_error is not None:
        return _failure("list_skills", employee_type_error)
    kind, kind_error = _optional_kind(raw_args.get("kind"))
    if kind_error is not None:
        return _failure("list_skills", kind_error)
    limit, limit_error = _optional_int_arg(raw_args.get("limit"))
    if limit_error is not None:
        return _failure("list_skills", limit_error)

    try:
        catalog = LingNengSkillCatalog(settings)
        if not catalog.packages():
            return _failure("list_skills", "SKILL_CATALOG_EMPTY")
        items = catalog.list_skills(
            kind=kind,
            employee_type=employee_type,
            limit=limit,
        )
    except Exception:
        return _failure("list_skills", "SKILL_CATALOG_ERROR")

    return _dump(
        _public_result(
            tool_name="list_skills",
            success=True,
            status="succeeded",
            summary=f"Found {len(items)} LingNeng skills.",
            safe_output={
                "skills": [_dump_model(item) for item in items],
                "count": len(items),
            },
            metadata={
                "warning_count": len(catalog.warnings),
                "limit": limit,
            },
        )
    )


def search_skills_handler(args: dict[str, Any] | None = None, **kwargs: Any) -> str:
    del kwargs
    settings = _CURRENT_SETTINGS.get()
    if settings is None:
        return _failure("search_skills", "NOT_CONFIGURED")
    raw_args, error = _args(args)
    if error is not None:
        return _failure("search_skills", error)

    query = _required_text_arg(raw_args.get("query"))
    if query is None:
        return _failure("search_skills", "INVALID_ARGUMENT")
    if len(query) > SEARCH_SKILLS_QUERY_MAX_CHARS:
        return _failure("search_skills", "INVALID_ARGUMENT")
    employee_type, employee_type_error = _optional_text_arg(
        raw_args.get("employee_type")
    )
    if employee_type_error is not None:
        return _failure("search_skills", employee_type_error)
    kind, kind_error = _optional_kind(raw_args.get("kind"))
    if kind_error is not None:
        return _failure("search_skills", kind_error)
    limit, limit_error = _optional_int_arg(raw_args.get("limit"))
    if limit_error is not None:
        return _failure("search_skills", limit_error)

    try:
        catalog = LingNengSkillCatalog(settings)
        if not catalog.packages():
            return _failure("search_skills", "SKILL_CATALOG_EMPTY")
        items = catalog.search_skills(
            query,
            employee_type=employee_type,
            kind=kind,
            limit=limit,
        )
    except Exception:
        return _failure("search_skills", "SKILL_CATALOG_ERROR")

    return _dump(
        _public_result(
            tool_name="search_skills",
            success=True,
            status="succeeded",
            summary=f"Found {len(items)} LingNeng skills for the query.",
            safe_output={
                "skills": [_dump_model(item) for item in items],
                "count": len(items),
            },
            metadata={
                "warning_count": len(catalog.warnings),
                "limit": limit,
            },
        )
    )


def read_skill_handler(args: dict[str, Any] | None = None, **kwargs: Any) -> str:
    del kwargs
    settings = _CURRENT_SETTINGS.get()
    if settings is None:
        return _failure("read_skill", "NOT_CONFIGURED")
    raw_args, error = _args(args)
    if error is not None:
        return _failure("read_skill", error)

    skill_id = _required_skill_id(raw_args.get("skill_id"))
    max_chars, max_chars_error = _optional_positive_int_arg(raw_args.get("max_chars"))
    if skill_id is None or max_chars_error is not None:
        return _failure("read_skill", "INVALID_ARGUMENT")

    try:
        catalog = LingNengSkillCatalog(settings)
        result = catalog.read_skill(skill_id, max_chars=max_chars)
    except Exception:
        return _failure("read_skill", "SKILL_CATALOG_ERROR")

    if not result.success:
        return _failure(
            "read_skill",
            result.code or "NOT_FOUND",
            safe_output={"skill_id": skill_id},
            message=result.message,
        )

    return _dump(
        _public_result(
            tool_name="read_skill",
            success=True,
            status="succeeded",
            summary=f"Read LingNeng skill {skill_id}.",
            safe_output={
                "skill": _dump_model(result.skill),
                "body": result.body,
                "body_truncated": result.body_truncated,
                "resource_manifest": _dump_model(result.resource_manifest),
            },
            metadata={
                "warning_count": len(result.warnings),
                "max_chars": max_chars,
            },
        )
    )


def read_skill_resource_handler(
    args: dict[str, Any] | None = None,
    **kwargs: Any,
) -> str:
    del kwargs
    settings = _CURRENT_SETTINGS.get()
    if settings is None:
        return _failure("read_skill_resource", "NOT_CONFIGURED")
    raw_args, error = _args(args)
    if error is not None:
        return _failure("read_skill_resource", error)

    skill_id = _required_skill_id(raw_args.get("skill_id"))
    resource_id = _required_text_arg(raw_args.get("resource_id"))
    max_chars, max_chars_error = _optional_positive_int_arg(raw_args.get("max_chars"))
    if skill_id is None or resource_id is None or max_chars_error is not None:
        return _failure("read_skill_resource", "INVALID_ARGUMENT")

    try:
        catalog = LingNengSkillCatalog(settings)
        result = catalog.read_skill_resource(
            skill_id,
            resource_id,
            max_chars=max_chars,
            max_bytes=settings.skill_resource_max_bytes,
        )
    except Exception:
        return _failure("read_skill_resource", "SKILL_CATALOG_ERROR")

    safe_output = {
        "skill_id": result.skill_id or skill_id,
        "resource_id": result.resource_id or resource_id,
        "content": result.content,
        "content_truncated": result.content_truncated,
        "size_bytes": result.size_bytes,
        "mime_type": result.mime_type,
    }
    if not result.success:
        safe_output.pop("content", None)
        return _failure(
            "read_skill_resource",
            result.code or "RESOURCE_NOT_ALLOWED",
            safe_output=safe_output,
            message=result.message,
        )

    return _dump(
        _public_result(
            tool_name="read_skill_resource",
            success=True,
            status="succeeded",
            summary=f"Read LingNeng skill resource {result.resource_id}.",
            safe_output=safe_output,
            metadata={
                "max_chars": max_chars,
                "max_bytes": settings.skill_resource_max_bytes,
            },
        )
    )


def _args(args: dict[str, Any] | None) -> tuple[dict[str, Any], str | None]:
    if args is None:
        return {}, None
    if not isinstance(args, dict):
        return {}, "INVALID_ARGUMENT"
    return args, None


def _required_text_arg(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or _CONTROL_CHAR_RE.search(stripped):
        return None
    return stripped


def _optional_text_arg(value: Any) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    if not isinstance(value, str):
        return None, "INVALID_ARGUMENT"
    stripped = value.strip()
    if not stripped:
        return None, None
    if _CONTROL_CHAR_RE.search(stripped):
        return None, "INVALID_ARGUMENT"
    return stripped, None


def _required_skill_id(value: Any) -> str | None:
    skill_id = _required_text_arg(value)
    if skill_id is None or not _PACKAGE_NAME_RE.fullmatch(skill_id):
        return None
    return skill_id


def _optional_kind(value: Any) -> tuple[str | None, str | None]:
    kind, error = _optional_text_arg(value)
    if error is not None or kind is None:
        return None, error
    if kind not in {"employee_base", "task", "capability", "infrastructure"}:
        return None, "INVALID_ARGUMENT"
    return kind, None


def _optional_int_arg(value: Any) -> tuple[int | None, str | None]:
    if value is None:
        return None, None
    if isinstance(value, bool):
        return None, "INVALID_ARGUMENT"
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, "INVALID_ARGUMENT"
    if parsed <= 0:
        return None, "INVALID_ARGUMENT"
    return parsed, None


def _optional_positive_int_arg(value: Any) -> tuple[int | None, str | None]:
    if value is None:
        return None, None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, "INVALID_ARGUMENT"
    if parsed <= 0:
        return None, "INVALID_ARGUMENT"
    return parsed, None


def _failure(
    tool_name: str,
    code: str,
    *,
    safe_output: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    message: str | None = None,
) -> str:
    return _dump(
        _public_result(
            tool_name=tool_name,
            success=False,
            status="failed",
            summary=_PUBLIC_MESSAGE_BY_CODE.get(code, "LingNeng skill tool failed."),
            safe_output=safe_output,
            metadata=metadata,
            code=code,
            message=message,
        )
    )


def _public_result(
    *,
    tool_name: str,
    success: bool,
    status: ToolStatus,
    summary: str,
    safe_output: dict[str, Any] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    code: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    public_code = _public_text(code or "", max_chars=100) or None
    public_message = (
        _public_text(message, max_chars=500)
        if message
        else _PUBLIC_MESSAGE_BY_CODE.get(public_code)
    )
    return {
        "success": success,
        "tool_name": tool_name,
        "status": status,
        "summary": _public_text(summary, max_chars=500),
        "safe_output": _sanitize_mapping(safe_output or {}),
        "artifacts": _sanitize_list(artifacts or []),
        "metadata": _sanitize_mapping(metadata or {}),
        "code": public_code,
        "message": public_message,
    }


def _dump(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False)


def _dump_model(value: BaseModel | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return value.model_dump(mode="json")


def _sanitize_mapping(value: dict[str, Any]) -> dict[str, Any]:
    sanitized = _sanitize_public_value(value)
    if not isinstance(sanitized, dict):
        return {}
    return sanitized


def _sanitize_list(value: list[dict[str, Any]]) -> list[Any]:
    sanitized = _sanitize_public_value(value)
    if not isinstance(sanitized, list):
        return []
    return sanitized


def _sanitize_public_value(value: Any, *, depth: int = 0) -> Any:
    if depth >= _MAX_PUBLIC_DEPTH:
        return {"truncated": True, "reason": "max_depth"}
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        omitted_count = 0
        items = list(value.items())
        for key, item in items[:_MAX_PUBLIC_ITEMS]:
            if _is_forbidden_key(key):
                omitted_count += 1
                continue
            sanitized[str(key)] = _sanitize_public_value(item, depth=depth + 1)
        omitted_count += max(0, len(items) - _MAX_PUBLIC_ITEMS)
        if omitted_count:
            sanitized["truncated"] = True
            sanitized["omitted_count"] = omitted_count
        return sanitized
    if isinstance(value, list | tuple):
        sanitized_items = [
            _sanitize_public_value(item, depth=depth + 1)
            for item in list(value)[:_MAX_PUBLIC_ITEMS]
        ]
        omitted_count = max(0, len(value) - _MAX_PUBLIC_ITEMS)
        if omitted_count:
            sanitized_items.append(
                {"truncated": True, "omitted_count": omitted_count}
            )
        return sanitized_items
    if isinstance(value, str):
        return _public_text(value, max_chars=20000)
    if value is None or isinstance(value, bool | int | float):
        return value
    return None


def _public_text(value: str, *, max_chars: int) -> str:
    clean_text = _CONTROL_CHAR_RE.sub("", value).strip()
    public_text = _replace_local_path_fragments(clean_text)
    lowered = public_text.lower()
    if any(part in lowered for part in _FORBIDDEN_TEXT_PARTS):
        return ""
    return public_text[:max_chars]


def _is_forbidden_key(value: object) -> bool:
    lowered = str(value).lower()
    return any(part in lowered for part in _FORBIDDEN_KEY_PARTS)


def _replace_local_path_fragments(value: str) -> str:
    without_local_uris = _LOCAL_URI_RE.sub("[local_path_removed]", value)
    return _LOCAL_ABSOLUTE_PATH_RE.sub(
        "[local_path_removed]",
        without_local_uris,
    )
