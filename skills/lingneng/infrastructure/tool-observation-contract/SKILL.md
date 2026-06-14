---
name: tool-observation-contract
description: 工具观察平台契约 Skill，定义工具结果进入业务回答时的使用规则。
version: 1.0.0
metadata:
  lingneng:
    schema_version: "1.0"
    kind: infrastructure
    source: python
    status: active
    user_visible: false
    script_policy: metadata_only
    tags: [infrastructure, tools]
    domains: [platform]
  hermes:
    tags: [lingneng]
    requires_tools: [read_skill]
    fallback_for_toolsets: [lingneng]
---

## Applies To

适用于所有注册 server tools 的调用结果，包括时间、搜索、文档、图片和图表工具。

## Runtime Contract

工具结果只能作为已观察到的信息使用，回答中应保留限制和失败状态。
工具缺失或未配置时继续文本回答；工具超时或返回空结果时，也继续提供不依赖该工具的文本回答，并说明当前依据不足。

## Constraints

不得假设工具未返回的字段；不得把模型猜测包装成工具观察结果。
隐藏或不可见工具不代表已授权；未出现在当前 toolset 的工具也不代表已经执行。
只有真实工具返回的结果可以称为“已查询”“已生成”“已检索”或“已观察到”。

## Failure Handling

工具错误、超时或空结果时，说明可用信息不足，并给出无需工具的替代输出。
