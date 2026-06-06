import json
from urllib.parse import quote

import pytest
from pydantic import ValidationError

from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_events import Artifact
from lingneng.tools.artifacts import (
    artifact_from_public_dict,
    dedupe_artifacts,
    sanitize_artifact_public_dict,
)


ARTIFACT = {
    "artifact_id": "artifact-doc-1",
    "artifact_type": "document",
    "source": "document_generation",
    "file_name": "report.pdf",
    "mime_type": "application/pdf",
    "url": "https://files.example.test/report.pdf",
    "object_key": "external/java-agent-file/artifact-doc-1",
    "format": "pdf",
    "target_format": "pdf",
    "conversion_required": False,
    "conversion_owner": None,
}


def _percent_encode(value: str, rounds: int) -> str:
    encoded = value
    for _ in range(rounds):
        encoded = quote(encoded, safe="")
    return encoded


def test_artifact_from_public_dict_accepts_java_fields():
    artifact = artifact_from_public_dict(ARTIFACT)

    assert isinstance(artifact, Artifact)
    assert artifact.artifact_id == "artifact-doc-1"
    assert artifact.object_key == "external/java-agent-file/artifact-doc-1"


def test_artifact_validation_enforces_allowed_hosts(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_ARTIFACT_URL_ALLOWED_HOSTS": "files.example.test",
        }
    )

    sanitized = sanitize_artifact_public_dict(
        {**ARTIFACT, "url": "https://evil.example.test/report.pdf"},
        settings=settings,
    )

    assert "url" not in sanitized
    with pytest.raises(ValidationError):
        artifact_from_public_dict(sanitized, settings=settings)


def test_artifact_validation_accepts_allowed_public_host(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_ARTIFACT_URL_ALLOWED_HOSTS": "files.example.test",
        }
    )

    artifact = artifact_from_public_dict(ARTIFACT, settings=settings)

    assert artifact.url == "https://files.example.test/report.pdf"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/report.pdf",
        "http://10.1.2.3/report.pdf",
        "http://172.16.0.1/report.pdf",
        "http://192.168.1.1/report.pdf",
        "http://169.254.169.254/latest/meta-data",
        "http://localhost/report.pdf",
        "http://[::1]/report.pdf",
    ],
)
def test_artifact_validation_rejects_private_or_local_hosts_even_when_allowlisted(
    tmp_path,
    url,
):
    host = url.split("//", 1)[1].split("/", 1)[0].strip("[]")
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_ARTIFACT_URL_ALLOWED_HOSTS": host,
        }
    )

    sanitized = sanitize_artifact_public_dict(
        {**ARTIFACT, "url": url},
        settings=settings,
    )

    assert "url" not in sanitized
    with pytest.raises(ValidationError):
        artifact_from_public_dict(sanitized, settings=settings)


@pytest.mark.parametrize(
    "url",
    [
        "file:///Users/rotas/secret.pdf",
        "local://artifact-doc-1",
        "/Users/rotas/secret.pdf",
        "https://user:password@files.example.test/report.pdf",
        "https://files.example.test /report.pdf",
        "https://files.example.test\x00/report.pdf",
    ],
)
def test_artifact_sanitizer_strips_unsafe_urls(url):
    sanitized = sanitize_artifact_public_dict({**ARTIFACT, "url": url})

    dumped = json.dumps(sanitized, ensure_ascii=False)
    assert url not in dumped
    assert "file://" not in dumped
    assert "local://" not in dumped
    assert "/Users/rotas" not in dumped
    with pytest.raises(ValidationError):
        artifact_from_public_dict(sanitized)


@pytest.mark.parametrize(
    "url",
    [
        "https://files.example.test%20.evil.test/report.pdf",
        "https://files.example.test%0a.evil.test/report.pdf",
        "https://local%68ost/report.pdf",
    ],
)
def test_artifact_sanitizer_decodes_authority_before_checks(url):
    sanitized = sanitize_artifact_public_dict({**ARTIFACT, "url": url})

    assert "url" not in sanitized
    with pytest.raises(ValidationError):
        artifact_from_public_dict(sanitized)


