---
name: knowledge-base-answer
description: 知识库问答任务 Skill，用于基于企业资料回答制度、产品和流程问题。
version: 1.0.0
metadata:
  lingneng:
    schema_version: "1.0"
    kind: task
    source: python
    status: active
    user_visible: true
    script_policy: metadata_only
    tags: [rag, qa]
    domains: [restaurant]
    tools:
      - web_search
    target_employee_types:
      - boss_assistant
      - operation_specialist
      - member_operator
      - marketing_planner
      - marketing_content_creator
      - product_combo_advisor
    supporting_skills:
      - rag-citation-contract
      - business-answer-contract
  hermes:
    tags: [lingneng]
    requires_tools: [read_skill]
    fallback_for_toolsets: [lingneng]
triggers: [知识库, 怎么规定, SOP, 资料里]
---

## When to Use

用户询问企业资料、制度、产品信息、SOP、培训内容或需要引用知识库事实时使用。

## When Not to Use

纯创意文案、无需知识依据的闲聊、复杂经营方案或只需要生成 artifact 时不要使用。

## Preconditions

需要有明确问题、可检索的知识库范围，或用户提供的资料片段。

## Workflow

1. 识别用户问题和检索关键词。
2. 基于召回内容回答，并区分确定信息和未覆盖信息。
3. 必要时给出下一步查询或人工确认建议。

## RAG Guidance

必须优先使用知识库证据；无法检索到依据时不要编造。

## Tool Guidance

只有当用户明确需要公开实时信息补充，且平台启用时，才考虑 `web_search`。

## Output Contract

输出直接答案、依据摘要、限制说明和需要用户确认的事项。

## Failure Handling

知识库无命中或证据不足时说明未找到依据，并给出可追问方向。

## Examples

- “资料里会员生日券怎么用？”
- “SOP 里闭店检查有哪些步骤？”

## Resources

无固定资源；运行时依赖 RAG 检索上下文。
