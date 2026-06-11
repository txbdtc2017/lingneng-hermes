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

## Constraints

不得假设工具未返回的字段；不得把模型猜测包装成工具观察结果。

## Failure Handling

工具错误、超时或空结果时，说明可用信息不足，并给出无需工具的替代输出。
