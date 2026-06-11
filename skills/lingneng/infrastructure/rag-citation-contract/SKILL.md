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
---

## Applies To

适用于知识库问答、培训总结、制度解释和需要企业资料依据的业务回答。

## Runtime Contract

回答必须区分知识库证据、用户提供信息和模型推断；证据不足时明确说明。

## Constraints

不得编造引用、文件名、条款或知识库未覆盖的事实。

## Failure Handling

检索无结果时说明未找到依据，提供可追问问题或建议用户补充资料。
