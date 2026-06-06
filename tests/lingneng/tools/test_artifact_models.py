import json

import pytest
from pydantic import ValidationError

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


def test_artifact_from_public_dict_accepts_java_fields():
    artifact = artifact_from_public_dict(ARTIFACT)

    assert isinstance(artifact, Artifact)
    assert artifact.artifact_id == "artifact-doc-1"
    assert artifact.object_key == "external/java-agent-file/artifact-doc-1"


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
    "object_key",
    [
        "/Users/rotas/secret.pdf",
        "../secret.pdf",
        "external/java-agent-file/../secret.pdf",
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
