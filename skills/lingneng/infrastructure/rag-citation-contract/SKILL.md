---
name: rag-citation-contract
description: RAG 引用平台契约 Skill，定义知识库证据、引用和不确定性表达。
version: 1.0.0
metadata:
  lingneng:
    schema_version: "1.0"
    kind: infrastructure
    source: python
    status: active
    user_visible: false
    script_policy: metadata_only
    tags: [infrastructure, rag]
    domains: [platform]
  hermes:
    tags: [lingneng]
    requires_tools: [read_skill]
    fallback_for_toolsets: [lingneng]
---

## Applies To

适用于知识库问答、培训总结、制度解释和需要企业资料依据的业务回答。

## Runtime Contract

回答必须区分知识库证据、用户提供信息和模型推断；证据不足时明确说明。
内部训练资料和历史案例优先使用 retrieve_rag；门店知识和企业规则也优先走内部检索。
实时公共事实使用 web_search；外部政策、近期活动和开放互联网信息也应标注时效性。

## Constraints

不得编造引用、文件名或条款；也不得编造知识库未覆盖的事实。
不得把没有检索到的材料写成引用；不得虚构资料标题、章节、制度条款、案例编号或来源文件名。
模型常识只能作为推断或建议，不能冒充知识库证据。

## Business Decision Boundary

- internal learned knowledge uses retrieve_rag.
- realtime public facts use web_search.
- `retrieve_rag` is a normal Hermes tool, not a required-first prefetch node.
- Do not fabricate citations when `retrieve_rag` returns no usable context.

## Failure Handling

检索无结果时说明未找到依据，提供可追问问题或建议用户补充资料。
