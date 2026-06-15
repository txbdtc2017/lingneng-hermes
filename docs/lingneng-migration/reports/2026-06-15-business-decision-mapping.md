# LingNeng Business Decision Mapping

Phase 17 maps old LingNengAI judgment knowledge into Hermes-native
destinations. No pre-agent router, graph, request planner, or model-based
admission service is introduced.

## Runtime Boundary

Hermes remains the only chat runtime. The Java stream path continues to use
`HermesAgentRunAdapter`, `AIAgent`, Hermes SessionDB, the dedicated `lingneng`
toolset, and the existing SSE bridge.

## Prohibited Runtime Components

The following names are reference-only and must not be rebuilt as active
LingNeng-Hermes runtime paths:

- `RuntimeDecisionService`
- `EntryDecisionService`
- `SemanticDecisionService`
- `RequestPlanner`
- `ToolAdmissionService`
- `light_llm_answer`
- `tool_only_agent`
- `direct_attachment_answer`
- `smalltalk_final_reply`

## Hermes-Native Destination Table

| Case id | Old judgment | Hermes-native destination | Decision | Expected tool |
| --- | --- | --- | --- | --- |
| `direct_answer:member_repurchase` | direct answer / business agent | employee_skill | migrate_as_guidance | none |
| `non_jump_input:identity` | smalltalk/meta non-jump | infrastructure_skill | migrate_as_guidance | none |
| `route_suggest:content_to_planner` | route suggestion | employee_handoff_tool | migrate_as_tool_contract | employee_handoff |
| `route_confirm:broad_marketing` | route confirmation | employee_handoff_tool | migrate_as_tool_contract | employee_handoff |
| `explicit_switch:user_named_employee` | explicit employee switch | employee_handoff_tool | migrate_as_tool_contract | employee_handoff |
| `boss_fallback:unclear_business` | fallback to boss assistant | employee_skill | migrate_as_guidance | none |
| `tool_admission:explicit_artifact` | side-effect tool admission | tool_schema | migrate_as_tool_contract | document_generation |
| `rag_internal:training_rule` | required-first RAG | tool_schema | migrate_as_tool_contract | retrieve_rag |
| `web_realtime:latest_trend` | realtime public facts | tool_schema | migrate_as_tool_contract | web_search |
| `attachment_boundary:uploaded_file` | attachment gate/direct answer | attachment_context | preserve_existing_runtime | none |
| `history_boundary:java_history` | selected history | sessiondb | preserve_existing_runtime | none |
| `compliance_boundary:unsafe_claim` | compliance block | infrastructure_skill | migrate_as_guidance | none |

## Mapping Notes

### direct_answer:member_repurchase

会员复购方案属于当前会员运营顾问可处理的业务问题。它 stays in
`employee_skill` as `migrate_as_guidance`; `RuntimeDecisionService` and
`RequestPlanner` are not restored to decide a direct answer before Hermes.

### non_jump_input:identity

身份和能力说明由当前员工自然回答。This maps to `infrastructure_skill` and
`migrate_as_guidance`, without `smalltalk_final_reply` or `light_llm_answer`.

### route_suggest:content_to_planner

内容创意师遇到活动策划请求时 should express the recommendation through
`employee_handoff_tool` with `employee_handoff`, not through
`RuntimeDecisionService` or `EntryDecisionService`.

### route_confirm:broad_marketing

新品推广这类宽泛请求 uses `employee_handoff_tool` confirmation semantics.
The pending confirmation boundary remains Hermes-native and does not re-create
old route confirmation nodes.

### explicit_switch:user_named_employee

When the user explicitly names a known employee, the expected tool is
`employee_handoff`. The destination remains `employee_handoff_tool`, with no
pre-agent employee switch path.

### boss_fallback:unclear_business

Unclear business-health requests can be handled first by the current employee
with optional boss-assistant guidance. This is `employee_skill` and
`migrate_as_guidance`, not threshold-based fallback routing.

### tool_admission:explicit_artifact

PDF/report generation requires explicit artifact intent. The behavior belongs
to `tool_schema` and `migrate_as_tool_contract`; `ToolAdmissionService` is
replaced by schema guidance, provider fail-closed behavior, and ToolRunGuard.

### rag_internal:training_rule

Internal training-rule questions call `retrieve_rag` through the normal
`tool_schema` destination. There is no required-first RAG prefetch node or
`RuntimeDecisionService` gate.

### web_realtime:latest_trend

Public current-trend questions use `web_search` through `tool_schema`.
`RequestPlanner` realtime mode is not rebuilt; unavailable providers should
degrade to non-realtime guidance.

### attachment_boundary:uploaded_file

Uploaded files are scoped attachment context, not a separate direct-answer
runtime path. The case preserves the existing `attachment_context` runtime
boundary, expects no tool, and prohibits `direct_attachment_answer`.

### history_boundary:java_history

Conversation history comes from Hermes SessionDB. Java history may be counted
or traced but is not injected into agent context. This preserves the existing
`sessiondb` runtime boundary and does not migrate old history selectors.

### compliance_boundary:unsafe_claim

Unsafe claims, such as fabricated real customer reviews, are handled by narrow
infrastructure skill guidance. The expected outcome is safe refusal plus a
compliant alternative, without rebuilding a broad compliance classifier.
