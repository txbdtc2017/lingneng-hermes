import json

from lingneng.config.settings import LingNengSettings
from lingneng.events.bridge import (
    artifact_events_from_tool_result,
    dedupe_artifacts,
    final_answer,
)
from lingneng.schemas.chat_events import ArtifactCreatedEvent, FinalEvent


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


def result_payload(**overrides):
    payload = {
        "success": True,
        "tool_name": "document_generation",
        "status": "succeeded",
        "summary": "PDF 文档生成完成",
        "safe_output": {"artifact_count": 1},
        "artifacts": [ARTIFACT],
        "metadata": {},
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def test_artifact_tool_result_emits_artifact_created():
    events, artifacts = artifact_events_from_tool_result(
        tool_name="document_generation",
        result=result_payload(),
    )

    assert [type(event) for event in events] == [ArtifactCreatedEvent]
    assert events[0].artifact_id == "artifact-doc-1"
    assert artifacts == [ARTIFACT]


def test_artifact_tool_result_accepts_dict_payload():
    events, artifacts = artifact_events_from_tool_result(
        tool_name="chart_visualization",
        result={
            "success": True,
            "tool_name": "chart_visualization",
            "artifacts": [
                {
                    **ARTIFACT,
                    "artifact_id": "artifact-chart-1",
                    "artifact_type": "image",
                    "source": "chart_visualization",
                    "mime_type": "image/png",
                    "file_name": "chart.png",
                    "format": "png",
                    "target_format": "png",
                }
            ],
        },
    )

    assert [event.artifact_id for event in events] == ["artifact-chart-1"]
    assert artifacts[0]["source"] == "chart_visualization"


def test_non_artifact_tool_result_is_ignored():
    events, artifacts = artifact_events_from_tool_result(
        tool_name="retrieve_rag",
        result=result_payload(tool_name="retrieve_rag"),
    )

    assert events == []
    assert artifacts == []


def test_invalid_artifacts_are_ignored():
    events, artifacts = artifact_events_from_tool_result(
        tool_name="document_generation",
        result=result_payload(
            artifacts=[ARTIFACT, {**ARTIFACT, "url": "file:///tmp/a"}]
        ),
    )

    assert len(events) == 1
    assert artifacts == [ARTIFACT]


def test_artifact_events_enforce_settings_allowlist(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_ARTIFACT_URL_ALLOWED_HOSTS": "files.example.test",
        }
    )

    events, artifacts = artifact_events_from_tool_result(
        tool_name="document_generation",
        result=result_payload(
            artifacts=[
                {**ARTIFACT, "url": "https://evil.example.test/report.pdf"},
                ARTIFACT,
            ]
        ),
        settings=settings,
    )

    assert [event.artifact_id for event in events] == ["artifact-doc-1"]
    assert artifacts == [ARTIFACT]


def test_malformed_tool_result_is_ignored():
    events, artifacts = artifact_events_from_tool_result(
        tool_name="image_generation",
        result="{not-json",
    )

    assert events == []
    assert artifacts == []


def test_dedupe_artifacts_by_artifact_id():
    duplicate = {**ARTIFACT, "file_name": "duplicate.pdf"}
    second = {**ARTIFACT, "artifact_id": "artifact-img-1", "artifact_type": "image"}

    assert dedupe_artifacts([ARTIFACT, duplicate, second]) == [ARTIFACT, second]


def test_final_answer_accepts_artifacts():
    event = final_answer(run_id="run-1", answer="完成", artifacts=[ARTIFACT])

    assert isinstance(event, FinalEvent)
    assert event.model_dump(mode="json")["artifacts"] == [ARTIFACT]


def test_final_answer_enforces_settings_allowlist(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_ARTIFACT_URL_ALLOWED_HOSTS": "files.example.test",
        }
    )

    event = final_answer(
        run_id="run-1",
        answer="完成",
        artifacts=[
            {**ARTIFACT, "url": "https://evil.example.test/report.pdf"},
            ARTIFACT,
        ],
        settings=settings,
    )

    assert event.model_dump(mode="json")["artifacts"] == [ARTIFACT]
