from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class JavaPayloadModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class EmployeeType(str, Enum):
    BOSS_ASSISTANT = "boss_assistant"
    OPERATION_SPECIALIST = "operation_specialist"
    PRODUCT_COMBO_ADVISOR = "product_combo_advisor"
    MARKETING_PLANNER = "marketing_planner"
    MARKETING_CONTENT_CREATOR = "marketing_content_creator"
    MEMBER_OPERATOR = "member_operator"


class QueryPayload(JavaPayloadModel):
    message_id: str | None = None
    content: str
    content_type: str = "text"

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query.content must not be empty")
        return value


class EmployeePayload(JavaPayloadModel):
    employee_id: str | None = None
    employee_type: EmployeeType
    display_name: str | None = None


class SystemPromptPayload(JavaPayloadModel):
    content: str
    version: str | None = None


class SkillPayload(JavaPayloadModel):
    skill_id: str
    skill_version: str
    skill_hash: str
    inline: dict[str, Any] | str | None = None


class HistoryMessage(JavaPayloadModel):
    message_id: str | None = None
    role: Literal["user", "assistant"]
    content: str


class HistoryOptions(JavaPayloadModel):
    source: str = "java_payload"
    max_history_tokens: int = 4096


class AttachmentPayload(JavaPayloadModel):
    file_id: str
    file_name: str
    mime_type: str
    size: int | None = None
    download_url: str
    download_url_expires_at: str | None = None
    usage: str = "session_context"


class RuntimeContext(JavaPayloadModel):
    timezone: str = "Asia/Shanghai"
    region: str = "CN"


class StreamOptions(JavaPayloadModel):
    include_agent_steps: bool = True
    include_citations: bool = True
    include_rag_context: bool = False


class ModelOptions(JavaPayloadModel):
    enable_internal_reasoning: bool = False


class RegenerateOptions(JavaPayloadModel):
    enabled: bool = False
    from_message_id: str | None = None
    extra_instruction: str | None = None


class RoutingOptions(JavaPayloadModel):
    confirmed_employee_type: EmployeeType | None = None
    confirmation_message_id: str | None = None


class ChatStreamRequest(JavaPayloadModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    request_id: str
    tenant_id: str
    user_id: str
    session_id: str
    conversation_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("conversationId", "conversation_id"),
    )
    query: QueryPayload
    employee: EmployeePayload
    system_prompt: SystemPromptPayload
    skill: SkillPayload
    history: list[HistoryMessage] = Field(default_factory=list)
    history_options: HistoryOptions = Field(default_factory=HistoryOptions)
    attachments: list[AttachmentPayload] = Field(default_factory=list)
    runtime_context: RuntimeContext = Field(default_factory=RuntimeContext)
    stream_options: StreamOptions = Field(default_factory=StreamOptions)
    model_options: ModelOptions = Field(default_factory=ModelOptions)
    regenerate: RegenerateOptions = Field(default_factory=RegenerateOptions)
    routing: RoutingOptions = Field(default_factory=RoutingOptions)
