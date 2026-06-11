---
name: document-generation
description: 文档生成能力 Skill，约束 PDF 报告 artifact 的输入、调用和交付边界。
version: 1.0.0
metadata:
  lingneng:
    schema_version: "1.0"
    kind: capability
    source: python
    status: active
    user_visible: true
    script_policy: metadata_only
    tags: [capability, artifact]
    domains: [document]
    capability_name: document_generation
    tools:
      - document_generation
    supporting_skills:
      - artifact-output-contract
      - report-formatting
---

## Capability Scope

把已经组织好的完整正文转换为可下载 PDF 报告 artifact。

## When to Use

用户明确需要报告、文件、PDF、可下载材料或正式交付物时使用。

## Input Requirements

必须提供标题和完整报告正文；不要只传摘要、提纲或工具说明。

## Tool Guidance

调用 `document_generation` 前先完成正文组织和格式检查。

## Output Contract

交付结果应说明已生成文档 artifact，并保留正文关键结论。

## Failure Handling

正文不足时先补全结构；工具失败时返回可复制的 Markdown 正文。

## Examples

- 将培训总结生成 PDF。
- 将经营复盘整理为可下载报告。