@pytest.mark.parametrize(
    "url",
    [
        "https://files.example.test/%2e%2e/report.pdf",
        "https://files.example.test/%252e%252e/report.pdf",
        "https://files.example.test/../report.pdf",
        "https://files.example.test//Users/rotas/report.pdf",
        "https://files.example.test/%2FUsers%2Frotas%2Freport.pdf",
        "https://files.example.test/reports/%5cUsers%5crotas%5creport.pdf",
        f"https://files.example.test/{_percent_encode('/Users/rotas/report.pdf', 6)}",
        f"https://files.example.test/{_percent_encode('/Users/rotas/report.pdf', 7)}",
    ],
)
def test_artifact_sanitizer_strips_unsafe_url_paths(url):
    sanitized = sanitize_artifact_public_dict({**ARTIFACT, "url": url})

    dumped = json.dumps(sanitized, ensure_ascii=False)
    assert url not in dumped
    assert "/Users" not in dumped
    assert "%2e%2e" not in dumped.lower()
    assert "../" not in dumped
    with pytest.raises(ValidationError):
        artifact_from_public_dict(sanitized)


def test_artifact_sanitizer_keeps_safe_policy_url_path():
    value = {
        **ARTIFACT,
        "url": "https://files.example.test/reports/password-policy.pdf",
    }

    sanitized = sanitize_artifact_public_dict(value)
    artifact = artifact_from_public_dict(sanitized)

    assert artifact.url == "https://files.example.test/reports/password-policy.pdf"


@pytest.mark.parametrize(
    "object_key",
    [
        "/Users/rotas/secret.pdf",
        "../secret.pdf",
        "external/java-agent-file/%2e%2e/report.pdf",
        "external/java-agent-file/../secret.pdf",
        r"external/java-agent-file/C:\Users\rotas\report.pdf",
        f"external/java-agent-file/{_percent_encode('../secret.pdf', 6)}",
        f"external/java-agent-file/{_percent_encode('/Users/rotas/report.pdf', 6)}",
        "external/java-agent-file/\x00secret.pdf",
    ],
)
def test_artifact_sanitizer_strips_unsafe_object_keys(object_key):
    sanitized = sanitize_artifact_public_dict({**ARTIFACT, "object_key": object_key})

    dumped = json.dumps(sanitized, ensure_ascii=False)
    assert object_key not in dumped
    assert "/Users/rotas" not in dumped
    with pytest.raises(ValidationError):
        artifact_from_public_dict(sanitized)


@pytest.mark.parametrize(
    ("query", "forbidden"),
    [
        ("file=/Users/rotas/report.pdf&download=1", "/Users"),
        ("redirect=https://user:pass@files.example.test/report.pdf", "user:pass"),
        ("p=..%252Freport.pdf", ".."),
        ("..%252Freport=1", ".."),
    ],
)
def test_artifact_sanitizer_removes_url_query_with_unsafe_value(query, forbidden):
    unsafe = {**ARTIFACT, "url": f"https://files.example.test/report.pdf?{query}"}

    sanitized = sanitize_artifact_public_dict(unsafe)
    artifact = artifact_from_public_dict(sanitized)

    assert sanitized["url"] == "https://files.example.test/report.pdf"
    assert artifact.url == "https://files.example.test/report.pdf"
    dumped = json.dumps(sanitized, ensure_ascii=False)
    assert forbidden not in dumped
    assert query not in dumped


def test_artifact_sanitizer_keeps_safe_url_query():
    value = {**ARTIFACT, "url": "https://files.example.test/report.pdf?download=1"}

    sanitized = sanitize_artifact_public_dict(value)
    artifact = artifact_from_public_dict(sanitized)

    assert artifact.url == "https://files.example.test/report.pdf?download=1"


def test_artifact_sanitizer_keeps_policy_file_names_with_secret_words():
    value = {
        **ARTIFACT,
        "file_name": "password-policy.pdf",
        "object_key": "artifacts/artifact-doc-1/password-policy.pdf",
    }

    sanitized = sanitize_artifact_public_dict(value)
    artifact = artifact_from_public_dict(sanitized)

    assert artifact.file_name == "password-policy.pdf"
    assert artifact.object_key == "artifacts/artifact-doc-1/password-policy.pdf"


