---
name: image-generation
description: 图片生成能力 Skill，约束文生图 artifact 的提示词、尺寸和安全边界。
version: 1.0.0
metadata:
  lingneng:
    schema_version: "1.0"
    kind: capability
    source: python
    status: active
    user_visible: true
    script_policy: metadata_only
    tags: [capability, image]
    domains: [marketing]
    capability_name: image_generation
    tools:
      - image_generation
    supporting_skills:
      - artifact-output-contract
  hermes:
    tags: [lingneng]
    requires_tools: [read_skill]
    fallback_for_toolsets: [lingneng]
---

## Capability Scope

根据业务用途和视觉提示词生成图片 artifact，不负责完整营销方案设计。

## When to Use

用户明确需要图片、海报素材、视觉概念图或图片 prompt 落地时使用。

## Input Requirements

需要主题、主体、风格、场景、尺寸和禁止元素；缺失时先生成安全默认提示词。

## Tool Guidance

调用 `image_generation` 时传入具体 prompt、尺寸、质量和数量。

## Output Contract

返回图片 artifact 说明，并简述生成意图和可用于的场景。

## Failure Handling

工具不可用时输出可复用的图片提示词和人工设计说明。

## Examples

- 生成新品套餐海报背景图。
- 为小红书封面生成视觉方向。
