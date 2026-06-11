---
name: training-summary-report
description: 培训总结报告任务 Skill，用于培训纪要整理、重点提炼和报告交付。
version: 1.0.0
metadata:
  lingneng:
    schema_version: "1.0"
    kind: task
    source: python
    status: active
    user_visible: true
    script_policy: metadata_only
    tags: [training, report]
    domains: [restaurant]
    tools:
      - document_generation
    target_employee_types:
      - boss_assistant
      - operation_specialist
    supporting_skills:
      - document-generation
      - report-formatting
      - artifact-output-contract
  hermes:
    tags: [lingneng]
    requires_tools: [read_skill]
    fallback_for_toolsets: [lingneng]
triggers: [培训总结, 培训纪要, 学习报告, 会议总结]
---

## When to Use

用户要求把培训、会议、学习材料或知识点整理成结构化总结或 PDF 报告时使用。

## When Not to Use

单个知识点问答、营销文案创作、会员活动策划或经营数据深度诊断时不要使用。

## Preconditions

需要具备培训主题、材料内容、参训对象或用户提供的纪要片段。

## Workflow

1. 提炼培训目标、核心内容和关键结论。
2. 归纳方法、流程、注意事项和行动项。
3. 根据受众组织成报告结构。
4. 需要下载交付时生成完整文档正文。

## RAG Guidance

培训材料来自知识库时，引用关键来源，不把未检索到的内容写成事实。

## Tool Guidance

用户需要 PDF 或正式报告时使用 `document_generation`。

## Output Contract

输出包含摘要、重点内容、行动项、待跟进问题和可交付报告正文。

## Failure Handling

材料不足时提供摘要框架，并提示用户补充原文、录音转写或附件内容。

## Examples

- “把今天的培训内容整理成老板能看的报告。”
- “根据这些笔记输出培训总结。”

## Resources

无固定资源；优先使用用户提供材料和知识库培训内容。
