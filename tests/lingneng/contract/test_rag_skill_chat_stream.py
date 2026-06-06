from __future__ import annotations

from fastapi.testclient import TestClient

from lingneng.api.app import create_app
from lingneng.config.settings import LingNengSettings
from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter
from lingneng.session.run_store import LingNengRunStore
from lingneng.tools.rag import RagRetrieveResult
from tests.lingneng.api.test_chat_stream_contract import parse_sse
from tests.lingneng.schemas.test_chat_request_schema import full_payload
from tests.lingneng.skills.test_skill_loader import write_skill
from tools.registry import registry


INTERNAL_KEY = "key"
INLINE_MARKER = "INLINE MUST NOT APPEAR"
FINAL_ANSWER = "基于知识库，建议这样写。"
CITATION = {
    "document_id": "doc-1",
    "source_file_id": "file-1",
    "source_file_name": "menu.pdf",
    "page_no": 2,
    "section_title": "会员套餐",
    "chunk_id": "chunk-1",
    "score": 0.92,
}


class FakeProvider:
    def retrieve(self, request):
        return RagRetrieveResult(
            status="hit",
            context="会员套餐规则来自知识库。",
            citations=[CITATION],
            metadata={"duration_ms": 3},
        )


class ContractRagSkillAgent:
    system_message_seen = ""

    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")
        self.tool_progress_callback = kwargs.get("tool_progress_callback")

    def run_conversation(self, user_message, system_message=None, **kwargs):
        type(self).system_message_seen = system_message or ""
        self.tool_progress_callback(
            "tool.started",
            "retrieve_rag",
            "query='会员套餐'",
            {"query": "会员套餐"},
        )
        result = registry.dispatch(
            "retrieve_rag",
            {"query": "会员套餐", "top_k": 1},
        )
        self.tool_progress_callback(
            "tool.completed",
            "retrieve_rag",
            None,
            None,
            duration=0.01,
            is_error=False,
            result=result,
        )
        self.stream_delta_callback("基于知识库，")
        self.stream_delta_callback("建议这样写。")
        return {"final_response": FINAL_ANSWER, "messages": []}


def settings(tmp_path, skill_root):
    return LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path / "runtime"),
            "LINGNENG_AGENT_MODE": "hermes",
            "LINGNENG_INTERNAL_API_KEY": INTERNAL_KEY,
            "LINGNENG_SKILL_ROOTS": str(skill_root),
        }
    )


def test_rag_skill_chat_stream_contract(tmp_path, monkeypatch):
    skill_root = tmp_path / "skills"
    write_skill(
        skill_root,
        "employee-marketing-content-creator",
        kind="employee_base",
        employee_type="marketing_content_creator",
        display_name="内容创意师",
        body="## Role Identity\n你是内容创意师。\n## RAG Guidance\n需要事实时查知识库。",
    )
    write_skill(
        skill_root,
        "marketing-copy-generation",
        body="## When to Use\n生成营销文案。\n## Workflow\n先确认渠道。",
    )
    monkeypatch.setattr(
        "lingneng.runtime.hermes_adapter._build_rag_provider",
        lambda settings: FakeProvider(),
    )
    resolved_settings = settings(tmp_path, skill_root)
    adapter = HermesAgentRunAdapter(
        settings=resolved_settings,
        agent_cls=ContractRagSkillAgent,
    )
    app = create_app(
        settings=resolved_settings,
        adapter=adapter,
        run_store=LingNengRunStore(tmp_path / "runs.sqlite3"),
    )
    payload = full_payload()
    payload["skill"]["skill_id"] = "marketing-copy-generation"
    payload["skill"]["inline"] = {"summary": INLINE_MARKER}
    payload["stream_options"]["include_citations"] = True
    payload["stream_options"]["include_rag_context"] = True

    response = TestClient(app).post(
        "/internal/agent/chat/stream",
        json=payload,
        headers={"X-Internal-Key": INTERNAL_KEY},
    )
    frames = parse_sse(response.text)
    event_names = [name for name, _data in frames]
    final = frames[-1][1]

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert event_names[0] == "run_started"
    assert event_names[-1] == "final"
    assert "agent_step" in event_names
    assert "citation_delta" in event_names
    assert "rag_context" in event_names
    assert "answer_delta" in event_names
    completed_step_index = next(
        index
        for index, (name, data) in enumerate(frames)
        if name == "agent_step" and data["status"] == "succeeded"
    )
    citation_index = event_names.index("citation_delta")
    rag_context_index = event_names.index("rag_context")
    first_answer_index = event_names.index("answer_delta")
    assert completed_step_index < citation_index
    assert completed_step_index < rag_context_index
    assert completed_step_index < citation_index < rag_context_index < first_answer_index
    assert any(citation["chunk_id"] == "chunk-1" for citation in final["citations"])
    assert (
        "".join(data["text"] for name, data in frames if name == "answer_delta")
        == final["answer"]
    )
    assert final["answer"] == FINAL_ANSWER
    prompt = ContractRagSkillAgent.system_message_seen
    assert "employee-marketing-content-creator" in prompt
    assert "内容创意师" in prompt
    assert "marketing-copy-generation" in prompt
    assert "生成营销文案" in prompt
    assert INLINE_MARKER not in prompt
