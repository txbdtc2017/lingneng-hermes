---
name: chart-visualization
description: 图表可视化能力 Skill，约束图表、流程图和思维导图类 artifact。
version: 1.0.0
metadata:
  lingneng:
    schema_version: "1.0"
    kind: capability
    source: python
    status: active
    user_visible: true
    script_policy: metadata_only
    tags: [capability, chart]
    domains: [analysis]
    capability_name: chart_visualization
    tools:
      - chart_visualization
    supporting_skills:
      - artifact-output-contract
  hermes:
    tags: [lingneng]
    requires_tools: [read_skill]
    fallback_for_toolsets: [lingneng]
---

## Capability Scope

把结构化数据摘要转换为图表、流程图或思维导图 artifact。

## When to Use

用户需要趋势、对比、结构、流程、因果关系或报告配图时使用。

## Input Requirements

需要图表类型、主题和数据摘要；数据口径不清时先说明假设。

## Tool Guidance

调用 `chart_visualization` 时提供清晰主题和可视化所需的数据摘要。

## Output Contract

交付图表 artifact，并在文本中说明图表表达的关键结论。

## Failure Handling

工具失败时输出文本表格、图表描述和可重试的数据摘要。

## Examples

- 门店月度销售趋势图。
- 活动执行流程图。
