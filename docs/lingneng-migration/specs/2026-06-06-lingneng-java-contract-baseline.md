# LingNeng Java Contract Baseline

## Source References

This baseline was captured on 2026-06-06 from the current LingNengAI reference
checkout:

- `/Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/http/chat_request.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/http/chat_events.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/api/internal/chat_stream.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/application/chat_event_bridge.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_stream_event_order.py`

The target LingNeng-Hermes runtime must keep Java-facing behavior compatible
with these references unless a later approved phase explicitly changes the
contract.

## HTTP Entrypoint

The Java-facing streaming endpoint is:

```text
POST /internal/agent/chat/stream
```

The request body is JSON. The successful response media type is
`text/event-stream`. In the LingNengAI reference, the router prefix is
`/internal/agent/chat` and the route path is `/stream`, which together form the
entrypoint above.

## Request Model Baseline

The reference request model is `ChatStreamRequest`.

Required top-level fields in the reference schema:

- `request_id`
- `tenant_id`
- `user_id`
- `session_id`
- `query`
- `employee`
- `system_prompt`
- `skill`

This includes the core fields called out by the Phase 0 plan and records the
additional reference-schema fact that `system_prompt` has no default. Phase 1
schema tests should treat `system_prompt.content` as a required full Java
payload assertion.

Top-level unknown fields are accepted and ignored through
`ConfigDict(extra="ignore")`.

`conversation_id` is optional and accepts both wire names:

- `conversation_id`
- `conversationId`

`query` fields:

- `message_id`: optional string.
- `content`: required string.
- `content_type`: string, defaults to `text`.

`system_prompt` fields:

- `content`: required string.
- `version`: optional string.

`skill` fields:

- `skill_id`: required string.
- `skill_version`: required string.
- `skill_hash`: required string.
- `inline`: optional object, string, or null.

`history` is a list of messages with:

- `message_id`: optional string.
- `role`: `user` or `assistant`.
- `content`: required string.

Accepted structured fields with defaults:

- `history_options`: defaults to `source="java_payload"` and
  `max_history_tokens=4096`.
- `attachments`: defaults to an empty list.
- `runtime_context`: defaults to `timezone="Asia/Shanghai"` and `region="CN"`.
- `stream_options`: defaults to `include_agent_steps=true`,
  `include_citations=true`, and `include_rag_context=false`; unknown option
  fields are ignored.
- `model_options`: defaults to `enable_internal_reasoning=false`; unknown
  option fields are ignored.
- `regenerate`: defaults to `enabled=false`, with optional `from_message_id`
  and `extra_instruction`.
- `routing`: accepts optional `confirmed_employee_type` and
  `confirmation_message_id`.

## Employee Identity Baseline

The reference `employee` object contains:

- `employee_id`: optional string.
- `employee_type`: required employee type.
- `display_name`: optional string.

Allowed employee types:

- `boss_assistant`
- `operation_specialist`
- `product_combo_advisor`
- `marketing_planner`
- `marketing_content_creator`
- `member_operator`

LingNeng-Hermes session key resolution must use the employee identity dimension:

- Prefer `tenant_id:user_id:employee_id:conversation_id`.
- If `employee_id` is missing, use
  `tenant_id:user_id:employee_type:conversation_id`.
- If `conversation_id` is missing, fall back to `session_id` only for
  compatibility and record degradation metadata.

## Session And History Policy

Python owns Agent session and conversation history in LingNeng-Hermes. Java
`history` is accepted for compatibility and diagnostics, but it must not be
merged into Hermes Agent context or persisted as Hermes conversation history.

The accepted diagnostics are limited to facts such as whether `history` exists,
message count, and rough bounds useful for migration debugging. Full Java
history content should not be logged as routine trace data.

`request_id` is the idempotency key within the resolved LingNeng session. A
repeated `request_id` for the same session must not append the user message
twice and must not start a duplicate Agent run.

## Attachment Baseline

The reference `attachments` field is a list. Each attachment contains:

- `file_id`: required string.
- `file_name`: required string.
- `mime_type`: required string.
- `size`: optional integer.
- `download_url`: required string.
- `download_url_expires_at`: optional string.
- `usage`: string, defaults to `session_context`.

Phase 1 only needs to preserve and parse this shape. Attachment downloading,
content extraction, and per-request attachment understanding are later runtime
capabilities.

## SSE Encoding Baseline

The reference encoder emits one SSE frame per business event:

```text
event: <event_name>
data: <json>

```

The exact Python reference is equivalent to:

```python
f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
```

JSON is emitted with `ensure_ascii=False`, so UTF-8 text remains readable on the
wire. `ChatEventBridge.to_sse()` returns `{"event": event.event, "data": ...}`
and excludes the event field from `data`. Therefore the SSE `event:` line is
the event type source of truth; `data` JSON does not need to include an `event`
property.

## Formal SSE Event Names

The formal LingNeng-Hermes P1 event name set is:

- `run_started`
- `agent_step`
- `route_result`
- `route_suggestion`
- `route_confirm_required`
- `citation_delta`
- `rag_context`
- `artifact_created`
- `answer_delta`
- `final`
- `compliance_block`
- `error`

The LingNengAI reference also defines auxiliary event models:

- `tool_started`
- `tool_result`
- `console_debug`

These auxiliary names are not part of the formal LingNeng-Hermes P1 event name
set unless a later approved phase adopts them.

## Minimum Phase 1 Event Subset

Phase 1 must support this minimum subset:

- `run_started`
- `answer_delta`
- `final`
- `error`

