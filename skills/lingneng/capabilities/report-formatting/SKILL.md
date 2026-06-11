---
name: report-formatting
description: 报告格式化能力 Skill，约束报告结构、标题层级和业务表达格式。
version: 1.0.0
metadata:
  lingneng:
    schema_version: "1.0"
    kind: capability
    source: python
    status: active
    user_visible: true
    script_policy: metadata_only
    tags: [capability, formatting]
    domains: [document]
    capability_name: report_formatting
    supporting_skills:
      - business-answer-contract
---

## Capability Scope

整理报告结构、层级、表格和交付语言，不直接调用不存在的格式化工具。

## When to Use

需要把答案改成经营报告、执行方案、复盘纪要或正式文档结构时使用。

## Input Requirements

需要主题、受众、原始内容和期望格式；缺少时使用通用业务报告结构。

## Tool Guidance

本能力不声明独立 server tool；如需 PDF 交付，应与 `document-generation` 协作。

## Output Contract

输出标题、摘要、正文层级、表格或清单，保证可读且可直接复制。

## Failure Handling

内容不足时先生成结构化模板，并标注待补字段。

## Examples

- 把活动方案改成老板汇报版。
- 把培训纪要整理成正式报告结构。
