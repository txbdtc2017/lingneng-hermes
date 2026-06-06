import json

from fastapi.testclient import TestClient

from lingneng.api.app import create_app
from lingneng.config.settings import LingNengSettings
from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter
from tests.lingneng.schemas.test_chat_request_schema import full_payload


INTERNAL_KEY = "key"


def parse_sse(text: str) -> list[tuple[str, dict]]:
    frames = []
    for raw_frame in text.strip().split("\n\n"):
        lines = raw_frame.splitlines()
        if not lines or lines[0].startswith(":"):
            continue
        event_line = next(line for line in lines if line.startswith("event: "))
        data_line = next(line for line in lines if line.startswith("data: "))
        frames.append(
            (
                event_line.removeprefix("event: "),
                json.loads(data_line.removeprefix("data: ")),
            )
        )
    return frames


class ContractAgent:
    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")

    def run_conversation(self, *args, **kwargs):
        self.stream_delta_callback("你")
        self.stream_delta_callback("好")
        return {"final_response": "你好", "messages": []}


def test_hermes_mode_no_tool_chat_stream_contract(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_AGENT_MODE": "hermes",
            "LINGNENG_INTERNAL_API_KEY": INTERNAL_KEY,
        }
    )
    adapter = HermesAgentRunAdapter(settings=settings, agent_cls=ContractAgent)
    app = create_app(settings=settings, adapter=adapter)
    payload = full_payload()
    payload["attachments"] = []
    response = TestClient(app).post(
        "/internal/agent/chat/stream",
        json=payload,
        headers={"X-Internal-Key": INTERNAL_KEY},
    )

    frames = parse_sse(response.text)
    event_names = [event_name for event_name, _ in frames]
    deltas = [
        data["text"] for event_name, data in frames if event_name == "answer_delta"
    ]
    final_payload = frames[-1][1]

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert event_names == ["run_started", "answer_delta", "answer_delta", "final"]
    assert "".join(deltas) == final_payload["answer"]
    assert final_payload["answer"] == "你好"
    assert "event" not in final_payload
