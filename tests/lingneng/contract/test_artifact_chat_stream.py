from __future__ import annotations

from fastapi.testclient import TestClient

from lingneng.api.app import create_app
from lingneng.config.settings import LingNengSettings
from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter
from lingneng.session.run_store import LingNengRunStore
from lingneng.tools.document_generation import (
    DocumentGenerationResult,
    document_generation_context,
)
from tests.lingneng.api.test_chat_stream_contract import parse_sse
from tests.lingneng.schemas.test_chat_request_schema import full_payload
from tools.registry import registry


INTERNAL_KEY = "key"
FINAL_ANSWER = "文档已生成。"
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


class FakeDocumentProvider:
    def generate(self, request):
        del request
        return DocumentGenerationResult(
            summary="PDF 文档生成完成",
            artifacts=[ARTIFACT],
            safe_output={"artifact_count": 1},
        )


class ContractArtifactAgent:
    calls = 0

    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")
        self.tool_progress_callback = kwargs.get("tool_progress_callback")

    def run_conversation(self, *args, **kwargs):
        del args, kwargs
        type(self).calls += 1
        self.tool_progress_callback(
            "tool.started",
            "document_generation",
            None,
            {},
        )
        result = registry.dispatch(
            "document_generation",
            {
                "title": "报告",
                "instruction": "生成报告",
                "content": "正文",
            },
        )
        self.tool_progress_callback(
            "tool.completed",
            "document_generation",
            None,
            None,
            duration=0.01,
            is_error=False,
            result=result,
        )
        self.stream_delta_callback(FINAL_ANSWER)
        return {"final_response": FINAL_ANSWER, "messages": []}


def settings(tmp_path) -> LingNengSettings:
    return LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path / "runtime"),
            "LINGNENG_AGENT_MODE": "hermes",
            "LINGNENG_INTERNAL_API_KEY": INTERNAL_KEY,
        }
    )


def test_artifact_chat_stream_contract_persists_and_replays_final_artifacts(tmp_path):
    ContractArtifactAgent.calls = 0
    resolved_settings = settings(tmp_path)
    adapter = HermesAgentRunAdapter(
        settings=resolved_settings,
        agent_cls=ContractArtifactAgent,
    )
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    app = create_app(
        settings=resolved_settings,
        adapter=adapter,
        run_store=store,
    )
    client = TestClient(app)
    payload = full_payload()
    payload["attachments"] = []

    with document_generation_context(
        resolved_settings,
        provider=FakeDocumentProvider(),
    ):
        first = client.post(
            "/internal/agent/chat/stream",
            json=payload,
            headers={"X-Internal-Key": INTERNAL_KEY},
        )

    assert first.status_code == 200
    assert first.headers["content-type"].startswith("text/event-stream")
    first_frames = parse_sse(first.text)
    first_event_names = [name for name, _data in first_frames]
    assert first_event_names == [
        "run_started",
        "agent_step",
        "agent_step",
        "artifact_created",
        "answer_delta",
        "final",
    ]
    assert first_frames[1][1]["status"] == "started"
    assert first_frames[2][1]["status"] == "succeeded"
    artifact_created = first_frames[3][1]
    first_final = first_frames[-1][1]
    persisted = store.get_by_run_id(first_final["run_id"])
    assert artifact_created == ARTIFACT
    assert first_final["artifacts"] == [artifact_created]
    assert persisted is not None
    assert persisted.artifacts == [artifact_created]

    second = client.post(
        "/internal/agent/chat/stream",
        json=payload,
        headers={"X-Internal-Key": INTERNAL_KEY},
    )
    second_frames = parse_sse(second.text)
    second_event_names = [name for name, _data in second_frames]
    second_final = second_frames[-1][1]

    assert second.status_code == 200
    assert second_event_names == ["run_started", "answer_delta", "final"]
    assert second_final["run_id"] == first_final["run_id"]
    assert second_final["artifacts"] == first_final["artifacts"]
    assert ContractArtifactAgent.calls == 1
