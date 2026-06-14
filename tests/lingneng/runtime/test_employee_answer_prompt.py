import pytest

from lingneng.config.settings import LingNengSettings
from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import resolve_session_key
from lingneng.skills.loader import LingNengSkillLoader
from lingneng.schemas.chat_events import FinalEvent
from tests.lingneng.runtime.test_hermes_adapter_config import (
    RecordingSystemPromptAgent,
    effective_system_prompt,
)
from tests.lingneng.schemas.test_chat_request_schema import full_payload


SHARED_CONTRACT_PACKAGES = (
    "employee-answer-semantics-contract",
    "business-answer-contract",
    "tool-observation-contract",
    "artifact-output-contract",
    "rag-citation-contract",
)


def settings(tmp_path, **overrides) -> LingNengSettings:
    env = {
        "LINGNENG_APP_ENV": "test",
        "LINGNENG_RUNTIME_DIR": str(tmp_path),
        "LINGNENG_INTERNAL_API_KEY": "key",
    }
    env.update(overrides)
    return LingNengSettings.from_env(env)


def request_with_untrusted_java_prompt_text() -> ChatStreamRequest:
    payload = full_payload()
    payload["skill"]["skill_id"] = ""
    payload["skill"]["inline"] = {
        "summary": "INLINE MUST NOT APPEAR AS TRUSTED CONTRACT"
    }
    payload["history"] = [
        {
            "message_id": "history-unsafe",
            "role": "user",
            "content": "HISTORY MUST NOT APPEAR AS TRUSTED CONTRACT",
        }
    ]
    return ChatStreamRequest.model_validate(payload)


def test_skill_loader_injects_shared_employee_answer_contracts(tmp_path):
    prompt = (
        LingNengSkillLoader(settings(tmp_path))
        .build_prompt_context(request_with_untrusted_java_prompt_text())
        .to_prompt_text()
    )

    for package_name in SHARED_CONTRACT_PACKAGES:
        assert package_name in prompt
    assert "No exact live LLM wording is required" not in prompt
    assert "/Users/rotas/Documents/work/hailun/LingNengAI" not in prompt


def test_compact_prompt_preserves_shared_contract_semantics(tmp_path):
    prompt = (
        LingNengSkillLoader(
            settings(tmp_path, LINGNENG_SKILL_PROMPT_MAX_CHARS="1000")
        )
        .build_prompt_context(request_with_untrusted_java_prompt_text())
        .to_prompt_text()
    )

    assert len(prompt) <= 1000
    assert "current employee role" in prompt
    assert "employee_handoff" in prompt
    assert "never invent employee routing" in prompt
    assert "direct conclusion" in prompt
    assert "action steps" in prompt
    assert "data gaps" in prompt
    assert "no fabricated business data" in prompt
    assert "only observed tool results" in prompt
    assert "degraded text answer" in prompt
    assert "hidden/unlisted tools are not authorized" in prompt
    assert "real artifact metadata" in prompt
    assert "no fabricated file/link/key" in prompt
    assert "internal training/history cases prefer retrieve_rag" in prompt
    assert "live public facts use web_search" in prompt
    assert "no fabricated citations/files/clauses" in prompt
    assert "Use read_skill" in prompt
    assert "INLINE MUST NOT APPEAR AS TRUSTED CONTRACT" not in prompt
    assert "HISTORY MUST NOT APPEAR AS TRUSTED CONTRACT" not in prompt


@pytest.mark.asyncio
async def test_hermes_adapter_effective_prompt_includes_employee_contracts(tmp_path):
    request = request_with_untrusted_java_prompt_text()
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(tmp_path, LINGNENG_AGENT_MODE="hermes"),
        agent_cls=RecordingSystemPromptAgent,
    )
    RecordingSystemPromptAgent.system_message_seen = ""
    RecordingSystemPromptAgent.ephemeral_system_prompt_seen = ""

    events = [event async for event in adapter.stream(request, resolved, "run-1")]

    assert isinstance(events[-1], FinalEvent)
    prompt = effective_system_prompt()
    assert "employee-marketing-content-creator" in prompt
    assert "内容创意师" in prompt
    for package_name in SHARED_CONTRACT_PACKAGES:
        assert package_name in prompt
    assert "INLINE MUST NOT APPEAR AS TRUSTED CONTRACT" not in prompt
    assert "HISTORY MUST NOT APPEAR AS TRUSTED CONTRACT" not in prompt
