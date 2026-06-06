import pytest
from pydantic import ValidationError

from lingneng.schemas.chat_request import ChatStreamRequest, EmployeeType


def full_payload() -> dict:
    return {
        "request_id": "req-001",
        "tenant_id": "tenant-a",
        "user_id": "user-a",
        "session_id": "session-a",
        "conversation_id": "conv-a",
        "query": {
            "message_id": "msg-001",
            "content": "请生成一段会员运营文案",
            "content_type": "text",
            "unknown_query_field": "ignored",
        },
        "employee": {
            "employee_id": "emp-001",
            "employee_type": "marketing_content_creator",
            "display_name": "营销内容员工",
            "unknown_employee_field": "ignored",
        },
        "system_prompt": {
            "content": "你是灵能营销内容员工。",
            "version": "v1",
            "unknown_prompt_field": "ignored",
        },
        "skill": {
            "skill_id": "skill-marketing-content",
            "skill_version": "2026-06-06",
            "skill_hash": "sha256-test",
            "inline": {"summary": "写作技能"},
            "unknown_skill_field": "ignored",
        },
        "history": [
            {
                "message_id": "h-1",
                "role": "user",
                "content": "上一轮用户问题",
                "unknown_history_field": "ignored",
            },
            {"message_id": "h-2", "role": "assistant", "content": "上一轮回答"},
        ],
        "history_options": {
            "source": "java_payload",
            "max_history_tokens": 4096,
            "unknown_history_option": "ignored",
        },
        "attachments": [
            {
                "file_id": "file-001",
                "file_name": "brief.pdf",
                "mime_type": "application/pdf",
                "size": 1234,
                "download_url": "https://files.example.test/brief.pdf",
                "download_url_expires_at": "2026-06-07T00:00:00+08:00",
                "usage": "session_context",
                "unknown_attachment_field": "ignored",
            }
        ],
        "runtime_context": {
            "timezone": "Asia/Shanghai",
            "region": "CN",
            "unknown_runtime_field": "ignored",
        },
        "stream_options": {
            "include_agent_steps": True,
            "include_citations": True,
            "include_rag_context": False,
            "ignored_stream_option": "ignored",
        },
        "model_options": {
            "enable_internal_reasoning": False,
            "ignored_model_option": "ignored",
        },
        "regenerate": {
            "enabled": False,
            "from_message_id": None,
            "extra_instruction": None,
            "unknown_regenerate_field": "ignored",
        },
        "routing": {
            "confirmed_employee_type": "marketing_content_creator",
            "confirmation_message_id": "confirm-001",
            "unknown_routing_field": "ignored",
        },
        "unknown_java_field": "ignored",
    }


def test_parses_full_java_payload():
    request = ChatStreamRequest.model_validate(full_payload())

    assert request.request_id == "req-001"
    assert request.tenant_id == "tenant-a"
    assert request.user_id == "user-a"
    assert request.session_id == "session-a"
    assert request.conversation_id == "conv-a"
    assert request.query.content == "请生成一段会员运营文案"
    assert request.employee.employee_id == "emp-001"
    assert request.employee.employee_type is EmployeeType.MARKETING_CONTENT_CREATOR
    assert request.system_prompt.content == "你是灵能营销内容员工。"
    assert request.skill.skill_id == "skill-marketing-content"
    assert len(request.history) == 2
    assert request.history[0].role == "user"
    assert request.attachments[0].file_id == "file-001"
    assert request.runtime_context.timezone == "Asia/Shanghai"
    assert request.stream_options.include_agent_steps is True
    assert request.model_options.enable_internal_reasoning is False
    assert request.regenerate.enabled is False
    assert request.routing is not None
    assert request.routing.confirmed_employee_type is EmployeeType.MARKETING_CONTENT_CREATOR


def test_accepts_conversation_id_alias():
    payload = full_payload()
    payload.pop("conversation_id")
    payload["conversationId"] = "conv-alias"

    request = ChatStreamRequest.model_validate(payload)

    assert request.conversation_id == "conv-alias"


def test_json_schema_exposes_java_conversation_id_alias():
    properties = ChatStreamRequest.model_json_schema()["properties"]

    assert "conversationId" in properties
    assert "conversation_id" not in properties


def test_ignores_unknown_java_fields():
    request = ChatStreamRequest.model_validate(full_payload())
    data = request.model_dump()

    assert "unknown_java_field" not in data
    assert "unknown_query_field" not in data["query"]
    assert "unknown_employee_field" not in data["employee"]
    assert "ignored_stream_option" not in data["stream_options"]
    assert "ignored_model_option" not in data["model_options"]
    assert "unknown_routing_field" not in data["routing"]


def test_defaults_for_structured_optional_fields():
    payload = full_payload()
    for key in [
        "history",
        "history_options",
        "attachments",
        "runtime_context",
        "stream_options",
        "model_options",
        "regenerate",
        "routing",
    ]:
        payload.pop(key)

    request = ChatStreamRequest.model_validate(payload)

    assert request.history == []
    assert request.history_options.source == "java_payload"
    assert request.history_options.max_history_tokens == 4096
    assert request.attachments == []
    assert request.runtime_context.timezone == "Asia/Shanghai"
    assert request.runtime_context.region == "CN"
    assert request.stream_options.include_agent_steps is True
    assert request.stream_options.include_citations is True
    assert request.stream_options.include_rag_context is False
    assert request.model_options.enable_internal_reasoning is False
    assert request.regenerate.enabled is False
    assert request.routing.confirmed_employee_type is None


@pytest.mark.parametrize("content", ["", "   "])
def test_rejects_empty_query_content(content):
    payload = full_payload()
    payload["query"]["content"] = content

    with pytest.raises(ValidationError):
        ChatStreamRequest.model_validate(payload)


def test_rejects_unknown_employee_type():
    payload = full_payload()
    payload["employee"]["employee_type"] = "unknown_employee"

    with pytest.raises(ValidationError):
        ChatStreamRequest.model_validate(payload)
