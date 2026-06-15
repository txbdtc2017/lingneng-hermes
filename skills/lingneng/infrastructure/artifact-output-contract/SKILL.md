---
name: artifact-output-contract
description: Artifact 输出平台契约 Skill，定义工具生成文件和图片时的交付规则。
version: 1.0.0
metadata:
  lingneng:
    schema_version: "1.0"
    kind: infrastructure
    source: python
    status: active
    user_visible: false
    script_policy: metadata_only
    tags: [infrastructure, artifact]
    domains: [platform]
  hermes:
    tags: [lingneng]
    requires_tools: [read_skill]
    fallback_for_toolsets: [lingneng]
---

## Applies To

适用于 `document_generation`、`image_generation`、`chart_visualization` 生成的 artifact。

## Runtime Contract

工具调用前必须准备完整输入；工具返回后文本答案应说明 artifact 用途和关键内容。
只有真实 artifact 结果才能声明文件、图片或图表已生成。
只有收到 `artifact_created` 或等价 artifact 元数据后，才可以在最终回答中确认生成成功。

## Constraints

不要把未生成的文件说成已生成；不要暴露本地绝对路径或内部临时文件路径。
没有 `artifact_created` 时不要声称生成成功；可以提供可复制正文、提示词、图表数据或后续生成建议。
不要编造文件名、下载链接、对象存储 key、图片尺寸或图表地址。

## Explicit Artifact Intent

- Artifact tools require explicit deliverable intent such as file, PDF, Word, image, poster, chart, export, or download.
- Do not claim a file, image, chart, or report was generated unless a real artifact result exists.
- Advice, analysis, strategy, copy, or planning text alone is not a real artifact result.

## Failure Handling

artifact 生成失败时，返回可复制的正文、提示词或图表数据摘要，并说明失败状态。