Other formal events may be added in later phases as RAG, routing, artifacts,
skills, and tool progress are migrated.

## Event Payload Baseline

Reference event models inherit optional envelope fields:

- `schema_version`
- `request_id`
- `run_id`
- `event_id`
- `event_sequence`
- `event_time`

For most events, unset envelope fields are omitted from dumped JSON. The current
LingNengAI stream path stamps envelope data before sending full runtime streams;
Phase 1 tests should allow the minimum event fields below and may also assert
stamped envelope fields when the route owns event sequencing.

Minimum Phase 1 payloads:

- `run_started`: includes at least `run_id` and `request_id`.
- `answer_delta`: includes `text` and optional `sequence`.
- `final`: includes `run_id`, `status`, and `answer`; also supports optional
  `route`, `citations`, `artifacts`, `degradation_codes`, and `trace_summary`.
- `error`: includes `code` and `message` in the LingNengAI reference.

Important non-minimum formal payloads:

- `agent_step`: includes `sequence`, `step_id`, `phase`, `status`, `title`,
  `short_text`, `summary`, optional `detail`, `source`, `public`,
  `display_mode`, `refs`, and `metadata`.
- `route_result`: includes `target_employee_type`, `confidence`,
  `need_confirm`, and `is_current_employee`.
- `route_suggestion`: includes `current_employee_type`,
  `target_employee_type`, `confidence`, `reason`, and `reply`.
- `route_confirm_required`: includes `query`, `candidates`, and `reply`;
  each candidate includes `employee_type`, `confidence`, `label`, and `reason`.
- `citation_delta`: uses the citation contract from the reference RAG schema.
- `rag_context`: includes `context`, `citations`, `status`, and `metadata`.
- `artifact_created`: uses the artifact contract from the reference tool
  artifact schema.
- `compliance_block`: includes `risk_level`, `risk_categories`, and `reply`.

Terminal `final.status` values accepted by the reference are:

- `succeeded`
- `degraded`
- `failed`
- `blocked`

`final` must not include a `tool_plan` field.

## Event Order Baseline

The design baseline requires:

- `run_started` is emitted before answer events.
- `answer_delta` events, when present, are emitted before `final`.
- A successful stream emits exactly one `final`.
- `final` is terminal for successful or degraded streams.
- `error` is terminal on unrecoverable failure after the SSE stream has begun.

The LingNengAI event-order contract test adds these current stream constraints
when agent steps are enabled:

- At least one `agent_step` appears in the stream.
- The first `agent_step` appears before the first `answer_delta`.
- The `answer_generation.started` agent step appears before the first
  `answer_delta`.
- The `answer_generation.completed` agent step appears after the last
  `answer_delta`.
- When `final.answer` is non-empty, at least one `answer_delta` appears before
  `final`.
- The concatenation of all `answer_delta.text` values before `final` equals
  `final.answer`.

## Heartbeat Baseline

The heartbeat frame is:

```text
: ping

```

The exact string is `: ping\n\n`. The reference heartbeat interval is
`15.0` seconds. Heartbeats are SSE comment frames and must not be treated as
business events by Java consumers.

## Error Event Baseline

The LingNengAI reference `ErrorEvent` contains:

- `code`
- `message`

The total LingNeng-Hermes runtime design raises the minimum for future runtime
errors. Phase 1 and later runtime errors should also carry:

- `run_id`
- `request_id`
- `trace_id`
- `recoverable`

Before the SSE stream begins, authentication or request validation failures may
return normal HTTP errors. After the stream begins, business and runtime
failures should be represented as `error` SSE events and then terminate the
stream when unrecoverable.

## Reference Test Result

Required command:

```bash
python -m pytest /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py -q
```

Observed result with the ambient shell `python` from the LingNengAI checkout:

```text
Exit status: 1
/Users/rotas/miniconda3/bin/python: No module named pytest
```

Observed result in the LingNengAI reference virtual environment:

```bash
/Users/rotas/Documents/work/hailun/LingNengAI/.venv/bin/python -m pytest /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py -q
```

```text
Exit status: 0
..............                                                           [100%]
14 passed in 0.03s
```

The contract baseline uses the passing reference virtual environment result as
the authoritative test result. The ambient failure is an environment activation
issue, not a contract failure.

## Phase 1 Implementation Notes

Phase 1 should turn this baseline into Hermes-side schema and SSE tests before
runtime code is added.

Required request assertions:

- Parse the full Java payload shape, including `history_options`,
  `attachments`, `runtime_context`, `stream_options`, `model_options`,
  `regenerate`, and `routing`.
- Accept both `conversation_id` and `conversationId`.
- Ignore unknown Java fields at the request boundary.
- Reject an empty `query.content`.
- Keep `EmployeeType` limited to the six known LingNeng values.

Required SSE assertions:

- Encode with `event: <name>` and UTF-8 JSON `data`.
- Keep heartbeat as `: ping\n\n`.
- Do not require an `event` property inside `data`.
- Support the minimum Phase 1 subset: `run_started`, `answer_delta`, `final`,
  and `error`.
- Preserve event order so `run_started` precedes answer events, successful
  streams terminate with one `final`, and unrecoverable streamed failures
  terminate with `error`.

Required session assertions:

- Resolve session keys with tenant, user, employee identity, and
  `conversation_id`.
- Fall back to `employee_type` when `employee_id` is missing.
- Fall back to `session_id` only when `conversation_id` is missing and expose
  degradation metadata.
- Count Java `history` for diagnostics without adding it to Hermes Agent
  context.
