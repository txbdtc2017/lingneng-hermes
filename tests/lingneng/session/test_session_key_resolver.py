import pytest
from pydantic import ValidationError

from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import ResolvedSessionKey, resolve_session_key
from tests.lingneng.schemas.test_chat_request_schema import full_payload


def request_from(payload: dict) -> ChatStreamRequest:
    return ChatStreamRequest.model_validate(payload)


def test_resolves_with_employee_id_and_conversation_id():
    resolved = resolve_session_key(request_from(full_payload()))

    assert resolved.session_key == "tenant-a:user-a:emp-001:conv-a"
    assert resolved.tenant_id == "tenant-a"
    assert resolved.user_id == "user-a"
    assert resolved.employee_id == "emp-001"
    assert resolved.employee_type == "marketing_content_creator"
    assert resolved.conversation_id == "conv-a"
    assert resolved.session_id == "session-a"
    assert resolved.degraded is False
    assert resolved.degradation_reason is None
    assert resolved.history_message_count == 2
    assert resolved.context_messages == []


def test_resolves_with_employee_type_when_employee_id_missing():
    payload = full_payload()
    payload["employee"].pop("employee_id")

    resolved = resolve_session_key(request_from(payload))

    assert resolved.session_key == "tenant-a:user-a:marketing_content_creator:conv-a"
    assert resolved.employee_id is None
    assert resolved.employee_type == "marketing_content_creator"
    assert resolved.degraded is False
    assert resolved.degradation_reason is None


def test_blank_employee_id_falls_back_to_employee_type():
    payload = full_payload()
    payload["employee"]["employee_id"] = "   "

    resolved = resolve_session_key(request_from(payload))

    assert resolved.session_key == "tenant-a:user-a:marketing_content_creator:conv-a"
    assert resolved.employee_id is None
    assert resolved.employee_type == "marketing_content_creator"
    assert resolved.degraded is False


def test_falls_back_to_session_id_when_conversation_id_missing():
    payload = full_payload()
    payload.pop("conversation_id")

    resolved = resolve_session_key(request_from(payload))

    assert resolved.session_key == "tenant-a:user-a:emp-001:session-a"
    assert resolved.conversation_id is None
    assert resolved.session_id == "session-a"
    assert resolved.degraded is True
    assert resolved.degradation_reason == "conversation_id_missing"


def test_blank_conversation_id_falls_back_to_session_id():
    payload = full_payload()
    payload["conversation_id"] = "   "

    resolved = resolve_session_key(request_from(payload))

    assert resolved.session_key == "tenant-a:user-a:emp-001:session-a"
    assert resolved.conversation_id is None
    assert resolved.session_id == "session-a"
    assert resolved.degraded is True
    assert resolved.degradation_reason == "conversation_id_missing"


def test_history_is_counted_but_not_returned_as_context():
    payload = full_payload()
    payload["history"].append(
        {"message_id": "h-3", "role": "user", "content": "不要进入上下文"}
    )

    resolved = resolve_session_key(request_from(payload))

    assert resolved.history_message_count == 3
    assert resolved.context_messages == []


@pytest.mark.parametrize(
    ("field_path", "value"),
    [
        (("tenant_id",), "tenant:a"),
        (("user_id",), "user:a"),
        (("employee", "employee_id"), "emp:001"),
        (("conversation_id",), "conv:a"),
    ],
)
def test_rejects_colons_in_session_key_segments(field_path, value):
    payload = full_payload()
    target = payload
    for key in field_path[:-1]:
        target = target[key]
    target[field_path[-1]] = value

    with pytest.raises(ValueError, match="must not contain ':'"):
        resolve_session_key(request_from(payload))


def test_rejects_colon_in_fallback_session_id_segment():
    payload = full_payload()
    payload.pop("conversation_id")
    payload["session_id"] = "session:a"

    with pytest.raises(ValueError, match="must not contain ':'"):
        resolve_session_key(request_from(payload))


@pytest.mark.parametrize("field", ["tenant_id", "user_id"])
def test_rejects_blank_required_session_key_segments(field):
    payload = full_payload()
    payload[field] = "   "

    with pytest.raises(ValueError, match="must not be empty"):
        resolve_session_key(request_from(payload))


def test_rejects_blank_fallback_session_id_segment():
    payload = full_payload()
    payload.pop("conversation_id")
    payload["session_id"] = "   "

    with pytest.raises(ValueError, match="must not be empty"):
        resolve_session_key(request_from(payload))


def test_resolved_session_key_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ResolvedSessionKey.model_validate(
            {
                "session_key": "tenant-a:user-a:emp-001:conv-a",
                "tenant_id": "tenant-a",
                "user_id": "user-a",
                "conversation_id": "conv-a",
                "session_id": "session-a",
                "employee_id": "emp-001",
                "employee_type": "marketing_content_creator",
                "degraded": False,
                "degradation_reason": None,
                "history_message_count": 2,
                "context_messages": [],
                "unknown": "forbidden",
            }
        )


@pytest.mark.parametrize(
    ("degraded", "degradation_reason"),
    [
        (True, None),
        (False, "conversation_id_missing"),
    ],
)
def test_resolved_session_key_rejects_inconsistent_degradation_state(
    degraded, degradation_reason
):
    with pytest.raises(ValidationError):
        ResolvedSessionKey.model_validate(
            {
                "session_key": "tenant-a:user-a:emp-001:conv-a",
                "tenant_id": "tenant-a",
                "user_id": "user-a",
                "conversation_id": "conv-a",
                "session_id": "session-a",
                "employee_id": "emp-001",
                "employee_type": "marketing_content_creator",
                "degraded": degraded,
                "degradation_reason": degradation_reason,
                "history_message_count": 2,
                "context_messages": [],
            }
        )
