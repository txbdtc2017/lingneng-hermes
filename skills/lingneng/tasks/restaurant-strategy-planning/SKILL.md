---
name: restaurant-strategy-planning
description: 餐饮经营策略规划任务 Skill，用于经营策略顾问处理目标设定、计划拆解、路线图、增长策略、进度追踪、预算达成率、完成率、差距预警、策略复盘、季度规划和年度规划。
version: 1.0.0
metadata:
  lingneng:
    schema_version: "1.0"
    kind: task
    source: python
    status: active
    user_visible: true
    script_policy: metadata_only
    tags: [operation, strategy, planning]
    domains: [restaurant]
    tools:
      - chart_visualization
      - document_generation
    target_employee_types:
      - operation_specialist
    supporting_skills:
      - chart-visualization
      - document-generation
      - report-formatting
      - business-answer-contract
  hermes:
    tags: [lingneng]
    requires_tools: [read_skill]
    fallback_for_toolsets: [lingneng]
triggers: [目标, 计划, 路线图, 增长, 进度, 完成率, 预算达成率, 差距, 差多少, 怎么追, 复盘, 季度, 年度, 规划, 策略, 达到多少, 怎么实现]
---

## When to Use

用户要求经营策略顾问设定餐饮经营目标、拆解月度或季度计划、制定年度路线图、提升增长、追踪预算达成率或完成率、判断进度差距、制定追赶动作、做策略复盘或规划下一阶段经营动作时使用。用户表达为“今年想冲一下”“怎么达到目标”“现在进度怎么样”“差多少怎么追”“季度复盘”也应使用。

## When Not to Use

单次门店经营健康诊断、员工薪资异常、具体菜单工程、套餐定价、会员召回活动、营销文案生成、纯知识库问答或只需要整理会议纪要时不要使用；这些场景应交给对应 task。

## Preconditions

尽量具备目标周期、当前营收基数、目标营收、当前实际营收、日期进度、门店数量、经营模式、成本约束和已执行策略。缺少信息时先用可得数据做初步判断，再追问关键输入。

## Reference Selection

用户需要完整目标规划 SOP、年度/月度路线图模板、进度追踪口径、策略复盘格式或经营策略顾问原始工作手册时，读取 `references/strategy-planning-playbook.md`。只需判断目标进度时先按本 skill 工作流回答。

## Workflow

1. 识别任务模式：判断用户是在目标设定、路线图拆解、进度预警还是策略复盘；如果混合出现，先处理最急的经营风险。
2. 重建目标背景：做追踪或复盘前必须重新确认本轮目标周期、目标值、当前实际、已过时间和关键策略，因为系统不能假设跨会话记忆。
3. 先给立即动作再追问：即使信息不全，也先给 1-3 个当前可执行动作；随后最多追问 3 个关键输入，并说明用途。
4. 目标设定：用历史营收基数、增长意愿、经营模式和成本压力判断目标是否稳健、进取或过高；给出目标区间和主要增长杠杆。
5. 路线图拆解：把年度或季度目标拆到月度、门店或品类，明确每月营收目标、成本预算上限、核心任务和复盘节点；营收按客流 x 客单价拆解，利润按营收减人工、材料、房租能耗和其他成本拆解。
6. 进度预警：计算营收进度 = 实际营收 / 目标营收，时间进度 = 已过天数 / 周期总天数，差距 = 目标营收 - 实际营收，剩余日均 = 差距 / 剩余天数，挑战倍数 = 剩余日均 / 当前日均；用节奏比判断正常、轻微滞后或显著滞后。
7. 策略复盘：先输出可计算部分的初版复盘，再补充策略效果、成本健康、增长质量和可复制经验；区分季节性、大单扰动、策略贡献和执行偏差。
8. 收敛为行动计划：每次输出都必须给出下一阶段最高优先级动作、负责人建议、观察周期、验证指标和需要复盘的节点。

## RAG Guidance

涉及历史目标、预算、门店业绩、节假日安排、已执行活动、企业 SOP 或行业基准时检索知识库。复盘引用历史数据时标注来源；没有历史数据时明确使用估算口径。

## Tool Guidance

年度或季度路线图、进度趋势、目标树、成本结构和复盘对比可使用 `chart_visualization`。用户要求保存年度计划、季度复盘、进度追踪表或正式策略报告时使用 `document_generation`。

## Output Contract

输出应包含：任务模式判断、目标背景、关键计算、进度或差距结论、立即动作、后续计划、最多 3 个待补输入及用途。追踪类回答必须展示营收进度、时间进度、差距、剩余日均和挑战倍数；规划类回答必须展示目标拆解和路线图。

## Failure Handling

缺少目标值、实际营收或日期时，先给定性判断和临时动作，再追问关键输入。最多追问 3 个问题，且每个问题说明用途；如果用户无法提供精确数值，允许使用粗估区间继续规划，并标注风险。

## Examples

- “去年做了 235 万，今年想好好冲一下，不知道从哪里入手。”
- “5 月目标 40 万，现在 15 号才 13 万，帮我看看进度。”
- “下半年怎么规划，才能把营收拉上去？”
- “Q2 做完了，帮我复盘哪些策略有效。”
- “年度目标要拆成每个月的执行路线图。”

## Resources

- `references/strategy-planning-playbook.md`