@pytest.mark.parametrize(
    "object_key",
    [
        "external/java-agent-file/token=abc123/report.pdf",
        "external/java-agent-file/api_key/report.pdf",
        "external/java-agent-file/bearer abc123/report.pdf",
        "external/java-agent-file/x-amz-signature/report.pdf",
    ],
)
def test_artifact_sanitizer_strips_secret_shaped_object_keys(object_key):
    sanitized = sanitize_artifact_public_dict({**ARTIFACT, "object_key": object_key})

    dumped = json.dumps(sanitized, ensure_ascii=False).lower()
    assert object_key.lower() not in dumped
    assert "token" not in dumped
    assert "api_key" not in dumped
    assert "bearer" not in dumped
    assert "x-amz" not in dumped
    with pytest.raises(ValidationError):
        artifact_from_public_dict(sanitized)


def test_artifact_sanitizer_strips_secret_shaped_url_queries():
    unsafe = {
        **ARTIFACT,
        "url": "https://files.example.test/report.pdf?token=abc&download=1",
    }

    sanitized = sanitize_artifact_public_dict(unsafe)
    artifact = artifact_from_public_dict(sanitized)

    assert sanitized["url"] == "https://files.example.test/report.pdf"
    assert artifact.url == "https://files.example.test/report.pdf"
    assert "token" not in json.dumps(sanitized, ensure_ascii=False).lower()


def test_artifact_sanitizer_removes_control_characters_from_public_strings():
    sanitized = sanitize_artifact_public_dict(
        {
            **ARTIFACT,
            "file_name": "rep\x00ort.pdf",
            "source": "document\ngeneration",
        }
    )

    assert sanitized["file_name"] == "report.pdf"
    assert sanitized["source"] == "documentgeneration"


def test_artifact_sanitizer_strips_local_paths_from_public_strings():
    sanitized = sanitize_artifact_public_dict(
        {**ARTIFACT, "file_name": "/Users/rotas/secret.pdf"}
    )

    dumped = json.dumps(sanitized, ensure_ascii=False)
    assert "/Users/rotas" not in dumped
    with pytest.raises(ValidationError):
        artifact_from_public_dict(sanitized)


@pytest.mark.parametrize(
    ("field", "value", "forbidden"),
    [
        ("file_name", "report /Users/rotas/secret.pdf", "/Users/rotas"),
        ("file_name", "report C:\\Users\\rotas\\secret.pdf", "C:\\Users"),
        ("file_name", "..%252Freport.pdf", ".."),
        ("source", "bearer abc123", "bearer"),
        ("source", "document_generation token=abc123", "token"),
        ("source", "generated ..%252Freport.pdf", ".."),
    ],
)
def test_artifact_sanitizer_strips_embedded_local_paths_and_secrets_from_strings(
    field, value, forbidden
):
    sanitized = sanitize_artifact_public_dict({**ARTIFACT, field: value})

    dumped = json.dumps(sanitized, ensure_ascii=False).lower()
    assert value.lower() not in dumped
    assert forbidden.lower() not in dumped
    with pytest.raises(ValidationError):
        artifact_from_public_dict(sanitized)


def test_dedupe_artifacts_by_artifact_id_preserves_first_seen():
    duplicate = {**ARTIFACT, "file_name": "duplicate.pdf"}
    second = {**ARTIFACT, "artifact_id": "artifact-img-1", "artifact_type": "image"}

    assert dedupe_artifacts([ARTIFACT, duplicate, second]) == [ARTIFACT, second]


def test_dedupe_artifacts_preserves_artifacts_without_ids():
    first_missing = {**ARTIFACT, "artifact_id": ""}
    second_missing = {**ARTIFACT, "artifact_id": "", "file_name": "second.pdf"}

    assert dedupe_artifacts([first_missing, second_missing]) == [
        first_missing,
        second_missing,
    ]
