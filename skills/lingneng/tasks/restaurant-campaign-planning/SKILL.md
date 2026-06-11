---
name: restaurant-campaign-planning
description: 餐饮活动策划任务 Skill，用于活动主题策划师规划营销日历、节日节点、活动主题方案、活动机制、预算拆分、执行排期和物料需求。
version: 1.0.0
metadata:
  lingneng:
    schema_version: "1.0"
    kind: task
    source: python
    status: active
    user_visible: true
    script_policy: metadata_only
    tags: [marketing, campaign, calendar]
    domains: [restaurant]
    tools:
      - document_generation
      - chart_visualization
    target_employee_types:
      - marketing_planner
    supporting_skills:
      - document-generation
      - chart-visualization
      - report-formatting
      - business-answer-contract
triggers: [营销活动, 活动策划, 节日活动, 营销日历, 五一, 端午, 中秋, 国庆, 主题方案]
---

## When to Use

用户要求活动主题策划师规划餐饮营销日历、节日节点、活动主题、营销活动机制、预算拆分、ROI 预估、执行排期、物料需求或“某个节日该做什么活动”时使用。用户说“五一应该搞什么活动”“端午活动怎么做”“下个月营销计划怎么排”“预算 5000 想拉新”“给我 3 个活动方案”都应使用。

## When Not to Use

最终小红书正文、朋友圈文案、海报标语、社群推送、短视频脚本、KOL Brief 或点评回复应交给 `marketing-copy-generation`。渠道选择、竞品动态、KOL 投放、平台运营和裂变老带新策略应交给 `restaurant-channel-growth-strategy`。会员分层召回和复购自动化应交给 `member-repurchase-campaign`。

## Preconditions

优先确认活动周期、节日或触发节点、餐厅定位、核心目标、预算范围、目标客群、可用渠道、门店承接能力和已有活动限制。信息不足时先按中高端餐饮默认假设给出可执行框架，再最多追问 3 个会影响排期、预算或玩法选择的关键问题。

## Reference Selection

按日期、月份、节日、节气、黄金周、季度或年度规划活动时，读取 `references/marketing-nodes.md`，用于判断节点强度、筹备周期、平台大促节奏和季度营销重心。只做常规活动机制或非节点促活时，可以不读取 reference，直接按用户目标设计方案。

需要活动主题策划师完整原始手册、三方案长模板、营销日历完整格式、活动执行排期模板或跨渠道协作边界时，读取 `references/campaign-planner-playbook.md`。

## Workflow

1. 识别任务类型：区分营销日历、单节点活动主题、热点活动、品牌周年、新品上市或常规促活；混合请求时先处理时间敏感的节点。
2. 判断节点与筹备状态：结合当前日期、活动日期和 reference，判断处于战略规划期、正式筹备期、预热冲刺期、临阵冲量期还是节后复盘期。
3. 明确活动目标：把目标归类为拉新获客、老客复购、提升客单、品牌曝光、节日冲量或清理库存，并说明目标对玩法和预算的影响。
4. 输出活动主题方案：默认给出 3 个差异化方案，分别在主题调性、目标客群、活动机制、渠道组合和预算打法上拉开差异；随后用对比表推荐最适合方案。
5. 输出营销日历：营销日历请求必须包含节点概览、周计划、预算/ROI、执行排期、KPI 和物料需求；月度或季度计划应写明每周主题、渠道动作和复盘节点。
6. 设计活动机制：给出套餐或权益、互动体验、预约或核销规则、渠道配合、员工执行要点和风险控制；中高端餐饮应避免单纯低价满减损伤品牌调性。
7. 拆预算与 ROI：按物料、菜品成本、平台推广、达人或内容、私域触达和机动预算拆分；用客流、客单价、转化率和毛利保护估算 ROI。
8. 收敛执行排期：给出从筹备、物料、平台配置、内容预热、正式执行到复盘的时间轴，并列出需要交给内容创意师产出的物料清单。

## 多节点节日策略

当当前日期上下文提供节日/节点主次信息时，按以下规则组织方案：

- `primary` 节点是本轮营销主线。活动主题、核心权益、预算拆分、排期、物料和 ROI 预估优先围绕 `primary` 设计。
- `secondary` 节点只作为辅助活动、分客群分支、私域内容、承接排期或补充传播话题，不要抢占主线。
- `background` 节点只作为轻量内容参考，除非用户主动要求，否则不展开成完整方案。
- 用户显式指定节点时，以用户指定节点为主，不因全局 S/A/B/C/D 等级降低其主线地位。
- 如果用户问月度或季度营销日历，先用 `primary` 节点确定月度主题，再把 `secondary` 节点安排为分周补充或客群专项。

## RAG Guidance

涉及品牌调性、历史活动效果、会员画像、门店承接能力、菜品成本、平台合同、过往营销预算或企业 SOP 时检索知识库。引用历史数据时说明口径；没有数据时用保守估算，并标注哪些假设会影响 ROI。

## Tool Guidance

需要展示营销日历、甘特排期、预算结构、ROI 对比或节点优先级时可使用 `chart_visualization`。用户要求“整理成方案”“生成活动计划书”“导出文档”时使用 `document_generation`；不要把工具不可见时未生成的图表或文档说成已经完成。

## Output Contract

活动主题请求应包含：核心洞察、活动背景、3 个差异化方案、方案对比表、推荐方案、预算拆分、ROI 预估、执行时间轴、物料需求和风险提示。营销日历请求应包含：节点概览、月度或季度主题、周计划、预算/ROI 汇总、执行排期、KPI、复盘机制和待补数据。

## Failure Handling

活动日期不明确时按最近相关节点或用户提到的月份规划，并说明假设。预算未知时给低、中、高三档玩法。缺少门店定位或客群时使用中高端正餐默认口径，但提示品牌调性会影响方案命名、折扣力度和渠道选择。

## Examples

- “五一应该搞什么活动，预算 5000 想拉新。”
- “帮我做一份 6 月营销日历。”
- “端午节想做一个有品质感的活动主题，给我 3 个方案。”
- “中秋家宴怎么策划，预算和物料也列一下。”
- “下季度有哪些节点值得重点投入？”

## Resources

- `references/marketing-nodes.md`：年度营销节点、平台大促、季度重心和筹备周期参考。
- `references/campaign-planner-playbook.md`
