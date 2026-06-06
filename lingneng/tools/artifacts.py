from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit, urlunsplit

from lingneng.schemas.chat_events import Artifact


_ARTIFACT_PUBLIC_FIELDS = frozenset(
    {
        "artifact_id",
        "artifact_type",
        "source",
        "file_name",
        "mime_type",
        "url",
        "object_key",
        "format",
        "target_format",
        "conversion_required",
        "conversion_owner",
    }
)
_STRING_FIELDS = frozenset(
    {
        "artifact_id",
        "artifact_type",
        "source",
        "file_name",
        "mime_type",
        "format",
        "target_format",
        "conversion_owner",
    }
)
_SECRET_QUERY_PARTS = (
    "access_key",
    "access_token",
    "api_key",
    "authorization",
    "bearer",
    "credential",
    "password",
    "passwd",
    "secret",
    "signature",
    "token",
    "x-amz",
)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
_UNIX_LOCAL_PATH_FRAGMENT_RE = re.compile(
    r"(?<![A-Za-z0-9._-])/(?:Users|home|private|tmp|var|etc|opt|root)\b"
)
_WINDOWS_PATH_FRAGMENT_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")
_URL_CREDENTIALS_FRAGMENT_RE = re.compile(r"://[^/?#\s:@]+:[^/?#\s:@]+@")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?:^|[^a-z0-9])("
    + "|".join(re.escape(marker) for marker in _SECRET_QUERY_PARTS)
    + r"(?:-[a-z0-9_-]+)?)\s*[:=]",
    re.IGNORECASE,
)
_BEARER_TOKEN_RE = re.compile(
    r"(?:^|[^a-z0-9])bearer\s+\S+",
    re.IGNORECASE,
)
_SECRET_SEGMENT_MARKERS = frozenset(
    {
        "access_key",
        "access_token",
        "api_key",
        "authorization",
        "bearer",
        "credential",
        "password",
        "passwd",
        "secret",
        "signature",
        "token",
        "x-amz",
        "x-amz-signature",
    }
)
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"^[a-zA-Z]:[\\/]")


def artifact_from_public_dict(value: dict[str, Any]) -> Artifact:
    return Artifact.model_validate(sanitize_artifact_public_dict(value))


def sanitize_artifact_public_dict(value: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, item in value.items():
        if key not in _ARTIFACT_PUBLIC_FIELDS:
            continue
        if key == "url":
            clean_url = _sanitize_public_url(item)
            if clean_url:
                sanitized[key] = clean_url
            continue
        if key == "object_key":
            clean_object_key = _sanitize_object_key(item)
            if clean_object_key:
                sanitized[key] = clean_object_key
            continue
        if key in _STRING_FIELDS:
            if item is None:
                sanitized[key] = None
            elif isinstance(item, str):
                clean_text = _sanitize_public_string(item)
                if clean_text is not None:
                    sanitized[key] = clean_text
            else:
                clean_text = _sanitize_public_string(str(item))
                if clean_text is not None:
                    sanitized[key] = clean_text
            continue
        if key == "conversion_required":
            if isinstance(item, bool):
                sanitized[key] = item
            continue
        if item is None or isinstance(item, bool | int | float | str):
            sanitized[key] = item
    return sanitized


def dedupe_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for artifact in artifacts:
        artifact_id = artifact.get("artifact_id")
        dedupe_key = artifact_id.strip() if isinstance(artifact_id, str) else ""
        if dedupe_key:
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
        deduped.append(artifact)
    return deduped


def _sanitize_public_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if _CONTROL_CHAR_RE.search(stripped) or _looks_like_local_path(stripped):
        return None

    try:
        parts = urlsplit(stripped)
    except ValueError:
        return None

    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"}:
        return None
    if not parts.netloc or _has_whitespace_or_control(parts.netloc):
        return None
    if parts.username or parts.password:
        return None
    decoded_path = unquote(parts.path)
    if (
        _CONTROL_CHAR_RE.search(decoded_path)
        or _has_path_traversal(decoded_path)
        or _contains_embedded_local_path(decoded_path)
    ):
        return None
    if _query_looks_secret(parts.query):
        return urlunsplit((scheme, parts.netloc, parts.path, "", ""))
    return urlunsplit((scheme, parts.netloc, parts.path, parts.query, ""))


def _sanitize_object_key(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    decoded = unquote(stripped)
    if (
        _CONTROL_CHAR_RE.search(stripped)
        or _CONTROL_CHAR_RE.search(decoded)
        or _looks_like_local_path(stripped)
        or _looks_like_local_path(decoded)
        or _contains_embedded_local_path(decoded)
        or _contains_secret_marker(decoded)
    ):
        return None
    if _has_path_traversal(decoded):
        return None
    return stripped


def _strip_control_chars(value: str) -> str:
    return _CONTROL_CHAR_RE.sub("", value)


def _sanitize_public_string(value: str) -> str | None:
    clean_text = _strip_control_chars(value).strip()
    decoded = unquote(clean_text)
    if (
        _looks_like_local_path(clean_text)
        or _looks_like_local_path(decoded)
        or _contains_embedded_local_path(decoded)
        or _contains_secret_marker(decoded)
    ):
        return None
    return clean_text


def _has_whitespace_or_control(value: str) -> bool:
    return any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value)


def _looks_like_local_path(value: str) -> bool:
    lowered = value.lower()
    return (
        lowered.startswith(("file://", "local://"))
        or value.startswith(("/", "\\", "~"))
        or _WINDOWS_ABSOLUTE_PATH_RE.match(value) is not None
    )


def _contains_embedded_local_path(value: str) -> bool:
    lowered = value.lower()
    return (
        "file://" in lowered
        or "local://" in lowered
        or _WINDOWS_PATH_FRAGMENT_RE.search(value) is not None
        or _UNIX_LOCAL_PATH_FRAGMENT_RE.search(value) is not None
    )


def _has_path_traversal(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return any(part in {"..", "."} for part in normalized.split("/"))


def _query_looks_secret(query: str) -> bool:
    if not query:
        return False
    decoded_query = unquote(query)
    if (
        _CONTROL_CHAR_RE.search(decoded_query)
        or _contains_embedded_local_path(decoded_query)
        or _contains_url_credentials_fragment(decoded_query)
        or _contains_secret_marker(decoded_query)
    ):
        return True
    for key, value in parse_qsl(query, keep_blank_values=True):
        decoded_key = unquote(key)
        decoded_value = unquote(value)
        if (
            _CONTROL_CHAR_RE.search(decoded_key)
            or _CONTROL_CHAR_RE.search(decoded_value)
            or _contains_embedded_local_path(decoded_key)
            or _contains_embedded_local_path(decoded_value)
            or _contains_url_credentials_fragment(decoded_key)
            or _contains_url_credentials_fragment(decoded_value)
            or _contains_secret_marker(decoded_key)
            or _contains_secret_marker(decoded_value)
        ):
            return True
    return False


def _contains_secret_marker(value: str) -> bool:
    lowered = value.lower()
    if _SECRET_ASSIGNMENT_RE.search(lowered) or _BEARER_TOKEN_RE.search(lowered):
        return True
    segments = re.split(r"[/\\?&#\s]+", lowered)
    return any(
        segment in _SECRET_SEGMENT_MARKERS or segment.startswith("x-amz-")
        for segment in segments
    )


def _contains_url_credentials_fragment(value: str) -> bool:
    return _URL_CREDENTIALS_FRAGMENT_RE.search(value) is not None
