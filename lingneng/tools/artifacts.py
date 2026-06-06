from __future__ import annotations

import re
from ipaddress import ip_address
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit, urlunsplit

from lingneng.config.settings import LingNengSettings
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
_PATH_TRAVERSAL_FRAGMENT_RE = re.compile(r"(?:^|[\s/])\.\.?(?:/|$)")
_LOCAL_ROOT_PATH_FRAGMENT_RE = re.compile(
    r"(?<![A-Za-z0-9._-])[\\/]+(?:Users|home|private|tmp|var|etc|opt|root)\b"
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


def artifact_from_public_dict(
    value: dict[str, Any],
    *,
    settings: LingNengSettings | None = None,
    allowed_hosts: list[str] | tuple[str, ...] | set[str] | None = None,
) -> Artifact:
    return Artifact.model_validate(
        sanitize_artifact_public_dict(
            value,
            settings=settings,
            allowed_hosts=allowed_hosts,
        )
    )


def sanitize_public_url(
    value: Any,
    *,
    settings: LingNengSettings | None = None,
    allowed_hosts: list[str] | tuple[str, ...] | set[str] | None = None,
) -> str | None:
    return _sanitize_public_url(
        value,
        settings=settings,
        allowed_hosts=allowed_hosts,
    )


def sanitize_strict_public_url(
    value: Any,
    *,
    settings: LingNengSettings | None = None,
    allowed_hosts: list[str] | tuple[str, ...] | set[str] | None = None,
) -> str | None:
    clean_url = _sanitize_public_url(
        value,
        settings=settings,
        allowed_hosts=allowed_hosts,
    )
    if clean_url is None or not isinstance(value, str):
        return None
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return None
    original_without_fragment = urlunsplit(
        (parts.scheme.lower(), parts.netloc, parts.path, parts.query, "")
    )
    if clean_url != original_without_fragment:
        return None
    return clean_url


def sanitize_artifact_public_dict(
    value: dict[str, Any],
    *,
    settings: LingNengSettings | None = None,
    allowed_hosts: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, item in value.items():
        if key not in _ARTIFACT_PUBLIC_FIELDS:
            continue
        if key == "url":
            clean_url = _sanitize_public_url(
                item,
                settings=settings,
                allowed_hosts=allowed_hosts,
            )
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


def stable_percent_decode(value: str, *, max_rounds: int = 5) -> tuple[str, bool]:
    return _stable_percent_decode(value, max_rounds=max_rounds)


def _sanitize_public_url(
    value: Any,
    *,
    settings: LingNengSettings | None = None,
    allowed_hosts: list[str] | tuple[str, ...] | set[str] | None = None,
) -> str | None:
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
    decoded_netloc, netloc_stable = _stable_percent_decode(parts.netloc)
    if (
        not netloc_stable
        or decoded_netloc != parts.netloc
        or _has_whitespace_or_control(decoded_netloc)
        or _contains_url_credentials_fragment(f"{scheme}://{decoded_netloc}")
    ):
        return None
    if parts.username or parts.password:
        return None
    host = _url_host(stripped)
    if not host or _is_disallowed_public_host(host):
        return None
    normalized_allowed_hosts = _normalized_allowed_hosts(
        _configured_allowed_hosts(settings=settings, allowed_hosts=allowed_hosts)
    )
    if normalized_allowed_hosts and host not in normalized_allowed_hosts:
        return None
    decoded_path, path_stable = _stable_percent_decode(parts.path)
    if (
        not path_stable
        or _CONTROL_CHAR_RE.search(decoded_path)
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
    decoded, decode_stable = _stable_percent_decode(stripped)
    if (
        not decode_stable
        or _CONTROL_CHAR_RE.search(stripped)
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
    decoded, decode_stable = _stable_percent_decode(clean_text)
    if (
        not decode_stable
        or _looks_like_local_path(clean_text)
        or _looks_like_local_path(decoded)
        or _has_path_traversal(decoded)
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
        or _LOCAL_ROOT_PATH_FRAGMENT_RE.search(value) is not None
    )


def _has_path_traversal(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return any(part in {"..", "."} for part in normalized.split("/")) or (
        _PATH_TRAVERSAL_FRAGMENT_RE.search(normalized) is not None
    )


def _query_looks_secret(query: str) -> bool:
    if not query:
        return False
    decoded_query, query_stable = _stable_percent_decode(query)
    if (
        not query_stable
        or _CONTROL_CHAR_RE.search(decoded_query)
        or _has_path_traversal(decoded_query)
        or _contains_embedded_local_path(decoded_query)
        or _contains_url_credentials_fragment(decoded_query)
        or _contains_secret_marker(decoded_query)
    ):
        return True
    for key, value in parse_qsl(query, keep_blank_values=True):
        decoded_key, key_stable = _stable_percent_decode(key)
        decoded_value, value_stable = _stable_percent_decode(value)
        if (
            not key_stable
            or not value_stable
            or _CONTROL_CHAR_RE.search(decoded_key)
            or _CONTROL_CHAR_RE.search(decoded_value)
            or _has_path_traversal(decoded_key)
            or _has_path_traversal(decoded_value)
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


def _configured_allowed_hosts(
    *,
    settings: LingNengSettings | None,
    allowed_hosts: list[str] | tuple[str, ...] | set[str] | None,
) -> list[str] | tuple[str, ...] | set[str]:
    if allowed_hosts is not None:
        return allowed_hosts
    if settings is not None:
        return settings.artifact_url_allowed_hosts
    return []


def _normalized_allowed_hosts(
    hosts: list[str] | tuple[str, ...] | set[str],
) -> set[str]:
    normalized: set[str] = set()
    for host in hosts:
        value = str(host).strip().lower()
        if not value:
            continue
        if "://" in value:
            parsed_host = _url_host(value)
            if parsed_host:
                normalized.add(parsed_host)
            continue
        value = value.split("/", 1)[0]
        if value.startswith("[") and "]" in value:
            value = value[1 : value.index("]")]
        elif value.count(":") == 1:
            value = value.split(":", 1)[0]
        decoded, stable = _stable_percent_decode(value)
        if not stable or decoded != value or _has_whitespace_or_control(decoded):
            continue
        normalized.add(decoded.rstrip("."))
    return normalized


def _url_host(value: str) -> str | None:
    try:
        host = urlsplit(value).hostname
    except (AttributeError, ValueError):
        return None
    if not host:
        return None
    decoded, stable = _stable_percent_decode(host)
    if not stable or decoded != host or _has_whitespace_or_control(decoded):
        return None
    return decoded.lower().rstrip(".")


def _is_disallowed_public_host(host: str) -> bool:
    normalized = host.strip().lower().rstrip(".")
    if normalized == "localhost" or normalized.endswith(".localhost"):
        return True
    try:
        parsed_ip = ip_address(normalized)
    except ValueError:
        return False
    return not parsed_ip.is_global


def _stable_percent_decode(value: str, *, max_rounds: int = 5) -> tuple[str, bool]:
    decoded = value
    for _ in range(max_rounds):
        next_decoded = unquote(decoded)
        if next_decoded == decoded:
            return decoded, True
        decoded = next_decoded
    return decoded, unquote(decoded) == decoded
